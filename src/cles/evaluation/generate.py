"""Stage: generate answers to the held-out examples of the newest dataset with one system.

The system is chosen with EVAL_SYSTEM (an entry of eval/systems.yaml). Every system gets the
exact prompts stored in the dataset, so differences come from the model, not from retrieval.
Answers go to artifacts/eval/<system>/outputs.jsonl; examples already answered are skipped
(that file is the cache, so a rerun costs nothing). `--dry-run` counts and estimates, calls nothing.

The `openai` backend is paid and sends case text to a third party: public cases only (guard:
ALLOW_EXTERNAL_GENERATOR). The `hf` backend needs a GPU (Unsloth, same 4-bit load as training).
The `served` backend calls an OpenAI-compatible server you run (vLLM behind an SSH tunnel, docs/06)
with the same settings as `hf`: temperature 0, no constrained JSON, the same token limit. It runs
on the laptop, so the checks (L1-L5 data, scoring) stay local; LLM_BASE_URL and LLM_MODEL select it.
"""

import json
import logging
import re
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


_PASSAGES = re.compile(r"(RETRIEVED PASSAGES[^\n]*\n).*?(\n\nGRAPH FACTS)", re.S)
_GRAPH = re.compile(r"(GRAPH FACTS[^\n]*\n).*?(\n\n(?:PRECEDENT OUTCOMES|Retrieval found))", re.S)
_PRECEDENTS = re.compile(r"(PRECEDENT OUTCOMES[^\n]*\n).*?(\n\nRetrieval found)", re.S)


def strip_context(user_message: str) -> str:
    """The same prompt without retrieval: no passages, no graph facts, no precedent outcomes, weak
    evidence. For the baseline 'fine-tuned model without retrieval' (INSTRUCTIONS 14)."""
    text = _PASSAGES.sub(r"\1(none found)\2", user_message)
    text = _GRAPH.sub(r"\1(none)\2", text)
    text = _PRECEDENTS.sub(r"\1(no outcome known for the retrieved decisions)\2", text)
    return re.sub(r"Retrieval found \w+ evidence\.", "Retrieval found weak evidence.", text)


def prompt_of(example: dict, without_retrieval: bool = False) -> list[dict]:
    """System and user messages of the example (the stored assistant message is the target)."""
    messages = [m for m in example["messages"] if m["role"] != "assistant"]
    if without_retrieval:
        messages = [
            {**m, "content": strip_context(m["content"])} if m["role"] == "user" else m
            for m in messages
        ]
    return messages


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
    generator = {
        "openai": lambda: _openai_generator(settings, system),
        "served": lambda: _served_generator(settings, system),
        "hf": lambda: _hf_generator(settings, system),
    }[system["backend"]]()
    cost, failed = write_rows(out_path, generator(todo), settings)
    if system["backend"] in ("openai", "served"):
        summary["cost_usd"] = cost
    if failed:  # the answers that did arrive are saved; the failed ones are retried on a rerun
        raise RuntimeError(
            f"{len(failed)} of {len(todo)} requests failed and were not saved; rerun to retry "
            f"them (first error: {failed[0]['error'][:200]})"
        )
    return summary


def write_rows(out_path: Path, rows, settings: Settings) -> tuple[float, list[dict]]:
    """Append every answer to the cache file as it arrives; returns (cost, failed requests).

    A request that failed (no credit, a timeout) has no answer: it is not written, because a
    cached empty answer would be skipped on a rerun and scored as a wrong one. An answer that
    arrived but is invalid is written (that is a result)."""
    cost, failed = 0.0, []
    with out_path.open("a") as out:
        for row in rows:
            if "error" in row:
                failed.append(row)
                continue
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
    return cost, failed


def _openai_generator(settings: Settings, system: dict):
    check_generator_allowed(settings)
    client = make_client(settings)

    def one(e: dict) -> dict:
        started = time.monotonic()
        try:
            reply = client.complete_json(prompt_of(e))
            text, tin, tout = reply.text, reply.input_tokens, reply.output_tokens
        except Exception as exc:  # no answer: reported, not cached, retried on a rerun
            log.warning("generation failed for %s: %s", e["example_id"], exc)
            return {"example_id": e["example_id"], "error": str(exc)}
        return _row(e, text, tin, tout, started, client.model)

    def generate(examples: list[dict]):
        with ThreadPoolExecutor(max_workers=settings.llm_concurrency) as pool:
            futures = [pool.submit(one, e) for e in examples]
            for future in as_completed(futures):  # the caller writes rows from this thread
                yield future.result()

    return generate


def _served_generator(settings: Settings, system: dict):
    """Same decoding as the `hf` backend, through a served model (greedy, free text)."""
    from openai import OpenAI

    check_generator_allowed(settings)
    if not settings.llm_model:
        raise ConfigError("LLM_MODEL is not set (the served model name, for example cles)")
    client = OpenAI(
        api_key=settings.openai_api_key or "local",
        base_url=settings.llm_base_url,
        timeout=settings.llm_timeout_seconds,
    )

    def one(e: dict) -> dict:
        started = time.monotonic()
        try:
            reply = client.chat.completions.create(
                model=settings.llm_model,
                messages=prompt_of(e, system.get("without_retrieval", False)),
                temperature=0,
                max_tokens=settings.eval_max_new_tokens,
                extra_body=settings.llm_extra_body or None,
            )
            usage = reply.usage
            text = reply.choices[0].message.content or ""
            tin, tout = (usage.prompt_tokens, usage.completion_tokens) if usage else (0, 0)
        except Exception as exc:  # no answer: reported, not cached, retried on a rerun
            log.warning("generation failed for %s: %s", e["example_id"], exc)
            return {"example_id": e["example_id"], "error": str(exc)}
        return _row(e, text, tin, tout, started, settings.llm_model)

    def generate(examples: list[dict]):
        with ThreadPoolExecutor(max_workers=settings.llm_concurrency) as pool:
            futures = [pool.submit(one, e) for e in examples]
            for future in as_completed(futures):
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
                    prompt_of(e, system.get("without_retrieval", False)),
                    tokenize=False,
                    add_generation_prompt=True,
                    enable_thinking=False,
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
