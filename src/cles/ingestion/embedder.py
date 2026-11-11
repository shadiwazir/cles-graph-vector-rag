"""Embedding model wrapper (sentence-transformers). Install with `uv sync --extra embed`."""

import logging

from cles.config import Settings

log = logging.getLogger(__name__)

# bge models retrieve better when short queries carry this prefix; passages get none.
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


class Embedder:
    def __init__(self, model_name: str, device: str, batch_size: int = 32):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError("missing dependency: run `uv sync --extra embed`") from exc
        if device == "auto":
            import torch

            device = "cuda" if torch.cuda.is_available() else "cpu"
        log.info("loading %s on %s", model_name, device)
        self.model = SentenceTransformer(model_name, device=device)
        self.batch_size = batch_size
        self.device = device

    @classmethod
    def from_settings(cls, settings: Settings) -> "Embedder":
        return cls(
            settings.embedding_model, settings.embedding_device, settings.embedding_batch_size
        )

    def embed_passages(self, texts: list[str]) -> list[list[float]]:
        return self._encode(texts)

    def embed_query(self, text: str) -> list[float]:
        return self._encode([QUERY_PREFIX + text])[0]

    def _encode(self, texts: list[str]) -> list[list[float]]:
        vectors = self.model.encode(
            texts, batch_size=self.batch_size, normalize_embeddings=True, show_progress_bar=False
        )
        return vectors.tolist()
