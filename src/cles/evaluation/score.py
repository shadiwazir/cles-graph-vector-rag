"""Stage: score the answers of every system in artifacts/eval/*/outputs.jsonl.

Scores against the real outcome of each held-out decision, verifies every citation with the
deterministic verifier (needs Postgres and Neo4j), and writes artifacts/eval/report.json and
report.md. No paid calls. Systems are compared on the same examples only.
"""

import json
import logging
from datetime import date
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

from cles.config import get_settings
from cles.db import connect, recorded_run
from cles.domain.pack import load_pack
from cles.evaluation.answers import parse_answer
from cles.evaluation.generate import load_eval_examples, read_done
from cles.evaluation.judge import mean_faithfulness
from cles.evaluation.scoring import aggregate, score_answer
from cles.graph.client import make_driver
from cles.inference.verifier import CitationVerifier
from cles.observability import metrics as m
from cles.retrieval.graph import GraphRetriever
from cles.stage import StageContext, stage_main
from cles.tracking import flatten_scopes as flatten
from cles.tracking import log_eval_runs

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
                    checks: list[dict] = []  # per citation: kept so the explorer can mark them
                    if advice is not None and isinstance(advice.get("routes"), list):
                        try:
                            report = verifier.verify(advice, date.fromisoformat(e["as_of"]))
                            total, failed = report.total, report.failed
                            checks = [
                                {"case_id": c.case_id, "para": c.para, "status": c.status}
                                for c in report.checks
                            ]
                        except Exception as exc:  # malformed authority objects
                            log.warning("verify failed for %s/%s: %s", name, e["example_id"], exc)
                    row = score_answer(e, advice, errors, early, caps, total, failed)
                    rows[name].append({**row, "citation_checks": checks})
            stats.update(systems=list(outputs), examples=len(examples))
    finally:
        driver.close()

    results = {name: aggregate(r) for name, r in rows.items()}
    for name in results:  # LLM-judge faithfulness, when `judge_eval` has run (a trend signal)
        judged = mean_faithfulness(settings.eval_out_dir / name / "judge.jsonl")
        if judged:
            (
                results[name]["all"]["judge_answers"],
                results[name]["all"]["judge_faithfulness_mean"],
            ) = judged
    settings.eval_out_dir.mkdir(parents=True, exist_ok=True)
    (settings.eval_out_dir / "report.json").write_text(
        json.dumps({"dataset": str(folder), "results": results, "rows": rows}, indent=2)
    )
    (settings.eval_out_dir / "report.md").write_text(_markdown(folder, results, len(examples)))
    report_md = settings.eval_out_dir / "report.md"
    flat = write_metrics_file(Path(settings.eval_metrics_file), results)
    emit_gauges(results)
    mlflow_runs = log_eval_runs(
        settings, results, folder, systems_meta(settings, outputs), report_md
    )
    headline = {n: r["all"]["top_outcome_ok"]["rate"] for n, r in results.items()}
    return {
        "systems": list(outputs),
        "examples": len(examples),
        "top_outcome_ok": headline,
        "metrics_file": str(settings.eval_metrics_file),
        "mlflow_runs": len(mlflow_runs),
        "report": str(report_md),
        "metrics": len(flat),
    }


def write_metrics_file(path: Path, results: dict) -> dict[str, float]:
    """Flat numbers for `dvc metrics show/diff` (git-tracked, so every commit has its scores)."""
    flat = {
        f"{system}.{k}": v for system, scopes in results.items() for k, v in flatten(scopes).items()
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(flat, indent=1, sort_keys=True) + "\n")
    return flat


def emit_gauges(results: dict) -> None:
    """Latest scores as OpenTelemetry gauges (Prometheus reads them via the Collector)."""
    for system, scopes in results.items():
        for scope, summary in scopes.items():
            for metric, value in summary.items():
                attrs = {"system": system, "scope": scope, "metric": metric}
                if isinstance(value, dict) and value.get("rate") is not None:
                    m.eval_quality.set(float(value["rate"]), attrs)
                elif isinstance(value, int | float) and not isinstance(value, bool):
                    (m.eval_quality if metric.endswith("_rate") else m.eval_count).set(
                        float(value), attrs
                    )


def systems_meta(settings, outputs: dict) -> dict[str, dict]:
    """Backend, base model and adapter of each system, from eval/systems.yaml."""
    defined = yaml.safe_load(settings.eval_systems_file.read_text())["systems"]
    meta = {}
    for name in outputs:
        entry = defined.get(name, {})
        model = next(iter(read_done(settings.eval_out_dir / name / "outputs.jsonl").values()), {})
        meta[name] = {**entry, "model": model.get("model", "")}
    return meta


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
