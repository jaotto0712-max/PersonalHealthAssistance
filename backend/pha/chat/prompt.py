"""Prompt construction within Phi-3-mini's 4k context window.

Layout (retrieved context goes in the system turn so the user turn matches training):
    system:    shared persona (training/system_prompt.txt) + retrieval instructions + excerpts
    history:   most recent turns that fit
    user:      the current message
"""

import math
from dataclasses import dataclass
from pathlib import Path

from pha.llm.base import ChatMessage
from pha.rag.store import StoredHit

RAG_INSTRUCTIONS = """\
The user's own documents are provided below as numbered excerpts. Use them when they are relevant to the question, and cite every excerpt you use with its number in square brackets, like [1]. Only state values from the user's records that appear in the excerpts; never guess or invent them. If the excerpts do not contain the answer, say that you could not find it in their documents, then answer from general health knowledge."""  # noqa: E501

NO_CONTEXT_INSTRUCTIONS = """\
No relevant excerpts were found in the user's uploaded documents. If the question is about their personal records or results, say you could not find that information in their documents. Answer from general health knowledge and do not use citation markers."""  # noqa: E501

CONTEXT_TOKEN_CAP = 1600
HISTORY_TOKEN_CAP = 900
SAFETY_MARGIN = 64  # template tokens and estimation error


def estimate_tokens(text: str) -> int:
    """~4 characters per token for English; deliberately conservative (rounds up)."""
    return math.ceil(len(text) / 4) + 4  # + per-message template overhead


def load_system_prompt(path: Path) -> str:
    return path.read_text().strip()


def format_excerpts(chunks: list[StoredHit]) -> str:
    lines = ["User documents:"]
    for n, c in enumerate(chunks, start=1):
        lines.append(f"[{n}] ({c.filename}, p.{c.page})\n{c.text}")
    return "\n\n".join(lines)


@dataclass(frozen=True)
class BuiltPrompt:
    messages: list[ChatMessage]
    chunks: list[StoredHit]  # chunks actually included; citation [n] = chunks[n-1]
    history_turns: int  # how many history turns were included
    estimated_tokens: int


def _system(base: str, chunks: list[StoredHit]) -> str:
    if chunks:
        return f"{base}\n\n{RAG_INSTRUCTIONS}\n\n{format_excerpts(chunks)}"
    return f"{base}\n\n{NO_CONTEXT_INSTRUCTIONS}"


def build_prompt(
    base_system: str,
    message: str,
    history: list[ChatMessage],
    chunks: list[StoredHit],
    *,
    num_ctx: int,
    num_predict: int,
) -> BuiltPrompt:
    """Fit system + excerpts + history + message into num_ctx - num_predict tokens.

    Trimming order: oldest history first, then lowest-scoring excerpts. The current message
    and the top-scoring excerpt are always kept.
    """
    budget = num_ctx - num_predict - SAFETY_MARGIN
    chunks = sorted(chunks, key=lambda c: c.score, reverse=True)
    while len(chunks) > 1 and estimate_tokens(format_excerpts(chunks)) > CONTEXT_TOKEN_CAP:
        chunks = chunks[:-1]
    turns = list(history)
    while turns and sum(estimate_tokens(t.content) for t in turns) > HISTORY_TOKEN_CAP:
        turns = turns[1:]

    def total() -> int:
        return (
            estimate_tokens(_system(base_system, chunks))
            + sum(estimate_tokens(t.content) for t in turns)
            + estimate_tokens(message)
        )

    while total() > budget and turns:
        turns = turns[1:]
    while total() > budget and len(chunks) > 1:
        chunks = chunks[:-1]

    messages = [
        ChatMessage("system", _system(base_system, chunks)),
        *turns,
        ChatMessage("user", message),
    ]
    return BuiltPrompt(messages, chunks, len(turns), total())
