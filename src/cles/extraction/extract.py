"""Stage: LLM extraction for every document that has no valid result yet.

Paid calls: results are cached in `extractions` by (doc_id, schema_version, model), so a re-run
never pays twice. `--dry-run` calls nothing and prints a token and cost estimate.
"""

import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

import psycopg

from cles.config import get_settings
from cles.db import connect, recorded_run
from cles.domain.pack import load_pack
from cles.extraction.extractor import (
    ExtractionOutcome,
    estimate_input_tokens,
    extract_document,
    known_values,
    schema_version,
)
from cles.llm.base import estimate_cost
from cles.llm.openai_client import make_client
from cles.stage import StageContext, stage_main

log = logging.getLogger(__name__)


def pending_documents(conn: psycopg.Connection, version: str, model: str, limit: int | None):
    """(doc_id, title, doc_date, header, text) for documents without an 'ok' extraction."""
    rows = conn.execute(
        """SELECT d.doc_id, d.title, d.doc_date, d.metadata->>'header',
                  (SELECT string_agg(c.text, E'\\n' ORDER BY c.chunk_index)
                     FROM chunks c WHERE c.doc_id = d.doc_id AND c.level = 'parent')
             FROM documents d
            WHERE NOT EXISTS (SELECT 1 FROM extractions e
                               WHERE e.doc_id = d.doc_id AND e.schema_version = %s
                                 AND e.model = %s AND e.status = 'ok')
            ORDER BY d.doc_id
            LIMIT %s""",
        (version, model, limit),
    ).fetchall()
    return rows


def save_outcome(
    conn: psycopg.Connection, outcome: ExtractionOutcome, version: str, model: str, cost
) -> None:
    conn.execute(
        """INSERT INTO extractions (doc_id, schema_version, model, result, status, cost_usd)
           VALUES (%s, %s, %s, %s, %s, %s)
           ON CONFLICT (doc_id, schema_version, model) DO UPDATE
              SET result = EXCLUDED.result, status = EXCLUDED.status,
                  cost_usd = EXCLUDED.cost_usd, created_at = now()""",
        (
            outcome.doc_id,
            version,
            model,
            json.dumps(outcome.result if outcome.status == "ok" else {"error": outcome.error}),
            outcome.status,
            cost,
        ),
    )
    conn.commit()


def run(ctx: StageContext) -> dict:
    settings = get_settings()
    pack = load_pack(settings.domain_packs_dir, settings.domain_pack)
    version = schema_version(pack)
    model = settings.llm_model or "(unset)"

    with connect(settings) as conn, recorded_run(conn, "extract", ctx.run_id) as stats:
        docs = pending_documents(conn, version, model, ctx.limit)
        est_in = sum(estimate_input_tokens(pack, h or "", t or "") for _, _, _, h, t in docs)
        est_out = len(docs) * settings.extraction_output_tokens_estimate
        est_cost = estimate_cost(
            est_in, est_out, settings.llm_price_input_per_mtok, settings.llm_price_output_per_mtok
        )
        stats.update(pending=len(docs), est_input_tokens=est_in, est_cost_usd=est_cost)
        if ctx.dry_run or not docs:
            return {
                "pending": len(docs),
                "est_input_tokens": est_in,
                "est_output_tokens": est_out,
                "est_cost_usd": est_cost,
                "model": model,
                "schema_version": version,
            }

        client = make_client(settings)  # fails clearly if key or model is missing
        counts = {"ok": 0, "invalid": 0, "failed": 0}
        spent = 0.0
        with ThreadPoolExecutor(max_workers=settings.llm_concurrency) as pool:
            futures = [
                pool.submit(
                    extract_document,
                    client,
                    pack,
                    doc_id,
                    h or "",
                    t or "",
                    known_values(pack, doc_id, title, doc_date),
                )
                for doc_id, title, doc_date, h, t in docs
            ]
            for future in as_completed(futures):  # DB writes stay on this thread
                outcome = future.result()
                cost = estimate_cost(
                    outcome.input_tokens,
                    outcome.output_tokens,
                    settings.llm_price_input_per_mtok,
                    settings.llm_price_output_per_mtok,
                )
                save_outcome(conn, outcome, version, model, cost)
                counts[outcome.status] += 1
                spent += cost or 0.0
                if outcome.status != "ok":
                    log.warning("%s: %s: %s", outcome.doc_id, outcome.status, outcome.error)
        stats.update(**counts, cost_usd=spent)
    return {
        **counts,
        "cost_usd": spent if est_cost is not None else None,
        "model": model,
        "schema_version": version,
    }


if __name__ == "__main__":
    stage_main("extract", run)
