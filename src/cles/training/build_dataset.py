"""Stage: build leakage-free training examples (one per stage of each case).

Steps: split documents by time, retrieve context from older documents only, ask the LLM for the
ideal advice (cached; paid), check leakage rules, write train.jsonl, eval.jsonl, manifest.json.
`--dry-run` retrieves and estimates tokens and cost but calls nothing and writes nothing.
"""

import hashlib
import json
import logging
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import date

import psycopg

from cles.config import Settings, get_settings
from cles.db import connect, recorded_run
from cles.domain.pack import DomainPack, load_pack
from cles.extraction.extractor import schema_version
from cles.graph.client import make_driver
from cles.inference.advisor import AdviceRequest, search_text
from cles.inference.prompt import build_messages
from cles.ingestion.chunker import count_tokens
from cles.ingestion.embedder import Embedder
from cles.llm.base import estimate_cost
from cles.llm.openai_client import make_client
from cles.retrieval.graph import GraphRetriever
from cles.retrieval.hybrid import HybridRetriever
from cles.retrieval.types import ContextPack, SearchFilter
from cles.stage import StageContext, stage_main
from cles.training.dataset import DocInfo, assign_split, pick_question
from cles.training.leakage import check_example, check_split
from cles.training.target import TargetSpec, build_target_messages, generate_target, input_hash

log = logging.getLogger(__name__)


@dataclass
class Prepared:
    """Everything needed to generate and assemble one example."""

    example_id: str
    doc: DocInfo
    stage: str
    question: str
    case_text: str
    as_of: date
    split: str
    context: ContextPack
    base_messages: list[dict]
    target_messages: list[dict]
    spec: TargetSpec
    key: str  # cache key part: hash of the target prompt
    doc_dates: dict[str, str] = field(default_factory=dict)  # doc_id -> date, set before assembly


def load_docs(conn: psycopg.Connection, version: str) -> list[DocInfo]:
    rows = conn.execute(
        """SELECT DISTINCT ON (e.doc_id) e.doc_id, d.title, d.doc_date, e.result
             FROM extractions e JOIN documents d USING (doc_id)
            WHERE e.status = 'ok' AND e.schema_version = %s AND d.doc_date IS NOT NULL
            ORDER BY e.doc_id, e.created_at DESC""",
        (version,),
    ).fetchall()
    return [DocInfo(doc_id, title, doc_date, result) for doc_id, title, doc_date, result in rows]


def prepare_examples(
    docs: list[DocInfo],
    split: dict[str, str],
    split_date: date,
    pack: DomainPack,
    retriever: HybridRetriever,
    limit: int | None = None,
) -> list[Prepared]:
    prepared: list[Prepared] = []
    for doc in sorted(docs, key=lambda d: (d.doc_date, d.doc_id)):
        for stage_item in doc.extraction.get("stages", []):
            stage = stage_item["stage"]
            question = pick_question(pack, stage, doc.doc_id)
            if question is None:
                continue
            case_text = stage_item["known_so_far"]
            # Training: older documents only. Evaluation: only documents from before the split.
            as_of = doc.doc_date if split[doc.doc_id] == "train" else split_date
            context = retriever.retrieve(
                search_text(AdviceRequest(case_text, question)),
                SearchFilter(as_of=as_of, exclude_doc_ids=(doc.doc_id,)),
            )
            base = build_messages(pack, case_text, question, context)
            target = build_target_messages(pack, base, doc.extraction, stage_item)
            spec = TargetSpec(
                doc.doc_id,
                doc.title,
                doc.extraction["outcome"],
                tuple(doc.extraction.get("remedies", [])),
                context,
            )
            prepared.append(
                Prepared(
                    f"{doc.doc_id}#{stage}",
                    doc,
                    stage,
                    question,
                    case_text,
                    as_of,
                    split[doc.doc_id],
                    context,
                    base,
                    target,
                    spec,
                    input_hash(target),
                )
            )
            if limit and len(prepared) >= limit:
                return prepared
    return prepared


def cached_target(conn: psycopg.Connection, item: Prepared, model: str) -> dict | None:
    row = conn.execute(
        "SELECT result FROM training_targets "
        "WHERE example_id = %s AND input_hash = %s AND model = %s AND status = 'ok'",
        (item.example_id, item.key, model),
    ).fetchone()
    return row[0] if row else None


def save_target(conn, item: Prepared, model: str, outcome, cost) -> None:
    conn.execute(
        """INSERT INTO training_targets (example_id, input_hash, model, result, status, cost_usd)
           VALUES (%s, %s, %s, %s, %s, %s)
           ON CONFLICT (example_id, input_hash, model) DO UPDATE
              SET result = EXCLUDED.result, status = EXCLUDED.status,
                  cost_usd = EXCLUDED.cost_usd, created_at = now()""",
        (
            item.example_id,
            item.key,
            model,
            json.dumps(outcome.result if outcome.status == "ok" else {"error": outcome.error}),
            outcome.status,
            cost,
        ),
    )
    conn.commit()


