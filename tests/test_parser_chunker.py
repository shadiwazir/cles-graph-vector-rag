from pathlib import Path

import pytest

from cles.domain.pack import load_pack
from cles.ingestion.chunker import build_chunks, count_tokens
from cles.ingestion.parser import ParseError, parse_pdf, parse_text

ROOT = Path(__file__).parent.parent
CFG = load_pack(ROOT / "domain_packs", "legal_ca_on").sections

SAMPLE = """COURT OF APPEAL FOR ONTARIO
CITATION: R. v. Example, 2026 ONCA 999
DATE: 20261001
Smith J.A.:
A.
INTRODUCTION
[1]
The appellant appeals his conviction.
Page:  2
[2]
He raises one ground.
B. FACTS
[3] The events happened in 2024.
Released: October 1, 2026
“Smith J.A.”
"""


def parse(text=SAMPLE):
    return parse_text(text, "2026 ONCA 999", "x.pdf", "h", CFG)


def test_metadata_and_header():
    doc = parse()
    assert doc.title == "R. v. Example"
    assert str(doc.doc_date) == "2026-10-01"
    assert "CITATION" in doc.header


def test_paragraph_numbers_noise_and_sections():
    doc = parse()
    assert [p.number for p in doc.paragraphs] == [1, 2, 3]
    assert [p.section_type for p in doc.paragraphs] == ["introduction", "introduction", "facts"]
    all_text = " ".join(p.text for p in doc.paragraphs)
    assert "Page:" not in all_text and "Released" not in all_text and "J.A." not in all_text


def test_document_without_markers_falls_back_to_blocks():
    doc = parse(
        "CITATION: X, 2026 ONCA 1\n\n"
        + "First block of text. " * 20
        + "\n\n"
        + "Second block. " * 20
    )
    assert len(doc.paragraphs) >= 2 and doc.paragraphs[0].number is None


def test_empty_text_is_an_error():
    with pytest.raises(ParseError):
        parse("   \n ")


def test_children_respect_limit_and_keep_paragraph_numbers():
    paragraphs = "\n".join(f"[{i}]\n" + "word " * 120 for i in range(1, 9))
    doc = parse("CITATION: X, 2026 ONCA 1\n" + paragraphs)
    chunks = build_chunks(doc, max_tokens=400)
    children = [c for c in chunks if c.level == "child"]
    parents = [c for c in chunks if c.level == "parent"]
    assert len(parents) == 1 and len(children) > 1
    assert all(c.token_count <= 400 for c in children)
    assert all(c.parent_chunk_id == parents[0].chunk_id for c in children)
    assert children[0].para_start == 1 and children[-1].para_end == 8


def test_overlong_paragraph_is_split():
    doc = parse("CITATION: X, 2026 ONCA 1\n[1]\n" + "A sentence of several words. " * 200)
    children = [c for c in build_chunks(doc, max_tokens=100) if c.level == "child"]
    assert len(children) > 3 and all(c.token_count <= 100 for c in children)


def test_chunk_ids_are_deterministic():
    a = [c.chunk_id for c in build_chunks(parse())]
    b = [c.chunk_id for c in build_chunks(parse())]
    assert a == b


def test_count_tokens_grows_with_text():
    assert count_tokens("one two three") < count_tokens("one two three four five six")


SAMPLE_PDFS = sorted((ROOT / "data").glob("*.pdf"))


@pytest.mark.skipif(not SAMPLE_PDFS, reason="sample PDFs not present (run `dvc pull`)")
@pytest.mark.parametrize("pdf", SAMPLE_PDFS, ids=lambda p: p.stem)
def test_sample_pdfs_parse_and_chunk(pdf):
    doc = parse_pdf(pdf, CFG)
    assert doc.doc_date is not None and doc.title != doc.doc_id
    children = [c for c in build_chunks(doc) if c.level == "child"]
    assert children and all(c.token_count <= 400 for c in children)
