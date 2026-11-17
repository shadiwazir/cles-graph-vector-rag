import json
from datetime import date
from pathlib import Path

import pytest

from cles.domain.pack import load_pack
from cles.llm.base import LLMResponse
from cles.retrieval.types import ContextPack, Passage
from cles.training.build_dataset import Prepared, assemble, prepare_examples
from cles.training.dataset import DocInfo, assign_split, pick_question, render_hindsight
from cles.training.leakage import check_example, check_split
from cles.training.target import TargetSpec, check_target, generate_target

ROOT = Path(__file__).parent.parent
PACK = load_pack(ROOT / "domain_packs", "legal_ca_on")


def doc(doc_id, day, outcome="appeal_dismissed", remedies=()):
    ext = {
        "outcome": outcome,
        "remedies": list(remedies),
        "issues": ["i"],
        "stages": [
            {
                "stage": "facts",
                "known_so_far": "The accused was charged after an incident on a boat.",
                "next_steps": "The trial judge acquitted.",
            },
            {
                "stage": "grounds_of_appeal",
                "known_so_far": "The Crown appealed the acquittal arguing an error of law.",
                "next_steps": "The Court of Appeal allowed the appeal.",
            },
        ],
    }
    return DocInfo(doc_id, f"R. v. {doc_id}", day, ext)


DOCS = [doc(f"d{i}", date(2026, 1, i + 1)) for i in range(10)]


def test_split_puts_newest_in_eval_and_all_older_in_train():
    split_date, split = assign_split(DOCS, 0.2)
    assert split_date == date(2026, 1, 9)
    assert {d for d, s in split.items() if s == "eval"} == {"d8", "d9"}
    train_dates = [d.doc_date for d in DOCS if split[d.doc_id] == "train"]
    assert max(train_dates) < split_date


def test_split_keeps_same_date_documents_together():
    docs = [doc("a", date(2026, 1, 1)), doc("b", date(2026, 1, 5)), doc("c", date(2026, 1, 5))]
    split_date, split = assign_split(docs, 0.1)
    assert split["b"] == split["c"] == "eval" and split["a"] == "train"


def test_split_needs_training_documents():
    with pytest.raises(ValueError, match="no training documents"):
        assign_split([doc("a", date(2026, 1, 1)), doc("b", date(2026, 1, 1))], 0.1)


def test_question_is_deterministic_and_stage_specific():
    q1 = pick_question(PACK, "facts", "d1")
    assert q1 == pick_question(PACK, "facts", "d1") and q1 in PACK.training.questions["facts"]
    assert pick_question(PACK, "no_such_stage", "d1") is None


def test_hindsight_is_labelled_and_contains_the_outcome():
    text = render_hindsight(DOCS[0].extraction, DOCS[0].extraction["stages"][0])
    assert "never reveal" in text and "appeal_dismissed" in text and "acquitted" in text


# ---- target checks ----------------------------------------------------------------------------

PASSAGE = Passage(
    "c1", "2020 ONCA 5", "X v. Y", 4, 6, "The trial judge erred in law by ignoring it."
)
CONTEXT = ContextPack([PASSAGE], {}, "moderate", ["2020 ONCA 5"])


def spec(outcome="appeal_allowed", remedies=("new_trial_ordered",)):
    stage = "grounds_of_appeal"
    return TargetSpec("2026 ONCA 9", "R. v. Boat", stage, outcome, remedies, CONTEXT)


def advice(outcome="appeal_allowed", remedies=("new_trial_ordered",), authorities=None, text="x"):
    auth = (
        authorities
        if authorities is not None
        else [{"case_id": "2020 ONCA 5", "para": 5, "quote": "erred in law"}]
    )
    route = {
        "name": "Appeal",
        "description": text,
        "next_event": "The appeal is heard by a panel.",
        "expected_outcome": outcome,
        "expected_remedies": list(remedies),
        "likelihood": "high",
        "reasoning": text,
        "authorities": auth,
    }
    return {
        "stage": "grounds_of_appeal",
        "case_position": text,
        "routes": [route],
        "risks": [],
        "recommended_next_steps": [],
        "missing_information": [],
        "evidence_strength": "strong",
    }


def test_good_target_passes():
    assert check_target(advice(), spec()) == []


def test_first_route_must_match_what_happened():
    assert any(
        "expected_outcome" in p for p in check_target(advice("appeal_dismissed", ()), spec())
    )
    assert any("expected_remedies" in p for p in check_target(advice(remedies=()), spec()))


