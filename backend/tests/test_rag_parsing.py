import pytest

from pha.rag.chunker import chunk_pages, split_text
from pha.rag.parsers import ParseError, parse
from pha.rag.service import FileTooLarge, UnsupportedFileType, sanitize_filename, validate_upload
from tests.rag_helpers import fixture_bytes


def test_pdf_keeps_page_numbers():
    parsed = parse(fixture_bytes("lab-report.pdf"), ".pdf")
    assert parsed.page_count == 3 and not parsed.needs_ocr
    assert [p for p, _ in parsed.pages] == [1, 2, 3]
    assert "LDL cholesterol" in parsed.pages[1][1]


def test_image_only_pdf_needs_ocr():
    parsed = parse(fixture_bytes("scanned-letter.pdf"), ".pdf")
    assert parsed.needs_ocr


def test_docx_includes_table_text():
    text = parse(fixture_bytes("medication-list.docx"), ".docx").pages[0][1]
    assert "Atorvastatin | 20 mg" in text
    assert "Penicillin" in text


def test_text_and_markdown():
    assert parse(b"# Notes\nBP 120/80", ".md").pages == [(1, "# Notes\nBP 120/80")]
    assert parse("caf\xe9".encode("latin-1"), ".txt").pages[0][1] == "caf\xe9"


def test_corrupt_pdf_raises_parse_error():
    with pytest.raises(ParseError):
        parse(b"%PDF-1.4 this is not really a pdf", ".pdf")


def test_split_respects_size_and_overlap():
    text = " ".join(f"word{i}" for i in range(600))  # ~4.6k chars
    chunks = split_text(text, size=500, overlap=100)
    assert len(chunks) > 5
    assert all(len(c) <= 500 for c in chunks)
    for a, b in zip(chunks, chunks[1:], strict=False):
        assert a.split()[-1] in b  # consecutive chunks overlap


def test_split_prefers_paragraph_boundaries():
    chunks = split_text("First paragraph.\n\nSecond paragraph.", size=20, overlap=0)
    assert chunks == ["First paragraph.", "Second paragraph."]


def test_chunks_never_cross_pages():
    pages = [(1, "a " * 300), (2, "b " * 300)]
    chunks = chunk_pages(pages, size=200, overlap=40)
    assert {c.page for c in chunks} == {1, 2}
    assert all(set(c.text.split()) == {"a" if c.page == 1 else "b"} for c in chunks)
    assert [c.index for c in chunks] == list(range(len(chunks)))


def test_overlap_must_be_smaller_than_size():
    with pytest.raises(ValueError):
        split_text("x", size=100, overlap=100)


@pytest.mark.parametrize(
    ("raw", "ext", "expected"),
    [
        ("../../etc/passwd.txt", ".txt", "passwd.txt"),
        ("..\\..\\windows\\labs.pdf", ".pdf", "labs.pdf"),
        ("my labs (2026)!.PDF", ".pdf", "my labs _2026__.pdf"),
        (".pdf", ".pdf", "document.pdf"),
        ("x" * 300 + ".md", ".md", "x" * 120 + ".md"),
    ],
)
def test_sanitize_filename(raw, ext, expected):
    assert sanitize_filename(raw, ext) == expected


def test_validate_upload():
    assert validate_upload("Labs.PDF", "application/pdf", 10, 100) == ".pdf"
    assert validate_upload("notes.md", "application/octet-stream", 10, 100) == ".md"
    with pytest.raises(UnsupportedFileType):
        validate_upload("tool.exe", "application/octet-stream", 10, 100)
    with pytest.raises(UnsupportedFileType):
        validate_upload("labs.pdf", "image/png", 10, 100)
    with pytest.raises(FileTooLarge):
        validate_upload("labs.pdf", "application/pdf", 101, 100)
