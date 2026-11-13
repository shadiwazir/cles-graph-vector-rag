"""Stage: score the answers of every system in artifacts/eval/*/outputs.jsonl.

Scores against the real outcome of each held-out decision, verifies every citation with the
deterministic verifier (needs Postgres and Neo4j), and writes artifacts/eval/report.json and
report.md. No paid calls. Systems are compared on the same examples only.
"""

import json
import logging
from datetime import date

from jsonschema import Draft202012Validator

from cles.config import get_settings
from cles.db import connect, recorded_run
from cles.domain.pack import load_pack
from cles.evaluation.answers import parse_answer
from cles.evaluation.generate import load_eval_examples, read_done
from cles.evaluation.scoring import aggregate, score_answer
from cles.graph.client import make_driver
from cles.inference.verifier import CitationVerifier
from cles.retrieval.graph import GraphRetriever
from cles.stage import StageContext, stage_main

log = logging.getLogger(__name__)

# (label, key, shown as a rate) for the report tables
_RATES = [
    ("valid JSON", "valid_json"),
    ("matches schema", "valid_schema"),
    ("stage correct", "stage_ok"),
    ("top route = real outcome (late stages)", "top_outcome_ok"),
    ("any route = real outcome", "any_outcome_ok"),
    ("top route remedies = real (late stages)", "remedies_ok"),
    ("always predict 'dismissed' (late stages)", "majority_baseline"),
]


def run(ctx: StageContext) -> dict:
    settings = get_settings()
    pack = load_pack(settings.domain_packs_dir, settings.domain_pack)
    folder, examples = load_eval_examples(settings)
    examples = examples[: ctx.limit]
    validator = Draft202012Validator(pack.advice_schema)
    early = set(pack.training.early_stages)
    caps = pack.info.likelihood_caps_by_stage

    outputs = {
        d.name: read_done(d / "outputs.jsonl")
        for d in sorted(settings.eval_out_dir.glob("*/"))
        if (d / "outputs.jsonl").is_file()
    }
    if not outputs:
        raise FileNotFoundError(f"no outputs.jsonl under {settings.eval_out_dir}")
    ids = set.intersection(*(set(o) for o in outputs.values()))  # compare on common examples
    examples = [e for e in examples if e["example_id"] in ids]

    rows: dict[str, list[dict]] = {name: [] for name in outputs}
    driver = make_driver(settings)
    try:
        with connect(settings) as conn, recorded_run(conn, "eval_score", ctx.run_id) as stats:
            verifier = CitationVerifier(conn, GraphRetriever(driver, pack))
            for name, answers in outputs.items():
                for e in examples:
                    advice, errors = parse_answer(answers[e["example_id"]]["text"], validator)
                    total = failed = 0
                    if advice is not None and isinstance(advice.get("routes"), list):
                        try:
                            report = verifier.verify(advice, date.fromisoformat(e["as_of"]))
                            total, failed = report.total, report.failed
                        except Exception as exc:  # malformed authority objects
                            log.warning("verify failed for %s/%s: %s", name, e["example_id"], exc)
                    rows[name].append(score_answer(e, advice, errors, early, caps, total, failed))
            stats.update(systems=list(outputs), examples=len(examples))
    finally:
        driver.close()

    results = {name: aggregate(r) for name, r in rows.items()}
    settings.eval_out_dir.mkdir(parents=True, exist_ok=True)
    (settings.eval_out_dir / "report.json").write_text(
        json.dumps({"dataset": str(folder), "results": results, "rows": rows}, indent=2)
    )
    (settings.eval_out_dir / "report.md").write_text(_markdown(folder, results, len(examples)))
    headline = {n: r["all"]["top_outcome_ok"]["rate"] for n, r in results.items()}
    return {
        "systems": list(outputs),
        "examples": len(examples),
        "top_outcome_ok": headline,
        "report": str(settings.eval_out_dir / "report.md"),
    }


def _pct(cell: dict) -> str:
    return "n/a" if cell["rate"] is None else f"{cell['rate']:.0%} ({cell['hits']}/{cell['n']})"


def _markdown(folder, results: dict, n: int) -> str:
    names = list(results)
    out = [
        f"# Model evaluation\n\nDataset `{folder}`, {n} held-out examples, same for every system.\n"
    ]
    for scope in ["all", *[s for s in next(iter(results.values())) if s != "all"]]:
        count = results[names[0]][scope]["examples"]
        out += [f"\n## {scope} ({count} examples)\n", "| metric | " + " | ".join(names) + " |"]
        out.append("|---|" + "---|" * len(names))
        for label, key in _RATES:
            out.append(
                f"| {label} | " + " | ".join(_pct(results[x][scope][key]) for x in names) + " |"
            )
        for label, key in [
            ("citations claimed", "citations_claimed"),
            ("citations verified", "citations_verified"),
            ("citations failed verification", "citations_failed"),
            ("citations outside the supplied context", "citations_outside_context"),
            ("routes rated 'high' that were wrong at the top", "high_and_wrong"),
            ("likelihoods above the evidence cap", "likelihood_over_cap"),
        ]:
            out.append(
                f"| {label} | " + " | ".join(str(results[x][scope][key]) for x in names) + " |"
            )
    out.append(
        "\nWith about 12 examples per stage, differences under roughly 15 points are noise. "
        "Ground truth is the real decision; the training targets were written with hindsight."
    )
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    stage_main("eval_score", run)