def test_authority_must_come_from_the_retrieved_passages():
    outside = [{"case_id": "2020 ONCA 5", "para": 99, "quote": "erred in law"}]
    wrong_quote = [{"case_id": "2020 ONCA 5", "para": 5, "quote": "something else entirely"}]
    other_case = [{"case_id": "1999 ONCA 1", "para": 5, "quote": "erred in law"}]
    for authorities in (outside, wrong_quote, other_case):
        assert any(
            "not in the retrieved" in p
            for p in check_target(advice(authorities=authorities), spec())
        )


def test_target_must_not_mention_the_case_itself():
    problems = check_target(advice(text="As in R. v. Boat, the court will..."), spec())
    assert any("itself" in p for p in problems)


class Client:
    model = "fake"

    def __init__(self, *replies):
        self.replies = list(replies)

    def complete_json(self, messages):
        return LLMResponse(json.dumps(self.replies.pop(0)), 5, 5, "fake")


def test_generate_target_retries_with_feedback_then_caps_likelihood():
    bad, good = advice("appeal_dismissed", ()), advice()
    out = generate_target(Client(bad, good), [{"role": "user", "content": "x"}], PACK, spec())
    assert out.status == "ok" and out.input_tokens == 10
    assert out.result["routes"][0]["likelihood"] == "medium"  # capped: evidence is moderate
    assert out.result["evidence_strength"] == "moderate"


def test_generate_target_gives_up_after_repeated_failures():
    bad = advice("appeal_dismissed", ())
    out = generate_target(Client(bad, bad, bad), [{"role": "user", "content": "x"}], PACK, spec())
    assert out.status == "invalid" and "expected_outcome" in out.error


# ---- building and leakage ---------------------------------------------------------------------


class FakeRetriever:
    """Returns older documents only, like the real one: records the filters it was given."""

    def __init__(self):
        self.calls = []

    def retrieve(self, query, flt):
        self.calls.append(flt)
        older = [
            d
            for d in DOCS
            if flt.as_of and d.doc_date < flt.as_of and d.doc_id not in flt.exclude_doc_ids
        ]
        passages = [
            Passage(d.doc_id, d.doc_id, d.title, 1, 1, "text", distance=0.2) for d in older[-3:]
        ]
        return ContextPack(
            passages, {}, "strong" if len(passages) >= 3 else "weak", [p.doc_id for p in passages]
        )


def prepared():
    split_date, split = assign_split(DOCS, 0.2)
    retriever = FakeRetriever()
    items = prepare_examples(DOCS, split, split_date, PACK, retriever)
    dates = {d.doc_id: d.doc_date.isoformat() for d in DOCS}
    for item in items:
        item.doc_dates = dates
    return items, split_date, retriever


def example_for(item):
    return assemble(item, {"routes": []}, "fake", "v")


def test_prepared_examples_use_stage_text_and_exclude_the_case():
    items, split_date, retriever = prepared()
    assert len(items) == 20  # 10 documents x 2 stages
    assert all(
        i.doc.doc_id in flt.exclude_doc_ids for i, flt in zip(items, retriever.calls, strict=True)
    )
    first = items[0]
    assert first.case_text in first.base_messages[1]["content"]
    assert "HINDSIGHT" not in first.base_messages[1]["content"]  # the input never has hindsight
    assert "HINDSIGHT" in first.target_messages[1]["content"]


def test_eval_examples_use_the_split_date_as_context_limit():
    items, split_date, _ = prepared()
    evals = [i for i in items if i.split == "eval"]
    assert evals and all(i.as_of == split_date for i in evals)
    trains = [i for i in items if i.split == "train"]
    assert all(i.as_of == i.doc.doc_date for i in trains)


def test_clean_examples_pass_all_leakage_rules():
    items, split_date, _ = prepared()
    examples = [example_for(i) for i in items]
    assert all(check_example(e, PACK, split_date) == [] for e in examples)
    assert check_split(examples) == []


def test_l1_decision_in_case_text_is_caught():
    items, split_date, _ = prepared()
    e = example_for(items[0])
    e["case_text"] = "The Court of Appeal dismissed the appeal."
    assert any(v.startswith("L1") for v in check_example(e, PACK, split_date))