def assemble(item: Prepared, advice: dict, model: str, version: str) -> dict:
    """The JSONL record. `messages` is what the model trains on; the rest is metadata."""
    return {
        "example_id": item.example_id,
        "doc_id": item.doc.doc_id,
        "doc_date": item.doc.doc_date.isoformat(),
        "stage": item.stage,
        "as_of": item.as_of.isoformat(),
        "split": item.split,
        "case_text": item.case_text,
        "question": item.question,
        "evidence_strength": item.context.evidence_strength,
        "context_docs": [
            {"doc_id": d, "doc_date": item.doc_dates[d]} for d in item.context.retrieved_doc_ids
        ],
        "outcome": item.spec.outcome,
        "remedies": list(item.spec.remedies),
        "target_model": model,
        "extraction_version": version,
        "messages": [
            *item.base_messages,
            {"role": "assistant", "content": json.dumps(advice, ensure_ascii=False)},
        ],
    }


def run(ctx: StageContext) -> dict:
    settings = get_settings()
    pack = load_pack(settings.domain_packs_dir, settings.domain_pack)
    version = schema_version(pack)
    model = settings.llm_model or "(unset)"
    driver = make_driver(settings)
    try:
        with connect(settings) as conn, recorded_run(conn, "build_dataset", ctx.run_id) as stats:
            docs = load_docs(conn, version)
            split_date, split = assign_split(docs, settings.training_eval_fraction)
            graph = GraphRetriever(driver, pack)
            retriever = HybridRetriever(conn, Embedder.from_settings(settings), graph, settings)
            items = prepare_examples(docs, split, split_date, pack, retriever, ctx.limit)
            dates = {d.doc_id: d.doc_date.isoformat() for d in docs}
            for item in items:
                item.doc_dates = dates  # dates of context documents, for the leakage check

            todo = [i for i in items if cached_target(conn, i, model) is None]
            est_in = sum(count_tokens(m["content"]) for i in todo for m in i.target_messages)
            est_out = len(todo) * settings.extraction_output_tokens_estimate
            est_cost = estimate_cost(
                est_in,
                est_out,
                settings.llm_price_input_per_mtok,
                settings.llm_price_output_per_mtok,
            )
            summary = {
                "documents": len(docs),
                "split_date": str(split_date),
                "examples": len(items),
                "to_generate": len(todo),
                "est_input_tokens": est_in,
                "est_cost_usd": est_cost,
                "model": model,
            }
            stats.update(summary)
            if ctx.dry_run:
                return summary

            spent = _generate_missing(conn, todo, pack, settings, model)
            return {
                **summary,
                **_write(
                    conn, items, pack, settings, version, model, split_date, spent, ctx.run_id
                ),
            }
    finally:
        driver.close()


def _generate_missing(conn, todo: list[Prepared], pack, settings: Settings, model: str) -> float:
    if not todo:
        return 0.0
    client = make_client(settings)
    spent = 0.0
    with ThreadPoolExecutor(max_workers=settings.llm_concurrency) as pool:
        futures = {
            pool.submit(generate_target, client, i.target_messages, pack, i.spec): i for i in todo
        }
        for future in as_completed(futures):  # DB writes stay on this thread
            item, outcome = futures[future], future.result()
            cost = estimate_cost(
                outcome.input_tokens,
                outcome.output_tokens,
                settings.llm_price_input_per_mtok,
                settings.llm_price_output_per_mtok,
            )
            save_target(conn, item, model, outcome, cost)
            spent += cost or 0.0
            if outcome.status != "ok":
                log.warning("%s: %s: %s", item.example_id, outcome.status, outcome.error)
    return spent


def _write(conn, items, pack, settings, version, model, split_date, spent, run_id) -> dict:
    examples, dropped, missing = [], Counter(), 0
    for item in items:
        advice = cached_target(conn, item, model)
        if advice is None:
            missing += 1
            continue
        example = assemble(item, advice, model, version)
        violations = check_example(example, pack, split_date)
        for v in violations:
            dropped[v.split(":")[0]] += 1
        if not violations:
            examples.append(example)
    split_problems = check_split(examples)
    if split_problems:
        raise RuntimeError("; ".join(split_problems))

    out = settings.training_out_dir / run_id[:8]
    out.mkdir(parents=True, exist_ok=True)
    counts = {}
    for name in ("train", "eval"):
        rows = [e for e in examples if e["split"] == name]
        text = "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in rows)
        (out / f"{name}.jsonl").write_text(text, encoding="utf-8")
        counts[name] = {"examples": len(rows), "sha256": hashlib.sha256(text.encode()).hexdigest()}
    manifest = {
        "run_id": run_id,
        "pack": pack.info.name,
        "pack_version": pack.info.version,
        "extraction_version": version,
        "target_model": model,
        "split_date": str(split_date),
        "eval_fraction": settings.training_eval_fraction,
        "files": counts,
        "dropped_for_leakage": dict(dropped),
        "missing_targets": missing,
        "cost_usd_this_run": spent,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return {
        "written": str(out),
        "train": counts["train"]["examples"],
        "eval": counts["eval"]["examples"],
        "dropped": dict(dropped),
        "missing_targets": missing,
        "cost_usd": spent,
    }


if __name__ == "__main__":
    stage_main("build_dataset", run)
