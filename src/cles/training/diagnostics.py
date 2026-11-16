"""Dataset diagnostics that describe how well a split measures what it should (pure functions).

Two things a time-based split does not guarantee:

- Prior shift: the share of each outcome differs between training and evaluation decisions. A
  model then learns a base rate the evaluation does not have, and "better than the majority
  class" means something different on each side.
- Case families: decisions of one case (an appeal and the appeal after a retrial, companion
  appeals) must not sit on both sides of the split, or the evaluation partly repeats training.
  Shared party names are the signal; the pack lists the parties that do not identify a family.
  A candidate needs a human look (initials such as "R.G." name different people), so the
  check warns and reports, it does not fail the build.
"""

import itertools
import re
from collections import Counter


def outcome_shift(examples: list[dict]) -> dict:
    """Outcome share per split over distinct decisions, and the total variation distance
    between the two shares (0 = identical, 1 = disjoint)."""
    per_split: dict[str, dict[str, str]] = {"train": {}, "eval": {}}
    for e in examples:
        per_split[e["split"]][e["doc_id"]] = e["outcome"]
    shares = {}
    for split, decisions in per_split.items():
        counts = Counter(decisions.values())
        shares[split] = (
            {o: n / len(decisions) for o, n in sorted(counts.items())} if decisions else {}
        )
    outcomes = set(shares["train"]) | set(shares["eval"])
    distance = 0.5 * sum(
        abs(shares["train"].get(o, 0) - shares["eval"].get(o, 0)) for o in outcomes
    )
    return {
        "decisions": {s: len(d) for s, d in per_split.items()},
        "share": shares,
        "distance": round(distance, 3),
    }


def party_keys(
    parties: list[dict], ignore_kinds: list[str], ignore_patterns: list[str]
) -> set[str]:
    """Normalised names of the parties that can identify a case family."""
    skip = [re.compile(p) for p in ignore_patterns]
    keys = set()
    for party in parties or []:
        name = party.get("name", "")
        if party.get("kind") in ignore_kinds or any(p.search(name) for p in skip):
            continue
        key = re.sub(r"[^a-z0-9 ]", "", name.lower()).strip()
        if key:
            keys.add(key)
    return keys


def family_candidates(
    parties_by_doc: dict[str, set[str]], split_by_doc: dict[str, str]
) -> list[dict]:
    """Pairs of decisions on different sides of the split that share a party name."""
    found = []
    for a, b in itertools.combinations(sorted(parties_by_doc), 2):
        if split_by_doc.get(a) == split_by_doc.get(b) or not (
            split_by_doc.get(a) and split_by_doc.get(b)
        ):
            continue
        shared = parties_by_doc[a] & parties_by_doc[b]
        if shared:
            found.append({"docs": [a, b], "shared": sorted(shared)})
    return found
