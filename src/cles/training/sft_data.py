"""Turn dataset files into trainer records and measure their length in tokens."""

import json
import statistics
from pathlib import Path


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def to_prompt_completion(example: dict) -> dict:
    """Prompt-completion format: the trainer learns from the completion (the advice) only."""
    system, user, assistant = example["messages"]
    return {"prompt": [system, user], "completion": [assistant]}


def token_length(example: dict, tokenizer, enable_thinking: bool = False) -> int:
    """Length of the whole conversation after the model's chat template."""
    text = tokenizer.apply_chat_template(
        example["messages"], tokenize=False, enable_thinking=enable_thinking
    )
    return len(tokenizer(text)["input_ids"])


def keep_within(examples: list[dict], lengths: list[int], limit: int) -> tuple[list[dict], int]:
    """Examples that fit `limit` tokens. Longer ones are dropped, never truncated: cutting an
    example would cut its answer. Returns (kept, number dropped)."""
    kept = [e for e, n in zip(examples, lengths, strict=True) if n <= limit]
    return kept, len(examples) - len(kept)


def length_stats(lengths: list[int]) -> dict:
    if not lengths:
        return {"count": 0}
    ordered = sorted(lengths)
    return {
        "count": len(lengths),
        "total_tokens": sum(lengths),
        "mean": round(statistics.mean(lengths)),
        "p90": ordered[int(0.9 * (len(ordered) - 1))],
        "max": ordered[-1],
    }


def estimate_run(
    train_tokens: int, epochs: float, tokens_per_second: float | None, price_per_hour: float | None
) -> dict:
    """Training time and cost, when a throughput is configured."""
    total = train_tokens * epochs
    if not tokens_per_second:
        return {"train_tokens_total": round(total)}
    hours = total / tokens_per_second / 3600
    out = {"train_tokens_total": round(total), "est_hours": round(hours, 1)}
    if price_per_hour:
        out["est_cost_usd"] = round(hours * price_per_hour, 2)
    return out
