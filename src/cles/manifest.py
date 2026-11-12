"""Stage: record what the current stores were built from (INSTRUCTIONS.md section 17.2)."""

import subprocess
from pathlib import Path

import yaml

from cles.config import get_settings
from cles.db import connect, recorded_run
from cles.domain.pack import load_pack
from cles.stage import StageContext, stage_main


def git_commit() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        )
        return out.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def dvc_hash(pointer: Path) -> str | None:
    """md5 recorded in a DVC pointer file such as data.dvc, or None."""
    if not pointer.is_file():
        return None
    outs = (yaml.safe_load(pointer.read_text()) or {}).get("outs", [])
    return outs[0].get("md5") if outs else None


def run(ctx: StageContext) -> dict:
    settings = get_settings()
    pack = load_pack(settings.domain_packs_dir, settings.domain_pack)
    with connect(settings) as conn, recorded_run(conn, "record_manifest", ctx.run_id) as stats:
        schema_version = conn.execute(
            "SELECT version FROM flyway_schema_history WHERE success ORDER BY installed_rank DESC"
        ).fetchone()[0]
        row = {
            "git_commit": git_commit(),
            "raw_data_hash": dvc_hash(Path("data.dvc")),
            "pack_name": pack.info.name,
            "pack_version": pack.info.version,
            "embedding_model": settings.embedding_model,
            "schema_version": schema_version,
        }
        if not ctx.dry_run:
            conn.execute(
                """INSERT INTO build_manifest (git_commit, raw_data_hash, pack_name, pack_version,
                                               embedding_model, schema_version)
                   VALUES (%(git_commit)s, %(raw_data_hash)s, %(pack_name)s, %(pack_version)s,
                           %(embedding_model)s, %(schema_version)s)""",
                row,
            )
            conn.commit()
        stats.update(row)
    return row


if __name__ == "__main__":
    stage_main("record_manifest", run)
