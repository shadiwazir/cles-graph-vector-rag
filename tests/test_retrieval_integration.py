"""Needs Compose Postgres (ingested and embedded corpus that includes 2026 ONCA 719) and the
sentence-transformers extra. Graph checks also need Neo4j with the graph; each part is skipped
when unavailable."""

from datetime import date

import psycopg
import pytest

from cles.config import ConfigError, get_settings
from cles.retrieval.hybrid import HybridRetriever
from cles.retrieval.search import fulltext_search, vector_search
from cles.retrieval.types import SearchFilter

QUERY = "sentence for child luring and sexual interference, Crown appeal of a fit sentence"


@pytest.fixture(scope="module")
def conn():
    try:
        connection = psycopg.connect(get_settings().postgres_dsn(), connect_timeout=2)
    except (psycopg.OperationalError, ConfigError):
        pytest.skip("Postgres not available")
    embedded = connection.execute(
        "SELECT count(*) FROM chunks WHERE embedding IS NOT NULL"
    ).fetchone()[0]
    if not embedded:
        pytest.skip("sample is not embedded (run: cles run ingest embed)")
    yield connection
    connection.close()


@pytest.fixture(scope="module")
def embedder():
    pytest.importorskip("sentence_transformers")
    from cles.ingestion.embedder import Embedder

    return Embedder.from_settings(get_settings())


def _doc_ids(hits) -> list[str]:
    """Distinct document ids in rank order."""
    return list(dict.fromkeys(h.doc_id for h in hits))


def test_vector_search_finds_the_relevant_case(conn, embedder):
    # The corpus has other child-luring decisions, so the case must be among the best few.
    hits = vector_search(conn, embedder.embed_query(QUERY), SearchFilter(), 30)
    assert "2026 ONCA 719" in _doc_ids(hits)[:5]
    assert hits[0].distance <= hits[-1].distance


def test_fulltext_search_finds_keyword_match(conn):
    hits = fulltext_search(conn, "luring Snapchat complainant", SearchFilter(), 30)
    assert "2026 ONCA 719" in _doc_ids(hits)


def test_as_of_excludes_the_case_and_later_cases(conn, embedder):
    flt = SearchFilter(as_of=date(2026, 10, 8))  # 719 is dated 2026-10-08: strictly before only
    docs = {p.doc_id for p in vector_search(conn, embedder.embed_query(QUERY), flt, 50)}
    dates = dict(conn.execute("SELECT doc_id, doc_date FROM documents").fetchall())
    assert docs and all(dates[d] < date(2026, 10, 8) for d in docs)
    assert "2026 ONCA 719" not in docs


def test_exclude_doc_ids(conn, embedder):
    flt = SearchFilter(exclude_doc_ids=("2026 ONCA 719",))
    docs = {p.doc_id for p in vector_search(conn, embedder.embed_query(QUERY), flt, 50)}
    assert "2026 ONCA 719" not in docs
    assert not {p.doc_id for p in fulltext_search(conn, QUERY, flt, 50)} & {"2026 ONCA 719"}


def test_hybrid_returns_fused_passages_with_evidence(conn, embedder):
    pack = HybridRetriever(conn, embedder, None, get_settings()).retrieve(QUERY)
    assert pack.passages
    top = pack.passages[0].text.casefold()  # on topic, whichever decision ranks first
    assert "luring" in top or "sexual interference" in top or "sentence" in top
    assert pack.evidence_strength in {"moderate", "strong"}
    assert any(len(p.sources) == 2 for p in pack.passages)  # found by both searches


def test_unrelated_query_has_weak_evidence(conn, embedder):
    pack = HybridRetriever(conn, embedder, None, get_settings()).retrieve(
        "recipe for sourdough bread starter fermentation temperature"
    )
    assert pack.evidence_strength == "weak"
