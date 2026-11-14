"""Stage: export the paid extraction results to a JSONL file that DVC versions.

The `extractions` table is the most valuable derived data (re-creating it costs money), so it is
exported to artifacts/exports/extractions.jsonl, one row per (document, schema version, model),
sorted and with stable key order, so the same data always gives the same file hash
(INSTRUCTIONS 17.1). `record_manifest` stores the DVC hash of this export.
"""

import json
from pathlib import Path

from cles.config import get_settings
from cles.db import connect, recorded_run
from cles.stage import StageContext, stage_main

EXPORT_FILE = Path("artifacts/exports/extractions.jsonl")


def run(ctx: StageContext) -> dict:
    settings = get_settings()
    with connect(settings) as conn, recorded_run(conn, "export_extractions", ctx.run_id) as stats:
        rows = conn.execute(
            """SELECT doc_id, schema_version, model, status, result, cost_usd, created_at
               FROM extractions ORDER BY doc_id, schema_version, model"""
        ).fetchall()
        summary = {
            "rows": len(rows),
            "ok": sum(r[3] == "ok" for r in rows),
            "file": str(EXPORT_FILE),
        }
        if not ctx.dry_run:
            EXPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
            with EXPORT_FILE.open("w") as out:
                for doc_id, version, model, status, result, cost, created in rows:
                    record = {
                        "doc_id": doc_id,
                        "schema_version": version,
                        "model": model,
                        "status": status,
                        "result": result,
                        "cost_usd": float(cost) if cost is not None else None,
                        "created_at": created.isoformat(),
                    }
                    out.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")
        stats.update(summary)
    return summary


if __name__ == "__main__":
    stage_main("export_extractions", run)
