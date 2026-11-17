"""Likelihood and route order from the outcomes of the retrieved decisions (ADR 0024)."""

from cles.inference.evidence import (
    apply_evidence,
    precedent_level,
    precedent_share,
    render_precedents,
)

EARLY = {"facts", "procedural_history"}


def route(name, outcome, likelihood="medium"):
    return {"name": name, "expected_outcome": outcome, "likelihood": likelihood}


def advice(stage, *routes):
    return {"stage": stage, "routes": list(routes)}


def test_levels_follow_the_agreement_of_the_precedents():
    d, a = "dismissed", "allowed"
    assert precedent_level(d, [d, d]) == "high"  # unanimous, at least two
    assert precedent_level(d, [d]) == "medium"  # one precedent is not agreement
    assert precedent_level(d, [d, d, a]) == "medium"  # a majority
    assert precedent_level(d, [d, a]) == "medium"  # half
    assert precedent_level(a, [d, d, a]) == "low"  # a minority
    assert precedent_level(d, []) == "low" and precedent_level(d, ["", ""]) == "low"
    assert precedent_level(d, [d, d], min_decisions=3) == "medium"
    assert precedent_share(d, [d, a, "", d]) == 2 / 3  # unknown outcomes are not counted


def test_rendering_states_counts_most_common_first():
    assert render_precedents(["a", "b", "a", ""]) == "a: 2, b: 1 (of 3 retrieved decisions)"
    assert "no outcome known" in render_precedents([])


def test_late_stage_routes_get_computed_likelihoods_and_are_ordered_by_evidence():
    adv = advice(
        "grounds_of_appeal",
        route("allowed", "allowed", "high"),  # the writer's confident rating is replaced
        route("dismissed", "dismissed", "low"),
    )
    warnings = apply_evidence(adv, ["dismissed", "dismissed", "dismissed", "allowed"], EARLY)
    assert [r["name"] for r in adv["routes"]] == ["dismissed", "allowed"]
    assert [r["likelihood"] for r in adv["routes"]] == ["medium", "low"]
    assert any("ordered" in w for w in warnings) and any("set to" in w for w in warnings)


def test_order_does_not_depend_on_which_route_the_writer_listed_first():
    """Ties must not carry hindsight: the writer put the real outcome first, the tie-break is a
    hash of the seed and the outcome."""
    outcomes = ["x", "y"]  # an even split: both routes tie
    orders = set()
    for seed in (f"case{i}" for i in range(40)):
        first = advice("grounds_of_appeal", route("x", "x"), route("y", "y"))
        second = advice("grounds_of_appeal", route("y", "y"), route("x", "x"))
        apply_evidence(first, outcomes, EARLY, seed=seed)
        apply_evidence(second, outcomes, EARLY, seed=seed)
        assert [r["name"] for r in first["routes"]] == [r["name"] for r in second["routes"]]
        orders.add(first["routes"][0]["name"])
    assert orders == {"x", "y"}  # and it is not always the same route either


def test_early_stages_and_routes_without_outcome_are_left_alone():
    early = advice("facts", route("plead", "dismissed", "high"))
    assert apply_evidence(early, ["dismissed", "dismissed"], EARLY) == []
    assert early["routes"][0]["likelihood"] == "high"
    mixed = advice(
        "grounds_of_appeal", {"name": "procedural", "likelihood": "medium"}, route("a", "a")
    )
    apply_evidence(mixed, ["a", "a"], EARLY)
    assert [r["name"] for r in mixed["routes"]] == ["a", "procedural"]  # no outcome: after
    assert mixed["routes"][1]["likelihood"] == "medium"


def test_replayed_calibration_survives_malformed_answers_and_does_not_touch_the_original():
    from cles.evaluation.score import calibrate_answer

    example = {"example_id": "d#grounds_of_appeal", "evidence_strength": "strong"}
    caps = {"facts": "low"}
    broken = {"stage": "grounds_of_appeal", "routes": ["not an object", "either"]}
    for variant in ("+rule", "+lead"):
        out = calibrate_answer(broken, variant, ["a", "a"], EARLY, caps, example, 2)
        assert out == broken  # returned as it is, no crash
        assert calibrate_answer(None, variant, [], EARLY, caps, example, 2) is None
        assert calibrate_answer({"routes": "x"}, variant, [], EARLY, caps, example, 2) == {
            "routes": "x"
        }
    original = advice("grounds_of_appeal", route("b", "b", "high"), route("a", "a", "low"))
    lead = calibrate_answer(original, "+lead", ["a", "a", "a"], EARLY, caps, example, 2)
    assert [r["name"] for r in lead["routes"]] == ["a", "b"] and lead["routes"][0][
        "likelihood"
    ] == "high"
    assert [r["name"] for r in original["routes"]] == ["b", "a"]  # the stored answer is untouched
    rule = calibrate_answer(original, "+rule", ["a", "a", "a"], EARLY, caps, example, 2)
    assert [r["name"] for r in rule["routes"]] == ["b", "a"] and rule["routes"][0][
        "likelihood"
    ] == "medium"
