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


def _scored(doc, ok, likelihood, case_type="civil"):
    return {
        "example_id": f"{doc}#g",
        "doc_id": doc,
        "case_type": case_type,
        "stage": "grounds_of_appeal",
        "outcome": "x",
        "parsed": True,
        "schema_valid": True,
        "stage_ok": True,
        "top_outcome": "x",
        "top_likelihood": likelihood,
        "top_outcome_ok": ok,
        "any_outcome_ok": ok,
        "remedies_ok": ok,
        "top_high_and_wrong": likelihood == "high" and not ok,
        "routes": 1,
        "cites_total": 4,
        "cites_failed": 1,
        "cites_outside_context": 0,
        "cites_claimed": 4,
        "likelihood_over_cap": 0,
    }


def test_model_rows_are_pooled_over_folds_with_decision_intervals(tmp_path):
    from cles.evaluation.folds import model_rows

    for fold, docs in (("dev1", ("a", "b")), ("dev2", ("c", "d"))):
        (tmp_path / fold / "eval").mkdir(parents=True)
        rows = {"openai": [_scored(d, i % 2 == 0, "high") for i, d in enumerate(docs)]}
        variants = {"openai+lead": [_scored(d, True, "high") for d in docs]}
        report = {"rows": rows, "variant_rows": variants}
        (tmp_path / fold / "eval" / "report.json").write_text(json.dumps(report))
    assert model_rows(tmp_path / "dev3") == {}  # not scored yet: no error
    per_fold = {
        f: {"baseline_prior": [row(f"{f}x", True)]} | model_rows(tmp_path / f)
        for f in ("dev1", "dev2")
    }
    results = summarize_scopes(per_fold)
    pooled = results["openai"]["dev_pooled"]
    assert pooled["decisions"] == 4 and pooled["top_outcome_ok"]["hits"] == 2
    assert results["openai+lead"]["dev_pooled"]["top_outcome_ok"]["rate"] == 1.0
    assert pooled["high_precision"]["n"] == 4 and pooled["citation_failure_rate"] == 0.25
    assert "dev_pooled_civil" in results["openai"]  # split by case type like the baselines
    from cles.evaluation.folds import markdown

    plan = {
        "folds": [
            {
                "name": f,
                "train_decisions": 1,
                "eval_decisions": 2,
                "split_date": "d",
                "eval_case_types": {},
                "eval_outcomes": {},
            }
            for f in ("dev1", "dev2")
        ]
    }
    text = markdown(tmp_path, plan, results, ["dev1", "dev2"])
    assert "| openai+lead |" in text and "high right [" in text


def test_a_system_with_a_partial_fold_is_left_out_of_the_pooling(tmp_path):
    from cles.evaluation.folds import model_rows

    (tmp_path / "eval").mkdir()
    (tmp_path / "eval.jsonl").write_text(
        "\n".join(json.dumps({"example_id": str(i)}) for i in range(4))
    )
    complete = [_scored(f"d{i}", True, "high") for i in range(4)]
    partial = [_scored("d0", True, "high")]
    report = {
        "rows": {"openai": complete, "base": partial},
        "variant_rows": {"openai+lead": complete},
    }
    (tmp_path / "eval" / "report.json").write_text(json.dumps(report))
    assert sorted(model_rows(tmp_path)) == ["openai", "openai+lead"]  # "base" answered 1 of 4
