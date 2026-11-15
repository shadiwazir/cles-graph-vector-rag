"""Stage: acceptance check of a model version against eval/acceptance.yaml.

Reads the results of `eval_score` (artifacts/eval/report.json), judges the configured system
criterion by criterion and writes artifacts/eval/acceptance.json. Blocking criteria decide the
verdict; tracked criteria are reported. The verdict is provisional by design (no lawyer review).
When the MLflow registry has the adapter, the alias `accepted` or `candidate` is set on its
latest version. `scripts/pipeline.sh accept` exits non-zero when a blocking criterion fails.
"""

import contextlib
import json
import logging
import math
import operator
import os

import yaml

from cles.config import Settings, get_settings
from cles.observability import metrics as m
from cles.stage import StageContext, stage_main

log = logging.getLogger(__name__)
_OPS = {">=": operator.ge, "<=": operator.le, "==": operator.eq, ">": operator.gt, "<": operator.lt}
Z = 1.645  # one-sided 95 percent


def wilson_lower(hits: int, n: int, z: float = Z) -> float:
    """Lower bound of the Wilson score interval for a proportion."""
    if n == 0:
        return 0.0
    p = hits / n
    centre = p + z * z / (2 * n)
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (centre - margin) / (1 + z * z / n)


def metric_cell(results: dict, system: str, metric: str) -> dict | None:
    """{'value', 'n', 'hits'} of a metric in scope 'all', or None when it does not exist."""
    cell = results.get(system, {}).get("all", {}).get(metric)
    if cell is None:
        return None
    if isinstance(cell, dict):
        return {"value": cell.get("rate"), "n": cell.get("n"), "hits": cell.get("hits")}
    return {"value": cell, "n": None, "hits": None}


def evaluate(spec: dict, results: dict) -> list[dict]:
    """One verdict per criterion: passed, applicable and the numbers behind it."""
    system = spec["system"]
    out = []
    for c in spec["criteria"]:
        cell = metric_cell(results, system, c["metric"])
        tier = c.get("tier", "blocking")
        row = {"id": c["id"], "metric": c["metric"], "tier": tier, "op": c["op"], "passed": None}
        if cell is None or cell["value"] is None:
            out.append(row | {"note": "not measured"})
            continue
        n = cell["n"]
        if c.get("blocking_from_n") and n is not None and n >= c["blocking_from_n"]:
            tier = row["tier"] = "blocking"
        actual = cell["value"]
        if c.get("mode") == "wilson_lower":
            actual = wilson_lower(cell["hits"], cell["n"])
        threshold = c.get("value")
        if "reference" in c:
            threshold = metric_cell(results, system, c["reference"])["value"]
        elif "reference_system" in c:
            ref = metric_cell(results, c["reference_system"], c["metric"])
            threshold = None if ref is None else ref["value"] + c.get("margin", 0.0)
        row |= {"actual": actual, "threshold": threshold, "n": n}
        if c.get("min_n") and (n is None or n < c["min_n"]):
            out.append(row | {"note": f"only {n} examples apply (needs {c['min_n']})"})
        elif threshold is None:
            out.append(row | {"note": "reference not available"})
        else:
            out.append(row | {"passed": bool(_OPS[c["op"]](actual, threshold))})
    return out


def verdict(rows: list[dict]) -> dict:
    blocking = [r for r in rows if r["tier"] == "blocking"]
    failed = [r["id"] for r in blocking if r["passed"] is False]
    unmeasured = [r["id"] for r in blocking if r["passed"] is None]
    tracked_failed = [r["id"] for r in rows if r["tier"] == "tracked" and r["passed"] is False]
    status = "rejected" if failed else ("incomplete" if unmeasured else "accepted_provisional")
    return {
        "status": status,
        "blocking_failed": len(failed),
        "blocking_failed_ids": failed,
        "blocking_unmeasured_ids": unmeasured,
        "tracked_failed": len(tracked_failed),
        "tracked_failed_ids": tracked_failed,
    }


def set_registry_alias(settings: Settings, accepted: bool) -> str | None:
    """Alias the latest registered adapter version (best effort)."""
    try:
        from cles.tracking import available

        if not available(settings):
            return None
        os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")
        from mlflow import MlflowClient

        client = MlflowClient(tracking_uri=settings.mlflow_tracking_uri)
        versions = client.search_model_versions("name = 'cles-advisor'")
        if not versions:
            return None
        latest = max(versions, key=lambda v: int(v.version))
        alias = "accepted" if accepted else "candidate"
        for stale in ("accepted", "candidate"):
            with contextlib.suppress(Exception):  # alias not set yet
                client.delete_registered_model_alias("cles-advisor", stale)
        client.set_registered_model_alias("cles-advisor", alias, latest.version)
        return f"cles-advisor v{latest.version} -> {alias}"
    except Exception as exc:
        log.warning("could not set the registry alias: %s", exc)
        return None


def run(ctx: StageContext) -> dict:
    settings = get_settings()
    spec = yaml.safe_load(settings.acceptance_file.read_text())
    report = json.loads((settings.eval_out_dir / "report.json").read_text())
    rows = evaluate(spec, report["results"])
    result = verdict(rows)
    for r in rows:
        if r["passed"] is not None:
            m.acceptance.set(1.0 if r["passed"] else 0.0, {"criterion": r["id"], "tier": r["tier"]})
    out = {"system": spec["system"], "provisional": True, **result, "criteria": rows}
    if not ctx.dry_run:
        (settings.eval_out_dir / "acceptance.json").write_text(json.dumps(out, indent=1) + "\n")
        out["registry"] = set_registry_alias(settings, result["status"] == "accepted_provisional")
    return {k: v for k, v in out.items() if k != "criteria"} | {
        "file": "artifacts/eval/acceptance.json"
    }


if __name__ == "__main__":
    stage_main("accept_check", run)
