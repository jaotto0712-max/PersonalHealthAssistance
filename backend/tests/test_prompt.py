from pha.chat.prompt import (
    NO_CONTEXT_INSTRUCTIONS,
    RAG_INSTRUCTIONS,
    build_prompt,
    load_system_prompt,
    without_repeated_answers,
)
from pha.config import get_settings
from pha.llm.base import ChatMessage
from pha.rag.store import StoredHit

BASE = "You are a careful health assistant."


def hit(text: str, score: float, page: int = 2, filename: str = "labs.pdf") -> StoredHit:
    return StoredHit(
        text=text, doc_id="d1", filename=filename, page=page, chunk_index=0, score=score
    )


def build(message="is my LDL high?", history=(), chunks=(), num_ctx=4096, num_predict=768):
    return build_prompt(
        BASE, message, list(history), list(chunks), num_ctx=num_ctx, num_predict=num_predict
    )


def test_grounded_prompt_numbers_excerpts_with_filename_and_page():
    p = build(chunks=[hit("LDL 162 mg/dL", 0.8)])
    system = p.messages[0]
    assert system.role == "system" and system.content.startswith(BASE)
    assert RAG_INSTRUCTIONS in system.content
    assert "[1] (labs.pdf, p.2)\nLDL 162 mg/dL" in system.content
    assert p.messages[-1] == ChatMessage("user", "is my LDL high?")


def test_no_chunks_uses_general_knowledge_instructions():
    system = build().messages[0].content
    assert NO_CONTEXT_INSTRUCTIONS in system and "User documents:" not in system


def test_excerpts_numbered_by_descending_score():
    p = build(chunks=[hit("low", 0.5), hit("high", 0.9), hit("mid", 0.7)])
    assert [c.text for c in p.chunks] == ["high", "mid", "low"]


def test_history_included_in_order():
    history = [ChatMessage("user", "what is my LDL?"), ChatMessage("assistant", "162 mg/dL [1]")]
    p = build(message="what about my HDL?", history=history)
    assert p.messages[1:3] == history and p.history_turns == 2


def test_long_history_drops_oldest_turns_first():
    history = [
        ChatMessage("user" if i % 2 == 0 else "assistant", f"turn{i} " + "x" * 600)
        for i in range(12)
    ]
    p = build(history=history, chunks=[hit("LDL 162", 0.9)])
    kept = [m.content.split()[0] for m in p.messages[1:-1]]
    assert kept and kept[-1] == "turn11"  # most recent kept
    assert "turn0" not in kept
    assert p.chunks  # top chunk always kept


def test_tight_budget_drops_low_scoring_chunks_but_keeps_top_and_message():
    chunks = [hit("A" * 2000, 0.9), hit("B" * 2000, 0.8), hit("C" * 2000, 0.7)]  # ~500 tok each
    p = build(chunks=chunks, num_ctx=1600, num_predict=400)
    assert [c.text[0] for c in p.chunks] == ["A"]
    assert p.messages[-1].content == "is my LDL high?"


def test_prompt_fits_context_window():
    history = [ChatMessage("user", "q " * 300), ChatMessage("assistant", "a " * 300)] * 5
    chunks = [hit("lab value " * 80, 0.9 - i / 10) for i in range(4)]
    p = build(history=history, chunks=chunks)
    assert p.estimated_tokens <= 4096 - 768


def test_shared_system_prompt_file_is_used_and_forbids_prescribing():
    text = load_system_prompt(get_settings().system_prompt_path)
    assert "never tell anyone to start, stop, or change a medication" in text
    assert "clinician" in text


def test_repeated_answers_are_collapsed_to_the_latest():
    copy = "I couldn't find any dietary advice related to DIEBATIC in your documents. " * 3
    history = [
        ChatMessage("user", "lower my blood pressure?"),
        ChatMessage("assistant", "Eat less salt."),
    ]
    for q in ("ok cs", "hash", "why repeat"):
        history += [
            ChatMessage("user", q),
            ChatMessage("assistant", copy + " [2]" if q == "hash" else copy),
        ]
    kept = without_repeated_answers(history)
    assert [t.content for t in kept] == [
        "lower my blood pressure?",
        "Eat less salt.",
        "why repeat",
        copy,
    ]
    assert without_repeated_answers(history[:2]) == history[:2]
