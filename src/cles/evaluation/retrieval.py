"""Retrieval metrics on a labelled question set (document level)."""

from dataclasses import dataclass
from statistics import mean

from cles.retrieval.hybrid import HybridRetriever
from cles.retrieval.types import SearchFilter


@dataclass(frozen=True)
class RetrievalCase:
    question: str
    expect: tuple[str, ...]  # doc ids that should be retrieved


def first_hit_rank(ranked_docs: list[str], expected: tuple[str, ...]) -> int | None:
    """1-based rank of the first expected document, or None."""
    for rank, doc in enumerate(ranked_docs, start=1):
        if doc in expected:
            return rank
    return None


def summarise(ranks: list[int | None], ks: tuple[int, ...] = (1, 3, 5)) -> dict:
    """Recall@k (share of questions with a hit in the top k documents) and MRR."""
    n = len(ranks)
    out = {f"recall@{k}": sum(1 for r in ranks if r is not None and r <= k) / n for k in ks}
    out["mrr"] = mean(1 / r if r else 0.0 for r in ranks)
    out["questions"] = n
    return out


def evaluate_retrieval(
    retriever: HybridRetriever, cases: list[RetrievalCase], flt: SearchFilter | None = None
) -> tuple[dict, list[dict]]:
    ranks, details = [], []
    for case in cases:
        pack = retriever.retrieve(case.question, flt)
        rank = first_hit_rank(pack.retrieved_doc_ids, case.expect)
        ranks.append(rank)
        details.append(
            {
                "question": case.question,
                "expect": list(case.expect),
                "rank": rank,
                "retrieved": pack.retrieved_doc_ids,
                "evidence": pack.evidence_strength,
            }
        )
    return summarise(ranks), details
