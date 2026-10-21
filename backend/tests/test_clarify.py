import pytest

from pha.chat.clarify import clarification, vocabulary
from pha.chat.orchestrator import ChatOrchestrator
from pha.llm.base import GenerationOptions
from pha.llm.fake import FakeLLM

LAB = "Lipid panel. LDL cholesterol 162 mg/dL HIGH. Atorvastatin 20 mg nightly."


def test_vocabulary_is_shipped():
    known, common = vocabulary()
    assert {"cholesterol", "creatinine", "metformin", "egfr"} <= known and "cholesterol" in common


@pytest.mark.parametrize("message", ["ok cs", "ok sh", "hash", "lol", "xyz?"])
def test_short_messages_without_a_known_word_are_questioned(message):
    reply = clarification(message, [LAB])
    assert reply and f'"{" ".join(message.split())}"' in reply


@pytest.mark.parametrize(
    ("message", "suggestion"),
    [
        ("what about the diebatic", "diabetic"),
        ("colestrol", "cholesterol"),
        ("presure?", "pressure"),
    ],
)
def test_misspellings_get_a_suggestion(message, suggestion):
    assert f'Did you mean "{suggestion}"?' in clarification(message, [LAB])


@pytest.mark.parametrize(
    "message",
    [
        "LDL?", "and my LDL?", "why?", "is it bad?", "covid?", "bp ok?", "statins?", "my meds",
        "what does that mean", "tell me more", "Is that normal?", "egfr", "why repeat",
        "ozempic?",  # unknown, but long with no close spelling: maybe a drug name
        "atorvastatin?",  # not in MedQuAD, but in the user's documents
        "How can I lower my blood pressure if I also have diabetes and kidney disease?",  # long
        "ok", "hmm ok",  # nothing to question
    ],
)  # fmt: skip
def test_real_questions_are_answered(message):
    assert clarification(message, [LAB]) is None


async def test_orchestrator_asks_instead_of_calling_the_model(tmp_path):
    from tests.rag_helpers import make_service

    svc = make_service(tmp_path)
    svc.ingest("labs.txt", None, LAB.encode())
    llm = FakeLLM("This must not be generated.")
    options = GenerationOptions(num_ctx=4096, num_predict=768, temperature=0.2)
    events = [
        e async for e in ChatOrchestrator(llm, svc.retriever, "BASE", options).run("hash", [])
    ]
    assert llm.calls == [] and events[0].data["clarify"] is True
    text = "".join(e.data["text"] for e in events if e.name == "token")
    assert text.startswith("I'm not sure what you mean") and events[-2].data == {"items": []}