def test_l2_case_in_its_own_context_is_caught():
    items, split_date, _ = prepared()
    e = example_for(items[-1])
    e["context_docs"].append({"doc_id": e["doc_id"], "doc_date": e["doc_date"]})
    assert any(v.startswith("L2") for v in check_example(e, PACK, split_date))


def test_l3_later_context_is_caught():
    items, split_date, _ = prepared()
    e = example_for(items[0])
    e["context_docs"] = [{"doc_id": "later", "doc_date": "2030-01-01"}]
    assert any(v.startswith("L3") for v in check_example(e, PACK, split_date))


def test_l5_eval_context_after_split_is_caught():
    items, split_date, _ = prepared()
    e = example_for(next(i for i in items if i.split == "eval"))
    e["as_of"] = "2030-01-01"  # as_of not violated, but the context is not before the split
    e["context_docs"] = [{"doc_id": "d9x", "doc_date": str(split_date)}]
    assert any(v.startswith("L5") for v in check_example(e, PACK, split_date))


def test_l4_overlapping_split_is_caught():
    items, _, _ = prepared()
    examples = [example_for(i) for i in items]
    next(e for e in examples if e["split"] == "train")["doc_date"] = "2030-01-01"
    assert any(v.startswith("L4") for v in check_split(examples))


def test_assembled_messages_are_the_runtime_prompt_plus_the_target():
    items, _, _ = prepared()
    e = assemble(items[0], {"routes": []}, "fake", "v")
    assert [m["role"] for m in e["messages"]] == ["system", "user", "assistant"]
    assert json.loads(e["messages"][2]["content"]) == {"routes": []}
    assert e["outcome"] == "appeal_dismissed" and isinstance(Prepared, type)


def test_target_must_not_name_its_briefing():
    for word in ("hindsight", "actual next event"):
        problems = check_target(advice(text=f"given the {word} the appeal wins"), spec())
        assert any("write as if" in p for p in problems), word


def test_stage_must_match_the_example():
    wrong = advice()
    wrong["stage"] = "facts"
    assert any("stage must be" in p for p in check_target(wrong, spec()))


def test_hindsight_block_carries_the_stage_for_the_writer_only():
    text = render_hindsight(DOCS[0].extraction, DOCS[0].extraction["stages"][1])
    assert "STAGE: grounds_of_appeal" in text


def test_early_stage_first_route_must_not_be_named_like_an_appeal_result():
    early = TargetSpec(
        "2026 ONCA 9",
        "R. v. Boat",
        "facts",
        "appeal_allowed",
        ("new_trial_ordered",),
        CONTEXT,
        tuple(PACK.training.early_stages),
        tuple(PACK.training.early_route_name_patterns),
    )
    named_like_result = advice()
    named_like_result["stage"] = "facts"
    named_like_result["routes"][0]["name"] = "Appeal allowed; convictions set aside"
    assert any("reads as an appeal result" in p for p in check_target(named_like_result, early))
    path = advice()
    path["stage"] = "facts"
    path["routes"][0]["name"] = "Contest the charges at trial"
    assert check_target(path, early) == []
    # the same name is fine once a decision exists
    assert not any("reads as" in p for p in check_target(advice(), spec()))


def _docs_on(dates):
    return [DocInfo(f"d{i}", f"t{i}", date.fromisoformat(d), {}) for i, d in enumerate(dates)]


def test_plan_folds_gives_disjoint_growing_windows_with_a_final_test():
    from datetime import timedelta

    from cles.training.dataset import fold_split, plan_folds

    start = date(2026, 1, 1)
    docs = _docs_on([(start + timedelta(days=i)).isoformat() for i in range(60)])
    folds = plan_folds(docs, window=10, dev_folds=3)
    assert [f.name for f in folds] == ["dev1", "dev2", "dev3", "test"]
    assert folds[-1].end_date is None and folds[0].end_date == folds[1].split_date
    sizes = []
    for fold in folds:
        split = fold_split(docs, fold)
        train = [d for d in docs if split.get(d.doc_id) == "train"]
        evaluation = [d for d in docs if split.get(d.doc_id) == "eval"]
        assert max(d.doc_date for d in train) < min(d.doc_date for d in evaluation)  # L4
        assert len(evaluation) == 10
        sizes.append(len(train))
    assert sizes == sorted(sizes) and sizes[0] == 20  # training grows; 60 - 4 windows of 10
    assert (
        len({d.doc_id for f in folds for d in docs if fold_split(docs, f).get(d.doc_id) == "eval"})
        == 40
    )


