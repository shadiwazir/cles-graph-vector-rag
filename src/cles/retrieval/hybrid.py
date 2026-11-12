"""Hybrid retrieval: vector + full-text (fused by RRF), optional rerank, then graph expansion."""

import logging
from dataclasses import replace

import psycopg

from cles.config import Settings
from cles.ingestion.embedder import Embedder
from cles.observability.telemetry import span
from cles.retrieval.fusion import rrf
from cles.retrieval.graph import GraphRetriever
from cles.retrieval.rerank import Reranker
from cles.retrieval.search import fulltext_search, vector_search
from cles.retrieval.types import ContextPack, Passage, SearchFilter

log = logging.getLogger(__name__)


class HybridRetriever:
    def __init__(
        self,
        conn: psycopg.Connection,
        embedder: Embedder,
        graph: GraphRetriever | None,
        settings: Settings,
        reranker: Reranker | None = None,
    ):
        self._conn = conn
        self._embedder = embedder
        self._graph = graph
        self._s = settings
        self._reranker = reranker

    def retrieve(self, query: str, flt: SearchFilter | None = None) -> ContextPack:
        flt = flt or SearchFilter()
        n = self._s.retrieval_candidates
        with span("vector_search", kind="RETRIEVER") as sp:
            vec_hits = vector_search(self._conn, self._embedder.embed_query(query), flt, n)
            sp.set_attribute("hits", len(vec_hits))
        with span("fulltext_search", kind="RETRIEVER") as sp:
            txt_hits = fulltext_search(self._conn, query, flt, n)
            sp.set_attribute("hits", len(txt_hits))

        passages = self._fuse(vec_hits, txt_hits)
        if self._reranker:
            with span("rerank"):
                passages = self._reranker.rerank(query, passages)
        passages = passages[: self._s.retrieval_k]

        doc_ids = list(dict.fromkeys(p.doc_id for p in passages))
        with span("graph_traversal", kind="RETRIEVER") as sp:
            graph = self._graph.expand_from_cases(doc_ids, flt.as_of) if self._graph else {}
            sp.set_attribute("rows", sum(len(rows) for rows in graph.values()))
        return ContextPack(
            passages=passages,
            graph=graph,
            evidence_strength=evidence_strength(passages, self._s),
            retrieved_doc_ids=doc_ids,
        )

    def _fuse(self, vec_hits: list[Passage], txt_hits: list[Passage]) -> list[Passage]:
        by_id: dict[str, Passage] = {}
        for hit in (*vec_hits, *txt_hits):
            known = by_id.get(hit.chunk_id)
            if known is None:
                by_id[hit.chunk_id] = replace(hit, sources=list(hit.sources))
            else:
                known.sources += hit.sources
                known.distance = known.distance if known.distance is not None else hit.distance
        scores = rrf(
            [[p.chunk_id for p in vec_hits], [p.chunk_id for p in txt_hits]], self._s.rrf_k
        )
        for chunk_id, score in scores.items():
            by_id[chunk_id].score = score
        return sorted(by_id.values(), key=lambda p: p.score, reverse=True)


def evidence_strength(passages: list[Passage], settings: Settings) -> str:
    """How much relevant material was found, judged by vector distance of the passages.

    strong: at least 3 passages within the strong distance; moderate: at least 2 within the
    weak distance; otherwise weak. Passages found only by full-text do not count as evidence.
    """
    distances = [p.distance for p in passages if p.distance is not None]
    if sum(d <= settings.evidence_strong_distance for d in distances) >= 3:
        return "strong"
    if sum(d <= settings.evidence_weak_distance for d in distances) >= 2:
        return "moderate"
    return "weak"
