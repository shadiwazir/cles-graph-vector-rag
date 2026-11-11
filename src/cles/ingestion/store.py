"""Write parsed documents and chunks to Postgres."""

import json
from enum import Enum

import psycopg

from cles.ingestion.chunker import Chunk
from cles.ingestion.parser import ParsedDocument


class StoreResult(Enum):
    INSERTED = "inserted"
    REPLACED = "replaced"  # same doc_id, new file content
    UNCHANGED = "unchanged"  # same doc_id, same content
    DUPLICATE = "duplicate"  # same content under another doc_id


def store_document(
    conn: psycopg.Connection, doc: ParsedDocument, chunks: list[Chunk], pack_name: str
) -> StoreResult:
    """Insert one document and its chunks in a single transaction. Idempotent."""
    row = conn.execute(
        "SELECT content_hash FROM documents WHERE doc_id = %s", (doc.doc_id,)
    ).fetchone()
    if row and row[0] == doc.content_hash:
        return StoreResult.UNCHANGED
    if not row:
        other = conn.execute(
            "SELECT doc_id FROM documents WHERE content_hash = %s", (doc.content_hash,)
        ).fetchone()
        if other:
            return StoreResult.DUPLICATE

    with conn.transaction():
        if row:  # content changed: chunks cascade-delete with the document
            conn.execute("DELETE FROM documents WHERE doc_id = %s", (doc.doc_id,))
        conn.execute(
            """INSERT INTO documents
               (doc_id, title, doc_date, source_path, content_hash, domain_pack, metadata)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (
                doc.doc_id,
                doc.title,
                doc.doc_date,
                doc.source_path,
                doc.content_hash,
                pack_name,
                json.dumps({"header": doc.header, "paragraph_count": len(doc.paragraphs)}),
            ),
        )
        with conn.cursor() as cur:
            # parents first: children reference them
            ordered = sorted(chunks, key=lambda c: c.level != "parent")
            cur.executemany(
                """INSERT INTO chunks
                   (chunk_id, doc_id, parent_chunk_id, level, section_type, chunk_index,
                    para_start, para_end, token_count, text)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                [
                    (
                        c.chunk_id,
                        c.doc_id,
                        c.parent_chunk_id,
                        c.level,
                        c.section_type,
                        c.chunk_index,
                        c.para_start,
                        c.para_end,
                        c.token_count,
                        c.text,
                    )
                    for c in ordered
                ],
            )
    conn.commit()  # the SELECTs above opened a transaction, so `conn.transaction()` was a savepoint
    return StoreResult.REPLACED if row else StoreResult.INSERTED
