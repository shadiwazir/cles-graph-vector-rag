"""Stage: drift and regression checks.

1. Regression: the latest evaluation (metrics/eval.json) against eval/baseline.json.
2. Online drift: the evidence mix and the citation failure rate of recent live requests
   (request_audit) against the evaluation reference.

The stage reports violations in its summary (and as a gauge for Prometheus) but does not fail:
`scripts/pipeline.sh drift` turns violations into an exit code. Set DRIFT_UPDATE_BASELINE=true to
make the latest evaluation the new baseline.
"""

import json
import logging
from collections import Counter

import yaml

from cles.config import Settings, get_settings
from cles.db import connect
from cles.evaluation.generate import load_eval_examples
from cles.observability import metrics as m
from cles.stage import StageContext, stage_main

log = logging.getLogger(__name__)
_ALL = ".all."
_RATE_KEYS = ("valid_schema", "stage_ok", "top_outcome_ok", "any_outcome_ok", "remedies_ok")


def compare_metrics(baseline: dict, current: dict, rules: dict) -> list[str]:
    """Violations of the regression rules, comparing scope 'all' of each system."""
    problems = []
    max_drop = rules["rates_max_drop"]
    for key, old in baseline.items():
        if _ALL not in key or key not in current:
            continue
        system, metric = key.split(_ALL)
        new = current[key]
        if metric in _RATE_KEYS and old - new > max_drop:
            problems.append(f"{system}: {metric} fell from {old:.2f} to {new:.2f}")
        limit = rules["counts_max_increase"].get(metric)
        if limit is not None and new - old > limit:
            problems.append(f"{system}: {metric} rose from {old:.0f} to {new:.0f}")
    return problems


def evidence_shares(values: list[str]) -> dict[str, float]:
    counts = Counter(values)
    total = sum(counts.values())
    return {k: counts.get(k, 0) / total for k in ("weak", "moderate", "strong")} if total else {}


def online_problems(
    reference: list[str], live: list[str], cites_total: int, cites_failed: int, rules: dict
) -> list[str]:
    """Violations of the online rules; empty when traffic is below `min_requests`."""
    if len(live) < rules["min_requests"]:
        return []
    problems = []
    ref, now = evidence_shares(reference), evidence_shares(live)
    for level in ref:
        shift = abs(now[level] - ref[level])
        if shift > rules["evidence_share_max_shift"]:
            problems.append(
                f"share of '{level}' evidence moved {ref[level]:.2f} -> {now[level]:.2f}"
            )
    if cites_total and cites_failed / cites_total > rules["citation_failure_rate_max"]:
        problems.append(f"citation failure rate {cites_failed / cites_total:.2f} in live requests")
    return problems


def run(ctx: StageContext) -> dict:
    settings = get_settings()
    rules = yaml.safe_load(settings.drift_thresholds_file.read_text())
    current = json.loads(settings.eval_metrics_file.read_text())
    baseline_path = settings.drift_baseline_file
    result: dict = {"baseline": str(baseline_path)}
    problems: list[str] = []

    if settings.drift_update_baseline or not baseline_path.is_file():
        if not ctx.dry_run:
            baseline_path.parent.mkdir(parents=True, exist_ok=True)
            baseline_path.write_text(json.dumps(current, indent=1, sort_keys=True) + "\n")
        result["baseline_written"] = True
    else:
        problems += compare_metrics(
            json.loads(baseline_path.read_text()), current, rules["regression"]
        )

    online = _online_check(settings, rules["online"])
    problems += online.pop("problems")
    result["online"] = online
    m.drift_violations.set(len(problems))
    return result | {"violations": len(problems), "problems": problems}


def _online_check(settings: Settings, rules: dict) -> dict:
    _, examples = load_eval_examples(settings)
    reference = [e["evidence_strength"] for e in examples]
    with connect(settings) as conn:
        rows = conn.execute(
            """SELECT evidence_strength, citations_total, citations_failed FROM request_audit
               WHERE environment = 'live' AND created_at > now() - make_interval(days => %s)""",
            (rules["window_days"],),
        ).fetchall()
    live = [r[0] for r in rows]
    total, failed = sum(r[1] for r in rows), sum(r[2] for r in rows)
    problems = online_problems(reference, live, total, failed, rules)
    return {
        "requests": len(live),
        "checked": len(live) >= rules["min_requests"],
        "problems": problems,
    }


if __name__ == "__main__":
    stage_main("drift_check", run)
