from datetime import date

import psycopg
import pytest

from cles.config import ConfigError, get_settings
from cles.inference.verifier import (
    AFTER_AS_OF,
    MISSING_PARAGRAPH,
    OK,
    QUOTE_NOT_FOUND,
    UNKNOWN_CASE,
    CitationVerifier,
    normalise,
    paragraph_texts,
    quote_in_paragraph,
)

PARENT = (
    "[1] The appellant appeals his conviction.\n"
    "[2] He raises one ground:\nidentification.\n[3] Done."
)


def test_normalise_unifies_quotes_dashes_and_spaces():
    assert normalise("The  “fit”\nsentence — raised") == 'the "fit" sentence - raised'


def test_paragraph_texts_picks_the_numbered_paragraph():
    assert paragraph_texts(PARENT, 2) == ["He raises one ground:\nidentification.\n"]
    assert paragraph_texts(PARENT, 9) == []


def test_quote_matching_rules():
    para = "The sentencing judge erred in principle by minimizing moral blameworthiness."
    assert quote_in_paragraph("erred in principle", para)
    assert quote_in_paragraph("ERRED  in\nprinciple", para)
    assert quote_in_paragraph("sentencing judge ... moral blameworthiness", para)
    assert not quote_in_paragraph("moral blameworthiness ... sentencing judge", para)  # order
    assert not quote_in_paragraph("the judge was right", para)
    assert not quote_in_paragraph("", para)


@pytest.fixture(scope="module")
def conn():
    try:
        connection = psycopg.connect(get_settings().postgres_dsn(), connect_timeout=2)
    except (psycopg.OperationalError, ConfigError):
        pytest.skip("Postgres not available")
    if not connection.execute("SELECT count(*) FROM documents").fetchone()[0]:
        pytest.skip("sample is not ingested")
    yield connection
    connection.close()


def _real_quote(conn, doc_id="2026 ONCA 719", para=1):
    (text,) = conn.execute(
        "SELECT text FROM chunks WHERE doc_id=%s AND level='parent' AND para_start<=%s "
        "AND para_end>=%s",
        (doc_id, para, para),
    ).fetchone()
    return " ".join(paragraph_texts(text, para)[0].split()[:8])


def advice(*authorities):
    return {"routes": [{"name": "r", "authorities": list(authorities)}]}


def test_verifier_statuses(conn):
    quote = _real_quote(conn)
    good = {"case_id": "2026 ONCA 719", "para": 1, "quote": quote}
    cases = {
        OK: good,
        UNKNOWN_CASE: {**good, "case_id": "1999 ONCA 1"},
        MISSING_PARAGRAPH: {**good, "para": 9999},
        QUOTE_NOT_FOUND: {**good, "quote": "this sentence is not in the decision at all"},
    }
    verifier = CitationVerifier(conn)
    for expected, authority in cases.items():
        report = verifier.verify(advice(authority))
        assert report.checks[0].status == expected, expected
        assert (report.failed == 0) == (expected == OK)


def test_failed_authorities_are_removed_and_good_ones_marked(conn):
    quote = _real_quote(conn)
    good = {"case_id": "2026 ONCA 719", "para": 1, "quote": quote}
    bad = {"case_id": "2026 ONCA 719", "para": 1, "quote": "invented text"}
    report = CitationVerifier(conn).verify(advice(good, bad, good))
    kept = report.advice["routes"][0]["authorities"]
    assert len(kept) == 2 and all(a["verified"] for a in kept)  # duplicate kept, bad removed
    assert report.total == 2 and report.failed == 1
    assert report.warnings() and "quote_not_found" in report.warnings()[0]


def test_authority_dated_after_as_of_is_rejected(conn):
    quote = _real_quote(conn)
    report = CitationVerifier(conn).verify(
        advice({"case_id": "2026 ONCA 719", "para": 1, "quote": quote}), as_of=date(2026, 10, 8)
    )
    assert report.checks[0].status == AFTER_AS_OF
