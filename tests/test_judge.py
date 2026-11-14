"""Judge prompt building, calibration maths and label handling (no model, no network)."""

import json

import pytest

from cles.evaluation.calibrate import read_labels, spearman, weighted_kappa
from cles.evaluation.judge import build_user_prompt, judge_one, mean_faithfulness

SCHEMA = {
    "type": "object",
    "required": ["routes", "faithfulness", "unsupported_claims", "confidence"],
    "properties": {"faithfulness": {"type": "integer", "minimum": 1, "maximum": 5}},
}
EXAMPLE = {
    "example_id": "X#facts",
    "messages": [
        {"role": "system", "content": "s"},
        {"role": "user", "content": "CASE: c\nRETRIEVED PASSAGES: p"},
        {"role": "assistant", "content": "{}"},
    ],
}


class FakeBackend:
    name = "fake-judge"

    def __init__(self, reply):
        self.reply = reply

    def judge(self, system, user):
        self.seen = user
        return self.reply, 10, 5


def test_prompt_has_the_context_and_the_answer():
    prompt = build_user_prompt(EXAMPLE, {"stage": "facts"})
    assert "RETRIEVED PASSAGES: p" in prompt and '"stage": "facts"' in prompt


def test_judge_one_validates_the_reply():
    good = json.dumps(
        {"routes": [], "faithfulness": 4, "unsupported_claims": [], "confidence": "high"}
    )
    row = judge_one(FakeBackend(good), "sys", SCHEMA, EXAMPLE, {})
    assert row["judgement"]["faithfulness"] == 4 and row["judge_model"] == "fake-judge"
    bad = judge_one(FakeBackend('{"faithfulness": 9}'), "sys", SCHEMA, EXAMPLE, {})
    assert bad["judgement"] is None and bad["errors"]


def test_kappa_is_one_for_perfect_agreement_and_low_for_opposites():
    ratings = [1, 2, 3, 4, 5, 3, 4]
    assert weighted_kappa(ratings, ratings) == pytest.approx(1.0)
    assert weighted_kappa([1, 1, 5, 5], [5, 5, 1, 1]) < 0
    assert weighted_kappa([], []) is None


def test_spearman_handles_ties_and_direction():
    assert spearman([1, 2, 3, 4], [10, 20, 30, 40]) == pytest.approx(1.0)
    assert spearman([1, 2, 3, 4], [4, 3, 2, 1]) == pytest.approx(-1.0)
    assert spearman([1, 1, 1], [1, 2, 3]) is None


def test_latest_label_wins(tmp_path):
    path = tmp_path / "labels.jsonl"
    rows = [
        {"example_id": "A", "system": "s", "faithfulness": 2},
        {"example_id": "A", "system": "s", "faithfulness": 5},
    ]
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    assert read_labels(path)[("A", "s")]["faithfulness"] == 5
    assert read_labels(tmp_path / "missing.jsonl") == {}


def test_mean_faithfulness(tmp_path):
    path = tmp_path / "judge.jsonl"
    rows = [
        {"example_id": "A", "judgement": {"faithfulness": 4}},
        {"example_id": "B", "judgement": {"faithfulness": 2}},
        {"example_id": "C", "judgement": None},
    ]
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    assert mean_faithfulness(path) == (2, 3.0)
    assert mean_faithfulness(tmp_path / "none.jsonl") is None
