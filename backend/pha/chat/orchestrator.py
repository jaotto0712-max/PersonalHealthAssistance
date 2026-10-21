"""Turns one user message into a stream of chat events (see specs/chat-api)."""

import asyncio
import dataclasses
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from fastapi.concurrency import run_in_threadpool

from pha.chat.clarify import clarification
from pha.chat.guard import DegenerationGuard
from pha.chat.prompt import COPY_CHECK_CHARS, answer_key, build_prompt
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
# Whole-message small talk. "Hi" scores ~0.54 against a lab report (the floor is 0.50, and real
# short questions such as "What was my BUN?" score as low as 0.51), so it would retrieve the
# report and the model would summarise it. Answer these directly instead.
_SMALL_TALK = {
    "greeting": r"(hi|hii+|hey|hello|hiya|howdy|good (morning|afternoon|evening)|greetings)"
    r"( there)?",
    "thanks": r"(thanks|thank you|thx|ty|thanks a lot|thank you so much|great,? thanks)",
    "bye": r"(bye|goodbye|see you|see ya|good night)",
    "how_are_you": r"(how are you|how's it going|how are you doing|what's up|sup)",
    "ack": r"(ok|okay|cool|great|got it|nice|sounds good|alright|k|stop|skip|never ?mind|"
    r"no thanks|nothing)",
}
SMALL_TALK = {
    kind: re.compile(rf"^\s*{pattern}[\s!.?,:)]*$", re.IGNORECASE)
    for kind, pattern in _SMALL_TALK.items()
}
SMALL_TALK_REPLIES = {
    "greeting": "Hi! I can answer questions about your health documents, like lab reports, "
    "medication lists and visit notes, and give general health information. "
    "What would you like to know?",
    "thanks": "You're welcome! Is there anything else you'd like to know?",
    "bye": "Take care! Your conversation is saved on this computer if you want to come back to it.",
    "how_are_you": "I'm doing well, thanks for asking! What health question can I help you with?",
    "ack": "Okay. Let me know if you have another question.",
}


def small_talk(message: str) -> str | None:
    """A fixed reply when the whole message is a greeting, thanks, goodbye or acknowledgement."""
    return next((SMALL_TALK_REPLIES[k] for k, rx in SMALL_TALK.items() if rx.match(message)), None)


