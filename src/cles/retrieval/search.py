"""Passage search in Postgres: vector (pgvector) and full-text, both respecting SearchFilter."""

import re

import psycopg

from cles.retrieval.types import Passage, SearchFilter

_WORD_RE = re.compile(r"\w{3,}")

_SELECT = """SELECT c.chunk_id::text, c.doc_id, d.title, c.para_start, c.para_end, c.text{extra}
               FROM chunks c JOIN documents d USING (doc_id)
              WHERE c.level = 'child' AND {condition}
                AND (%(as_of)s::date IS NULL OR d.doc_date < %(as_of)s::date)
                AND NOT (c.doc_id = ANY(%(exclude)s))
              ORDER BY {order} LIMIT %(limit)s"""


def vector_search(
    conn: psycopg.Connection, embedding: list[float], flt: SearchFilter, limit: int
) -> list[Passage]:
    sql = _SELECT.format(
        extra=", c.embedding <=> %(vec)s::vector AS distance",
        condition="c.embedding IS NOT NULL",
        order="c.embedding <=> %(vec)s::vector",
    )
    rows = conn.execute(sql, _params(flt, limit, vec=embedding)).fetchall()
    return [Passage(*row[:6], distance=row[6], sources=["vector"]) for row in rows]


def fulltext_search(
    conn: psycopg.Connection, query: str, flt: SearchFilter, limit: int
) -> list[Passage]:
    tsquery = or_query(query)
    if not tsquery:
        return []
    sql = _SELECT.format(
        extra="",
        condition="c.tsv @@ to_tsquery('english', %(q)s)",
        order="ts_rank_cd(c.tsv, to_tsquery('english', %(q)s)) DESC",
    )
    rows = conn.execute(sql, _params(flt, limit, q=tsquery)).fetchall()
    return [Passage(*row[:6], sources=["fulltext"]) for row in rows]


def or_query(text: str) -> str:
    """Turn free text into a tsquery that matches ANY word ('a | b | c').

    A question is long, so requiring every word (plainto_tsquery) would match almost nothing.
    Only word characters are kept, so the result is safe to pass to to_tsquery.
    """
    words = dict.fromkeys(w.lower() for w in _WORD_RE.findall(text))
    return " | ".join(words)


def _params(flt: SearchFilter, limit: int, **extra) -> dict:
    return {"as_of": flt.as_of, "exclude": list(flt.exclude_doc_ids), "limit": limit, **extra}
