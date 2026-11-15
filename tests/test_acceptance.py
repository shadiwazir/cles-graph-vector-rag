"""Acceptance criteria evaluation (pure functions)."""

from cles.evaluation.accept import evaluate, verdict, wilson_lower


def cell(rate, n, hits=None):
    return {"rate": rate, "n": n, "hits": round(rate * n) if hits is None else hits}


RESULTS = {
    "ft": {
        "all": {
            "valid_schema": cell(1.0, 48),
            "citations_outside_context": 0,
            "citation_failure_rate": 0.04,
            "top_outcome_ok": cell(0.46, 24, 11),
            "majority_baseline": cell(0.42, 24, 10),
            "high_precision": cell(0.47, 17, 8),
            "likelihood_over_cap": 6,
        }
    },
    "base": {"all": {"top_outcome_ok": cell(0.62, 24, 15)}},
}


def spec(*criteria):
    return {"system": "ft", "criteria": list(criteria)}


def test_wilson_lower_is_below_the_point_estimate_and_grows_with_n():
    assert wilson_lower(11, 24) < 11 / 24
    assert wilson_lower(110, 240) > wilson_lower(11, 24)
    assert wilson_lower(0, 0) == 0.0


def test_value_reference_and_reference_system_comparisons():
    rows = evaluate(
        spec(
            {"id": "a", "metric": "valid_schema", "op": ">=", "value": 0.98},
            {"id": "b", "metric": "top_outcome_ok", "op": ">=", "reference": "majority_baseline"},
            {
                "id": "c",
                "metric": "top_outcome_ok",
                "op": ">=",
                "reference_system": "base",
                "margin": -0.10,
            },
            {"id": "d", "metric": "citations_outside_context", "op": "==", "value": 0},
        ),
        RESULTS,
    )
    assert {r["id"]: r["passed"] for r in rows} == {"a": True, "b": True, "c": False, "d": True}


def test_interval_rule_is_stricter_than_the_point_estimate():
    row = evaluate(
        spec(
            {
                "id": "w",
                "mode": "wilson_lower",
                "metric": "top_outcome_ok",
                "op": ">=",
                "reference": "majority_baseline",
            }
        ),
        RESULTS,
    )[0]
    assert row["passed"] is False and row["actual"] < 0.46


def test_min_n_makes_a_criterion_inconclusive_not_failed():
    row = evaluate(
        spec({"id": "h", "metric": "high_precision", "op": ">=", "value": 0.67, "min_n": 30}),
        RESULTS,
    )[0]
    assert row["passed"] is None and "needs 30" in row["note"]


def test_tracked_criterion_becomes_blocking_with_enough_examples():
    crit = {
        "id": "t",
        "tier": "tracked",
        "blocking_from_n": 20,
        "metric": "top_outcome_ok",
        "op": ">=",
        "value": 0.9,
    }
    assert evaluate(spec(crit), RESULTS)[0]["tier"] == "blocking"
    assert evaluate(spec({**crit, "blocking_from_n": 100}), RESULTS)[0]["tier"] == "tracked"


def test_verdict_rejects_on_a_failed_blocking_criterion_only():
    rows = evaluate(
        spec(
            {"id": "ok", "tier": "blocking", "metric": "valid_schema", "op": ">=", "value": 0.98},
            {"id": "hp", "tier": "blocking", "metric": "high_precision", "op": ">=", "value": 0.67},
            {
                "id": "tr",
                "tier": "tracked",
                "metric": "likelihood_over_cap",
                "op": "<=",
                "value": 3,
            },
        ),
        RESULTS,
    )
    v = verdict(rows)
    assert (
        v["status"] == "rejected"
        and v["blocking_failed_ids"] == ["hp"]
        and v["tracked_failed_ids"] == ["tr"]
    )
    assert verdict([r for r in rows if r["id"] == "ok"])["status"] == "accepted_provisional"


def test_unmeasured_blocking_criterion_means_incomplete():
    rows = evaluate(spec({"id": "x", "metric": "nope", "op": ">=", "value": 1}), RESULTS)
    assert verdict(rows)["status"] == "incomplete"


def test_missing_reference_is_reported():
    rows = evaluate(
        spec({"id": "r", "metric": "top_outcome_ok", "op": ">=", "reference_system": "ghost"}),
        RESULTS,
    )
    assert rows[0]["passed"] is None
