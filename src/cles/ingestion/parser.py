"""PDF to structured document.

Reading rules (paragraph markers, noise, headings, metadata patterns) come from the domain
pack's `sections.yaml`; nothing here is specific to one domain.
"""

import hashlib
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from cles.domain.pack import SectionConfig


class ParseError(ValueError):
    """The document could not be turned into usable text."""


@dataclass(frozen=True)
class Paragraph:
    number: int | None  # the "[n]" marker, None if the document has no markers
    section: str  # heading text, e.g. "INTRODUCTION"
    section_type: str  # mapped from the heading via the pack, e.g. "facts"
    text: str


@dataclass(frozen=True)
class ParsedDocument:
    doc_id: str
    title: str
    doc_date: date | None
    source_path: str
    content_hash: str
    header: str  # text before the first paragraph (parties, counsel, court)
    paragraphs: list[Paragraph]


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def extract_text(path: Path) -> str:
    """Plain text of all pages. Imported lazily so tests of the text logic need no PDF library."""
    import pymupdf

    with pymupdf.open(path) as pdf:
        return "\n".join(page.get_text() for page in pdf)


def parse_pdf(path: Path, cfg: SectionConfig) -> ParsedDocument:
    text = extract_text(path)
    if len(text.strip()) < 200:
        raise ParseError(f"{path.name}: almost no text (scanned PDF? needs OCR)")
    # The file name is a more reliable id than text inside the document.
    doc_id = path.stem.replace("_", " ")
    return parse_text(text, doc_id, str(path), file_hash(path), cfg)


def parse_text(
    text: str, doc_id: str, source_path: str, content_hash: str, cfg: SectionConfig
) -> ParsedDocument:
    lines = _clean_lines(text, cfg)
    marker = re.compile(cfg.paragraph_marker)
    heading = re.compile(cfg.heading_pattern) if cfg.heading_pattern else None
    title_re = re.compile(cfg.heading_title_pattern) if cfg.heading_title_pattern else None

    header_lines: list[str] = []
    paragraphs: list[Paragraph] = []
    section = "Reasons"
    number: int | None = None
    buffer: list[str] = []
    seen_marker = False

    def flush() -> None:
        body = _normalise(" ".join(buffer))
        if body:
            paragraphs.append(Paragraph(number, section, _section_type(section, cfg), body))
        buffer.clear()

    skip_next = False
    for i, line in enumerate(lines):
        if skip_next:
            skip_next = False
            continue
        m = marker.match(line)
        if m:
            flush()
            seen_marker = True
            number = int(m.group(1))
            if m.group(2):
                buffer.append(m.group(2))
        elif (
            heading
            and (h := heading.match(line))
            and (title := _heading_title(h, lines, i, title_re))
        ):
            flush()
            number = None
            section = title
            skip_next = not h.group(1)
        elif seen_marker:
            buffer.append(line)
        else:
            header_lines.append(line)
    flush()

    if not seen_marker:
        paragraphs = _paragraphs_from_blocks(text, cfg)
        header_lines = []
    if not paragraphs:
        raise ParseError(f"{doc_id}: no paragraphs found")

    header = _normalise_block(header_lines)
    return ParsedDocument(
        doc_id=doc_id,
        title=_search(cfg.metadata.title_pattern, header) or doc_id,
        doc_date=_parse_date(_search(cfg.metadata.date_pattern, header), cfg),
        source_path=source_path,
        content_hash=content_hash,
        header=header,
        paragraphs=paragraphs,
    )


def _heading_title(
    match: re.Match[str], lines: list[str], i: int, title_re: re.Pattern[str] | None
) -> str | None:
    """Title of a heading: on the same line, or on the next line when the label stands alone."""
    if match.group(1):
        return _normalise(match.group(1))
    nxt = lines[i + 1] if i + 1 < len(lines) else ""
    if title_re and title_re.match(nxt):
        return _normalise(nxt)
    return None


def _clean_lines(text: str, cfg: SectionConfig) -> list[str]:
    noise = [re.compile(p) for p in cfg.noise_lines]
    return [line for line in text.splitlines() if not any(n.match(line) for n in noise)]


def _paragraphs_from_blocks(text: str, cfg: SectionConfig) -> list[Paragraph]:
    """Fallback for documents without paragraph markers: split on blank lines."""
    clean = "\n".join(_clean_lines(text, cfg))
    blocks = (_normalise(b) for b in re.split(r"\n\s*\n", clean))
    return [Paragraph(None, "Reasons", "other", b) for b in blocks if b]


def _section_type(section: str, cfg: SectionConfig) -> str:
    lowered = section.lower()
    for section_type, words in cfg.section_keywords.items():
        if any(w in lowered for w in words):
            return section_type
    return "other"


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _normalise_block(lines: list[str]) -> str:
    return "\n".join(s for s in (_normalise(line) for line in lines) if s)


def _search(pattern: str, text: str) -> str | None:
    m = re.search(pattern, text)
    return m.group(1).strip() if m else None


def _parse_date(value: str | None, cfg: SectionConfig) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, cfg.metadata.date_format).date()
    except ValueError:
        return None
