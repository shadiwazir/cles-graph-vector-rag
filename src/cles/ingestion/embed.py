"""Stage: embed child chunks that have no embedding yet.

Run it on a GPU machine for the real corpus. Resumable: only rows without an embedding are
processed, so a re-run continues where it stopped.
"""

import logging

from pgvector.psycopg import register_vector

from cles.config import get_settings
from cles.db import connect, recorded_run
from cles.ingestion.embedder import Embedder
from cles.ingestion.indexes import drop_vector_index
from cles.stage import StageContext, stage_main

log = logging.getLogger(__name__)

PAGE = 512  # rows read from Postgres per round
BULK_THRESHOLD = 1000  # above this, drop the HNSW index first (faster); `build_indexes` restores it


def run(ctx: StageContext) -> dict:
    settings = get_settings()
    with connect(settings) as conn, recorded_run(conn, "embed", ctx.run_id) as stats:
        pending = conn.execute(
            "SELECT count(*) FROM chunks WHERE level = 'child' AND embedding IS NULL"
        ).fetchone()[0]
        todo = min(pending, ctx.limit) if ctx.limit else pending
        stats.update(pending=pending, planned=todo)
        if ctx.dry_run or todo == 0:
            return {"pending": pending, "embedded": 0}

        if todo > BULK_THRESHOLD:
            drop_vector_index(conn)
            log.info("dropped HNSW index for bulk embedding; run `build_indexes` afterwards")
        register_vector(conn)
        embedder = Embedder.from_settings(settings)

        done = 0
        while done < todo:
            rows = conn.execute(
                """SELECT chunk_id, text FROM chunks
                   WHERE level = 'child' AND embedding IS NULL
                   ORDER BY doc_id, chunk_index LIMIT %s""",
                (min(PAGE, todo - done),),
            ).fetchall()
            vectors = embedder.embed_passages([text for _, text in rows])
            with conn.cursor() as cur:
                cur.executemany(
                    "UPDATE chunks SET embedding = %s WHERE chunk_id = %s",
                    [(v, cid) for (cid, _), v in zip(rows, vectors, strict=True)],
                )
            conn.commit()
            done += len(rows)
            stats["embedded"] = done
            log.info("embedded %d/%d", done, todo)
    return {"pending": pending, "embedded": done, "device": embedder.device}


if __name__ == "__main__":
    stage_main("embed", run)
