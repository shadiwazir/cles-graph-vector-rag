"""Decision-level uncertainty and the model-free baselines (no database, no model)."""

import json

from cles.evaluation.baselines import (
    baseline_rows,
    load_outcomes,
    precedent_outcome,
    prior_outcome,
    summarize,
)
from cles.evaluation.scoring import aggregate, score_answer
from cles.evaluation.statistics import cluster_bootstrap, cluster_rate

EARLY = {"facts", "procedural_history"}


def test_cluster_rate_skips_not_applicable_and_counts_decisions():
    cell = cluster_rate([("a", True), ("a", False), ("b", None), ("c", True)])
    assert (cell["n"], cell["hits"], cell["clusters"]) == (3, 2, 2)


def test_interval_is_wider_when_the_examples_of_a_decision_agree():
    """Four examples per decision that all agree carry the evidence of one example each, so the
    interval over decisions must be wider than a naive one over examples."""
    items = [(f"d{i}", i < 6) for i in range(12) for _ in range(4)]  # 6 of 12 decisions hit
    cell = cluster_bootstrap(items)
    assert cell["rate"] == 0.5 and cell["clusters"] == 12
    assert cell["low"] <= 0.5 <= cell["high"]
    assert cell["high"] - cell["low"] > 0.35  # about +-0.28 for 12 decisions, not +-0.14


def test_interval_is_deterministic_and_none_for_one_decision():
    items = [("a", True), ("b", False), ("c", True)]
    assert cluster_bootstrap(items) == cluster_bootstrap(items)
    one = cluster_bootstrap([("a", True), ("a", False)])
    assert one["low"] is None and one["high"] is None


def test_summary_reports_decisions_and_interval():
    rows = []
    for i in range(6):
        ex = {
            "example_id": f"d{i}#g",
            "doc_id": f"d{i}",
            "stage": "grounds_of_appeal",
            "outcome": "appeal_dismissed",
            "evidence_strength": "moderate",
        }
        adv = {
            "stage": "grounds_of_appeal",
            "routes": [
                {"expected_outcome": "appeal_dismissed" if i % 2 else "x", "likelihood": "high"}
            ],
        }
        rows.append(score_answer(ex, adv, [], EARLY, {}))
    total = aggregate(rows)["all"]
    assert total["decisions"] == 6 and total["top_outcome_ok"]["rate"] == 0.5
    assert total["top_outcome_low"] is not None and total["high_precision_high"] is not None


def _example(doc, stage, outcome, ctx):
    return {
        "example_id": f"{doc}#{stage}",
        "doc_id": doc,
        "stage": stage,
        "outcome": outcome,
        "context_docs": [{"doc_id": c} for c in ctx],
    }


def test_prior_counts_decisions_not_examples():
    train = [_example("a", s, "allowed", []) for s in ("facts", "grounds", "x", "y")]
    train += [_example("b", "g", "dismissed", []), _example("c", "g", "dismissed", [])]
    assert prior_outcome(train) == "dismissed"  # 2 decisions against 1, though 4 examples vs 2


def test_precedent_vote_plurality_tie_goes_to_better_rank_and_unanimity():
    outcomes = {
        "p": "dismissed",
        "q": "allowed",
        "r": "allowed",
        "s": "dismissed",
        "t": "dismissed",
    }
    assert precedent_outcome(_example("z", "g", "?", ["p", "q", "r"]), outcomes) == (
        "allowed",
        False,
    )
    assert precedent_outcome(_example("z", "g", "?", ["q", "p"]), outcomes) == ("allowed", False)
    assert precedent_outcome(_example("z", "g", "?", ["p", "s", "t"]), outcomes) == (
        "dismissed",
        True,
    )
    assert precedent_outcome(_example("z", "g", "?", ["unknown"]), outcomes) == (None, False)


def test_baseline_rows_score_late_stages_only_and_summarize():
    outcomes = {"p": "dismissed", "s": "dismissed"}
    examples = [
        _example("d1", "facts", "dismissed", ["p", "s"]),
        _example("d1", "grounds_of_appeal", "dismissed", ["p", "s"]),
        _example("d2", "grounds_of_appeal", "allowed", ["p", "s"]),
    ]
    rows = baseline_rows(examples, outcomes, "dismissed", EARLY)
    assert [r["top_outcome_ok"] for r in rows["baseline_prior"]] == [None, True, False]
    summary = summarize(rows["baseline_precedent"])
    assert summary["top_outcome_ok"]["n"] == 2 and summary["decisions"] == 2
    assert summary["unanimous_ok"]["hits"] == 1


def test_load_outcomes_filters_by_version_and_status(tmp_path):
    path = tmp_path / "x.jsonl"
    lines = [
        {"doc_id": "a", "schema_version": "v1", "status": "ok", "result": {"outcome": "allowed"}},
        {"doc_id": "a", "schema_version": "v0", "status": "ok", "result": {"outcome": "old"}},
        {"doc_id": "b", "schema_version": "v1", "status": "failed", "result": None},
    ]
    path.write_text("\n".join(json.dumps(x) for x in lines))
    assert load_outcomes(path, "v1") == {"a": "allowed"}


def test_outcome_shift_counts_decisions_and_measures_distance():
    from cles.training.diagnostics import outcome_shift

    def ex(doc, split, outcome):
        return {"doc_id": doc, "split": split, "outcome": outcome}

    same = [ex("a", "train", "x"), ex("a", "train", "x"), ex("b", "eval", "x")]
    assert outcome_shift(same)["distance"] == 0
    skew = [ex("a", "train", "x"), ex("b", "train", "x"), ex("c", "eval", "y")]
    shift = outcome_shift(skew)
    assert shift["distance"] == 1 and shift["decisions"] == {"train": 2, "eval": 1}


