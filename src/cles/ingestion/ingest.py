"""Stage: parse PDFs, chunk them and store documents and chunks in Postgres (no embeddings)."""

import logging

from cles.config import get_settings
from cles.db import connect, recorded_run
from cles.domain.pack import load_pack
from cles.ingestion.chunker import build_chunks
from cles.ingestion.parser import ParseError, parse_pdf
from cles.ingestion.store import StoreResult, store_document
from cles.stage import StageContext, stage_main

log = logging.getLogger(__name__)


def run(ctx: StageContext) -> dict:
    settings = get_settings()
    pack = load_pack(settings.domain_packs_dir, settings.domain_pack)
    pdfs = sorted(settings.data_dir.glob("*.pdf"))
    if ctx.limit:
        pdfs = pdfs[: ctx.limit]

    counts = {r.value: 0 for r in StoreResult}
    failed: dict[str, str] = {}  # quarantine: file name -> reason

    with connect(settings) as conn, recorded_run(conn, "ingest", ctx.run_id) as stats:
        for path in pdfs:
            try:
                doc = parse_pdf(path, pack.sections)
                chunks = build_chunks(doc)
                if ctx.dry_run:
                    counts[StoreResult.INSERTED.value] += 1
                    continue
                counts[store_document(conn, doc, chunks, pack.info.name).value] += 1
            except ParseError as exc:
                log.warning("quarantined %s: %s", path.name, exc)
                failed[path.name] = str(exc)
        stats.update(files=len(pdfs), **counts, failed=failed)

    return {"files": len(pdfs), **counts, "failed": len(failed), "quarantine": failed}


if __name__ == "__main__":
    stage_main("ingest", run)
