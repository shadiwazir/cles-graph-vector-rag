"""Leakage rules L1 to L5 (INSTRUCTIONS.md section 9.2), checked on finished examples.

These checks only read the example (and the split date), so they can be re-run on a dataset
file by anyone, independently of the builder.
"""

import re
from datetime import date

from cles.domain.pack import DomainPack


def check_example(example: dict, pack: DomainPack, split_date: date) -> list[str]:
    """Violations of L1 to L3 and L5 for one example. Empty list when clean."""
    violations = []
    user = example["messages"][1]["content"]
    as_of = date.fromisoformat(example["as_of"])

    # L1: the case text (what the lawyer knows) must not describe the decision.
    check = pack.info.leak_check
    if check:
        for pattern in check.patterns:
            if m := re.search(pattern, example["case_text"]):
                violations.append(f"L1: case text mentions the decision ('{m.group(0)}')")
                break

    context = example["context_docs"]
    # L2: the case itself never appears in its own context or prompt.
    if any(c["doc_id"] == example["doc_id"] for c in context) or example["doc_id"] in user:
        violations.append("L2: the case appears in its own input")
    # L3: no context document is dated on or after as_of.
    later = [c["doc_id"] for c in context if date.fromisoformat(c["doc_date"]) >= as_of]
    if later:
        violations.append(f"L3: context from {later} is not older than {as_of}")
    # L5: evaluation examples use only documents from before the split.
    if example["split"] == "eval":
        late = [c["doc_id"] for c in context if date.fromisoformat(c["doc_date"]) >= split_date]
        if late:
            violations.append(f"L5: evaluation context includes {late}, not before {split_date}")
    return violations


def check_split(examples: list[dict]) -> list[str]:
    """L4: every training document is strictly older than every evaluation document."""
    train = [date.fromisoformat(e["doc_date"]) for e in examples if e["split"] == "train"]
    evaluation = [date.fromisoformat(e["doc_date"]) for e in examples if e["split"] == "eval"]
    if train and evaluation and max(train) >= min(evaluation):
        return [f"L4: latest training document {max(train)} is not older than {min(evaluation)}"]
    return []
