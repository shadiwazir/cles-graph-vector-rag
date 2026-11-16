"""Uncertainty of an evaluation rate when the independent unit is the decision, not the example.

Every held-out decision yields several examples (one per stage), and the examples of one
decision are not independent: they share facts, parties and the outcome. Counting 48 examples
overstates the evidence; here the whole decision is resampled instead (cluster bootstrap), so
the interval reflects the number of decisions. Pure functions, deterministic for a given seed.
"""

import random

RESAMPLES = 2000
SEED = 20261116


def cluster_rate(items: list[tuple[str, bool | None]]) -> dict:
    """Pooled rate of the applicable (not None) values and the number of clusters behind it."""
    applicable = [(c, v) for c, v in items if v is not None]
    hits = sum(bool(v) for _, v in applicable)
    return {
        "n": len(applicable),
        "hits": hits,
        "rate": hits / len(applicable) if applicable else None,
        "clusters": len({c for c, _ in applicable}),
    }


def cluster_bootstrap(
    items: list[tuple[str, bool | None]],
    level: float = 0.95,
    resamples: int = RESAMPLES,
    seed: int = SEED,
) -> dict:
    """`cluster_rate` plus a percentile interval from resampling whole clusters (decisions).

    `items` are (cluster_id, value) pairs; None values (the metric does not apply) are skipped.
    The interval is None when fewer than two clusters apply, because one cluster says nothing
    about spread."""
    cell = cluster_rate(items)
    by_cluster: dict[str, list[bool]] = {}
    for cluster, value in items:
        if value is not None:
            by_cluster.setdefault(cluster, []).append(bool(value))
    cell["low"] = cell["high"] = None
    if len(by_cluster) < 2:
        return cell
    groups = list(by_cluster.values())
    rng = random.Random(seed)
    rates = []
    for _ in range(resamples):
        sample = [rng.choice(groups) for _ in groups]
        n = sum(len(g) for g in sample)
        rates.append(sum(sum(g) for g in sample) / n)
    rates.sort()
    tail = (1 - level) / 2
    cell["low"] = rates[int(tail * resamples)]
    cell["high"] = rates[min(int((1 - tail) * resamples), resamples - 1)]
    return cell