# Fine-tuned models copy their previous answer word for word when the new message is vague
# ("ok cs", "why repeat"): v3 did in 4 of 8 such messages, phi3-base in 0 (2026-10-07). Distinct
# template answers differ only in a value ("eGFR was 101" vs "68"), so match exactly, not fuzzily.
def repeats_previous(start: str, history: list[ChatMessage]) -> bool:
    """The answer so far is the beginning of an earlier answer in this chat."""
    key = answer_key(start)
    if len(key) < 40:  # "Yes." alone is not a copy
        return False
    return any(answer_key(t.content).startswith(key) for t in history if t.role == "assistant")


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

        # 2. Small talk ("Hi", "thanks"): a fixed reply, no retrieval and no model call.
        if reply := small_talk(message):
            yield Event(
                "meta",
                {"emergency": False, "retrieved_count": 0, "model": None, "small_talk": True},
            )
            yield Event("token", {"text": reply})
            yield Event("sources", {"items": []})
            yield Event("done", {"disclaimer": DISCLAIMER, "usage": {}})
            return

        # 3. Retrieve from the user's documents (blocking embed + query → worker thread).
        chunks: list[StoredHit] = []
        if self.retriever is not None:
            previous = next((t.content for t in reversed(history) if t.role == "user"), None)
            chunks = await run_in_threadpool(self.retriever.search, message, previous=previous)

        # 3b. A short message with no word we know ("ok cs", "hash"): ask, don't guess.
        if reply := clarification(message, (c.text for c in chunks)):
            yield Event(
                "meta",
                {"emergency": False, "retrieved_count": 0, "model": None, "clarify": True},
            )
            yield Event("token", {"text": reply})
            yield Event("sources", {"items": []})
            yield Event("done", {"disclaimer": DISCLAIMER, "usage": {}})
            return

        # 4. Build a prompt that fits the context window.
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

        # 5. Personal question but nothing retrieved: say so ourselves (models don't reliably).
        answer: list[str] = []
        if not prompt.chunks and PERSONAL.search(message):
            has_docs = self.retriever is not None and self.retriever.has_documents()
            notice = NOT_FOUND_NOTICE if has_docs else NO_DOCUMENTS_NOTICE
            answer.append(notice)
            yield Event("token", {"text": notice})

        # 6. Stream the answer one checked sentence at a time; stop on loops or word salad.
        #    Cancellation (client disconnect, or a guard stop) propagates into the backend.
        #    The start of the answer is held back until it can be compared with earlier answers;
        #    a copy, or garbage before anything was shown, is discarded and the question asked
        #    once more without the chat history.
        stats = GenerationStats()
        guard = DegenerationGuard()
        # Reading values from the user's documents should be deterministic: no sampling.
        options = (
            dataclasses.replace(self.options, temperature=0.0) if prompt.chunks else self.options
        )
        messages = prompt.messages
        held: list[str] | None = [] if any(t.role == "assistant" for t in history) else None
        retried = False
        try:
            while True:
                copied = False
                stream = self.llm.stream(messages, options, stats)
                try:
                    async for token in stream:
                        safe = guard.feed(CONTROL_CHARS.sub("", token))
                        if safe and held is not None:
                            held.append(safe)
                            safe = ""
                            start = "".join(held)
                            if len(answer_key(start)) >= COPY_CHECK_CHARS:
                                if repeats_previous(start, history):
                                    copied = True
                                    break
                                safe, held = start, None
                        if safe:
                            answer.append(safe)
                            yield Event("token", {"text": safe})
                        if guard.stopped:
                            break
                finally:
                    # Close now (not at garbage collection) so a guard stop really cancels the
                    # model request; for Ollama this closes the HTTP stream and generation ends.
                    await stream.aclose()
                if held is not None and not copied and not guard.stopped:
                    held.append(guard.flush())  # a short answer: compare all of it
                    copied = repeats_previous("".join(held), history)
                # Garbled before anything was shown: the history can cause that too (a chat full
                # of repeated answers made v3 produce garbage on every try), so retry likewise.
                garbled = held is not None and guard.reason in ("gibberish", "word_salad")
                if not (copied or garbled) or retried:
                    break
                retried = True
                messages = build_prompt(
                    self.system_prompt,
                    message,
                    [],
                    prompt.chunks,
                    num_ctx=self.options.num_ctx,
                    num_predict=self.options.num_predict,
                ).messages
                stats, guard, held = GenerationStats(), DegenerationGuard(), None
            if held:
                answer.append(start := "".join(held))
                yield Event("token", {"text": start})
            tail = guard.flush()
            if tail:
                answer.append(tail)
                yield Event("token", {"text": tail})
            if guard.stopped:
                answer.append(guard.note)
                yield Event("token", {"text": guard.note})
            if note := same_name_notice(message, prompt.chunks):
                answer.append(note)
                yield Event("token", {"text": note})
        except asyncio.CancelledError:
            raise
        except LlmError as e:
            # show what was generated before the failure
            if partial := "".join(held or []) + guard.flush():
                yield Event("token", {"text": partial})
            yield Event("error", {"code": e.code, "message": str(e)})
            return
        except Exception:  # never leak internals to the client
            yield Event("error", {"code": "llm_error", "message": "The model failed to respond."})
            return

        # 7. Sources after the text, so the UI can link the [n] markers.
        yield Event("sources", {"items": source_items(prompt.chunks, "".join(answer))})
        usage = {
            "prompt_tokens": stats.prompt_tokens or prompt.estimated_tokens,
            "completion_tokens": stats.completion_tokens,
            "history_turns": prompt.history_turns,
            "stopped_early": guard.stopped,
            "stop_reason": guard.reason,
            "retried_without_history": retried,
            **stats.extra,
        }
        yield Event("done", {"disclaimer": DISCLAIMER, "usage": usage})
