"""Score one model answer against the real outcome of the case (pure functions, no I/O).

Ground truth is the real disposition and remedies of the held-out decision, not the
hindsight-written training target.
"""

from collections import defaultdict

from cles.inference.calibration import cap_likelihood

MAJORITY_OUTCOME = "appeal_dismissed"  # reference: always predict the most common outcome


def score_answer(
    example: dict,
    advice: dict | None,
    schema_errors: list[str],
    early_stages: set[str],
    stage_caps: dict[str, str],
    cites_total: int = 0,
    cites_failed: int = 0,
) -> dict:
    """Per-example metrics. Outcome metrics apply to the stages where routes name an appeal
    result (`top_outcome_ok` is None for the early stages, where routes are procedural)."""
    routes = advice.get("routes") if isinstance(advice, dict) else None
    routes = routes if isinstance(routes, list) and all(isinstance(r, dict) for r in routes) else []
    late = example["stage"] not in early_stages
    truth, truth_remedies = example["outcome"], set(example.get("remedies") or [])
    top = routes[0] if routes else {}
    top_outcome = top.get("expected_outcome")
    context_ids = {c["doc_id"] for c in example.get("context_docs", [])}
    cited = [a for r in routes for a in (r.get("authorities") or []) if isinstance(a, dict)]
    over_cap = len(cap_likelihood(_copy(advice, routes), example["evidence_strength"], stage_caps))
    return {
        "example_id": example["example_id"],
        "stage": example["stage"],
        "outcome": truth,
        "parsed": advice is not None,
        "schema_valid": advice is not None and not schema_errors,
        "stage_ok": isinstance(advice, dict) and advice.get("stage") == example["stage"],
        "top_outcome": top_outcome,
        "top_outcome_ok": (top_outcome == truth) if late else None,
        "any_outcome_ok": any(r.get("expected_outcome") == truth for r in routes),
        "remedies_ok": (set(top.get("expected_remedies") or []) == truth_remedies)
        if late
        else None,
        "top_high_and_wrong": late and top.get("likelihood") == "high" and top_outcome != truth,
        "routes": len(routes),
        "cites_total": cites_total,
        "cites_failed": cites_failed,
        "cites_outside_context": sum(a.get("case_id") not in context_ids for a in cited),
        "cites_claimed": len(cited),
        "likelihood_over_cap": over_cap,
    }


def _copy(advice: dict | None, routes: list[dict]) -> dict:
    stage = advice.get("stage", "") if isinstance(advice, dict) else ""
    return {"stage": stage, "routes": [dict(r) for r in routes]}


def _rate(values: list[bool | None]) -> dict:
    """Share of True among the applicable (not None) values, with the counts."""
    applicable = [v for v in values if v is not None]
    hits = sum(bool(v) for v in applicable)
    return {
        "n": len(applicable),
        "hits": hits,
        "rate": hits / len(applicable) if applicable else None,
    }


def aggregate(rows: list[dict]) -> dict:
    """Metrics for all rows and per stage."""
    by_stage: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_stage[r["stage"]].append(r)
    return {"all": _summary(rows), **{s: _summary(v) for s, v in sorted(by_stage.items())}}


def _summary(rows: list[dict]) -> dict:
    claimed = sum(r["cites_claimed"] for r in rows)
    verified_total = sum(r["cites_total"] for r in rows)
    failed = sum(r["cites_failed"] for r in rows)
    return {
        "examples": len(rows),
        "valid_json": _rate([r["parsed"] for r in rows]),
        "valid_schema": _rate([r["schema_valid"] for r in rows]),
        "stage_ok": _rate([r["stage_ok"] for r in rows]),
        "top_outcome_ok": _rate([r["top_outcome_ok"] for r in rows]),
        "any_outcome_ok": _rate([r["any_outcome_ok"] for r in rows]),
        "remedies_ok": _rate([r["remedies_ok"] for r in rows]),
        "majority_baseline": _rate(
            [
                r["outcome"] == MAJORITY_OUTCOME if r["top_outcome_ok"] is not None else None
                for r in rows
            ]
        ),
        "high_and_wrong": sum(bool(r["top_high_and_wrong"]) for r in rows),
        "citations_claimed": claimed,
        "citations_verified": verified_total - failed,
        "citations_failed": failed,
        "citations_outside_context": sum(r["cites_outside_context"] for r in rows),
        "likelihood_over_cap": sum(r["likelihood_over_cap"] for r in rows),
    }
