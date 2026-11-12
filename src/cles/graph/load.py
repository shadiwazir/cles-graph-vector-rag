"""Stage: write the newest valid extraction of every document into Neo4j. Idempotent."""

import logging

from cles.config import get_settings
from cles.db import connect, recorded_run
from cles.domain.pack import load_pack
from cles.extraction.extractor import schema_version
from cles.graph.client import ensure_schema, make_driver
from cles.graph.writer import GraphWriter
from cles.stage import StageContext, stage_main

log = logging.getLogger(__name__)


def run(ctx: StageContext) -> dict:
    settings = get_settings()
    pack = load_pack(settings.domain_packs_dir, settings.domain_pack)
    version = schema_version(pack)

    with connect(settings) as conn, recorded_run(conn, "graph_load", ctx.run_id) as stats:
        rows = conn.execute(
            """SELECT DISTINCT ON (doc_id) doc_id, result FROM extractions
                WHERE status = 'ok' AND schema_version = %s
                ORDER BY doc_id, created_at DESC LIMIT %s""",
            (version, ctx.limit),
        ).fetchall()
        stats.update(extractions=len(rows), schema_version=version)
        if ctx.dry_run:
            return {"extractions": len(rows), "schema_version": version}

        driver = make_driver(settings)
        try:
            ensure_schema(driver, pack.graph)
            writer = GraphWriter(driver, pack)
            for doc_id, result in rows:
                writer.write(result)
                log.info("graph loaded %s", doc_id)
        finally:
            driver.close()
    return {"loaded": len(rows), "schema_version": version}


if __name__ == "__main__":
    stage_main("graph_load", run)
