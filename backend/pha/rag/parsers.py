"""Text extraction that preserves page numbers where the format has them."""

import io
from dataclasses import dataclass

from docx import Document as DocxDocument
from pypdf import PdfReader

from pha.rag.lab_tables import extract_pages, is_boilerplate

# Bump when extraction output changes: existing uploads are re-indexed at startup.
# 2: column tables; 3: older results off rows; 4: older results as history chunks;
# 5: same-name tests labelled by specimen, explicit "no reference range established"
EXTRACTOR_VERSION = 5

# A PDF with less extractable text than this (per page, on average) is treated as scanned.
MIN_CHARS_PER_PAGE = 20


class ParseError(Exception):
    """The file could not be read as the format its extension claims."""


@dataclass(frozen=True)
class ParsedDocument:
    pages: list[tuple[int, str]]  # (1-based page number, text)
    page_count: int
    needs_ocr: bool = False


def _strip_boilerplate(text: str) -> str:
    return "\n".join(line for line in text.splitlines() if not is_boilerplate(line))


def _parse_pdf(data: bytes) -> ParsedDocument:
    try:
        reader = PdfReader(io.BytesIO(data))
        plain = [page.extract_text() or "" for page in reader.pages]
    except Exception as e:  # pypdf raises many exception types for malformed files
        raise ParseError(f"Could not read PDF: {e}") from e
    # Lab tables: column-aware text where a results header is found; elsewhere keep pypdf's text.
    geometric = extract_pages(data) or []
    pages = []
    for i, text in enumerate(plain, start=1):
        current, older, has_table = geometric[i - 1] if i <= len(geometric) else ("", "", False)
        pages.append((i, current if has_table else _strip_boilerplate(text)))
        if has_table and older:  # separate block -> separate "history" chunks
            pages.append((i, older))
    count = len(pages)
    text_chars = sum(len(t.strip()) for _, t in pages)
    return ParsedDocument(
        pages=pages, page_count=count, needs_ocr=text_chars < MIN_CHARS_PER_PAGE * max(count, 1)
    )


def _parse_docx(data: bytes) -> ParsedDocument:
    try:
        doc = DocxDocument(io.BytesIO(data))
    except Exception as e:
        raise ParseError(f"Could not read DOCX: {e}") from e
    blocks = [p.text for p in doc.paragraphs]
    for table in doc.tables:
        for row in table.rows:
            blocks.append(" | ".join(cell.text.strip() for cell in row.cells))
    text = "\n".join(blocks)
    return ParsedDocument(pages=[(1, text)], page_count=1, needs_ocr=not text.strip())


def _parse_text(data: bytes) -> ParsedDocument:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = data.decode("latin-1")
    return ParsedDocument(pages=[(1, text)], page_count=1, needs_ocr=not text.strip())


PARSERS = {".pdf": _parse_pdf, ".docx": _parse_docx, ".txt": _parse_text, ".md": _parse_text}


def parse(data: bytes, extension: str) -> ParsedDocument:
    try:
        parser = PARSERS[extension.lower()]
    except KeyError:
        raise ParseError(f"Unsupported extension: {extension}") from None
    return parser(data)
