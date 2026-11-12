import json
from pathlib import Path

import pytest

from cles.config import ConfigError, Settings
from cles.domain.pack import load_pack
from cles.inference.guard import check_generator_allowed, is_external
from cles.training.sft_config import load_sft_config
from cles.training.sft_data import (
    estimate_run,
    keep_within,
    length_stats,
    to_prompt_completion,
    token_length,
)
from cles.training.train_sft import _check_leakage, _measure

ROOT = Path(__file__).parent.parent


class FakeTokenizer:
    """One token per word; the 'chat template' just joins the message contents."""

    def apply_chat_template(self, messages, tokenize=False, enable_thinking=False):
        return " ".join(m["content"] for m in messages)

    def __call__(self, text):
        return {"input_ids": text.split()}


def example(words_prompt=10, words_answer=5, doc_id="d1"):
    return {
        "doc_id": doc_id,
        "messages": [
            {"role": "system", "content": "s"},
            {"role": "user", "content": " ".join(["u"] * words_prompt)},
            {"role": "assistant", "content": " ".join(["a"] * words_answer)},
        ],
    }


def test_shipped_configs_load():
    big = load_sft_config(ROOT / "configs/sft/qwen3_8b_qlora.yaml")
    assert big.backend == "unsloth" and big.lora.r == 64 and big.lora.alpha == 128
    assert big.max_seq_length == 8192 and big.load_in_4bit
    smoke = load_sft_config(ROOT / "configs/sft/smoke_cpu.yaml")
    assert smoke.backend == "plain" and smoke.max_steps == 2 and not smoke.load_in_4bit


def test_params_are_flat_for_tracking():
    params = load_sft_config(ROOT / "configs/sft/smoke_cpu.yaml").params()
    assert params["lora_r"] == 8 and params["base_model"].startswith("Qwen")
    assert all(not isinstance(v, dict) for v in params.values())


def test_prompt_completion_split():
    record = to_prompt_completion(example())
    assert [m["role"] for m in record["prompt"]] == ["system", "user"]
    assert [m["role"] for m in record["completion"]] == ["assistant"]


def test_token_length_and_filtering():
    tokenizer = FakeTokenizer()
    examples = [example(10, 5), example(100, 50)]
    lengths = [token_length(e, tokenizer) for e in examples]
    assert lengths == [1 + 10 + 5, 1 + 100 + 50]
    kept, dropped = keep_within(examples, lengths, 50)
    assert kept == examples[:1] and dropped == 1


def test_length_stats():
    stats = length_stats([10, 20, 30, 40, 100])
    assert stats["count"] == 5 and stats["total_tokens"] == 200 and stats["max"] == 100
    assert length_stats([]) == {"count": 0}


def test_estimate_needs_a_throughput():
    assert estimate_run(1_000_000, 2, None, None) == {"train_tokens_total": 2_000_000}
    out = estimate_run(36_000_000, 1, 10_000, 2.0)
    assert out["est_hours"] == 1.0 and out["est_cost_usd"] == 2.0


def test_measure_reports_drops_and_estimate():
    cfg = load_sft_config(ROOT / "configs/sft/smoke_cpu.yaml").model_copy(
        update={"max_seq_length": 50, "train_max_examples": None}
    )
    train = [example(10, 5), example(100, 50)]
    kept, eval_set, summary = _measure(train, [example(10, 5)], FakeTokenizer(), cfg)
    assert len(kept) == 1 and len(eval_set) == 1
    assert summary["dropped_too_long"] == 1 and summary["train_examples"] == 1


def test_training_refuses_a_dataset_that_breaks_leakage_rules():
    pack = load_pack(ROOT / "domain_packs", "legal_ca_on")
    leaky = {
        "example_id": "x#facts",
        "doc_id": "d1",
        "doc_date": "2026-01-02",
        "stage": "facts",
        "as_of": "2026-01-02",
        "split": "train",
        "case_text": "The Court of Appeal dismissed the appeal.",
        "context_docs": [],
        "messages": example()["messages"],
    }
    manifest = {"split_date": "2026-02-01"}
    with pytest.raises(RuntimeError, match="leakage"):
        _check_leakage([leaky], manifest, pack)
    clean = {**leaky, "case_text": "The accused was charged after an incident."}
    _check_leakage([clean], manifest, pack)  # no exception


def test_trusted_host_may_receive_case_text():
    url = "https://gpu.example.com/v1"
    base = Settings(_env_file=None, llm_base_url=url)
    assert is_external(url) and not is_external(url, ["gpu.example.com"])
    with pytest.raises(ConfigError, match="TRUSTED_GENERATOR_HOSTS"):
        check_generator_allowed(base)
    check_generator_allowed(
        base.model_copy(update={"trusted_generator_hosts": ["gpu.example.com"]})
    )


def test_dataset_manifest_fields_used_for_lineage_exist():
    # the fields train_sft reads from the dataset manifest must be written by build_dataset
    import inspect

    from cles.training import build_dataset

    source = inspect.getsource(build_dataset._write)
    for key in ("run_id", "pack_version", "split_date", "files"):
        assert f'"{key}"' in source
    assert json.dumps({"sha256": 1})
