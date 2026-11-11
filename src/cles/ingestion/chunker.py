"""Parent-child chunking.

Parent chunk = a section (consecutive paragraphs under one heading), returned as context.
Child chunk = a group of whole paragraphs of at most `max_tokens`, embedded for search.
The embedding model reads at most 512 tokens, so children stay under 400 by default.
"""

import math
import re
import uuid
from dataclasses import dataclass
from itertools import groupby

from cles.ingestion.parser import Paragraph, ParsedDocument

_NAMESPACE = uuid.UUID("6f1a1c52-3f4e-4c7e-9a3d-0c1e5f6a7b21")
_TOKEN_RE = re.compile(r"\w+|[^\w\s]")
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True)
class Chunk:
    chunk_id: uuid.UUID
    doc_id: str
    parent_chunk_id: uuid.UUID | None
    level: str  # "parent" or "child"
    section_type: str
    chunk_index: int
    para_start: int | None
    para_end: int | None
    token_count: int
    text: str


def count_tokens(text: str) -> int:
    """Cheap estimate of wordpiece tokens (about 1.3 per word or symbol)."""
    return math.ceil(len(_TOKEN_RE.findall(text)) * 1.3)


def chunk_id(doc_id: str, level: str, index: int) -> uuid.UUID:
    """Deterministic id, so re-ingesting a document produces the same ids."""
    return uuid.uuid5(_NAMESPACE, f"{doc_id}|{level}|{index}")


def build_chunks(doc: ParsedDocument, max_tokens: int = 400) -> list[Chunk]:
    parents: list[Chunk] = []
    children: list[Chunk] = []
    for parent_index, (_, group) in enumerate(groupby(doc.paragraphs, key=lambda p: p.section)):
        paras = list(group)
        parent_id = chunk_id(doc.doc_id, "parent", parent_index)
        parent_text = "\n".join(_labelled(p) for p in paras)
        parents.append(
            Chunk(
                parent_id,
                doc.doc_id,
                None,
                "parent",
                paras[0].section_type,
                parent_index,
                *_para_range(paras),
                count_tokens(parent_text),
                parent_text,
            )
        )
        for pieces in _pack_paragraphs(paras, max_tokens):
            child_index = len(children)
            text = "\n".join(text for _, text in pieces)
            numbers = [n for n, _ in pieces if n is not None]
            children.append(
                Chunk(
                    chunk_id(doc.doc_id, "child", child_index),
                    doc.doc_id,
                    parent_id,
                    "child",
                    paras[0].section_type,
                    child_index,
                    min(numbers, default=None),
                    max(numbers, default=None),
                    count_tokens(text),
                    text,
                )
            )
    return parents + children


def _labelled(p: Paragraph) -> str:
    return f"[{p.number}] {p.text}" if p.number is not None else p.text


def _para_range(paras: list[Paragraph]) -> tuple[int | None, int | None]:
    numbers = [p.number for p in paras if p.number is not None]
    return (min(numbers), max(numbers)) if numbers else (None, None)


def _pack_paragraphs(paras: list[Paragraph], max_tokens: int) -> list[list[tuple[int | None, str]]]:
    """Greedily group paragraphs into pieces of at most `max_tokens`; never split a paragraph
    unless it is longer than the limit on its own."""
    groups: list[list[tuple[int | None, str]]] = []
    current: list[tuple[int | None, str]] = []
    size = 0
    for p in paras:
        for text in _split_long(_labelled(p), max_tokens):
            tokens = count_tokens(text)
            if current and size + tokens > max_tokens:
                groups.append(current)
                current, size = [], 0
            current.append((p.number, text))
            size += tokens
    if current:
        groups.append(current)
    return groups


def _split_long(text: str, max_tokens: int) -> list[str]:
    """Split an over-long paragraph at sentence boundaries, then at words if needed."""
    if count_tokens(text) <= max_tokens:
        return [text]
    pieces: list[str] = []
    current = ""
    for sentence in _SENTENCE_RE.split(text):
        for part in _split_words(sentence, max_tokens):
            candidate = f"{current} {part}".strip()
            if current and count_tokens(candidate) > max_tokens:
                pieces.append(current)
                current = part
            else:
                current = candidate
    if current:
        pieces.append(current)
    return pieces


def _split_words(text: str, max_tokens: int) -> list[str]:
    if count_tokens(text) <= max_tokens:
        return [text]
    words = text.split()
    step = max(1, int(max_tokens / 1.3) - 1)
    return [" ".join(words[i : i + step]) for i in range(0, len(words), step)]
