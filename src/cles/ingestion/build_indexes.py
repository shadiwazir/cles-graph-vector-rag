"""Stage: (re)create the HNSW vector index and refresh statistics. Idempotent."""

from cles.config import get_settings
from cles.db import connect, recorded_run
from cles.ingestion.indexes import create_vector_index
from cles.stage import StageContext, stage_main


def run(ctx: StageContext) -> dict:
    with connect(get_settings()) as conn, recorded_run(conn, "build_indexes", ctx.run_id) as stats:
        if not ctx.dry_run:
            create_vector_index(conn)
            conn.autocommit = True
            conn.execute("ANALYZE chunks")
        embedded = conn.execute(
            "SELECT count(*) FROM chunks WHERE embedding IS NOT NULL"
        ).fetchone()[0]
        stats["embedded_chunks"] = embedded
    return {"embedded_chunks": embedded}


if __name__ == "__main__":
    stage_main("build_indexes", run)
