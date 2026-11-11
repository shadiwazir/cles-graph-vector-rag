"""Needs the Compose Postgres with migrations applied; skipped otherwise."""

from datetime import date
from pathlib import Path

import psycopg
import pytest

from cles.config import ConfigError, get_settings
from cles.domain.pack import load_pack
from cles.ingestion.chunker import build_chunks
from cles.ingestion.parser import parse_text
from cles.ingestion.store import StoreResult, store_document

CFG = load_pack(Path(__file__).parent.parent / "domain_packs", "legal_ca_on").sections


@pytest.fixture
def conn():
    try:
        connection = psycopg.connect(get_settings().postgres_dsn(), connect_timeout=2)
    except (psycopg.OperationalError, ConfigError):
        pytest.skip("Postgres not available")
    yield connection
    connection.rollback()
    connection.execute("DELETE FROM documents WHERE doc_id LIKE 'TEST %'")
    connection.commit()
    connection.close()


def _doc(content_hash: str, doc_id: str = "TEST 1"):
    text = "CITATION: X, 2026 ONCA 1\nDATE: 20261001\n[1]\nSome text.\n[2]\nMore text."
    return parse_text(text, doc_id, "t.pdf", content_hash, CFG)


def test_store_is_idempotent_and_detects_changes(conn):
    doc = _doc("hash-a")
    chunks = build_chunks(doc)
    assert store_document(conn, doc, chunks, "legal_ca_on") is StoreResult.INSERTED
    assert store_document(conn, doc, chunks, "legal_ca_on") is StoreResult.UNCHANGED

    other_id = _doc("hash-a", "TEST 2")
    assert store_document(conn, other_id, build_chunks(other_id), "p") is StoreResult.DUPLICATE

    changed = _doc("hash-b")
    assert store_document(conn, changed, build_chunks(changed), "p") is StoreResult.REPLACED
    count = conn.execute("SELECT count(*) FROM chunks WHERE doc_id = 'TEST 1'").fetchone()[0]
    assert count == len(build_chunks(changed))
    row = conn.execute("SELECT doc_date FROM documents WHERE doc_id='TEST 1'").fetchone()
    assert row[0] == date(2026, 10, 1)
