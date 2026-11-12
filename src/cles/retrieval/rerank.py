"""Optional cross-encoder reranking of the fused candidates."""

from typing import Protocol

from cles.retrieval.types import Passage


class Reranker(Protocol):
    def rerank(self, query: str, passages: list[Passage]) -> list[Passage]: ...


class CrossEncoderReranker:
    """Scores (query, passage) pairs with a cross-encoder. Needs `uv sync --extra embed`."""

    def __init__(self, model_name: str, device: str = "cpu"):
        from sentence_transformers import CrossEncoder

        self._model = CrossEncoder(model_name, device=device)

    def rerank(self, query: str, passages: list[Passage]) -> list[Passage]:
        if not passages:
            return passages
        scores = self._model.predict([(query, p.text) for p in passages])
        for passage, score in zip(passages, scores, strict=True):
            passage.score = float(score)
        return sorted(passages, key=lambda p: p.score, reverse=True)
