"""What the retrieved precedents say about an outcome, computed by code (ADR 0024).

The likelihood of a route and the order of the routes follow from the outcomes of the retrieved
decisions, not from a language model's opinion. A model that knows the outcome (the target writer)
cannot invent a confident rating, and a model that does not (the advisor at runtime) cannot
overstate one. The model explains the routes; this module sets the numbers.

Principle (fixed in advance, not fitted to any model's answers): a route's outcome is rated
- "high" when at least `min_decisions` retrieved decisions have a known outcome and all of them
  equal it (the evidence speaks with one voice),
- "medium" when at least half of the retrieved decisions with a known outcome equal it,
- "low" otherwise (including when no outcome is known).
Routes are ordered by the share of precedents behind their outcome. Ties are broken by a hash of
a seed and the outcome, so the order never depends on which route a writer happened to list first
(that would carry hindsight into the training targets).
"""

import hashlib
from collections import Counter

_LEVELS = ["low", "medium", "high"]


def precedent_share(outcome: str | None, outcomes: list[str]) -> float:
    """Share of the retrieved decisions (with a known outcome) that have this outcome."""
    known = [o for o in outcomes if o]
    return sum(o == outcome for o in known) / len(known) if known else 0.0


def precedent_level(outcome: str | None, outcomes: list[str], min_decisions: int = 2) -> str:
    """ "low", "medium" or "high" for a route that ends in `outcome` (see the module docstring)."""
    known = [o for o in outcomes if o]
    share = precedent_share(outcome, known)
    if known and share == 1.0 and len(known) >= min_decisions:
        return "high"
    return "medium" if known and share >= 0.5 else "low"


def render_precedents(outcomes: list[str]) -> str:
    """One line for the prompt: the outcomes of the retrieved decisions, most common first."""
    known = [o for o in outcomes if o]
    if not known:
        return "(no outcome known for the retrieved decisions)"
    counts = Counter(known).most_common()
    parts = ", ".join(f"{outcome}: {n}" for outcome, n in counts)
    return f"{parts} (of {len(known)} retrieved decisions)"


def _tiebreak(seed: str, outcome: str | None) -> str:
    return hashlib.sha256(f"{seed}|{outcome}".encode()).hexdigest()


def apply_evidence(
    advice: dict,
    outcomes: list[str],
    early_stages: set[str],
    min_decisions: int = 2,
    seed: str = "",
) -> list[str]:
    """Set every route's likelihood from the precedents and order the routes by the evidence.

    Late stages only: routes there name an appeal outcome; at early stages routes are procedural
    paths and the stage cap decides. Routes without an outcome keep their place after the others.
    Returns a warning per route whose likelihood changed or moved."""
    if advice.get("stage") in early_stages or not isinstance(advice.get("routes"), list):
        return []
    routes = advice["routes"]
    warnings = []
    for route in routes:
        outcome = route.get("expected_outcome")
        if not outcome:
            continue
        level = precedent_level(outcome, outcomes, min_decisions)
        if route.get("likelihood") != level:
            warnings.append(
                f"likelihood of '{route.get('name', '?')}' set to {level} from the outcomes of "
                f"the retrieved decisions (was {route.get('likelihood')})"
            )
            route["likelihood"] = level

    def order(route: dict) -> tuple:
        outcome = route.get("expected_outcome")
        if not outcome:
            return (1, 0.0, "")
        return (0, -precedent_share(outcome, outcomes), _tiebreak(seed, outcome))

    ordered = sorted(routes, key=order)
    if [id(r) for r in ordered] != [id(r) for r in routes]:
        warnings.append("routes ordered by the outcomes of the retrieved decisions")
        advice["routes"] = ordered
    return warnings
