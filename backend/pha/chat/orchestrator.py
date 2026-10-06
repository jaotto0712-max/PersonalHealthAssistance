"""Turns one user message into a stream of chat events (see specs/chat-api)."""

import asyncio
import dataclasses
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from fastapi.concurrency import run_in_threadpool

from pha.chat.guard import STOPPED_NOTE, DegenerationGuard
from pha.chat.prompt import build_prompt
from pha.llm.base import ChatMessage, GenerationOptions, GenerationStats, LLMBackend, LlmError
from pha.rag.lab_tables import twin_notes
from pha.rag.retriever import Retriever
from pha.rag.store import StoredHit
from pha.safety.emergency import detect_emergency
from pha.safety.messages import DISCLAIMER, emergency_message

CITATION = re.compile(r"\[(\d{1,2})\]")
# C0/C1 control characters (except tab/newline/CR). Quantized models occasionally emit a stray
# byte such as \x9d inside a word; never forward those to the UI.
CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")
SNIPPET_CHARS = 300
PERSONAL = re.compile(
    r"\b(my|mine|am i|do i|did i|have i|should i|i have|i'm|i am)\b", re.IGNORECASE
)
NO_DOCUMENTS_NOTICE = (
    "You haven't uploaded any documents yet, so I can't see your health records. "
    "Here is general information.\n\n"
)
NOT_FOUND_NOTICE = (
    "I couldn't find information about this in your documents, so here is general information.\n\n"
)
SPECIMEN_WORDS = re.compile(r"\b(blood|serum|plasma|urine|urinary)\b", re.IGNORECASE)
# "protein to creatinine ratio", "creatinine clearance": a different test that shares the name
COMPOUND_TEST = re.compile(r"\b(ratio|clearance|index)\b|/", re.IGNORECASE)


def same_name_notice(message: str, chunks: list[StoredHit]) -> str | None:
    """The report lists this test for two specimens (blood and urine creatinine) and the question
    doesn't say which: name both. Small models answer with one value whatever the excerpt says
    (measured in add-lab-specimen-and-reference-clarity), so the app adds this itself."""
    if SPECIMEN_WORDS.search(message) or COMPOUND_TEST.search(message):
        return None
    words = set(re.findall(r"[a-z0-9/]+", message.lower()))
    for chunk in chunks:
        for base, listed in twin_notes(chunk.text):
            if set(base.split()) <= words:
                return (
                    f"\n\n_Note: your report has more than one {base} result ({listed}). "
                    "They are different tests; ask about a specific one if it matters._"
                )
    return None


@dataclass(frozen=True)
class Event:
    name: str  # meta | token | sources | done | error
    data: dict[str, Any]


def cited_numbers(answer: str) -> set[int]:
    return {int(n) for n in CITATION.findall(answer)}


def source_items(chunks: list[StoredHit], answer: str) -> list[dict[str, Any]]:
    cited = cited_numbers(answer)
    return [
        {
            "n": n,
            "doc_id": c.doc_id,
            "filename": c.filename,
            "page": c.page,
            "score": round(c.score, 4),
            "snippet": c.text if len(c.text) <= SNIPPET_CHARS else c.text[:SNIPPET_CHARS] + "…",
            "cited": n in cited,
        }
        for n, c in enumerate(chunks, start=1)
    ]


class ChatOrchestrator:
    def __init__(
        self,
        llm: LLMBackend,
        retriever: Retriever | None,
        system_prompt: str,
        options: GenerationOptions,
    ):
        self.llm = llm
        self.retriever = retriever
        self.system_prompt = system_prompt
        self.options = options

    async def run(self, message: str, history: list[ChatMessage]) -> AsyncIterator[Event]:
        # 1. Safety first: an emergency never reaches retrieval or the model.
        if match := detect_emergency(message):
            yield Event(
                "meta",
                {
                    "emergency": True,
                    "category": match.category,
                    "retrieved_count": 0,
                    "model": None,
                },
            )
            for word in re.findall(r"\S+\s*", emergency_message(match.category)):
                yield Event("token", {"text": word})
            yield Event("sources", {"items": []})
            yield Event("done", {"disclaimer": DISCLAIMER, "usage": {}})
            return

        # 2. Retrieve from the user's documents (blocking embed + query → worker thread).
        chunks: list[StoredHit] = []
        if self.retriever is not None:
            previous = next((t.content for t in reversed(history) if t.role == "user"), None)
            chunks = await run_in_threadpool(self.retriever.search, message, previous=previous)

        # 3. Build a prompt that fits the context window.
        prompt = build_prompt(
            self.system_prompt,
            message,
            history,
            chunks,
            num_ctx=self.options.num_ctx,
            num_predict=self.options.num_predict,
        )
        yield Event(
            "meta",
            {"emergency": False, "retrieved_count": len(prompt.chunks), "model": self.llm.model},
        )

        # 4. Personal question but nothing retrieved: say so ourselves (models don't reliably).
        answer: list[str] = []
        if not prompt.chunks and PERSONAL.search(message):
            has_docs = self.retriever is not None and self.retriever.has_documents()
            notice = NOT_FOUND_NOTICE if has_docs else NO_DOCUMENTS_NOTICE
            answer.append(notice)
            yield Event("token", {"text": notice})

        # 5. Stream the answer one checked sentence at a time; stop on loops or word salad.
        #    Cancellation (client disconnect, or a guard stop) propagates into the backend.
        stats = GenerationStats()
        guard = DegenerationGuard()
        # Reading values from the user's documents should be deterministic: no sampling.
        options = (
            dataclasses.replace(self.options, temperature=0.0) if prompt.chunks else self.options
        )
        stream = self.llm.stream(prompt.messages, options, stats)
        try:
            try:
                async for token in stream:
                    safe = guard.feed(CONTROL_CHARS.sub("", token))
                    if safe:
                        answer.append(safe)
                        yield Event("token", {"text": safe})
                    if guard.stopped:
                        break
            finally:
                # Close now (not at garbage collection) so a guard stop really cancels the model
                # request; for Ollama this closes the HTTP stream and generation ends.
                await stream.aclose()
            tail = guard.flush()
            if tail:
                answer.append(tail)
                yield Event("token", {"text": tail})
            if guard.stopped:
                answer.append(STOPPED_NOTE)
                yield Event("token", {"text": STOPPED_NOTE})
            if note := same_name_notice(message, prompt.chunks):
                answer.append(note)
                yield Event("token", {"text": note})
        except asyncio.CancelledError:
            raise
        except LlmError as e:
            if partial := guard.flush():  # show what was generated before the failure
                yield Event("token", {"text": partial})
            yield Event("error", {"code": e.code, "message": str(e)})
            return
        except Exception:  # never leak internals to the client
            yield Event("error", {"code": "llm_error", "message": "The model failed to respond."})
            return

        # 6. Sources after the text, so the UI can link the [n] markers.
        yield Event("sources", {"items": source_items(prompt.chunks, "".join(answer))})
        usage = {
            "prompt_tokens": stats.prompt_tokens or prompt.estimated_tokens,
            "completion_tokens": stats.completion_tokens,
            "history_turns": prompt.history_turns,
            "stopped_early": guard.stopped,
            "stop_reason": guard.reason,
            **stats.extra,
        }
        yield Event("done", {"disclaimer": DISCLAIMER, "usage": usage})
