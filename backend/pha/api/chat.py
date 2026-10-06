import json
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator
from sse_starlette import EventSourceResponse

from pha.chat.orchestrator import ChatOrchestrator
from pha.chats.store import ChatStore
from pha.llm.base import ChatMessage

router = APIRouter(tags=["chat"])

MAX_MESSAGE_CHARS = 4000
MAX_HISTORY_TURNS = 20


class Turn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=2 * MAX_MESSAGE_CHARS)


class ChatRequest(BaseModel):
    message: str = Field(max_length=MAX_MESSAGE_CHARS)
    history: list[Turn] = Field(default_factory=list, max_length=MAX_HISTORY_TURNS)
    # Saved conversation: the server loads history from the local store (client history ignored)
    # and saves this exchange. Omit for stateless chat (nothing is written).
    conversation_id: str | None = Field(default=None, max_length=64)

    @field_validator("message")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("message must not be empty")
        return value.strip()


@router.post(
    "/chat",
    response_class=EventSourceResponse,
    responses={200: {"description": "Server-Sent Events: meta, token…, sources, done | error"}},
)
async def chat(body: ChatRequest, request: Request) -> EventSourceResponse:
    orchestrator: ChatOrchestrator = request.app.state.chat
    store: ChatStore = request.app.state.chats
    conv_id = body.conversation_id
    if conv_id is not None:
        if not store.exists(conv_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Conversation not found.")
        history = store.history(conv_id)
        store.add_message(conv_id, "user", body.message)  # saved before generating
    else:
        history = [ChatMessage(t.role, t.content) for t in body.history]

    async def events():
        # sse-starlette cancels this generator when the client disconnects, which cancels the
        # in-flight model request (the cancellation propagates into the LLM backend's stream).
        text: list[str] = []
        sources: list[dict] = []
        emergency: str | None = None
        outcome = "stopped"  # until a done/error event says otherwise (e.g. the user hit Stop)
        error: str | None = None
        try:
            async for event in orchestrator.run(body.message, history):
                if event.name == "meta":
                    if event.data.get("emergency"):
                        emergency = event.data.get("category") or "emergency"
                    if conv_id is not None:
                        event.data["conversation_id"] = conv_id
                elif event.name == "token":
                    text.append(event.data["text"])
                elif event.name == "sources":
                    sources = event.data["items"]
                elif event.name == "done":
                    outcome = "stopped" if event.data["usage"].get("stopped_early") else "done"
                elif event.name == "error":
                    outcome, error = "error", event.data["message"]
                yield {"event": event.name, "data": json.dumps(event.data)}
        finally:
            if conv_id is not None:
                store.add_message(
                    conv_id, "assistant", "".join(text), outcome, sources, emergency, error
                )

    return EventSourceResponse(events(), ping=15)