def test_plan_folds_keeps_same_date_decisions_together_and_rejects_tiny_corpora():
    from cles.training.dataset import fold_split, plan_folds

    dates = ["2026-01-01"] * 4 + [f"2026-02-{i:02d}" for i in range(1, 21)]
    docs = _docs_on(dates)
    folds = plan_folds(docs, window=5, dev_folds=2)
    for fold in folds:
        split = fold_split(docs, fold)
        same_day = {split.get(d.doc_id) for d in docs if d.doc_date == date(2026, 1, 1)}
        assert len(same_day) == 1  # never split across train and eval
    with pytest.raises(ValueError, match="too few"):
        plan_folds(_docs_on(["2026-01-01", "2026-01-02"]), window=5, dev_folds=3)
    with pytest.raises(ValueError, match="same date|too small"):
        plan_folds(_docs_on(["2026-01-01"] * 30), window=5, dev_folds=3)


# ---- rolling-origin folds (ADR 0023) -----------------------------------------------------------


def test_folds_share_training_examples_and_obey_every_leakage_rule():
    from cles.training.dataset import fold_split, plan_folds

    folds = plan_folds(DOCS, window=2, dev_folds=2)  # 10 documents: 2 + 2 + 2 evaluation windows
    cache: dict = {}
    retriever = FakeRetriever()
    dates = {d.doc_id: d.doc_date.isoformat() for d in DOCS}
    seen_train: dict[str, set] = {}
    for fold in folds:
        split = fold_split(DOCS, fold)
        items = prepare_examples(
            [d for d in DOCS if d.doc_id in split],
            split,
            fold.split_date,
            PACK,
            retriever,
            None,
            cache,
        )
        for item in items:
            item.doc_dates = dates
        examples = [example_for(i) for i in items]
        assert all(check_example(e, PACK, fold.split_date) == [] for e in examples)
        assert check_split(examples) == []
        seen_train[fold.name] = {i.example_id for i in items if i.split == "train"}
    names = [f.name for f in folds]
    assert seen_train[names[0]] < seen_train[names[1]] < seen_train[names[2]]  # training grows
    calls_with_cache = len(retriever.calls)
    fresh = FakeRetriever()
    for fold in folds:
        split = fold_split(DOCS, fold)
        prepare_examples(
            [d for d in DOCS if d.doc_id in split], split, fold.split_date, PACK, fresh
        )
    assert calls_with_cache < len(fresh.calls)  # shared training examples are retrieved once


def test_evaluation_example_without_a_target_is_a_prompt_only_record():
    items, split_date, _ = prepared()
    item = next(i for i in items if i.split == "eval")
    bare = assemble(item, None, "fake", "v")
    assert [m["role"] for m in bare["messages"]] == ["system", "user"]
    assert check_example(bare, PACK, split_date) == []  # leakage rules need only the prompt
    full = assemble(item, {"routes": []}, "fake", "v")
    assert [m["role"] for m in full["messages"]] == ["system", "user", "assistant"]
    assert "case_type" in full


def test_fold_description_counts_the_training_mix_and_the_window_mix():
    from cles.training.build_folds import describe_fold
    from cles.training.dataset import Fold, fold_split

    docs = [
        DocInfo(f"d{i}", "t", date(2026, 1, 1 + i), {"outcome": o, "case_type": c})
        for i, (o, c) in enumerate(
            [
                ("dismissed", "civil"),
                ("allowed", "criminal"),
                ("dismissed", "civil"),
                ("allowed", "civil"),
            ]
        )
    ]
    fold = Fold("dev1", date(2026, 1, 3), None)
    described = describe_fold(docs, fold, fold_split(docs, fold))
    assert described["train_outcomes"] == {"dismissed": 1, "allowed": 1}
    assert described["eval_decisions"] == 2 and described["eval_case_types"] == {"civil": 2}


def test_context_dates_cover_decisions_without_a_valid_extraction():
    """Retrieval can return a decision whose extraction was rejected; its date is still needed."""
    from cles.training.build_dataset import document_dates

    class Conn:
        def execute(self, sql):
            assert "FROM documents" in sql  # not from the extractions
            return self

        def fetchall(self):
            return [("2025 ONCA 897", date(2025, 11, 3)), ("d1", date(2026, 1, 2))]

    assert document_dates(Conn()) == {"2025 ONCA 897": "2025-11-03", "d1": "2026-01-02"}
