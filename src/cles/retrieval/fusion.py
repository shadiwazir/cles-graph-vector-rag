"""Reciprocal rank fusion: merge ranked lists without calibrating their scores."""


def rrf(rankings: list[list[str]], k: int = 60) -> dict[str, float]:
    """Each item scores the sum of 1 / (k + rank) over the lists that contain it (rank from 1)."""
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, key in enumerate(ranking, start=1):
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank)
    return scores
