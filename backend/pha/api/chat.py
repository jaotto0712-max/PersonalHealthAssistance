import json
from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field, field_validator
from sse_starlette import EventSourceResponse

from pha.chat.orchestrator import ChatOrchestrator
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
    history = [ChatMessage(t.role, t.content) for t in body.history]

    async def events():
        # sse-starlette cancels this generator when the client disconnects, which cancels the
        # in-flight model request (the cancellation propagates into the LLM backend's stream).
        async for event in orchestrator.run(body.message, history):
            yield {"event": event.name, "data": json.dumps(event.data)}

    return EventSourceResponse(events(), ping=15)
