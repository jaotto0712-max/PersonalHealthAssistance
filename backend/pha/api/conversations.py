from dataclasses import asdict
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from pha.chats.store import ChatStore

router = APIRouter(prefix="/conversations", tags=["conversations"])


def get_store(request: Request) -> ChatStore:
    return request.app.state.chats


Store = Annotated[ChatStore, Depends(get_store)]


class ConversationOut(BaseModel):
    id: str
    title: str | None
    created_at: str
    updated_at: str
    message_count: int


class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    status: str
    sources: list[dict[str, Any]]
    emergency: str | None
    error: str | None
    created_at: str


class ConversationDetail(ConversationOut):
    messages: list[MessageOut]


class Rename(BaseModel):
    title: str = Field(min_length=1, max_length=120)


def _not_found() -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, detail="Conversation not found.")


@router.get("")
def list_conversations(store: Store) -> list[ConversationOut]:
    return [
        ConversationOut(**{k: v for k, v in asdict(c).items() if k != "messages"})
        for c in store.all()
    ]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_conversation(store: Store) -> ConversationOut:
    c = store.create()
    return ConversationOut(
        id=c.id, title=c.title, created_at=c.created_at, updated_at=c.updated_at, message_count=0
    )


@router.get("/{conv_id}")
def get_conversation(conv_id: str, store: Store) -> ConversationDetail:
    c = store.get(conv_id)
    if c is None:
        raise _not_found()
    return ConversationDetail(**asdict(c))


@router.patch("/{conv_id}")
def rename_conversation(conv_id: str, body: Rename, store: Store) -> ConversationOut:
    if not store.rename(conv_id, body.title):
        raise _not_found()
    c = store.get(conv_id)
    assert c is not None
    return ConversationOut(**{k: v for k, v in asdict(c).items() if k != "messages"})


@router.delete("/{conv_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(conv_id: str, store: Store) -> None:
    if not store.delete(conv_id):
        raise _not_found()


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def delete_all_conversations(store: Store) -> None:
    store.delete_all()
