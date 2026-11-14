"""Copy runs from another MLflow store into the tracking server.

A rented GPU machine tracks into its own SQLite file (it cannot reach the laptop). After the
session, copy that file home and import it, so every run lives in one place:

    uv run python -m cles.mlflow_import --source sqlite:///artifacts/mlflow-gpu.db
    uv run python -m cles.mlflow_import --source sqlite:///artifacts/mlflow.db \
        --register cles-advisor --register-match poc

Already imported runs are skipped (tag `imported_from_run_id`), so it can be repeated. Artifacts are
copied when the source path exists here; for adapters, `artifacts/runs/<id>/adapter` next to the
repository is used (the run name ends with that id).
"""

import argparse
import contextlib
import json
import logging
import os
import re
import sys
from pathlib import Path

from cles.config import get_settings

log = logging.getLogger(__name__)
_RUN_DIR = re.compile(r"-([0-9a-f]{8})$")


def import_runs(source: str, destination: str, register: str | None, register_match: str) -> dict:
    os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")
    import mlflow
    from mlflow import MlflowClient
    from mlflow.entities import Metric, Param, RunTag

    src, dst = MlflowClient(tracking_uri=source), MlflowClient(tracking_uri=destination)
    mlflow.set_tracking_uri(destination)
    imported, skipped, registered = 0, 0, []
    for experiment in src.search_experiments():
        if experiment.name == "Default":
            continue
        target = dst.get_experiment_by_name(experiment.name)
        target_id = target.experiment_id if target else dst.create_experiment(experiment.name)
        known = {
            r.data.tags.get("imported_from_run_id")
            for r in dst.search_runs([target_id], max_results=5000)
        }
        for run in src.search_runs([experiment.experiment_id], max_results=5000):
            if run.info.run_id in known:
                skipped += 1
                continue
            name = run.info.run_name or run.info.run_id[:8]
            match = _RUN_DIR.search(name)
            tags = {k: v for k, v in run.data.tags.items() if not k.startswith("mlflow.")}
            tags |= {"imported_from_run_id": run.info.run_id, "imported_from_store": source}
            if match:
                tags["adapter_dir_id"] = match.group(1)
            created = dst.create_run(
                target_id, start_time=run.info.start_time, tags=tags, run_name=name
            )
            history = [
                Metric(m.key, m.value, m.timestamp, m.step)
                for key in run.data.metrics
                for m in src.get_metric_history(run.info.run_id, key)
            ]
            dst.log_batch(
                created.info.run_id,
                metrics=history,
                params=[Param(k, v) for k, v in run.data.params.items()],
                tags=[RunTag(k, v) for k, v in tags.items()],
            )
            _copy_artifacts(dst, created.info.run_id, run.info.artifact_uri, match)
            dst.set_terminated(created.info.run_id, run.info.status, run.info.end_time)
            imported += 1
    if register:
        registered = _register_adapters(dst, register, register_match)
    return {"imported": imported, "skipped": skipped, "registered": registered}


def _copy_artifacts(dst, run_id: str, source_uri: str, match: re.Match | None) -> None:
    local = Path(source_uri.removeprefix("file://"))
    with contextlib.redirect_stdout(sys.stderr):
        if local.is_dir() and any(local.iterdir()):
            dst.log_artifacts(run_id, str(local))
            return
        if match:  # the artifacts stayed on the GPU machine; the adapter was copied home
            folder = Path("artifacts/runs") / match.group(1)
            if (folder / "adapter").is_dir():
                dst.log_artifacts(run_id, str(folder / "adapter"), "adapter")
                if (folder / "sft_config.yaml").is_file():
                    dst.log_artifact(run_id, str(folder / "sft_config.yaml"))
            else:
                log.warning("artifacts of %s not available here", source_uri)


def _register_adapters(dst, name: str, match: str) -> list[str]:
    """Register the adapter of every matching run that has one and is not registered yet."""
    from mlflow.exceptions import MlflowException

    with contextlib.suppress(MlflowException):  # already exists
        dst.create_registered_model(name)
    done = {v.run_id for v in dst.search_model_versions(f"name = '{name}'")}
    added = []
    for experiment in dst.search_experiments():
        for run in dst.search_runs([experiment.experiment_id], max_results=5000):
            run_name = run.info.run_name or ""
            has_adapter = any(a.path == "adapter" for a in dst.list_artifacts(run.info.run_id))
            if match in run_name and has_adapter and run.info.run_id not in done:
                version = dst.create_model_version(
                    name,
                    source=f"{run.info.artifact_uri}/adapter",
                    run_id=run.info.run_id,
                    tags={"base_model": run.data.tags.get("base_model", "")},
                )
                added.append(f"{name} v{version.version} <- {run_name}")
    return added


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--source", required=True, help="source tracking URI, e.g. sqlite:///f.db")
    parser.add_argument("--destination", help="default: MLFLOW_TRACKING_URI")
    parser.add_argument("--register", help="register imported adapters under this model name")
    parser.add_argument("--register-match", default="", help="only runs whose name contains this")
    args = parser.parse_args(argv)
    destination = args.destination or get_settings().mlflow_tracking_uri
    result = import_runs(args.source, destination, args.register, args.register_match)
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
