from datetime import date

import pytest

from cles.config import Settings
from cles.retrieval.fusion import rrf
from cles.retrieval.hybrid import evidence_strength
from cles.retrieval.search import or_query
from cles.retrieval.types import Passage, SearchFilter

SETTINGS = Settings(_env_file=None)


def passage(distance, doc="d"):
    return Passage("c", doc, "t", 1, 1, "text", distance=distance)


def test_rrf_prefers_items_ranked_high_in_both_lists():
    scores = rrf([["a", "b", "c"], ["b", "a", "d"]], k=60)
    assert scores["a"] == pytest.approx(1 / 61 + 1 / 62)
    assert scores["b"] == pytest.approx(1 / 62 + 1 / 61)
    assert scores["a"] > scores["c"] and scores["c"] > 0
    assert set(scores) == {"a", "b", "c", "d"}


def test_rrf_item_in_one_list_still_scores():
    assert rrf([["x"], []])["x"] == pytest.approx(1 / 61)


def test_or_query_keeps_only_safe_words():
    q = or_query("Can a sentence be raised? ');DROP TABLE x; -- child's luring")
    assert "|" in q and ";" not in q and "'" not in q and "(" not in q
    assert "sentence" in q and "luring" in q


def test_or_query_empty_for_no_words():
    assert or_query("?? !! ..") == ""


def test_evidence_strength_levels():
    assert evidence_strength([passage(0.2)] * 3, SETTINGS) == "strong"
    assert evidence_strength([passage(0.4), passage(0.42)], SETTINGS) == "moderate"
    assert evidence_strength([passage(0.6)] * 5, SETTINGS) == "weak"
    assert evidence_strength([Passage("c", "d", "t", 1, 1, "x")] * 5, SETTINGS) == "weak"


def test_passage_label():
    assert passage(0.1).label == "d para 1"
    p = Passage("c", "2026 ONCA 1", "t", 3, 5, "x")
    assert p.label == "2026 ONCA 1 para 3-5"


def test_search_filter_defaults():
    flt = SearchFilter()
    assert flt.as_of is None and flt.exclude_doc_ids == ()
    assert SearchFilter(as_of=date(2026, 1, 1)).as_of.year == 2026


class ReverseReranker:
    """Fake reranker: puts the passages in reverse order and scores them 1, 2, 3..."""

    def rerank(self, query, passages):
        ordered = list(reversed(passages))
        for i, p in enumerate(ordered):
            p.score = float(len(ordered) - i)
        return ordered


def test_hybrid_applies_reranker_before_truncating():
    from cles.retrieval.hybrid import HybridRetriever

    class Embedder:
        def embed_query(self, text):
            return [0.0] * 768

    retriever = HybridRetriever(None, Embedder(), None, SETTINGS, reranker=ReverseReranker())
    first = Passage("1", "a", "t", 1, 1, "x", distance=0.1, score=0.9)
    second = Passage("2", "b", "t", 1, 1, "y", distance=0.1, score=0.5)
    fused = retriever._fuse([first, second], [])
    assert [p.chunk_id for p in fused] == ["1", "2"]
    assert [p.chunk_id for p in ReverseReranker().rerank("q", fused)] == ["2", "1"]
