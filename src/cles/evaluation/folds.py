"""Stage: evaluate the rolling-origin folds (ADR 0023) with the model-free predictors.

For every development fold the predictors (always the training majority, the precedent vote, the
precedent vote over same-type decisions) are scored on the fold's evaluation window, then pooled
over the dev folds and split by case type, with 95% intervals over decisions (the windows are
disjoint, so a decision counts once). Model outputs join the same tables once adapters exist.

The `test` fold is never used for a choice. It is evaluated only with FOLDS_INCLUDE_TEST=true and
a FOLDS_TEST_REASON, and every use is appended to eval/test_log.jsonl (git-tracked), so how often
the test was looked at is on record.
"""

import json
import logging
import time
from pathlib import Path

from cles.config import ConfigError, get_settings
from cles.domain.pack import load_pack
from cles.evaluation.baselines import baseline_rows, load_decisions, majority, summarize
from cles.extraction.export import EXPORT_FILE
from cles.lineage import git_commit
from cles.stage import StageContext, stage_main
from cles.tracking import flatten_scopes, log_eval_runs

log = logging.getLogger(__name__)


def latest_folds(root: Path) -> Path:
    plans = [d for d in root.iterdir() if (d / "plan.json").is_file()] if root.is_dir() else []
    if not plans:
        raise FileNotFoundError(f"no folds found in {root}: run build_folds first")
    return max(plans, key=lambda d: (d / "plan.json").stat().st_mtime)


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def fold_rows(folder: Path, decisions: dict[str, dict], early: set[str]) -> dict[str, list[dict]]:
    """Baseline rows of one fold's evaluation examples (prior from the fold's training mix)."""
    manifest = json.loads((folder / "manifest.json").read_text())
    prior = majority(manifest["fold"]["train_outcomes"])
    outcomes = {d: v["outcome"] for d, v in decisions.items()}
    case_types = {d: v["case_type"] for d, v in decisions.items()}
    examples = read_jsonl(folder / "eval.jsonl")
    return baseline_rows(examples, outcomes, prior, early, case_types)


def summarize_scopes(per_fold: dict[str, dict[str, list[dict]]]) -> dict[str, dict]:
    """{predictor: {scope: summary}} with scopes: each fold, dev_pooled, dev_pooled_<type>."""
    names = sorted({p for rows in per_fold.values() for p in rows})
    results: dict[str, dict] = {}
    for name in names:
        scopes = {fold: summarize(rows[name]) for fold, rows in per_fold.items() if name in rows}
        pooled = [r for rows in per_fold.values() for r in rows.get(name, [])]
        scopes["dev_pooled"] = summarize(pooled)
        for case_type in sorted({r["case_type"] for r in pooled if r["case_type"]}):
            sub = [r for r in pooled if r["case_type"] == case_type]
            scopes[f"dev_pooled_{case_type}"] = summarize(sub)
        results[name] = scopes
    return results


def _cell(summary: dict) -> str:
    c = summary["top_outcome_ok"]
    return "n/a" if c["rate"] is None else f"{c['rate']:.0%} ({c['hits']}/{c['n']})"


def _interval(summary: dict) -> str:
    low, high = summary.get("top_outcome_low"), summary.get("top_outcome_high")
    return "" if low is None else f" [{low:.0%} to {high:.0%}]"


def markdown(root: Path, plan: dict, results: dict, evaluated: list[str]) -> str:
    cols = [*evaluated, "dev_pooled", "dev_pooled_criminal", "dev_pooled_civil"]
    out = [
        f"# Rolling-origin folds `{root.name}`\n",
        "Top route = real outcome on late-stage examples; 95% interval over decisions in brackets.",
        "Windows are disjoint, so each decision is counted once in the pooled columns.\n",
        "| fold | train decisions | eval decisions | window from | civil share | dismissed |",
        "|---|---|---|---|---|---|",
    ]
    for f in plan["folds"]:
        if f["name"] not in evaluated:
            out.append(
                f"| {f['name']} | {f['train_decisions']} | {f['eval_decisions']} | "
                f"{f['split_date']} | locked | locked |"
            )
            continue
        n = f["eval_decisions"]
        civil = f["eval_case_types"].get("civil", 0) / n
        dismissed = f["eval_outcomes"].get("appeal_dismissed", 0) / n
        out.append(
            f"| {f['name']} | {f['train_decisions']} | {n} | {f['split_date']} "
            f"| {civil:.0%} | {dismissed:.0%} |"
        )
    out += ["", "| predictor | " + " | ".join(cols) + " |", "|---|" + "---|" * len(cols)]
    for name, scopes in results.items():
        cells = [(_cell(scopes[c]) + _interval(scopes[c])) if c in scopes else "-" for c in cols]
        out.append(f"| {name} | " + " | ".join(cells) + " |")
    same = results.get("baseline_precedent_same_type", {}).get("dev_pooled", {})
    if same.get("coverage") is not None:
        out.append(
            f"\nSame-type vote had at least one same-type precedent for "
            f"{same['coverage']:.0%} of the late-stage examples (otherwise it predicts nothing)."
        )
    return "\n".join(out) + "\n"


def log_test_use(settings, run_id: str, root: Path) -> None:
    """One line per evaluation of the test fold, git-tracked."""
    if not settings.folds_test_reason.strip():
        raise ConfigError("evaluating the test fold needs FOLDS_TEST_REASON (why now, which model)")
    entry = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "run_id": run_id,
        "folds": root.name,
        "reason": settings.folds_test_reason.strip(),
        "git_commit": git_commit(),
    }
    settings.test_log_file.parent.mkdir(parents=True, exist_ok=True)
    with settings.test_log_file.open("a") as log_file:
        log_file.write(json.dumps(entry) + "\n")


def run(ctx: StageContext) -> dict:
    settings = get_settings()
    pack = load_pack(settings.domain_packs_dir, settings.domain_pack)
    root = settings.folds_dir or latest_folds(settings.folds_out_dir)
    plan = json.loads((root / "plan.json").read_text())
    names = [f["name"] for f in plan["folds"]]
    evaluated = [n for n in names if n != "test" or settings.folds_include_test]
    if "test" in evaluated and not ctx.dry_run:
        log_test_use(settings, ctx.run_id, root)
    version = json.loads((root / names[0] / "manifest.json").read_text())["extraction_version"]
    decisions = load_decisions(EXPORT_FILE, version)
    early = set(pack.training.early_stages)
    per_fold = {n: fold_rows(root / n, decisions, early) for n in evaluated}
    results = summarize_scopes(per_fold)
    summary = {
        "folds": root.name,
        "evaluated": evaluated,
        "locked": [n for n in names if n not in evaluated],
        "top_outcome_ok": {
            p: s["dev_pooled"]["top_outcome_ok"]["rate"] for p, s in results.items()
        },
        "decisions": results["baseline_prior"]["dev_pooled"]["decisions"],
    }
    if ctx.dry_run:
        return summary
    (root / "report.json").write_text(json.dumps({"results": results}, indent=2))
    (root / "report.md").write_text(markdown(root, plan, results, evaluated))
    flat = {
        f"{p}.{k}": v for p, scopes in results.items() for k, v in flatten_scopes(scopes).items()
    }
    settings.folds_metrics_file.parent.mkdir(parents=True, exist_ok=True)
    settings.folds_metrics_file.write_text(json.dumps(flat, indent=1, sort_keys=True) + "\n")
    runs = log_eval_runs(settings, results, root, {}, root / "report.md")
    return {**summary, "report": str(root / "report.md"), "mlflow_runs": len(runs)}


if __name__ == "__main__":
    stage_main("folds_report", run)
