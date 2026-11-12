"""Pure logic for building training examples: time-based split, questions, hindsight text."""

import hashlib
import math
from dataclasses import dataclass
from datetime import date

from cles.domain.pack import DomainPack


@dataclass(frozen=True)
class DocInfo:
    doc_id: str
    title: str
    doc_date: date
    extraction: dict  # validated extraction result (see the pack's extraction_schema.json)


def assign_split(docs: list[DocInfo], eval_fraction: float) -> tuple[date, dict[str, str]]:
    """Time-based split (leakage rule L4): the newest documents are the evaluation set.

    The split date is the date of the k-th newest document, k = ceil(fraction * n). Every
    document dated on or after it is evaluation, every earlier one is training, so all training
    documents are strictly older than all evaluation documents.
    """
    if not docs:
        raise ValueError("no documents to split")
    ordered = sorted(docs, key=lambda d: d.doc_date, reverse=True)
    k = max(1, math.ceil(eval_fraction * len(docs)))
    split_date = ordered[k - 1].doc_date
    split = {d.doc_id: ("eval" if d.doc_date >= split_date else "train") for d in docs}
    if "train" not in split.values():
        raise ValueError(
            f"all {len(docs)} documents are dated {split_date}: no training documents remain"
        )
    return split_date, split


def pick_question(pack: DomainPack, stage: str, doc_id: str) -> str | None:
    """A question for this stage, chosen deterministically; None if the pack has none."""
    questions = pack.training.questions.get(stage)
    if not questions:
        return None
    digest = hashlib.sha256(f"{doc_id}|{stage}".encode()).digest()
    return questions[digest[0] % len(questions)]


def render_hindsight(extraction: dict, stage_item: dict) -> str:
    """What actually happened, for the target writer only. It never enters the example input."""
    lines = [
        "HINDSIGHT (what actually happened; never reveal it):",
        f"- outcome: {extraction.get('outcome')}",
        f"- remedies: {extraction.get('remedies', [])}",
        f"- issues: {extraction.get('issues', [])}",
        f"- legal principles: {extraction.get('principles', [])}",
        f"- provisions: {extraction.get('statute_provisions', [])}",
        f"- ACTUAL NEXT EVENT: {stage_item.get('next_steps', '')}",
    ]
    return "\n".join(lines)
