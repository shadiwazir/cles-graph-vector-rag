"""Generate and check the training target (the ideal advice) for one example."""

import hashlib
import json
from dataclasses import dataclass

from cles.domain.pack import DomainPack
from cles.inference.calibration import cap_likelihood
from cles.inference.verifier import quote_in_paragraph
from cles.llm.base import LLMClient
from cles.llm.structured import StructuredResult, ask_for_json
from cles.retrieval.types import ContextPack, Passage
from cles.training.dataset import render_hindsight


@dataclass(frozen=True)
class TargetSpec:
    """What the target must be consistent with."""

    doc_id: str
    title: str
    outcome: str
    remedies: tuple[str, ...]
    context: ContextPack


def build_target_messages(
    pack: DomainPack, base_messages: list[dict], extraction: dict, stage_item: dict
) -> list[dict]:
    """The runtime prompt plus a hindsight block, under the target-writing system prompt."""
    system = (
        f"{pack.target_prompt}\n\nReturn one JSON object that matches this JSON Schema:\n"
        f"{json.dumps(pack.advice_schema)}"
    )
    user = f"{base_messages[1]['content']}\n\n{render_hindsight(extraction, stage_item)}"
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def input_hash(messages: list[dict]) -> str:
    return hashlib.sha256(json.dumps(messages, sort_keys=True).encode()).hexdigest()[:16]


def check_target(advice: dict, spec: TargetSpec) -> list[str]:
    """Problems that make a generated target unusable. Empty list when it is fine."""
    problems = []
    routes = advice.get("routes", [])
    if not routes:
        return ["no routes"]
    top = routes[0]
    if top.get("expected_outcome") != spec.outcome:
        problems.append(
            f"routes/0/expected_outcome must equal '{spec.outcome}' (the first route matches "
            f"what actually happened), got '{top.get('expected_outcome')}'"
        )
    if set(top.get("expected_remedies", [])) != set(spec.remedies):
        problems.append(
            f"routes/0/expected_remedies must equal {list(spec.remedies)}, "
            f"got {top.get('expected_remedies', [])}"
        )
    for i, route in enumerate(routes):
        for j, authority in enumerate(route.get("authorities", [])):
            if not _supported_by_context(authority, spec.context.passages):
                problems.append(
                    f"routes/{i}/authorities/{j}: {authority.get('case_id')} para "
                    f"{authority.get('para')} and its quote are not in the retrieved passages"
                )
    text = json.dumps(advice).casefold()
    for own in (spec.doc_id, spec.title):
        if own and own.casefold() in text:
            problems.append(f"the answer mentions this case itself ('{own}')")
    return problems


def _supported_by_context(authority: dict, passages: list[Passage]) -> bool:
    """The cited paragraph lies in a retrieved passage of that case and the quote is in it."""
    para, quote = authority.get("para"), authority.get("quote")
    if not isinstance(para, int) or not quote:
        return False
    return any(
        p.doc_id == authority.get("case_id")
        and p.para_start is not None
        and p.para_start <= para <= (p.para_end or p.para_start)
        and quote_in_paragraph(quote, p.text)
        for p in passages
    )


def generate_target(
    client: LLMClient, messages: list[dict], pack: DomainPack, spec: TargetSpec
) -> StructuredResult:
    """Ask for the target, check it against the spec (retrying with the reasons), then cap
    likelihoods by the retrieval evidence."""
    outcome = ask_for_json(
        client,
        messages,
        pack.advice_schema,
        extra_check=lambda advice: check_target(advice, spec),
    )
    if outcome.status != "ok":
        return outcome
    advice = outcome.result
    advice["evidence_strength"] = spec.context.evidence_strength
    cap_likelihood(advice, spec.context.evidence_strength)
    return StructuredResult("ok", advice, outcome.input_tokens, outcome.output_tokens)
