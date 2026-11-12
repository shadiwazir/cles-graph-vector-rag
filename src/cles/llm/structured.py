"""Ask an LLM for a JSON object, validate it, and retry with the reasons when it is wrong."""

import json
from collections.abc import Callable
from dataclasses import dataclass

from jsonschema import Draft202012Validator

from cles.llm.base import LLMClient


@dataclass(frozen=True)
class StructuredResult:
    status: str  # "ok", "invalid" (never matched the rules) or "failed" (call error)
    result: dict
    input_tokens: int
    output_tokens: int
    error: str | None = None


def ask_for_json(
    client: LLMClient,
    messages: list[dict[str, str]],
    schema: dict,
    attempts: int = 3,
    prepare: Callable[[dict], dict] | None = None,
    extra_check: Callable[[dict], list[str]] | None = None,
) -> StructuredResult:
    """`prepare` cleans a parsed object before validation; `extra_check` returns further
    problems (as messages) for rules JSON Schema cannot express."""
    validator = Draft202012Validator(schema)
    tokens_in = tokens_out = 0
    problem = "no attempt made"
    for _ in range(attempts):
        try:
            reply = client.complete_json(messages)
        except Exception as exc:  # provider errors are reported, not raised
            return StructuredResult("failed", {}, tokens_in, tokens_out, str(exc))
        tokens_in += reply.input_tokens
        tokens_out += reply.output_tokens
        try:
            result = json.loads(reply.text)
        except json.JSONDecodeError as exc:
            problem = f"reply is not valid JSON: {exc}"
        else:
            if prepare and isinstance(result, dict):
                result = prepare(result)
            errors = sorted(validator.iter_errors(result), key=lambda e: list(e.path))
            if errors:
                problem = "; ".join(
                    f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message}" for e in errors[:5]
                )
            elif extra := (extra_check(result) if extra_check else []):
                problem = "; ".join(extra)
            else:
                return StructuredResult("ok", result, tokens_in, tokens_out)
        messages = [
            *messages,
            {"role": "assistant", "content": reply.text},
            {
                "role": "user",
                "content": f"That JSON was rejected: {problem}. Return a corrected JSON object.",
            },
        ]
    return StructuredResult("invalid", {}, tokens_in, tokens_out, problem)
