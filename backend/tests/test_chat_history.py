import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from pha.chats.store import ChatStore, derive_title
from pha.llm.base import LlmUnavailable
from pha.llm.fake import FakeLLM
from pha.main import create_app
from tests.rag_helpers import fixture_bytes, make_service
from tests.test_chat_api import parse_sse

# ---------------------------------------------------------------- store


def test_titles_from_first_question():
    assert (
        derive_title("What does my cholesterol result mean?")
        == "What does my cholesterol result mean?"
    )
    long = "Can you explain " + "very " * 30 + "carefully what my lipid panel says?"
    title = derive_title(long)
    assert len(title) <= 61 and title.endswith("…") and " " in title


def test_store_crud_and_ordering(tmp_path):
    store = ChatStore(tmp_path / "c.db")
    a, b = store.create(), store.create()
    store.add_message(a.id, "user", "First question about LDL")
    store.add_message(b.id, "user", "Second chat")
    store.add_message(a.id, "assistant", "Answer [1].", sources=[{"n": 1, "filename": "labs.pdf"}])
    convs = store.all()
    assert [c.id for c in convs] == [a.id, b.id]  # most recently updated first
    assert convs[0].title == "First question about LDL" and convs[0].message_count == 2
    full = store.get(a.id)
    assert [m.role for m in full.messages] == ["user", "assistant"]
    assert full.messages[1].sources == [{"n": 1, "filename": "labs.pdf"}]
    assert store.rename(a.id, "Lipids") and store.get(a.id).title == "Lipids"
    assert store.delete(b.id) and store.get(b.id) is None and not store.delete(b.id)
    store.delete_all()
    assert store.all() == []


def test_history_skips_emergencies_and_errors(tmp_path):
    store = ChatStore(tmp_path / "c.db")
    c = store.create()
    store.add_message(c.id, "user", "what is my LDL?")
    store.add_message(c.id, "assistant", "162 mg/dL [1].")
    store.add_message(c.id, "user", "I have chest pain")
    store.add_message(c.id, "assistant", "Call 911.", emergency="cardiac")
    store.add_message(c.id, "assistant", "", status="error", error="Ollama down")
    assert [(m.role, m.content) for m in store.history(c.id)] == [
        ("user", "what is my LDL?"), ("assistant", "162 mg/dL [1]."), ("user", "I have chest pain"),
    ]  # fmt: skip


def test_deleted_text_is_erased_from_the_file(tmp_path):
    path = tmp_path / "c.db"
    store = ChatStore(path)
    c = store.create()
    secret = "MY-PRIVATE-DIAGNOSIS-XYZZY " * 20
    store.add_message(c.id, "user", secret)
    store.delete(c.id)
    store._db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    store.close()
    raw = b"".join(p.read_bytes() for p in tmp_path.glob("c.db*"))
    assert b"MY-PRIVATE-DIAGNOSIS-XYZZY" not in raw


def test_store_persists_across_restarts(tmp_path):
    s1 = ChatStore(tmp_path / "c.db")
    c = s1.create()
    s1.add_message(c.id, "user", "hello")
    s1.close()
    s2 = ChatStore(tmp_path / "c.db")
    assert s2.get(c.id).messages[0].content == "hello"


# ---------------------------------------------------------------- API


@pytest.fixture
def app_parts(tmp_path):
    docs = make_service(tmp_path)
    docs.ingest("lab-report.pdf", None, fixture_bytes("lab-report.pdf"))
    return docs, ChatStore(tmp_path / "chats.db")


def client_for(app_parts, llm):
    docs, store = app_parts
    return TestClient(create_app(documents=docs, llm=llm, chats=store))


def test_conversation_lifecycle_over_api(app_parts):
    with client_for(app_parts, FakeLLM("LDL was 162 mg/dL [1].")) as api:
        conv = api.post("/api/conversations").json()
        assert conv["title"] is None and conv["message_count"] == 0
        events = parse_sse(
            api.post(
                "/api/chat", json={"message": "LDL cholesterol HDL", "conversation_id": conv["id"]}
            ).text
        )
        assert events[0][1]["conversation_id"] == conv["id"]
        listed = api.get("/api/conversations").json()
        assert listed[0]["id"] == conv["id"] and listed[0]["title"] == "LDL cholesterol HDL"
        assert listed[0]["message_count"] == 2
        detail = api.get(f"/api/conversations/{conv['id']}").json()
        user, assistant = detail["messages"]
        assert (user["role"], assistant["role"], assistant["status"]) == (
            "user",
            "assistant",
            "done",
        )
        assert assistant["content"] == "LDL was 162 mg/dL [1]." and assistant["sources"][0]["cited"]
        assert (
            api.patch(f"/api/conversations/{conv['id']}", json={"title": "Lipids"}).json()["title"]
            == "Lipids"
        )
        assert api.delete(f"/api/conversations/{conv['id']}").status_code == 204
        assert api.get(f"/api/conversations/{conv['id']}").status_code == 404
        assert api.delete(f"/api/conversations/{conv['id']}").status_code == 404