def test_family_candidates_cross_the_split_only_and_ignore_the_state_side():
    from cles.training.diagnostics import family_candidates, party_keys

    ignore = ["crown"]
    patterns = [r"(?i)his majesty"]
    one = party_keys(
        [{"name": "His Majesty the King", "kind": "other"}, {"name": "2206747 Ontario Limited"}],
        ignore,
        patterns,
    )
    other = party_keys(
        [{"name": "The Crown", "kind": "crown"}, {"name": "9999999 Ontario Limited"}],
        ignore,
        patterns,
    )
    assert (
        one == {"2206747 ontario limited"} and one != other
    )  # digits keep numbered companies apart
    parties = {"a": {"dw"}, "b": {"dw"}, "c": {"dw"}, "d": {"zz"}}
    split = {"a": "train", "b": "train", "c": "eval", "d": "eval"}
    found = family_candidates(parties, split)
    assert [f["docs"] for f in found] == [["a", "c"], ["b", "c"]]  # not a-b (same side)
    # a repeat player (a party in many decisions) is not a case family; the pair with the most
    # shared names comes first
    parties = {"a": {"bank", "x", "y"}, "b": {"bank"}, "c": {"bank", "x", "y"}, "d": {"bank"}}
    split = {"a": "train", "b": "train", "c": "eval", "d": "eval"}
    assert family_candidates(parties, split, max_party_decisions=3) == [
        {"docs": ["a", "c"], "shared": ["x", "y"]}
    ]
    assert len(family_candidates(parties, split)) == 4  # without the limit the bank links them


def _advice(stage, *routes):
    return {
        "stage": stage,
        "routes": [
            {"name": f"r{i}", "expected_outcome": o, "likelihood": lk}
            for i, (o, lk) in enumerate(routes)
        ],
    }


def test_precedent_rule_keeps_high_only_when_all_precedents_agree():
    from cles.inference.calibration import apply_precedent_rule

    agree = _advice("grounds_of_appeal", ("dismissed", "high"), ("allowed", "medium"))
    assert apply_precedent_rule(agree, ["dismissed", "dismissed"], EARLY) == []
    assert agree["routes"][0]["likelihood"] == "high"

    split = _advice("grounds_of_appeal", ("dismissed", "high"))
    warnings = apply_precedent_rule(split, ["dismissed", "allowed", "dismissed"], EARLY)
    assert split["routes"][0]["likelihood"] == "medium" and len(warnings) == 1

    other = _advice("grounds_of_appeal", ("allowed", "high"))  # precedents agree on another outcome
    apply_precedent_rule(other, ["dismissed", "dismissed"], EARLY)
    assert other["routes"][0]["likelihood"] == "medium"


def test_precedent_rule_needs_enough_known_decisions_and_skips_early_stages():
    from cles.inference.calibration import apply_precedent_rule

    one = _advice("grounds_of_appeal", ("dismissed", "high"))
    apply_precedent_rule(one, ["dismissed", ""], EARLY)  # one known outcome is not agreement
    assert one["routes"][0]["likelihood"] == "medium"
    assert apply_precedent_rule(_advice("facts", ("x", "high")), [], EARLY) == []
    low = _advice("grounds_of_appeal", ("dismissed", "low"))
    apply_precedent_rule(low, ["allowed", "dismissed"], EARLY)  # never raises, only lowers high
    assert low["routes"][0]["likelihood"] == "low"


def test_same_type_vote_counts_only_decisions_of_the_cases_own_type():
    outcomes = {"c1": "dismissed", "c2": "dismissed", "v1": "allowed", "v2": "allowed"}
    types = {"c1": "criminal", "c2": "criminal", "v1": "civil", "v2": "civil"}
    civil = _example("z", "g", "allowed", ["c1", "c2", "v1", "v2"]) | {"case_type": "civil"}
    plain, _ = precedent_outcome(civil, outcomes)
    same, unanimous = precedent_outcome(civil, outcomes, types)
    assert plain == "dismissed"  # the two criminal precedents come first and tie with civil
    assert same == "allowed" and unanimous  # only the civil ones count
    none = _example("z", "g", "x", ["c1"]) | {"case_type": "civil"}
    assert precedent_outcome(none, outcomes, types) == (None, False)  # no same-type precedent


def test_same_type_baseline_rows_differ_from_the_plain_vote_and_report_coverage():
    outcomes = {"c1": "dismissed", "v1": "allowed", "v2": "allowed"}
    types = {"c1": "criminal", "v1": "civil", "v2": "civil"}
    ex = _example("z", "grounds_of_appeal", "allowed", ["c1", "v1", "v2"]) | {"case_type": "civil"}
    only = _example("y", "grounds_of_appeal", "dismissed", ["c1"]) | {"case_type": "civil"}
    rows = baseline_rows([ex, only], outcomes, "dismissed", EARLY, types)
    assert rows["baseline_precedent"][0]["top_outcome"] == "allowed"
    assert [r["top_outcome"] for r in rows["baseline_precedent_same_type"]] == ["allowed", None]
    summary = summarize(rows["baseline_precedent_same_type"])
    assert summary["coverage"] == 0.5
    assert "baseline_precedent_same_type" not in baseline_rows([ex], outcomes, "x", EARLY)
