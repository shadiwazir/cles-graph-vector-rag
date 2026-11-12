"""Stage: evaluate retrieval (and optionally generation) on the development set.

Generation (`--with-generation`) calls the configured LLM, which costs money and sends the
questions to it: use public or synthetic questions only.
"""

import json
import logging
from pathlib import Path

import yaml

from cles.config import get_settings
from cles.db import connect, recorded_run
from cles.domain.pack import load_pack
from cles.evaluation.retrieval import RetrievalCase, evaluate_retrieval
from cles.graph.client import make_driver
from cles.inference.advisor import AdviceRequest, Advisor
from cles.inference.verifier import CitationVerifier
from cles.ingestion.embedder import Embedder
from cles.llm.openai_client import make_client
from cles.retrieval.graph import GraphRetriever
from cles.retrieval.hybrid import HybridRetriever
from cles.stage import StageContext, stage_main

log = logging.getLogger(__name__)
DEV_SET = Path("eval/retrieval_dev.yaml")
OUT_DIR = Path("artifacts/eval")


def load_cases(path: Path) -> list[RetrievalCase]:
    raw = yaml.safe_load(path.read_text())["cases"]
    return [RetrievalCase(c["q"], tuple(c["expect"])) for c in raw]


def run(ctx: StageContext, with_generation: bool = False) -> dict:
    settings = get_settings()
    pack = load_pack(settings.domain_packs_dir, settings.domain_pack)
    cases = load_cases(DEV_SET)[: ctx.limit]
    driver = make_driver(settings)
    try:
        with connect(settings) as conn, recorded_run(conn, "evaluate", ctx.run_id) as stats:
            graph = GraphRetriever(driver, pack)
            retriever = HybridRetriever(conn, Embedder.from_settings(settings), graph, settings)
            metrics, details = evaluate_retrieval(retriever, cases)
            report = {"retrieval": metrics, "details": details}
            if with_generation and not ctx.dry_run:
                report["generation"] = _evaluate_generation(
                    conn, retriever, graph, pack, settings, cases
                )
            stats.update(report.get("generation", {}) | metrics)
    finally:
        driver.close()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"{ctx.run_id}.json"
    out.write_text(json.dumps(report, indent=2, default=str))
    return {**metrics, **report.get("generation", {}), "report": str(out)}


def _evaluate_generation(conn, retriever, graph, pack, settings, cases) -> dict:
    advisor = Advisor(
        conn, retriever, CitationVerifier(conn, graph), make_client(settings), pack, settings
    )
    responses = [advisor.advise(AdviceRequest(c.question, c.question)) for c in cases]
    total = sum(r.citations_total for r in responses)
    failed = sum(r.citations_failed for r in responses)
    ok = [r for r in responses if r.advice is not None]
    return {
        "answers": len(responses),
        "answers_valid": len(ok),
        "citations_total": total,
        "citation_pass_rate": (total - failed) / total if total else None,
        "weak_evidence_share": sum(r.evidence_strength == "weak" for r in responses)
        / len(responses),
        "mean_latency_ms": sum(r.latency_ms for r in responses) / len(responses),
    }


if __name__ == "__main__":
    import sys

    flag = "--with-generation"
    with_generation = flag in sys.argv
    argv = [a for a in sys.argv[1:] if a != flag]
    stage_main("evaluate", lambda ctx: run(ctx, with_generation), argv=argv)
