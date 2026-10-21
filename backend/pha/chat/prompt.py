"""Prompt construction within Phi-3-mini's 4k context window.

Layout (retrieved context goes in the system turn so the user turn matches training):
    system:    shared persona (training/system_prompt.txt) + retrieval instructions + excerpts
    history:   most recent turns that fit
    user:      the current message
"""

import math
import re
from dataclasses import dataclass
from pathlib import Path

from pha.config import REPO_ROOT
from pha.llm.base import ChatMessage
from pha.rag.store import StoredHit

# Instruction text is shared with the training-data generator (training/prepare_medquad.py) so the
# fine-tuned model sees byte-identical prompts in training and in the app.
PROMPTS_DIR = REPO_ROOT / "training"
RAG_INSTRUCTIONS = (PROMPTS_DIR / "rag_instructions.txt").read_text().strip()
NO_CONTEXT_INSTRUCTIONS = (PROMPTS_DIR / "no_context_instructions.txt").read_text().strip()

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


COPY_CHECK_CHARS = 160
CITATION_MARK = re.compile(r"\[\d{1,2}\]")


def answer_key(text: str) -> str:
    """How the start of an answer is compared with earlier ones (case, spacing, [n] ignored)."""
    return " ".join(CITATION_MARK.sub("", text).lower().split())[:COPY_CHECK_CHARS]


def without_repeated_answers(history: list[ChatMessage]) -> list[ChatMessage]:
    """Drop exchanges whose answer repeats a later answer. A chat holding the same answer many
    times (copies from before the copy check existed) made v3 produce garbage on every try."""
    keep = [True] * len(history)
    seen: set[str] = set()
    for i in range(len(history) - 1, -1, -1):
        if history[i].role != "assistant":
            continue
        key = answer_key(history[i].content)
        if key in seen:
            keep[i] = False
            if i > 0 and history[i - 1].role == "user":
                keep[i - 1] = False
        seen.add(key)
    return [t for t, k in zip(history, keep, strict=True) if k]


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
    turns = without_repeated_answers(history)
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
