"""Turns one user message into a stream of chat events (see specs/chat-api)."""

import asyncio
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from fastapi.concurrency import run_in_threadpool

from pha.chat.prompt import build_prompt
from pha.llm.base import ChatMessage, GenerationOptions, GenerationStats, LLMBackend, LlmError
from pha.rag.retriever import Retriever
from pha.rag.store import StoredHit
from pha.safety.emergency import detect_emergency
from pha.safety.messages import DISCLAIMER, emergency_message

CITATION = re.compile(r"\[(\d{1,2})\]")
SNIPPET_CHARS = 300


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
            chunks = await run_in_threadpool(self.retriever.search, message)

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

        # 4. Stream the answer. Cancellation (client disconnect) propagates into the backend.
        stats = GenerationStats()
        answer: list[str] = []
        try:
            async for token in self.llm.stream(prompt.messages, self.options, stats):
                answer.append(token)
                yield Event("token", {"text": token})
        except asyncio.CancelledError:
            raise
        except LlmError as e:
            yield Event("error", {"code": e.code, "message": str(e)})
            return
        except Exception:  # never leak internals to the client
            yield Event("error", {"code": "llm_error", "message": "The model failed to respond."})
            return

        # 5. Sources after the text, so the UI can link the [n] markers.
        yield Event("sources", {"items": source_items(prompt.chunks, "".join(answer))})
        usage = {
            "prompt_tokens": stats.prompt_tokens or prompt.estimated_tokens,
            "completion_tokens": stats.completion_tokens,
            "history_turns": prompt.history_turns,
            **stats.extra,
        }
        yield Event("done", {"disclaimer": DISCLAIMER, "usage": usage})
