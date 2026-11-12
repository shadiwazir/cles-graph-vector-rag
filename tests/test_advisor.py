"""Advisor and API with a fake generator. Needs Postgres with the embedded sample; the API test
also needs Neo4j with the sample graph. Skipped otherwise."""

import json

import psycopg
import pytest

from cles.config import ConfigError, Settings, get_settings
from cles.domain.pack import load_pack
from cles.inference.advisor import AdviceRequest, Advisor
from cles.inference.guard import check_generator_allowed, is_external
from cles.inference.verifier import CitationVerifier, paragraph_texts
from cles.llm.base import LLMResponse
from cles.retrieval.hybrid import HybridRetriever

CASE = "The accused pleaded guilty to child luring and sexual interference; the Crown appeals."
QUESTION = "What are the prospects of increasing a sentence on a Crown appeal?"


class FakeGenerator:
    model = "fake"

    def __init__(self, reply: dict | str):
        self.reply = reply if isinstance(reply, str) else json.dumps(reply)
        self.prompts: list[list[dict]] = []

    def complete_json(self, messages):
        self.prompts.append(messages)
        return LLMResponse(self.reply, 10, 10, "fake")


def test_is_external():
    assert is_external("https://api.openai.com/v1")
    assert not is_external("http://localhost:11434/v1")
    assert not is_external("http://127.0.0.1:8000/v1")


def test_guard_blocks_external_generator_by_default():
    settings = Settings(_env_file=None, llm_base_url="https://api.openai.com/v1")
    with pytest.raises(ConfigError, match="third party"):
        check_generator_allowed(settings)
    check_generator_allowed(settings.model_copy(update={"allow_external_generator": True}))
    check_generator_allowed(Settings(_env_file=None, llm_base_url="http://localhost:11434/v1"))


@pytest.fixture(scope="module")
def settings():
    return get_settings().model_copy(update={"allow_external_generator": True})


@pytest.fixture(scope="module")
def conn(settings):
    try:
        connection = psycopg.connect(settings.postgres_dsn(), connect_timeout=2)
    except (psycopg.OperationalError, ConfigError):
        pytest.skip("Postgres not available")
    if not connection.execute("SELECT count(*) FROM chunks WHERE embedding IS NOT NULL").fetchone()[
        0
    ]:
        pytest.skip("sample is not embedded")
    yield connection
    connection.close()


@pytest.fixture(scope="module")
def embedder():
    pytest.importorskip("sentence_transformers")
    from cles.ingestion.embedder import Embedder

    return Embedder.from_settings(get_settings())


@pytest.fixture(scope="module")
def pack(settings):
    return load_pack(settings.domain_packs_dir, settings.domain_pack)


def real_quote(conn):
    (text,) = conn.execute(
        "SELECT text FROM chunks WHERE doc_id='2026 ONCA 719' AND level='parent' "
        "AND para_start<=1 AND para_end>=1"
    ).fetchone()
    return " ".join(paragraph_texts(text, 1)[0].split()[:8])


def make_advice(conn, quote="invented words that are in no decision"):
    route = {
        "name": "Crown appeal",
        "description": "d",
        "next_event": "The appeal is heard.",
        "expected_outcome": "appeal_allowed",
        "likelihood": "medium",
        "reasoning": "r",
        "authorities": [
            {"case_id": "2026 ONCA 719", "para": 1, "quote": real_quote(conn)},
            {"case_id": "2026 ONCA 719", "para": 1, "quote": quote},
            {"case_id": "1999 ONCA 1", "para": 1, "quote": "x"},
        ],
    }
    return {
        "stage": "grounds_of_appeal",
        "case_position": "p",
        "routes": [route],
        "risks": ["r"],
        "recommended_next_steps": ["s"],
        "missing_information": [],
        "evidence_strength": "strong",
    }


def build(conn, embedder, pack, settings, generator):
    retriever = HybridRetriever(conn, embedder, None, settings)
    return Advisor(conn, retriever, CitationVerifier(conn), generator, pack, settings)


def test_advisor_removes_unverified_citations_and_audits(conn, embedder, pack, settings):
    generator = FakeGenerator(make_advice(conn))
    advisor = build(conn, embedder, pack, settings, generator)
    response = advisor.advise(AdviceRequest(CASE, QUESTION))

    kept = response.advice["routes"][0]["authorities"]
    assert len(kept) == 1 and kept[0]["verified"] is True
    assert response.citations_total == 3 and response.citations_failed == 2
    assert any("quote_not_found" in w for w in response.warnings)
    assert any("unknown_case" in w for w in response.warnings)
    assert "not legal advice" in response.disclaimer and "Corpus:" in response.scope
    assert response.sources and response.sources[0]["label"].startswith("2026 ONCA")

    prompt = generator.prompts[0][1]["content"]
    assert CASE in prompt and "RETRIEVED PASSAGES" in prompt

    row = conn.execute(
        "SELECT citations_total, citations_failed, question_text, retrieved_ids "
        "FROM request_audit WHERE request_id = %s",
        (response.request_id,),
    ).fetchone()
    assert row[0] == 3 and row[1] == 2
    assert row[2] is None  # question text is not stored by default
    assert "2026 ONCA 719" in row[3]


def test_advisor_reports_generation_failure(conn, embedder, pack, settings):
    advisor = build(conn, embedder, pack, settings, FakeGenerator("not json"))
    response = advisor.advise(AdviceRequest(CASE, QUESTION))
    assert response.advice is None and response.error
    assert any("generation failed" in w for w in response.warnings)


def test_weak_evidence_is_flagged_and_caps_model_confidence(conn, embedder, pack, settings):
    advisor = build(conn, embedder, pack, settings, FakeGenerator(make_advice(conn)))
    response = advisor.advise(
        AdviceRequest("Tell me about sourdough bread starters and fermentation.", "How long?")
    )
    assert response.evidence_strength == "weak"
    assert response.advice["evidence_strength"] == "weak"  # model said strong; retrieval wins
    assert any("Weak evidence" in w for w in response.warnings)


def test_as_of_is_passed_to_retrieval(conn, embedder, pack, settings):
    from datetime import date

    advisor = build(conn, embedder, pack, settings, FakeGenerator(make_advice(conn)))
    response = advisor.advise(AdviceRequest(CASE, QUESTION, as_of=date(2026, 10, 8)))
    assert all("2026 ONCA 719" not in s["label"] for s in response.sources)
    # an authority dated on/after as_of is rejected even if the model cites it
    assert any("after_as_of" in w for w in response.warnings)


def test_likelihood_is_capped_by_evidence(conn, embedder, pack, settings):
    advice = make_advice(conn)
    advice["routes"][0]["likelihood"] = "high"
    advisor = build(conn, embedder, pack, settings, FakeGenerator(advice))
    response = advisor.advise(
        AdviceRequest("Tell me about sourdough bread starters and fermentation.", "How long?")
    )
    assert response.evidence_strength == "weak"
    assert response.advice["routes"][0]["likelihood"] == "low"
    assert any("likelihood" in w and "lowered" in w for w in response.warnings)
