from cles.inference.calibration import cap_likelihood


def advice(*levels):
    return {"routes": [{"name": f"r{i}", "likelihood": lvl} for i, lvl in enumerate(levels)]}


def test_caps_by_evidence_strength():
    a = advice("high", "medium", "low")
    warnings = cap_likelihood(a, "moderate")
    assert [r["likelihood"] for r in a["routes"]] == ["medium", "medium", "low"]
    assert len(warnings) == 1 and "high to medium" in warnings[0]


def test_weak_evidence_caps_everything_at_low():
    a = advice("high", "medium")
    assert len(cap_likelihood(a, "weak")) == 2
    assert {r["likelihood"] for r in a["routes"]} == {"low"}


def test_strong_evidence_changes_nothing():
    a = advice("high", "low")
    assert cap_likelihood(a, "strong") == []


def test_early_stage_cap_applies_even_with_strong_evidence():
    a = advice("high", "medium")
    a["stage"] = "facts"
    warnings = cap_likelihood(a, "strong", {"facts": "medium", "procedural_history": "medium"})
    assert [r["likelihood"] for r in a["routes"]] == ["medium", "medium"]
    assert len(warnings) == 1 and "facts stage" in warnings[0]


def test_late_stage_is_not_capped_by_stage():
    a = advice("high")
    a["stage"] = "grounds_of_appeal"
    assert cap_likelihood(a, "strong", {"facts": "medium"}) == []


def test_dismissed_outcome_with_remedies_is_rejected_by_schema():
    import json
    from pathlib import Path

    from jsonschema import Draft202012Validator

    schema = json.loads(Path("domain_packs/legal_ca_on/advice_schema.json").read_text())
    route = {
        "name": "r",
        "description": "d",
        "next_event": "The appeal is heard.",
        "expected_outcome": "appeal_dismissed",
        "expected_remedies": ["order_varied"],
        "likelihood": "low",
        "reasoning": "x",
        "authorities": [],
    }
    doc = {
        "stage": "grounds_of_appeal",
        "case_position": "p",
        "routes": [route],
        "risks": [],
        "recommended_next_steps": [],
        "missing_information": [],
        "evidence_strength": "weak",
    }
    assert list(Draft202012Validator(schema).iter_errors(doc))
    route["expected_remedies"] = []
    assert not list(Draft202012Validator(schema).iter_errors(doc))


def _validator():
    import json
    from pathlib import Path

    from jsonschema import Draft202012Validator

    return Draft202012Validator(
        json.loads(Path("domain_packs/legal_ca_on/advice_schema.json").read_text())
    )


def _advice(stage, with_outcome):
    route = {
        "name": "r",
        "description": "d",
        "next_event": "The trial judge rules on the facts.",
        "likelihood": "low",
        "reasoning": "x",
        "authorities": [],
    }
    if with_outcome:
        route["expected_outcome"] = "appeal_allowed"
    return {
        "stage": stage,
        "case_position": "p",
        "routes": [route],
        "risks": [],
        "recommended_next_steps": [],
        "missing_information": [],
        "evidence_strength": "weak",
    }


def test_early_stage_route_may_omit_expected_outcome():
    assert not list(_validator().iter_errors(_advice("facts", with_outcome=False)))


def test_late_stage_route_must_have_expected_outcome():
    assert list(_validator().iter_errors(_advice("lower_court_decision", with_outcome=False)))
    assert not list(_validator().iter_errors(_advice("lower_court_decision", with_outcome=True)))


def test_advice_stages_match_extraction_stages_and_training_questions():
    from pathlib import Path

    from cles.domain.pack import load_pack

    pack = load_pack(Path("domain_packs"), "legal_ca_on")
    stages = pack.extraction_schema["properties"]["stages"]["items"]["properties"]["stage"]["enum"]
    assert pack.advice_schema["properties"]["stage"]["enum"] == stages
    assert set(pack.training.questions) <= set(stages)
    assert set(pack.info.likelihood_caps_by_stage) <= set(stages)
