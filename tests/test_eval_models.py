"""Scoring and answer parsing for the model evaluation (no database, no model)."""

import json

from jsonschema import Draft202012Validator

from cles.evaluation.answers import parse_answer
from cles.evaluation.scoring import aggregate, score_answer

SCHEMA = {"type": "object", "required": ["stage"], "properties": {"stage": {"type": "string"}}}
EARLY = {"facts", "procedural_history"}


def example(stage="lower_court_decision", outcome="appeal_dismissed", remedies=()):
    return {
        "example_id": f"X#{stage}",
        "stage": stage,
        "outcome": outcome,
        "remedies": list(remedies),
        "evidence_strength": "moderate",
        "context_docs": [{"doc_id": "A"}],
    }


def advice(stage, outcome, likelihood="medium", remedies=(), cited="A"):
    return {
        "stage": stage,
        "routes": [
            {
                "name": "r",
                "expected_outcome": outcome,
                "likelihood": likelihood,
                "expected_remedies": list(remedies),
                "authorities": [{"case_id": cited, "para": 1, "quote": "q"}],
            }
        ],
    }


def score(ex, adv, errors=()):
    return score_answer(ex, adv, list(errors), EARLY, {"facts": "low"})


def test_parse_answer_strips_think_and_fences():
    v = Draft202012Validator(SCHEMA)
    text = '<think>hmm</think>\n```json\n{"stage": "facts"}\n```'
    assert parse_answer(text, v) == ({"stage": "facts"}, [])


def test_parse_answer_reports_bad_json_and_schema_errors():
    v = Draft202012Validator(SCHEMA)
    assert parse_answer("not json", v)[0] is None
    advice_obj, errors = parse_answer("{}", v)
    assert advice_obj == {} and errors


def test_late_stage_top_outcome_and_remedies():
    ex = example(outcome="appeal_allowed", remedies=["new_trial_ordered"])
    ok = score(ex, advice("lower_court_decision", "appeal_allowed", remedies=["new_trial_ordered"]))
    assert ok["top_outcome_ok"] and ok["remedies_ok"] and ok["stage_ok"]
    wrong = score(ex, advice("lower_court_decision", "appeal_dismissed", "high"))
    assert wrong["top_outcome_ok"] is False and wrong["top_high_and_wrong"]


def test_early_stage_outcome_not_applicable_but_any_route_counts():
    row = score(example("facts"), advice("facts", "appeal_dismissed"))
    assert row["top_outcome_ok"] is None and row["any_outcome_ok"]


def test_cites_outside_context_and_cap_violation():
    row = score(example("facts"), advice("facts", "appeal_dismissed", "high", cited="B"))
    assert row["cites_outside_context"] == 1 and row["likelihood_over_cap"] == 1


def test_unparsed_answer_scores_as_failure():
    row = score(example(), None, ["not valid JSON"])
    assert not row["parsed"] and not row["any_outcome_ok"] and row["routes"] == 0


def test_aggregate_per_stage_and_majority_baseline():
    rows = [
        score(
            example(outcome="appeal_dismissed"), advice("lower_court_decision", "appeal_dismissed")
        ),
        score(
            example(outcome="appeal_allowed"), advice("lower_court_decision", "appeal_dismissed")
        ),
        score(example("facts"), advice("facts", "appeal_dismissed")),
    ]
    result = aggregate(rows)
    assert result["all"]["top_outcome_ok"] == {"n": 2, "hits": 1, "rate": 0.5}
    assert result["lower_court_decision"]["examples"] == 2
    assert result["facts"]["top_outcome_ok"]["rate"] is None
    assert json.dumps(result)


def test_strip_context_removes_passages_and_graph_facts():
    from cles.evaluation.generate import prompt_of, strip_context

    user = (
        "CASE (as described by the lawyer):\nc\n\nQUESTION:\nq\n\n"
        "RETRIEVED PASSAGES (cite only these):\n[A para 1] T\ntext\n\n"
        "GRAPH FACTS (structured, from earlier decisions):\nfact: {}\n\n"
        "Retrieval found strong evidence."
    )
    stripped = strip_context(user)
    assert "text" not in stripped and "fact: {}" not in stripped
    assert "(none found)" in stripped and "(none)" in stripped
    assert stripped.endswith("Retrieval found weak evidence.") and "CASE" in stripped
    example = {"messages": [{"role": "system", "content": "s"}, {"role": "user", "content": user}]}
    assert (
        prompt_of(example, True)[1]["content"] == stripped
        and prompt_of(example)[1]["content"] == user
    )
