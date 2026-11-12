"""Keep the stated likelihood of a route within what the retrieved evidence supports."""

_LEVELS = ["low", "medium", "high"]
_CAP = {"weak": "low", "moderate": "medium", "strong": "high"}


def cap_likelihood(advice: dict, evidence_strength: str) -> list[str]:
    """Lower any route likelihood above the cap for this evidence strength. Returns warnings."""
    cap = _CAP.get(evidence_strength, "low")
    warnings = []
    for route in advice.get("routes", []):
        current = route.get("likelihood")
        if current in _LEVELS and _LEVELS.index(current) > _LEVELS.index(cap):
            route["likelihood"] = cap
            warnings.append(
                f"likelihood of '{route.get('name', '?')}' lowered from {current} to {cap}: "
                f"evidence is {evidence_strength}"
            )
    return warnings
