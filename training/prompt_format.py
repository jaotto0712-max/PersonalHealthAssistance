"""Prompt text and excerpt formatting shared by training-data generation and the app backend.

Standard library only. backend/pha/chat/prompt.py loads the same text files, and a backend test
asserts format_excerpts() here matches the backend's byte for byte.
"""

import re
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
SYSTEM_PROMPT_PATH = HERE / "system_prompt.txt"
RAG_INSTRUCTIONS_PATH = HERE / "rag_instructions.txt"
NO_CONTEXT_INSTRUCTIONS_PATH = HERE / "no_context_instructions.txt"
CHUNK_CHARS = 800  # the app's chunk size (PHA_CHUNK_SIZE)


@dataclass(frozen=True)
class Excerpt:
    filename: str
    page: int
    text: str


def read(path: Path) -> str:
    return path.read_text().strip()


def format_excerpts(excerpts: list[Excerpt]) -> str:
    lines = ["User documents:"]
    for n, e in enumerate(excerpts, start=1):
        lines.append(f"[{n}] ({e.filename}, p.{e.page})\n{e.text}")
    return "\n\n".join(lines)


def system_with_excerpts(base: str, rag_instructions: str, excerpts: list[Excerpt]) -> str:
    return f"{base}\n\n{rag_instructions}\n\n{format_excerpts(excerpts)}"


def system_without_excerpts(base: str, no_context_instructions: str) -> str:
    return f"{base}\n\n{no_context_instructions}"


def chunk_text(text: str, size: int = CHUNK_CHARS) -> list[str]:
    """Split like the app does (paragraphs, then sentences, then words) into ≤size chunks."""
    pieces: list[str] = []
    for para in re.split(r"\n{1,}", text.strip()):
        if len(para) <= size:
            pieces.append(para)
            continue
        for sent in re.split(r"(?<=[.!?])\s+", para):
            while len(sent) > size:
                cut = sent.rfind(" ", 0, size)
                cut = cut if cut > size // 2 else size
                pieces.append(sent[:cut])
                sent = sent[cut:].lstrip()
            pieces.append(sent)
    chunks: list[str] = []
    current = ""
    for p in (p for p in pieces if p.strip()):
        joined = f"{current}\n{p}" if current else p
        if len(joined) <= size:
            current = joined
        else:
            chunks.append(current)
            current = p
    if current:
        chunks.append(current)
    return chunks
