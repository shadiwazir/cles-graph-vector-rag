"""Ask the LLM to turn one document into the pack's extraction JSON, and validate it."""

import hashlib
import json
import re
from dataclasses import dataclass

from jsonschema import Draft202012Validator

from cles.domain.pack import DomainPack
from cles.ingestion.chunker import count_tokens
from cles.llm.base import LLMClient

MAX_ATTEMPTS = 3  # first try plus two retries that show the model what was wrong


@dataclass(frozen=True)
class ExtractionOutcome:
    doc_id: str
    status: str  # "ok", "invalid" (JSON did not match the schema) or "failed" (call error)
    result: dict
    input_tokens: int
    output_tokens: int
    error: str | None = None


def schema_version(pack: DomainPack) -> str:
    """Cache key part: changes when the pack version, prompt or schema changes."""
    digest = hashlib.sha256(
        (pack.extraction_prompt + json.dumps(pack.extraction_schema, sort_keys=True)).encode()
    ).hexdigest()[:8]
    return f"{pack.info.version}-{digest}"


def build_messages(
    pack: DomainPack, header: str, text: str, known: dict | None = None
) -> list[dict[str, str]]:
    system = (
        f"{pack.extraction_prompt}\n\nReturn one JSON object that matches this JSON Schema:\n"
        f"{json.dumps(pack.extraction_schema)}"
    )
    facts = "".join(f"- {k}: {v}\n" for k, v in (known or {}).items())
    user = (
        f"KNOWN FACTS (use exactly as given):\n{facts}\n" if facts else ""
    ) + f"DOCUMENT HEADER:\n{header}\n\nDOCUMENT TEXT:\n{text}"
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def estimate_input_tokens(pack: DomainPack, header: str, text: str) -> int:
    return sum(count_tokens(m["content"]) for m in build_messages(pack, header, text))


def find_leaks(result: dict, pack: DomainPack) -> list[str]:
    """Problems where text that must describe only what was known before the decision
    mentions the decision (see `leak_check` in pack.yaml). Empty list when clean."""
    check = pack.info.leak_check
    if check is None:
        return []
    patterns = [re.compile(p) for p in check.patterns]
    problems = []
    for i, item in enumerate(result.get(check.list_field, [])):
        text = item.get(check.text_field, "") if isinstance(item, dict) else ""
        for pattern in patterns:
            if m := pattern.search(text):
                problems.append(
                    f"{check.list_field}/{i}/{check.text_field}: mentions the decision "
                    f"('{m.group(0)}'); describe only what was known before it"
                )
                break
    return problems


def tidy(value, schema: dict):
    """Forgive harmless slips before validation: drop null values and match enum values
    case-insensitively ("Appellant" -> "appellant"). Anything else is left for the validator."""
    if isinstance(value, dict):
        props = schema.get("properties", {})
        return {k: tidy(v, props.get(k, {})) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        item_schema = schema.get("items", {})
        return [tidy(v, item_schema) for v in value if v is not None]
    if isinstance(value, str) and "enum" in schema:
        for option in schema["enum"]:
            if isinstance(option, str) and option.lower() == value.strip().lower():
                return option
    return value


def known_values(pack: DomainPack, doc_id: str, title: str, doc_date) -> dict:
    """Extraction fields filled from the parsed document, per the pack's `known_fields`."""
    source = {
        "doc_id": doc_id,
        "title": title,
        "doc_date": doc_date.isoformat() if doc_date else None,
    }
    return {f: source[col] for f, col in pack.info.known_fields.items() if source[col]}


def extract_document(
    client: LLMClient,
    pack: DomainPack,
    doc_id: str,
    header: str,
    text: str,
    known: dict | None = None,
) -> ExtractionOutcome:
    validator = Draft202012Validator(pack.extraction_schema)
    messages = build_messages(pack, header, text, known)
    tokens_in = tokens_out = 0
    problem = "no attempt made"
    for _ in range(MAX_ATTEMPTS):
        try:
            reply = client.complete_json(messages)
        except Exception as exc:  # provider errors: record and let the run continue
            return ExtractionOutcome(doc_id, "failed", {}, tokens_in, tokens_out, str(exc))
        tokens_in += reply.input_tokens
        tokens_out += reply.output_tokens
        try:
            result = json.loads(reply.text)
        except json.JSONDecodeError as exc:
            problem = f"reply is not valid JSON: {exc}"
        else:
            if isinstance(result, dict):
                result = tidy(result, pack.extraction_schema)
                result.update(known or {})  # parser-known fields win over the model
            errors = sorted(validator.iter_errors(result), key=lambda e: list(e.path))
            leaks = [] if errors else find_leaks(result, pack)
            if not errors and not leaks:
                return ExtractionOutcome(doc_id, "ok", result, tokens_in, tokens_out)
            if leaks:
                problem = "; ".join(leaks)
            else:
                problem = "; ".join(
                    f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message}" for e in errors[:5]
                )
        messages = [
            *messages,
            {"role": "assistant", "content": reply.text},
            {
                "role": "user",
                "content": f"That JSON was rejected: {problem}. Return a corrected JSON object.",
            },
        ]
    return ExtractionOutcome(doc_id, "invalid", {}, tokens_in, tokens_out, problem)
