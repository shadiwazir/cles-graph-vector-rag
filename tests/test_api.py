"""API smoke test: needs Postgres (embedded sample) and Neo4j (sample graph)."""

import json

import psycopg
import pytest

from cles.config import ConfigError, get_settings

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from cles.inference import app as app_module  # noqa: E402
from cles.llm.base import LLMResponse  # noqa: E402


class Generator:
    model = "fake"
    prompts: list = []

    def complete_json(self, messages):
        self.prompts.append(messages[1]["content"])
        advice = {
            "stage": "facts",
            "case_position": "p",
            "routes": [],
            "risks": [],
            "recommended_next_steps": [],
            "missing_information": [],
            "evidence_strength": "strong",
        }
        return LLMResponse(json.dumps(advice), 1, 1, "fake")


@pytest.fixture
def client(monkeypatch):
    settings = get_settings().model_copy(update={"allow_external_generator": True})
    try:
        psycopg.connect(settings.postgres_dsn(), connect_timeout=2).close()
        from neo4j import GraphDatabase

        driver = GraphDatabase.driver(settings.neo4j_uri, auth=settings.neo4j_auth())
        driver.verify_connectivity()
        driver.close()
    except (psycopg.OperationalError, ConfigError, Exception):
        pytest.skip("Postgres or Neo4j not available")
    pytest.importorskip("sentence_transformers")
    monkeypatch.setattr(app_module, "make_client", lambda s: Generator())
    with TestClient(app_module.create_app(settings)) as test_client:
        yield test_client


def test_health(client):
    assert client.get("/health").json()["status"] == "ok"


def test_advise_returns_structured_response(client):
    body = {
        "case_text": "The accused pleaded guilty to child luring; the Crown appeals the sentence.",
        "question": "What are the prospects on appeal?",
    }
    data = client.post("/advise", json=body).json()
    assert data["advice"]["evidence_strength"] in {"weak", "moderate", "strong"}
    assert data["disclaimer"] and data["scope"] and data["request_id"]
    assert data["sources"]


def test_page_is_served(client):
    page = client.get("/")
    assert page.status_code == 200 and "CLES advisor" in page.text


def test_history_is_folded_into_the_prompt(client):
    Generator.prompts.clear()
    body = {
        "case_text": "The accused pleaded guilty to child luring; the Crown appeals the sentence.",
        "question": "And what if the sentence is increased?",
        "history": [
            {"question": "What are the prospects on appeal?", "advice": {"stage": "facts"}}
        ],
    }
    data = client.post("/advise", json=body).json()
    prompt = Generator.prompts[-1]
    assert "EARLIER IN THIS CONVERSATION" in prompt and "What are the prospects" in prompt
    assert prompt.index("What are the prospects") < prompt.index("QUESTION:")
    assert data["extra"]["history"] == {"turns_sent": 1, "turns_dropped": 0}


def test_feedback_is_stored_on_the_audit_row(client):
    body = {
        "case_text": "The accused pleaded guilty to child luring; the Crown appeals the sentence.",
        "question": "What are the prospects on appeal?",
    }
    request_id = client.post("/advise", json=body).json()["request_id"]
    ok = client.post("/feedback", json={"request_id": request_id, "feedback": "reject"})
    assert ok.status_code == 200
    bad = client.post("/feedback", json={"request_id": request_id, "feedback": "maybe"})
    assert bad.status_code == 422
    unknown = "00000000-0000-0000-0000-000000000000"
    assert (
        client.post("/feedback", json={"request_id": unknown, "feedback": "accept"}).status_code
        == 404
    )


def test_validation_rejects_short_input(client):
    assert client.post("/advise", json={"case_text": "x", "question": "y"}).status_code == 422


def test_app_refuses_to_start_with_external_generator(monkeypatch):
    settings = get_settings().model_copy(
        update={"allow_external_generator": False, "llm_base_url": "https://api.openai.com/v1"}
    )
    with pytest.raises(ConfigError):
        app_module.create_app(settings)
