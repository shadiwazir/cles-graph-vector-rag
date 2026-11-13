"""Read a model's raw answer as advice JSON and check it against the pack's advice schema."""

import json
import re

from jsonschema import Draft202012Validator

_THINK = re.compile(r"<think>.*?</think>", re.S)
_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$")


def parse_answer(text: str, validator: Draft202012Validator) -> tuple[dict | None, list[str]]:
    """Return (advice, schema_errors). advice is None when the text is not a JSON object.

    A single attempt, no retries: the evaluation measures what the model produces on its own.
    """
    cleaned = _FENCE.sub("", _THINK.sub("", text).strip())
    try:
        advice = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        return None, [f"not valid JSON: {exc}"]
    if not isinstance(advice, dict):
        return None, ["JSON is not an object"]
    errors = sorted(validator.iter_errors(advice), key=lambda e: list(e.path))
    return advice, [f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message}" for e in errors[:5]]
