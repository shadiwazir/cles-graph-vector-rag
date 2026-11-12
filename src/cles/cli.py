"""`cles run <stage> [<stage> ...]`: thin runner that chains stages in order.

Stops at the first failure. Stages are plain commands, so any orchestrator can run them too.
"""

import argparse
import json
import subprocess
import sys
import uuid

# Stage name -> module. Add a stage here when it exists.
STAGES: dict[str, str] = {
    "validate_pack": "cles.domain.check",
    "ingest": "cles.ingestion.ingest",
    "embed": "cles.ingestion.embed",
    "build_indexes": "cles.ingestion.build_indexes",
    "extract": "cles.extraction.extract",
    "graph_load": "cles.graph.load",
}


def run_stage(module: str, extra_args: list[str]) -> dict:
    """Run one stage module and return its JSON summary (the last stdout line)."""
    proc = subprocess.run(
        [sys.executable, "-m", module, *extra_args],
        stdout=subprocess.PIPE,
        text=True,
        check=False,
    )
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    summary = json.loads(lines[-1]) if lines else {"status": "failed", "error": "no summary"}
    if proc.returncode != 0:
        summary["status"] = "failed"
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cles")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="run one or more stages in order")
    run.add_argument("stages", nargs="+", choices=sorted(STAGES))
    run.add_argument("--limit", type=int)
    run.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    run_id = uuid.uuid4().hex
    extra = ["--run-id", run_id]
    if args.limit is not None:
        extra += ["--limit", str(args.limit)]
    if args.dry_run:
        extra.append("--dry-run")

    for name in args.stages:
        summary = run_stage(STAGES[name], extra)
        print(json.dumps(summary))
        if summary.get("status") != "ok":
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
