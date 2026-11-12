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


def test_dismissed_outcome_with_remedies_is_rejected_by_schema():
    import json
    from pathlib import Path

    from jsonschema import Draft202012Validator

    schema = json.loads(Path("domain_packs/legal_ca_on/advice_schema.json").read_text())
    route = {
        "name": "r",
        "description": "d",
        "expected_outcome": "appeal_dismissed",
        "expected_remedies": ["order_varied"],
        "likelihood": "low",
        "reasoning": "x",
        "authorities": [],
    }
    doc = {
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
