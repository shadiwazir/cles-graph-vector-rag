"""Fold evaluation with the model-free predictors, and the lock on the test fold."""

import json

import pytest

from cles.config import ConfigError, Settings
from cles.evaluation.folds import log_test_use, markdown, summarize_scopes


def row(doc, ok, case_type="civil", unanimous=False, covered=True):
    return {
        "example_id": f"{doc}#g",
        "doc_id": doc,
        "stage": "grounds_of_appeal",
        "outcome": "x",
        "case_type": case_type,
        "top_outcome_ok": ok,
        "unanimous": unanimous,
        "covered": covered,
    }


def test_pooled_and_per_type_scopes_count_each_decision_once():
    per_fold = {
        "dev1": {"baseline_precedent": [row("a", True), row("b", False, "criminal")]},
        "dev2": {"baseline_precedent": [row("c", True), row("d", True, "criminal")]},
    }
    scopes = summarize_scopes(per_fold)["baseline_precedent"]
    assert scopes["dev1"]["decisions"] == 2 and scopes["dev_pooled"]["decisions"] == 4
    assert scopes["dev_pooled"]["top_outcome_ok"]["hits"] == 3
    assert scopes["dev_pooled_civil"]["top_outcome_ok"]["n"] == 2
    assert scopes["dev_pooled_criminal"]["top_outcome_ok"]["rate"] == 0.5


def test_markdown_marks_the_locked_test_fold():
    plan = {
        "folds": [
            {
                "name": "dev1",
                "train_decisions": 200,
                "eval_decisions": 2,
                "split_date": "2026-01-01",
                "eval_case_types": {"civil": 1},
                "eval_outcomes": {"appeal_dismissed": 1},
            },
            {
                "name": "test",
                "train_decisions": 235,
                "eval_decisions": 2,
                "split_date": "2026-02-01",
                "eval_case_types": {},
                "eval_outcomes": {},
            },
        ]
    }
    results = summarize_scopes({"dev1": {"baseline_prior": [row("a", True), row("b", False)]}})
    text = markdown(__import__("pathlib").Path("x"), plan, results, ["dev1"])
    assert "| test | 235 | 2 | 2026-02-01 | locked | locked |" in text
    assert "baseline_prior" in text


def test_the_test_fold_needs_a_reason_and_every_use_is_logged(tmp_path):
    settings = Settings(_env_file=None, test_log_file=tmp_path / "log.jsonl", folds_test_reason="")
    with pytest.raises(ConfigError, match="FOLDS_TEST_REASON"):
        log_test_use(settings, "run1", tmp_path / "folds1")
    assert not (tmp_path / "log.jsonl").exists()
    settings = settings.model_copy(update={"folds_test_reason": "release candidate 1"})
    log_test_use(settings, "run1", tmp_path / "folds1")
    log_test_use(settings, "run2", tmp_path / "folds1")
    lines = [json.loads(x) for x in (tmp_path / "log.jsonl").read_text().splitlines()]
    assert [x["run_id"] for x in lines] == ["run1", "run2"]
    assert lines[0]["reason"] == "release candidate 1" and lines[0]["folds"] == "folds1"
