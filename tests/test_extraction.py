import json
from pathlib import Path

from cles.domain.pack import load_pack
from cles.extraction.extractor import (
    build_messages,
    estimate_input_tokens,
    extract_document,
    known_values,
    schema_version,
)
from cles.llm.base import LLMResponse, estimate_cost

ROOT = Path(__file__).parent.parent
PACK = load_pack(ROOT / "domain_packs", "legal_ca_on")
VALID = (ROOT / "tests/fixtures/extraction_2026_ONCA_724.json").read_text()


class FakeClient:
    """Returns the queued replies in order."""

    model = "fake"

    def __init__(self, *replies: str):
        self.replies = list(replies)
        self.calls = 0

    def complete_json(self, messages):
        self.calls += 1
        return LLMResponse(self.replies.pop(0), 100, 50, "fake")


class BrokenClient:
    model = "fake"

    def complete_json(self, messages):
        raise RuntimeError("network down")


def test_fixture_matches_schema():
    out = extract_document(FakeClient(VALID), PACK, "d", "h", "t")
    assert out.status == "ok" and out.result["case_id"] == "2026 ONCA 724"


def test_invalid_json_is_retried_once_then_succeeds():
    client = FakeClient("not json", VALID)
    out = extract_document(client, PACK, "d", "h", "t")
    assert out.status == "ok" and client.calls == 2
    assert out.input_tokens == 200 and out.output_tokens == 100


def test_schema_violation_on_every_attempt_is_invalid():
    bad = json.dumps({"case_id": "x"})
    out = extract_document(FakeClient(bad, bad, bad), PACK, "d", "h", "t")
    assert out.status == "invalid" and "title" in out.error


def test_provider_error_is_recorded_not_raised():
    out = extract_document(BrokenClient(), PACK, "d", "h", "t")
    assert out.status == "failed" and "network down" in out.error


def test_messages_include_schema_and_document():
    system, user = build_messages(PACK, "HEADER", "BODY")
    assert "JSON Schema" in system["content"] and "BODY" in user["content"]
    assert estimate_input_tokens(PACK, "HEADER", "BODY") > 0


def test_schema_version_changes_with_prompt():
    a = schema_version(PACK)
    changed = type(PACK)(**{**PACK.__dict__, "extraction_prompt": PACK.extraction_prompt + "x"})
    assert schema_version(changed) != a


def test_cost_estimate():
    assert estimate_cost(1_000_000, 500_000, 2.0, 8.0) == 6.0
    assert estimate_cost(10, 10, None, None) is None


def test_known_fields_override_the_model():
    wrong = json.loads(VALID) | {"case_id": "WRONG", "title": "Wrong"}
    known = {"case_id": "2026 ONCA 724", "title": "Bradley Court Limited v. Tinkasimire"}
    out = extract_document(FakeClient(json.dumps(wrong)), PACK, "d", "h", "t", known)
    assert out.result["case_id"] == "2026 ONCA 724" and out.result["title"].startswith("Bradley")


def test_known_fields_fill_missing_required_fields():
    partial = {k: v for k, v in json.loads(VALID).items() if k not in ("case_id", "title")}
    known = {"case_id": "2026 ONCA 724", "title": "T"}
    out = extract_document(FakeClient(json.dumps(partial)), PACK, "d", "h", "t", known)
    assert out.status == "ok"


def test_known_values_from_pack_config():
    from datetime import date

    known = known_values(PACK, "2026 ONCA 724", "Title", date(2026, 10, 6))
    assert known == {"case_id": "2026 ONCA 724", "title": "Title", "decision_date": "2026-10-06"}


def test_tidy_drops_nulls_and_fixes_enum_case():
    from cles.extraction.extractor import tidy

    messy = {
        "outcome": "Appeal_Dismissed",
        "lawyers": [{"name": "A", "side": "Appellant"}],
        "citations": [{"case_id": "x", "treatment": "cited", "para": None}],
        "court": None,
    }
    clean = tidy(messy, PACK.extraction_schema)
    assert clean["outcome"] == "appeal_dismissed"
    assert clean["lawyers"][0]["side"] == "appellant"
    assert "para" not in clean["citations"][0] and "court" not in clean


def test_outcome_and_remedy_enums_match_outcomes_file():
    props = PACK.extraction_schema["properties"]
    assert props["outcome"]["enum"] == PACK.outcomes
    assert props["remedies"]["items"]["enum"] == PACK.remedies


def test_leak_check_flags_decision_in_known_so_far():
    from cles.extraction.extractor import find_leaks

    clean = {"stages": [{"known_so_far": "The trial judge convicted him and imposed 8 years."}]}
    leaky = {"stages": [{"known_so_far": "The Court of Appeal dismissed the appeals."}]}
    assert find_leaks(clean, PACK) == []
    assert find_leaks(leaky, PACK) and "stages/0/known_so_far" in find_leaks(leaky, PACK)[0]


def test_leak_triggers_retry_with_feedback():
    leaky = json.loads(VALID)
    leaky["stages"][0]["known_so_far"] = (
        "The appeal was dismissed by the Court of Appeal on all grounds."
    )
    client = FakeClient(json.dumps(leaky), VALID)
    out = extract_document(client, PACK, "d", "h", "t")
    assert out.status == "ok" and client.calls == 2


def test_dismissed_appeal_with_remedies_is_rejected_by_schema():
    bad = json.loads(VALID) | {"outcome": "appeal_dismissed", "remedies": ["order_varied"]}
    out = extract_document(FakeClient(*[json.dumps(bad)] * 3), PACK, "d", "h", "t")
    assert out.status == "invalid" and "remedies" in out.error


def test_advice_schema_enums_match_outcomes_file():
    route = PACK.advice_schema["properties"]["routes"]["items"]["properties"]
    assert route["expected_outcome"]["enum"] == PACK.outcomes
    assert route["expected_remedies"]["items"]["enum"] == PACK.remedies
