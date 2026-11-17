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


@dataclass(frozen=True)
class Fold:
    """One evaluation window of the rolling-origin design (ADR 0023).

    Training uses decisions dated before `split_date`; evaluation uses decisions dated on or after
    `split_date` and before `end_date` (open-ended for the last window). Later decisions do not
    exist for this fold: they would be the future."""

    name: str
    split_date: date
    end_date: date | None


def plan_folds(docs: list[DocInfo], window: int, dev_folds: int) -> list[Fold]:
    """Rolling-origin folds over the decisions sorted by date: `dev_folds` development windows
    for comparing and tuning, then a final `test` window that is never used for a choice.

    Each window holds about `window` decisions (same-date decisions stay together, so a window
    can be a little larger). Training sets grow from fold to fold, and every training decision is
    strictly older than every evaluation decision of its fold (leakage rule L4)."""
    n = len(docs)
    windows = dev_folds + 1
    if window < 1 or dev_folds < 1:
        raise ValueError("window and dev_folds must be at least 1")
    if n < (windows + 1) * window:
        raise ValueError(
            f"{n} decisions are too few for {dev_folds} dev folds and a test window of {window}"
        )
    dates = sorted(d.doc_date for d in docs)
    starts = [dates[n - (windows - i) * window] for i in range(windows)]
    if any(a >= b for a, b in zip(starts, starts[1:], strict=False)):
        raise ValueError("the windows are too small for the number of decisions on one date")
    names = [f"dev{i + 1}" for i in range(dev_folds)] + ["test"]
    ends = [*starts[1:], None]
    return [Fold(*item) for item in zip(names, starts, ends, strict=True)]


def fold_split(docs: list[DocInfo], fold: Fold) -> dict[str, str]:
    """doc_id -> "train" | "eval" for the decisions that exist in this fold (the rest is the
    future and is left out)."""
    split: dict[str, str] = {}
    for d in docs:
        if d.doc_date < fold.split_date:
            split[d.doc_id] = "train"
        elif fold.end_date is None or d.doc_date < fold.end_date:
            split[d.doc_id] = "eval"
    return split


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
        f"- STAGE: {stage_item.get('stage')}",
        f"- outcome: {extraction.get('outcome')}",
        f"- remedies: {extraction.get('remedies', [])}",
        f"- issues: {extraction.get('issues', [])}",
        f"- legal principles: {extraction.get('principles', [])}",
        f"- provisions: {extraction.get('statute_provisions', [])}",
        f"- ACTUAL NEXT EVENT: {stage_item.get('next_steps', '')}",
    ]
    return "\n".join(lines)
