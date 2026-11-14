"""Results explorer: builds its data from files only (no database, no model)."""

import json

import pytest

from cles.config import get_settings

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from cles.evaluation import explorer  # noqa: E402
from cles.evaluation.scoring import aggregate, score_answer  # noqa: E402

ADVICE = {
    "stage": "lower_court_decision",
    "case_position": "p",
    "routes": [
        {
            "name": "r",
            "description": "d",
            "next_event": "the hearing of the appeal",
            "likelihood": "medium",
            "reasoning": "x",
            "expected_outcome": "appeal_dismissed",
            "expected_remedies": [],
            "authorities": [{"case_id": "A", "para": 1, "quote": "q"}],
        }
    ],
    "risks": [],
    "recommended_next_steps": [],
    "missing_information": [],
    "evidence_strength": "moderate",
}
EXAMPLE = {
    "example_id": "X#lower_court_decision",
    "doc_id": "X",
    "stage": "lower_court_decision",
    "as_of": "2026-01-01",
    "question": "What now?",
    "case_text": "The accused was convicted.",
    "evidence_strength": "moderate",
    "context_docs": [{"doc_id": "A"}],
    "outcome": "appeal_dismissed",
    "remedies": [],
    "messages": [
        {"role": "system", "content": "s"},
        {"role": "user", "content": "u"},
        {"role": "assistant", "content": json.dumps(ADVICE)},
    ],
}


@pytest.fixture
def settings(tmp_path):
    folder = tmp_path / "datasets" / "d1"
    folder.mkdir(parents=True)
    (folder / "eval.jsonl").write_text(json.dumps(EXAMPLE) + "\n")
    out = tmp_path / "eval"
    rows, texts = {}, {"good": json.dumps(ADVICE), "bad": "not json"}
    for system, text in texts.items():
        (out / system).mkdir(parents=True)
        answer = {"example_id": EXAMPLE["example_id"], "text": text, "output_tokens": 5}
        (out / system / "outputs.jsonl").write_text(json.dumps(answer) + "\n")
        advice = ADVICE if system == "good" else None
        row = score_answer(EXAMPLE, advice, [], {"facts"}, {}, 1, 0)
        rows[system] = [{**row, "citation_checks": [{"case_id": "A", "para": 1, "status": "ok"}]}]
    results = {s: aggregate(r) for s, r in rows.items()}
    (out / "report.json").write_text(
        json.dumps({"dataset": "d1", "results": results, "rows": rows})
    )
    return get_settings().model_copy(
        update={
            "eval_out_dir": out,
            "dataset_dir": folder,
            "training_out_dir": tmp_path / "datasets",
        }
    )


def test_build_data_has_every_system_per_example(settings):
    data = explorer.build_data(settings)
    assert data["systems"] == ["good", "bad"] and len(data["examples"]) == 1
    answers = data["examples"][0]["answers"]
    assert answers["good"]["advice"]["stage"] == "lower_court_decision"
    assert answers["good"]["metrics"]["top_outcome_ok"] is True
    assert answers["bad"]["advice"] is None and answers["bad"]["raw"] == "not json"
    assert data["examples"][0]["target"]["stage"] == "lower_court_decision"
    assert data["extra"]["good"]["mean_routes"] == 1


def test_api_serves_page_and_data(settings):
    client = TestClient(explorer.create_app(settings))
    assert "results explorer" in client.get("/").text
    assert client.get("/api/data").json()["results"]["good"]["all"]["examples"] == 1


def test_labels_are_appended_and_shown_back(settings, tmp_path):
    labels = tmp_path / "labels" / "labels.jsonl"
    client = TestClient(
        explorer.create_app(settings.model_copy(update={"eval_labels_file": labels}))
    )
    body = {
        "example_id": EXAMPLE["example_id"],
        "system": "good",
        "faithfulness": 4,
        "usefulness": 2,
    }
    assert client.post("/api/label", json=body).status_code == 200
    assert client.post("/api/label", json={**body, "faithfulness": 5}).status_code == 200
    assert len(labels.read_text().splitlines()) == 2  # append-only record
    shown = client.get("/api/data").json()["examples"][0]["answers"]["good"]["label"]
    assert shown["faithfulness"] == 5  # the latest label wins
    assert client.post("/api/label", json={**body, "system": "nope"}).status_code == 404
    assert client.post("/api/label", json={**body, "faithfulness": 9}).status_code == 422


def test_api_reports_missing_report(settings, tmp_path):
    empty = settings.model_copy(update={"eval_out_dir": tmp_path / "nothing"})
    assert TestClient(explorer.create_app(empty)).get("/api/data").status_code == 404
