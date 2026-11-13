"""Folding earlier questions and answers into the case text (no database, no model)."""

from cles.inference.conversation import Turn, fold_history, summarise_advice

ADVICE = {
    "stage": "lower_court_decision",
    "case_position": "The Crown may appeal the sentence.",
    "routes": [{"name": "Crown appeal", "likelihood": "medium"}],
    "recommended_next_steps": ["File a notice of appeal"],
}


def test_summary_keeps_position_routes_and_steps():
    text = summarise_advice(ADVICE)
    assert "Crown appeal (medium)" in text and "File a notice of appeal" in text
    assert "stage lower_court_decision" in text


def test_summary_handles_missing_advice():
    assert "no advice" in summarise_advice(None)


def test_no_history_leaves_case_text_unchanged():
    assert fold_history("the case", [], 1000) == ("the case", 0)


def test_history_is_appended_in_order_after_the_case():
    turns = [Turn("first question?", ADVICE), Turn("second question?", None)]
    text, dropped = fold_history("the case", turns, 1000)
    assert dropped == 0 and text.startswith("the case")
    assert text.index("Earlier question 1") < text.index("Earlier question 2")
    assert "EARLIER IN THIS CONVERSATION" in text


def test_oldest_turns_are_dropped_first_when_over_budget():
    turns = [Turn(f"question number {i} " + "word " * 60, ADVICE) for i in range(1, 6)]
    text, dropped = fold_history("the case", turns, 400)
    assert 0 < dropped < 5
    assert "Earlier question 5" in text and "Earlier question 1:" not in text
    assert f"{dropped} earlier turns omitted" in text


def test_a_budget_too_small_for_any_turn_keeps_only_the_case():
    text, dropped = fold_history("the case", [Turn("q " * 500, ADVICE)], 10)
    assert text == "the case" and dropped == 1
