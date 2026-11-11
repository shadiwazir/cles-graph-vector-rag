"""Stage contract (INSTRUCTIONS.md section 7.0).

Each stage is `python -m cles.<module>`. It accepts --limit, --dry-run, --run-id,
prints one final JSON summary line to stdout, logs to stderr, and exits non-zero on failure.
"""

import argparse
import json
import logging
import sys
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from cles.observability.logging import setup_logging

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class StageContext:
    run_id: str
    limit: int | None
    dry_run: bool


def parse_args(argv: Sequence[str] | None = None) -> StageContext:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="process at most N items")
    parser.add_argument("--dry-run", action="store_true", help="do not write or call paid APIs")
    parser.add_argument("--run-id", default=None, help="id of this run (default: random)")
    args = parser.parse_args(argv)
    return StageContext(
        run_id=args.run_id or uuid.uuid4().hex, limit=args.limit, dry_run=args.dry_run
    )


def stage_main(
    name: str, fn: Callable[[StageContext], dict], argv: Sequence[str] | None = None
) -> None:
    """Run `fn`, print the JSON summary, exit 0 on success and 1 on failure."""
    setup_logging()
    ctx = parse_args(argv)
    try:
        result = fn(ctx)
    except Exception as exc:
        log.exception("stage %s failed", name)
        _print_summary(name, ctx, "failed", {"error": str(exc)})
        sys.exit(1)
    _print_summary(name, ctx, "ok", result)


def _print_summary(name: str, ctx: StageContext, status: str, details: dict) -> None:
    summary = {"stage": name, "run_id": ctx.run_id, "dry_run": ctx.dry_run, "status": status}
    summary.update(details)
    print(json.dumps(summary), flush=True)