def test_server_history_is_used_and_client_history_ignored(app_parts):
    llm = FakeLLM("ok.")
    with client_for(app_parts, llm) as api:
        cid = api.post("/api/conversations").json()["id"]
        api.post("/api/chat", json={"message": "what is my LDL?", "conversation_id": cid})
        injected = [{"role": "user", "content": "INJECTED"}]
        api.post(
            "/api/chat", json={"message": "and HDL?", "conversation_id": cid, "history": injected}
        )
        sent = llm.calls[1][0]
        assert [(m.role, m.content) for m in sent[1:]] == [
            ("user", "what is my LDL?"), ("assistant", "ok."), ("user", "and HDL?"),
        ]  # fmt: skip
        assert all("INJECTED" not in m.content for m in sent)


def test_stateless_chat_writes_nothing(app_parts):
    with client_for(app_parts, FakeLLM("ok.")) as api:
        api.post("/api/chat", json={"message": "what is cholesterol?", "history": []})
        assert api.get("/api/conversations").json() == []


def test_unknown_conversation_is_404_before_streaming(app_parts):
    with client_for(app_parts, FakeLLM("ok.")) as api:
        assert (
            api.post("/api/chat", json={"message": "hi", "conversation_id": "nope"}).status_code
            == 404
        )


def test_error_and_emergency_outcomes_are_saved(app_parts):
    docs, store = app_parts
    with client_for(app_parts, FakeLLM(error=LlmUnavailable("Ollama is not running."))) as api:
        cid = api.post("/api/conversations").json()["id"]
        api.post("/api/chat", json={"message": "what is cholesterol?", "conversation_id": cid})
        api.post(
            "/api/chat", json={"message": "I have crushing chest pain", "conversation_id": cid}
        )
    msgs = store.get(cid).messages
    assert (msgs[1].status, msgs[1].error) == ("error", "Ollama is not running.")
    assert msgs[3].emergency == "cardiac" and "911" in msgs[3].content and msgs[3].status == "done"


def test_guard_stop_is_saved_as_stopped(app_parts):
    docs, store = app_parts
    with client_for(
        app_parts, FakeLLM("Intro sentence here. " + "This exact sentence repeats forever. " * 5)
    ) as api:
        cid = api.post("/api/conversations").json()["id"]
        api.post("/api/chat", json={"message": "explain", "conversation_id": cid})
    answer = store.get(cid).messages[1]
    assert answer.status == "stopped" and answer.content.count("repeats forever") == 1


async def test_user_stop_saves_partial_answer(app_parts):
    """Disconnect mid-stream (the UI's Stop button): the partial answer is saved as 'stopped'."""
    docs, store = app_parts
    llm = FakeLLM(" ".join(f"Sentence {i} is here." for i in range(300)), delay_s=0.01)
    app = create_app(documents=docs, llm=llm, chats=store)
    cid = store.create().id
    body = json.dumps({"message": "tell me everything", "conversation_id": cid}).encode()
    disconnect, sent = asyncio.Event(), 0
    first = True

    async def receive():
        nonlocal first
        if first:
            first = False
            return {"type": "http.request", "body": body, "more_body": False}
        await disconnect.wait()
        return {"type": "http.disconnect"}

    async def send(message):
        nonlocal sent
        if message["type"] == "http.response.body" and b"event: token" in message.get("body", b""):
            sent += 1
            if sent == 3:
                disconnect.set()

    headers = [(b"content-type", b"application/json"), (b"host", b"127.0.0.1")]
    scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": "POST",
             "scheme": "http", "path": "/api/chat", "raw_path": b"/api/chat", "query_string": b"",
             "root_path": "", "headers": headers, "client": ("127.0.0.1", 1),
             "server": ("127.0.0.1", 8000)}  # fmt: skip
    async with app.router.lifespan_context(app):
        await asyncio.wait_for(app(scope, receive, send), timeout=10)
    answer = store.get(cid).messages[-1]
    assert answer.role == "assistant" and answer.status == "stopped"
    assert answer.content.startswith("Sentence 0 is here.") and "Sentence 299" not in answer.content
