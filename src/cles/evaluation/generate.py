"""Stage: generate answers to the held-out examples of the newest dataset with one system.

The system is chosen with EVAL_SYSTEM (an entry of eval/systems.yaml). Every system gets the
exact prompts stored in the dataset, so differences come from the model, not from retrieval.
Answers go to artifacts/eval/<system>/outputs.jsonl; examples already answered are skipped
(that file is the cache, so a rerun costs nothing). `--dry-run` counts and estimates, calls nothing.

The `openai` backend is paid and sends case text to a third party: public cases only (guard:
ALLOW_EXTERNAL_GENERATOR). The `hf` backend needs a GPU (Unsloth, same 4-bit load as training).
"""

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import yaml

from cles.config import ConfigError, Settings, get_settings
from cles.inference.guard import check_generator_allowed
from cles.ingestion.chunker import count_tokens
from cles.llm.base import estimate_cost
from cles.llm.openai_client import make_client
from cles.stage import StageContext, stage_main
from cles.training.check_dataset import latest_dataset

log = logging.getLogger(__name__)
EST_OUTPUT_TOKENS = 1200  # answers in the training data average about 1000 tokens


def load_eval_examples(settings: Settings) -> tuple[Path, list[dict]]:
    folder = settings.dataset_dir or latest_dataset(settings.training_out_dir)
    lines = (folder / "eval.jsonl").read_text().splitlines()
    return folder, [json.loads(line) for line in lines if line.strip()]


def load_system(settings: Settings) -> dict:
    systems = yaml.safe_load(settings.eval_systems_file.read_text())["systems"]
    if settings.eval_system not in systems:
        raise ConfigError(f"EVAL_SYSTEM '{settings.eval_system}' not in {sorted(systems)}")
    return systems[settings.eval_system]


def prompt_of(example: dict) -> list[dict]:
    """System and user messages of the example (the stored assistant message is the target)."""
    return [m for m in example["messages"] if m["role"] != "assistant"]


def read_done(path: Path) -> dict[str, dict]:
    if not path.is_file():
        return {}
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    return {r["example_id"]: r for r in rows}


def run(ctx: StageContext) -> dict:
    settings = get_settings()
    system = load_system(settings)
    folder, examples = load_eval_examples(settings)
    out_path = settings.eval_out_dir / settings.eval_system / "outputs.jsonl"
    done = read_done(out_path)
    todo = [e for e in examples if e["example_id"] not in done][: ctx.limit]
    summary = {
        "system": settings.eval_system,
        "backend": system["backend"],
        "dataset": str(folder),
        "examples": len(examples),
        "already_done": len(done),
        "to_generate": len(todo),
        "output": str(out_path),
    }
    if system["backend"] == "openai":
        tokens_in = sum(count_tokens(" ".join(m["content"] for m in prompt_of(e))) for e in todo)
        summary["est_cost_usd"] = estimate_cost(
            tokens_in,
            EST_OUTPUT_TOKENS * len(todo),
            settings.llm_price_input_per_mtok,
            settings.llm_price_output_per_mtok,
        )
    if ctx.dry_run or not todo:
        return summary

    out_path.parent.mkdir(parents=True, exist_ok=True)
    generator = (
        _openai_generator(settings)
        if system["backend"] == "openai"
        else _hf_generator(settings, system)
    )
    cost = 0.0
    with out_path.open("a") as out:
        for row in generator(todo):
            out.write(json.dumps(row) + "\n")
            out.flush()
            cost += (
                estimate_cost(
                    row["input_tokens"],
                    row["output_tokens"],
                    settings.llm_price_input_per_mtok,
                    settings.llm_price_output_per_mtok,
                )
                or 0.0
            )
    if system["backend"] == "openai":
        summary["cost_usd"] = cost
    return summary


def _openai_generator(settings: Settings):
    check_generator_allowed(settings)
    client = make_client(settings)

    def one(e: dict) -> dict:
        started = time.monotonic()
        try:
            reply = client.complete_json(prompt_of(e))
            text, tin, tout = reply.text, reply.input_tokens, reply.output_tokens
        except Exception as exc:  # recorded as an invalid answer, not a crash
            log.warning("generation failed for %s: %s", e["example_id"], exc)
            text, tin, tout = "", 0, 0
        return _row(e, text, tin, tout, started, client.model)

    def generate(examples: list[dict]):
        with ThreadPoolExecutor(max_workers=settings.llm_concurrency) as pool:
            futures = [pool.submit(one, e) for e in examples]
            for future in as_completed(futures):  # the caller writes rows from this thread
                yield future.result()

    return generate


def _hf_generator(settings: Settings, system: dict):
    """Greedy decoding with Unsloth, left-padded batches sorted by length."""

    def generate(examples: list[dict]):
        import torch
        from unsloth import FastLanguageModel  # must be imported before transformers

        name = system.get("adapter") or system["base_model"]
        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name=name, max_seq_length=12288, load_in_4bit=True
        )
        FastLanguageModel.for_inference(model)
        tokenizer.padding_side = "left"
        ordered = sorted(examples, key=lambda e: len(e["messages"][1]["content"]))
        size = settings.eval_batch_size
        for i in range(0, len(ordered), size):
            batch = ordered[i : i + size]
            texts = [
                tokenizer.apply_chat_template(
                    prompt_of(e), tokenize=False, add_generation_prompt=True, enable_thinking=False
                )
                for e in batch
            ]
            inputs = tokenizer(texts, return_tensors="pt", padding=True).to("cuda")
            started = time.monotonic()
            with torch.no_grad():
                generated = model.generate(
                    **inputs,
                    max_new_tokens=settings.eval_max_new_tokens,
                    do_sample=False,
                    pad_token_id=tokenizer.pad_token_id,
                )
            new = generated[:, inputs["input_ids"].shape[1] :]
            for e, ids in zip(batch, new, strict=True):
                n_out = int((ids != tokenizer.pad_token_id).sum())
                text = tokenizer.decode(ids, skip_special_tokens=True)
                yield _row(
                    e, text, int(inputs["attention_mask"].sum()) // len(batch), n_out, started, name
                )
            log.info("generated %d of %d", min(i + size, len(ordered)), len(ordered))

    return generate


def _row(e: dict, text: str, tin: int, tout: int, started: float, model: str) -> dict:
    return {
        "example_id": e["example_id"],
        "text": text,
        "input_tokens": tin,
        "output_tokens": tout,
        "seconds": round(time.monotonic() - started, 2),
        "model": model,
    }


if __name__ == "__main__":
    stage_main("eval_generate", run)
