"""Experiment tracking (MLflow) for every stage and every evaluation, best effort.

Tracking must help, never block: any failure here is logged as a warning and the stage goes on.
The tracking server is checked once per process with a short timeout, so a stopped server costs
about two seconds, not a crash. `MLFLOW_ENABLED=false` switches everything off.
"""

import contextlib
import logging
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

from cles.config import Settings
from cles.lineage import dvc_hash, git_commit

log = logging.getLogger(__name__)
PIPELINE_EXPERIMENT = "cles-pipeline"
EVAL_EXPERIMENT = "cles-eval"
_MAX_METRICS = 60
_reachable: dict[str, bool] = {}


def available(settings: Settings) -> bool:
    """True when tracking is enabled and the store can be reached (checked once)."""
    uri = settings.mlflow_tracking_uri
    if not settings.mlflow_enabled:
        return False
    if uri not in _reachable:
        ok = True
        if uri.startswith("http"):
            try:
                urllib.request.urlopen(f"{uri.rstrip('/')}/health", timeout=2).close()
            except Exception as exc:
                log.warning("MLflow not reachable at %s, run not tracked (%s)", uri, exc)
                ok = False
        _reachable[uri] = ok
    return _reachable[uri]


def lineage_tags() -> dict[str, str]:
    """What the code and data looked like: lets any run be traced back (INSTRUCTIONS 17.2)."""
    dirty = subprocess.run(
        ["git", "status", "--porcelain"], capture_output=True, text=True, check=False
    ).stdout.strip()
    return {
        "git_commit": git_commit(),
        "git_dirty": str(bool(dirty)).lower(),
        "raw_data_dvc_hash": dvc_hash(Path("data.dvc")) or "",
        "datasets_dvc_hash": dvc_hash(Path("artifacts/datasets.dvc")) or "",
    }


def numeric_metrics(summary: dict) -> dict[str, float]:
    """Numbers from a stage summary (top level and one level down), as MLflow metrics."""
    out: dict[str, float] = {}
    for key, value in summary.items():
        if isinstance(value, bool):
            continue
        if isinstance(value, int | float):
            out[key] = float(value)
        elif isinstance(value, dict):
            for sub, v in value.items():
                if isinstance(v, int | float) and not isinstance(v, bool):
                    out[f"{key}.{sub}"] = float(v)
    return dict(list(out.items())[:_MAX_METRICS])


def log_stage_run(
    settings: Settings, stage: str, run_id: str, summary: dict, seconds: float, limit: int | None
) -> None:
    """One MLflow run per stage run, in the experiment `cles-pipeline`."""
    try:
        if not available(settings):
            return
        os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")
        import mlflow

        mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
        mlflow.set_experiment(PIPELINE_EXPERIMENT)
        # MLflow prints "View run at ..." to stdout; stdout carries only the JSON summary.
        with (
            contextlib.redirect_stdout(sys.stderr),
            mlflow.start_run(run_name=f"{stage}-{run_id[:8]}"),
        ):
            mlflow.log_params({"stage": stage, "run_id": run_id, "limit": str(limit)})
            mlflow.set_tags(
                {
                    **lineage_tags(),
                    "stage": stage,
                    "status": str(summary.get("status", "")),
                    "pack": settings.domain_pack,
                    "llm_model": settings.llm_model or "",
                    "error": str(summary.get("error", ""))[:500],
                }
            )
            mlflow.log_metrics({**numeric_metrics(summary), "duration_seconds": seconds})
    except Exception as exc:  # tracking never breaks a stage
        log.warning("MLflow logging failed for stage %s: %s", stage, exc)


def log_eval_runs(
    settings: Settings, results: dict, dataset: Path, systems_meta: dict[str, dict], report: Path
) -> list[str]:
    """One MLflow run per evaluated system in `cles-eval`, so systems can be compared in the
    MLflow UI. `results` is {system: {scope: summary}} from `scoring.aggregate`."""
    run_ids: list[str] = []
    try:
        if not available(settings):
            return run_ids
        os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")
        import mlflow

        mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
        mlflow.set_experiment(EVAL_EXPERIMENT)
        for system, scopes in results.items():
            meta = systems_meta.get(system, {})
            with (
                contextlib.redirect_stdout(sys.stderr),
                mlflow.start_run(run_name=f"eval-{system}-{dataset.name}") as run,
            ):
                mlflow.log_params({"system": system, **{k: str(v) for k, v in meta.items()}})
                mlflow.set_tags({**lineage_tags(), "dataset_id": dataset.name, "system": system})
                mlflow.log_metrics(flatten_scopes(scopes))
                mlflow.log_artifact(str(report))
                outputs = settings.eval_out_dir / system / "outputs.jsonl"
                if outputs.is_file():
                    mlflow.log_artifact(str(outputs), "answers")
                run_ids.append(run.info.run_id)
    except Exception as exc:
        log.warning("MLflow logging of the evaluation failed: %s", exc)
    return run_ids


def flatten_scopes(scopes: dict) -> dict[str, float]:
    """{scope: {metric: {n, hits, rate} | number}} -> {'scope.metric': value}."""
    out: dict[str, float] = {}
    for scope, summary in scopes.items():
        for name, value in summary.items():
            if isinstance(value, dict):
                if value.get("rate") is not None:
                    out[f"{scope}.{name}"] = float(value["rate"])
            elif isinstance(value, int | float) and not isinstance(value, bool):
                out[f"{scope}.{name}"] = float(value)
    return out
