import pytest

from cles.evaluation.retrieval import first_hit_rank, summarise
from cles.evaluation.run import DEV_SET, load_cases


def test_first_hit_rank():
    assert first_hit_rank(["a", "b", "c"], ("c", "z")) == 3
    assert first_hit_rank(["a"], ("z",)) is None


def test_summarise_recall_and_mrr():
    result = summarise([1, 3, None, 2], ks=(1, 2, 3))
    assert result["recall@1"] == 0.25
    assert result["recall@2"] == 0.5
    assert result["recall@3"] == 0.75
    assert result["mrr"] == pytest.approx((1 + 1 / 3 + 0 + 1 / 2) / 4)


def test_dev_set_is_well_formed():
    cases = load_cases(DEV_SET)
    assert len(cases) >= 10
    assert all(c.question and c.expect for c in cases)
