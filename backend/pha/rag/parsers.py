"""Text extraction that preserves page numbers where the format has them."""

import io
from dataclasses import dataclass

from docx import Document as DocxDocument
from pypdf import PdfReader

# A PDF with less extractable text than this (per page, on average) is treated as scanned.
MIN_CHARS_PER_PAGE = 20


class ParseError(Exception):
    """The file could not be read as the format its extension claims."""


@dataclass(frozen=True)
class ParsedDocument:
    pages: list[tuple[int, str]]  # (1-based page number, text)
    page_count: int
    needs_ocr: bool = False


def _parse_pdf(data: bytes) -> ParsedDocument:
    try:
        reader = PdfReader(io.BytesIO(data))
        pages = [(i, page.extract_text() or "") for i, page in enumerate(reader.pages, start=1)]
    except Exception as e:  # pypdf raises many exception types for malformed files
        raise ParseError(f"Could not read PDF: {e}") from e
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
