import asyncio
import os

import pytest

from pha.chat.orchestrator import ChatOrchestrator, Event, source_items
from pha.llm.base import ChatMessage, GenerationOptions, LlmUnavailable
from pha.llm.fake import FakeLLM
from pha.rag.store import StoredHit
from pha.safety.messages import DISCLAIMER
from tests.rag_helpers import make_service

OPTIONS = GenerationOptions(num_ctx=4096, num_predict=768, temperature=0.2)


async def collect(orchestrator, message, history=()) -> list[Event]:
    return [e async for e in orchestrator.run(message, list(history))]


@pytest.fixture
def docs(tmp_path):
    svc = make_service(tmp_path)
    svc.ingest("labs.txt", None, b"Lipid panel. LDL cholesterol 162 mg/dL HIGH. HDL 48 mg/dL.")
    return svc


async def test_grounded_answer_event_sequence_and_citations(docs):
    llm = FakeLLM("Your LDL cholesterol was 162 mg/dL [1].")
    events = await collect(
        ChatOrchestrator(llm, docs.retriever, "BASE", OPTIONS), "is my LDL cholesterol high?"
    )
    names = [e.name for e in events]
    assert names[0] == "meta" and names[-2:] == ["sources", "done"]
    assert set(names[1:-2]) == {"token"}
    assert events[0].data == {"emergency": False, "retrieved_count": 1, "model": "fake"}
    assert (
        "".join(e.data["text"] for e in events if e.name == "token")
        == "Your LDL cholesterol was 162 mg/dL [1]."
    )
    (src,) = events[-2].data["items"]
    assert (
        src["n"] == 1
        and src["filename"] == "labs.txt"
        and src["page"] == 1
        and src["cited"] is True
    )
    assert events[-1].data["disclaimer"] == DISCLAIMER
    system = llm.calls[0][0][0].content
    assert system.startswith("BASE") and "[1] (labs.txt, p.1)" in system


async def test_uncited_sources_marked_false(docs):
    llm = FakeLLM("Cholesterol is a fat-like substance.")
    events = await collect(
        ChatOrchestrator(llm, docs.retriever, "BASE", OPTIONS), "LDL cholesterol"
    )
    assert all(not s["cited"] for s in events[-2].data["items"])


async def test_no_documents_path(tmp_path):
    llm = FakeLLM("General info.")
    events = await collect(ChatOrchestrator(llm, None, "BASE", OPTIONS), "how do vaccines work?")
    assert events[0].data["retrieved_count"] == 0
    assert events[-2].data == {"items": []}
    assert "No relevant excerpts" in llm.calls[0][0][0].content


async def test_emergency_short_circuits_model_and_retrieval(docs):
    llm = FakeLLM()
    events = await collect(
        ChatOrchestrator(llm, docs.retriever, "BASE", OPTIONS), "I want to end my life"
    )
    assert llm.calls == []
    assert events[0].data["emergency"] is True and events[0].data["category"] == "self_harm"
    assert "988" in "".join(e.data["text"] for e in events if e.name == "token")
    assert [e.name for e in events][-2:] == ["sources", "done"]


async def test_history_passed_to_model(docs):
    llm = FakeLLM("HDL was 48 mg/dL [1].")
    history = [ChatMessage("user", "what is my LDL?"), ChatMessage("assistant", "162 mg/dL [1].")]
    await collect(
        ChatOrchestrator(llm, docs.retriever, "BASE", OPTIONS), "what about my HDL?", history
    )
    sent = llm.calls[0][0]
    assert sent[1:3] == history and sent[-1] == ChatMessage("user", "what about my HDL?")


async def test_llm_unavailable_emits_error_event():
    llm = FakeLLM(error=LlmUnavailable("Cannot reach Ollama."))
    events = await collect(ChatOrchestrator(llm, None, "BASE", OPTIONS), "hello")
    assert [e.name for e in events] == ["meta", "error"]
    assert events[-1].data == {"code": "llm_unavailable", "message": "Cannot reach Ollama."}


async def test_mid_stream_failure_emits_error_after_partial_tokens():
    llm = FakeLLM("one two three four", fail_after=2, error=LlmUnavailable("lost connection"))
    events = await collect(ChatOrchestrator(llm, None, "BASE", OPTIONS), "hello")
    assert [e.name for e in events] == ["meta", "token", "token", "error"]


async def test_unexpected_exception_is_not_leaked():
    class Boom(FakeLLM):
        async def stream(self, messages, options, stats):
            raise RuntimeError("secret internal detail")
            yield  # pragma: no cover

    events = await collect(ChatOrchestrator(Boom(), None, "BASE", OPTIONS), "hello")
    assert events[-1].data == {"code": "llm_error", "message": "The model failed to respond."}


async def test_cancellation_stops_generation():
    llm = FakeLLM(" ".join(["word"] * 200), delay_s=0.01)
    orchestrator = ChatOrchestrator(llm, None, "BASE", OPTIONS)

    async def consume():
        async for _ in orchestrator.run("hello", []):
            pass

    task = asyncio.create_task(consume())
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert llm.cancelled


async def test_no_conversation_written_to_disk(docs, tmp_path):
    before = {p for p in tmp_path.rglob("*")}
    llm = FakeLLM("Answer [1].")
    await collect(ChatOrchestrator(llm, docs.retriever, "BASE", OPTIONS), "unique-question-xyz LDL")
    after = {p for p in tmp_path.rglob("*")}
    new_files = [p for p in after - before if p.is_file()]
    assert not any("unique-question-xyz" in p.read_text(errors="ignore") for p in new_files)
    for p in after:
        if p.is_file() and os.path.getsize(p) < 5_000_000:
            assert b"unique-question-xyz" not in p.read_bytes()


def test_snippets_are_truncated():
    long = StoredHit(
        text="x" * 1000, doc_id="d", filename="f.txt", page=1, chunk_index=0, score=0.9
    )
    (item,) = source_items([long], "")
    assert len(item["snippet"]) == 301 and item["snippet"].endswith("…")
