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

    def complete_json(self, messages):
        advice = {
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


def test_validation_rejects_short_input(client):
    assert client.post("/advise", json={"case_text": "x", "question": "y"}).status_code == 422


def test_app_refuses_to_start_with_external_generator(monkeypatch):
    settings = get_settings().model_copy(
        update={"allow_external_generator": False, "llm_base_url": "https://api.openai.com/v1"}
    )
    with pytest.raises(ConfigError):
        app_module.create_app(settings)
