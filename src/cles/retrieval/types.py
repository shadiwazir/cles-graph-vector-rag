"""Data passed between retrieval and generation."""

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class SearchFilter:
    """Limits every search. `as_of` keeps only documents dated before it (leakage rule L3);
    `exclude_doc_ids` removes the case itself (rule L2)."""

    as_of: date | None = None
    exclude_doc_ids: tuple[str, ...] = ()


@dataclass
class Passage:
    chunk_id: str
    doc_id: str
    title: str
    para_start: int | None
    para_end: int | None
    text: str
    distance: float | None = None  # cosine distance, when the passage came from vector search
    score: float = 0.0  # fused (and possibly reranked) score
    sources: list[str] = field(default_factory=list)  # "vector", "fulltext"

    @property
    def label(self) -> str:
        if self.para_start is None:
            return self.doc_id
        paras = (
            f"{self.para_start}"
            if self.para_start == self.para_end
            else f"{self.para_start}-{self.para_end}"
        )
        return f"{self.doc_id} para {paras}"


@dataclass
class ContextPack:
    passages: list[Passage]
    graph: dict[str, list[dict]]  # template name -> rows
    evidence_strength: str  # "weak" | "moderate" | "strong"
    retrieved_doc_ids: list[str]
