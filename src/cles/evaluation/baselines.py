"""Reference predictors that need no model: what the data alone says about an outcome.

A fine-tuned model is only worth its cost on outcomes if it beats these:

- `baseline_prior`: always predict the most common outcome of the training decisions.
- `baseline_precedent`: the most common outcome among the decisions that retrieval put into the
  example's context (the earlier decisions a lawyer would be shown). Ties go to the better-ranked
  decision.

Both are scored exactly like a model's top route (late stages only, against the real outcome of
the held-out decision), so they sit next to the systems in the same tables and in the acceptance
check. Pure functions plus one loader for the versioned extraction export.
"""

import json
from collections import Counter
from pathlib import Path

from cles.evaluation.statistics import cluster_bootstrap


def load_outcomes(export_file: Path, extraction_version: str | None = None) -> dict[str, str]:
    """doc_id -> outcome from the DVC-versioned extraction export (status ok rows only)."""
    outcomes: dict[str, str] = {}
    for line in export_file.read_text().splitlines():
        row = json.loads(line)
        if row["status"] != "ok":
            continue
        if extraction_version and row["schema_version"] != extraction_version:
            continue
        outcomes[row["doc_id"]] = row["result"]["outcome"]
    return outcomes


def prior_outcome(train_examples: list[dict]) -> str:
    """The most common outcome over the distinct training decisions (not over examples: a
    decision with four stages must not count four times)."""
    per_decision = {e["doc_id"]: e["outcome"] for e in train_examples}
    return Counter(per_decision.values()).most_common(1)[0][0]


def precedent_outcome(example: dict, outcomes: dict[str, str]) -> tuple[str | None, bool]:
    """(predicted outcome, unanimous) from the context decisions, in retrieval order.

    Unanimous means at least two context decisions have a known outcome and all agree: the case
    where the evidence speaks with one voice, the analogue of a model rating a route "high"."""
    ranked = [
        outcomes[c["doc_id"]] for c in example.get("context_docs", []) if c["doc_id"] in outcomes
    ]
    if not ranked:
        return None, False
    counts = Counter(ranked)
    best = max(counts.values())
    predicted = next(o for o in ranked if counts[o] == best)  # tie: the better-ranked one
    return predicted, len(ranked) >= 2 and len(counts) == 1


def baseline_rows(
    examples: list[dict],
    outcomes: dict[str, str],
    prior: str,
    early_stages: set[str],
) -> dict[str, list[dict]]:
    """Per-example rows of both baselines, shaped like the model rows the scorer aggregates
    (`top_outcome_ok` is None where routes are procedural, as for the models)."""
    rows: dict[str, list[dict]] = {"baseline_prior": [], "baseline_precedent": []}
    for e in examples:
        late = e["stage"] not in early_stages
        base = {"example_id": e["example_id"], "doc_id": e["doc_id"], "stage": e["stage"]}
        base |= {"outcome": e["outcome"]}
        predicted, unanimous = precedent_outcome(e, outcomes)
        rows["baseline_prior"].append(
            base
            | {"top_outcome": prior, "top_outcome_ok": (prior == e["outcome"]) if late else None}
        )
        rows["baseline_precedent"].append(
            base
            | {
                "top_outcome": predicted,
                "top_outcome_ok": (predicted == e["outcome"]) if late else None,
                "unanimous": unanimous,
            }
        )
    return rows


def summarize(rows: list[dict]) -> dict:
    """Headline cells of one baseline: rate with decision-level interval; for the precedent
    baseline also the rate when the precedents are unanimous."""
    items = [(r["doc_id"], r["top_outcome_ok"]) for r in rows]
    cell = cluster_bootstrap(items)
    summary = {
        "examples": len(rows),
        "decisions": cell["clusters"],
        "top_outcome_ok": {k: cell[k] for k in ("n", "hits", "rate")},
        "top_outcome_low": cell["low"],
        "top_outcome_high": cell["high"],
    }
    if rows and "unanimous" in rows[0]:
        sub = cluster_bootstrap(
            [(r["doc_id"], r["top_outcome_ok"] if r["unanimous"] else None) for r in rows]
        )
        summary["unanimous_ok"] = {k: sub[k] for k in ("n", "hits", "rate")}
    return summary
