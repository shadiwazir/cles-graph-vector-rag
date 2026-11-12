"""Deterministic citation verification (no LLM).

Every authority in an answer is checked against the corpus: the case exists and is not later
than `as_of`, the paragraph exists, and the quote appears in that paragraph. Authorities that
fail are removed from the answer and counted. Overruled authorities are kept but flagged.
"""

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date

import psycopg

from cles.retrieval.graph import GraphRetriever

OK = "ok"
UNKNOWN_CASE = "unknown_case"
AFTER_AS_OF = "after_as_of"
MISSING_PARAGRAPH = "missing_paragraph"
QUOTE_NOT_FOUND = "quote_not_found"

_PARA_SPLIT = re.compile(r"(?m)^\[(\d+)\]\s*")
_ELLIPSIS = re.compile(r"\s*(?:\.\.\.|…)\s*")
_TRANSLATE = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-"})


@dataclass(frozen=True)
class CitationCheck:
    case_id: str
    para: int | None
    status: str
    overruled_by: list[str] = field(default_factory=list)


@dataclass
class VerificationReport:
    checks: list[CitationCheck]
    total: int
    failed: int
    advice: dict  # the answer with failed authorities removed and survivors annotated

    def warnings(self) -> list[str]:
        out = [
            f"removed citation {c.case_id} para {c.para}: {c.status}"
            for c in self.checks
            if c.status != OK
        ]
        out += [
            f"{c.case_id} is overruled by {', '.join(c.overruled_by)}"
            for c in self.checks
            if c.status == OK and c.overruled_by
        ]
        return out


def normalise(text: str) -> str:
    """Casefold, unify quote and dash characters, collapse whitespace."""
    text = unicodedata.normalize("NFKC", text).translate(_TRANSLATE)
    return " ".join(text.split()).casefold()


def quote_in_paragraph(quote: str, paragraph: str) -> bool:
    """True when the quote is in the paragraph. An ellipsis splits the quote into segments
    that must all appear, in order."""
    haystack = normalise(paragraph)
    position = 0
    segments = [s for s in _ELLIPSIS.split(quote) if s.strip()]
    if not segments:
        return False
    for segment in segments:
        found = haystack.find(normalise(segment), position)
        if found < 0:
            return False
        position = found + len(normalise(segment))
    return True


def paragraph_texts(parent_text: str, para: int) -> list[str]:
    """Text of paragraph `para` inside a parent chunk written as '[n] text' lines."""
    parts = _PARA_SPLIT.split(parent_text)  # ['', '1', 'text', '2', 'text', ...]
    return [parts[i + 1] for i in range(1, len(parts) - 1, 2) if int(parts[i]) == para]


class CitationVerifier:
    def __init__(self, conn: psycopg.Connection, graph: GraphRetriever | None = None):
        self._conn = conn
        self._graph = graph

    def verify(self, advice: dict, as_of: date | None = None) -> VerificationReport:
        cache: dict[tuple, CitationCheck] = {}
        checks: list[CitationCheck] = []
        cleaned = {**advice, "routes": []}
        for route in advice.get("routes", []):
            kept = []
            for authority in route.get("authorities", []):
                key = (authority.get("case_id"), authority.get("para"), authority.get("quote"))
                if key not in cache:
                    cache[key] = self._check(authority, as_of)
                    checks.append(cache[key])
                check = cache[key]
                if check.status == OK:
                    kept.append({**authority, "verified": True, "overruled_by": check.overruled_by})
            cleaned["routes"].append({**route, "authorities": kept})
        failed = sum(c.status != OK for c in checks)
        return VerificationReport(checks, len(checks), failed, cleaned)

    def _check(self, authority: dict, as_of: date | None) -> CitationCheck:
        case_id, para, quote = (authority.get(k) for k in ("case_id", "para", "quote"))
        row = self._conn.execute(
            "SELECT doc_date FROM documents WHERE doc_id = %s", (case_id,)
        ).fetchone()
        if row is None:
            return CitationCheck(case_id, para, UNKNOWN_CASE)
        if as_of and row[0] and row[0] >= as_of:
            return CitationCheck(case_id, para, AFTER_AS_OF)
        if not isinstance(para, int) or not quote:
            return CitationCheck(case_id, para, MISSING_PARAGRAPH)
        texts = self._paragraphs(case_id, para)
        if not texts:
            return CitationCheck(case_id, para, MISSING_PARAGRAPH)
        if not any(quote_in_paragraph(quote, t) for t in texts):
            return CitationCheck(case_id, para, QUOTE_NOT_FOUND)
        return CitationCheck(case_id, para, OK, self._overruled_by(case_id, as_of))

    def _paragraphs(self, doc_id: str, para: int) -> list[str]:
        rows = self._conn.execute(
            """SELECT text FROM chunks WHERE doc_id = %s AND level = 'parent'
                  AND para_start <= %s AND para_end >= %s""",
            (doc_id, para, para),
        ).fetchall()
        return [t for (text,) in rows for t in paragraph_texts(text, para)]

    def _overruled_by(self, case_id: str, as_of: date | None) -> list[str]:
        if self._graph is None or "overruled_by" not in self._graph.templates:
            return []
        rows = self._graph.run("overruled_by", as_of, case_ids=[case_id])
        return [r["overruled_by"] for r in rows]
