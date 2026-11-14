"""Drift and regression rules (pure functions)."""

from cles.evaluation.drift import compare_metrics, evidence_shares, online_problems

RULES = {"rates_max_drop": 0.10, "counts_max_increase": {"citations_failed": 5}}
ONLINE = {"min_requests": 10, "evidence_share_max_shift": 0.2, "citation_failure_rate_max": 0.15}


def test_rate_drop_beyond_tolerance_is_a_violation():
    base = {"ft.all.top_outcome_ok": 0.60, "ft.all.valid_schema": 1.0}
    cur = {"ft.all.top_outcome_ok": 0.45, "ft.all.valid_schema": 0.95}
    problems = compare_metrics(base, cur, RULES)
    assert len(problems) == 1 and "top_outcome_ok" in problems[0]


def test_count_increase_and_other_scopes():
    base = {"ft.all.citations_failed": 8.0, "ft.facts.citations_failed": 0.0}
    cur = {"ft.all.citations_failed": 20.0, "ft.facts.citations_failed": 99.0}
    problems = compare_metrics(base, cur, RULES)
    assert problems == ["ft: citations_failed rose from 8 to 20"]  # only scope 'all' is compared


def test_no_change_no_violation():
    m = {"ft.all.top_outcome_ok": 0.5}
    assert compare_metrics(m, m, RULES) == []


def test_online_check_skips_when_traffic_is_low():
    assert online_problems(["strong"] * 10, ["weak"] * 3, 10, 9, ONLINE) == []


def test_online_check_flags_evidence_shift_and_citation_failures():
    ref = ["strong"] * 8 + ["moderate"] * 2
    live = ["weak"] * 8 + ["strong"] * 2
    problems = online_problems(ref, live, 20, 6, ONLINE)
    assert any("'weak'" in p for p in problems) and any("citation failure" in p for p in problems)


def test_evidence_shares_sum_to_one():
    assert sum(evidence_shares(["weak", "strong", "strong"]).values()) == 1
