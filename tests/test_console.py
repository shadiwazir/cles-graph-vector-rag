"""The console: one app with the home page, advisor API, explorer and platform status."""

import json

import psycopg
import pytest

from cles.config import ConfigError, get_settings

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from cles.console import app as console  # noqa: E402
from cles.inference import app as advisor_module  # noqa: E402
from cles.llm.base import LLMResponse  # noqa: E402


class Generator:
    model = "fake"

    def complete_json(self, messages):
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
    monkeypatch.setattr(advisor_module, "make_client", lambda s: Generator())
    monkeypatch.setattr(console, "probe", lambda url: (url != "broken", "HTTP 200"))
    with TestClient(console.create_app(settings)) as test_client:
        yield test_client


def test_home_page_and_assets_are_served(client):
    home = client.get("/")
    assert home.status_code == 200 and "CLES Advisor" in home.text
    assert "console.js" in home.text
    assert client.get("/assets/console.js").status_code == 200
    assert client.get("/assets/console.css").status_code == 200


def test_explorer_is_part_of_the_console(client):
    assert "results explorer" in client.get("/explorer").text


def test_info_describes_model_corpus_and_pack(client):
    data = client.get("/api/info").json()
    assert data["name"] == "CLES" and data["model"]["name"]
    assert data["corpus"]["decisions"] > 0 and data["pack"]["disclaimer"]


def test_status_lists_every_tool_with_its_state(client):
    data = client.get("/api/status").json()
    ids = {t["id"] for t in data["tools"]}
    assert {"mlflow", "grafana-quality", "phoenix", "prometheus", "postgres", "model"} <= ids
    assert all("ok" in t and "detail" in t for t in data["tools"])


def test_advisor_api_works_through_the_console(client):
    body = {
        "case_text": "The accused pleaded guilty to child luring; the Crown appeals the sentence.",
        "question": "What are the prospects on appeal?",
    }
    assert client.post("/advise", json=body).json()["advice"]["stage"] == "facts"


def test_tool_catalog_urls_follow_the_settings():
    settings = get_settings().model_copy(update={"grafana_url": "http://grafana.example:3000/"})
    urls = {t["id"]: t["url"] for t in console.tool_catalog(settings)}
    assert urls["grafana-quality"] == "http://grafana.example:3000/d/cles-quality"
    assert urls["api-docs"] == "/docs"
