"""Keep the stated likelihood of a route within what the evidence and the stage support."""

_LEVELS = ["low", "medium", "high"]
_CAP = {"weak": "low", "moderate": "medium", "strong": "high"}


def cap_likelihood(
    advice: dict, evidence_strength: str, stage_caps: dict[str, str] | None = None
) -> list[str]:
    """Lower any route likelihood above the cap. The cap is the lower of the one for this
    evidence strength and the one for the case stage (`stage_caps`, from the domain pack).
    Returns a warning per changed route."""
    cap = _CAP.get(evidence_strength, "low")
    stage_cap = (stage_caps or {}).get(advice.get("stage", ""))
    if stage_cap and _LEVELS.index(stage_cap) < _LEVELS.index(cap):
        cap, reason = stage_cap, f"the case is at the {advice['stage']} stage"
    else:
        reason = f"evidence is {evidence_strength}"
    warnings = []
    for route in advice.get("routes", []):
        current = route.get("likelihood")
        if current in _LEVELS and _LEVELS.index(current) > _LEVELS.index(cap):
            route["likelihood"] = cap
            warnings.append(
                f"likelihood of '{route.get('name', '?')}' lowered from {current} to {cap}: "
                f"{reason}"
            )
    return warnings


def apply_precedent_rule(
    advice: dict,
    context_outcomes: list[str],
    early_stages: set[str],
    min_decisions: int = 2,
) -> list[str]:
    """A route may be rated "high" only when the retrieved precedents back its outcome.

    The rule is fixed by principle, not fitted to any model's answers: "high" needs at least
    `min_decisions` retrieved decisions with a known outcome, all equal to the route's expected
    outcome (the evidence speaks with one voice). Otherwise the route is lowered to "medium".
    It applies to late stages only, where routes name an appeal result; at early stages the
    stage cap already limits the likelihood. `context_outcomes` are the outcomes of the decisions
    retrieved for this request. Returns a warning per changed route."""
    if advice.get("stage") in early_stages:
        return []
    known = [o for o in context_outcomes if o]
    warnings = []
    for route in advice.get("routes", []):
        if route.get("likelihood") != "high":
            continue
        outcome = route.get("expected_outcome")
        if len(known) >= min_decisions and all(o == outcome for o in known):
            continue
        route["likelihood"] = "medium"
        warnings.append(
            f"likelihood of '{route.get('name', '?')}' lowered from high to medium: the "
            f"retrieved decisions do not all support the outcome '{outcome}'"
        )
    return warnings
