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
