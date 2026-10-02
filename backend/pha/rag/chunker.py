"""Page-aware recursive character splitting with overlap."""

from dataclasses import dataclass

SEPARATORS = ("\n\n", "\n", ". ", " ", "")


@dataclass(frozen=True)
class Chunk:
    text: str
    page: int
    index: int  # position within the document


def _split(text: str, size: int, separators: tuple[str, ...]) -> list[str]:
    """Split into pieces no longer than `size`, preferring coarse separators.

    Separators stay attached to the piece before them, so "".join(pieces) == text.
    """
    if len(text) <= size:
        return [text]
    sep, *rest = separators
    if sep == "":
        return [text[i : i + size] for i in range(0, len(text), size)]
    if sep not in text:
        return _split(text, size, tuple(rest))
    parts = text.split(sep)
    pieces = [p + sep for p in parts[:-1]] + [parts[-1]]
    out: list[str] = []
    for piece in pieces:
        out.extend([piece] if len(piece) <= size else _split(piece, size, tuple(rest)))
    return [p for p in out if p]


def split_text(text: str, size: int, overlap: int) -> list[str]:
    """Greedily merge pieces into chunks of at most `size` chars, carrying ~`overlap` chars."""
    if overlap >= size:
        raise ValueError("overlap must be smaller than size")
    chunks: list[str] = []
    window: list[str] = []
    length = 0
    for piece in _split(text, size, SEPARATORS):
        if window and length + len(piece) > size:
            chunks.append("".join(window))
            # Keep trailing pieces (up to `overlap` chars) as the start of the next chunk.
            while window and (length > overlap or length + len(piece) > size):
                length -= len(window.pop(0))
        window.append(piece)
        length += len(piece)
    if window:
        chunks.append("".join(window))
    return [c.strip() for c in chunks if c.strip()]


def chunk_pages(pages: list[tuple[int, str]], size: int, overlap: int) -> list[Chunk]:
    """Chunk each page independently so no chunk spans a page boundary."""
    chunks: list[Chunk] = []
    for page, text in pages:
        for piece in split_text(text, size, overlap):
            chunks.append(Chunk(text=piece, page=page, index=len(chunks)))
    return chunks
