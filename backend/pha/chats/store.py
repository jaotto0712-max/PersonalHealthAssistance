"""Conversation history in a local SQLite file (data/chats.db). Nothing here leaves the machine.

secure_delete=ON overwrites deleted rows, so deleted health conversations don't linger in the file.
"""

import json
import re
import sqlite3
import threading
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pha.llm.base import ChatMessage

Status = Literal["done", "stopped", "error"]
TITLE_CHARS = 60
HISTORY_TURNS = 20

SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    title TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    seq INTEGER NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'done',
    sources TEXT,
    emergency TEXT,
    error TEXT,
    created_at TEXT NOT NULL,
    UNIQUE (conversation_id, seq)
);
CREATE INDEX IF NOT EXISTS idx_conversations_updated ON conversations(updated_at DESC);
"""


def _now() -> str:
    return datetime.now(UTC).isoformat()


def derive_title(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= TITLE_CHARS:
        return text
    cut = text.rfind(" ", 0, TITLE_CHARS)
    return text[: cut if cut > TITLE_CHARS // 2 else TITLE_CHARS].rstrip(" ,;:") + "…"


@dataclass
class StoredMessage:
    id: str
    role: str
    content: str
    status: str
    sources: list[dict[str, Any]] = field(default_factory=list)
    emergency: str | None = None
    error: str | None = None
    created_at: str = ""


@dataclass
class Conversation:
    id: str
    title: str | None
    created_at: str
    updated_at: str
    message_count: int = 0
    messages: list[StoredMessage] = field(default_factory=list)


class ChatStore:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        with self._lock:
            self._db.execute("PRAGMA journal_mode=WAL")
            self._db.execute("PRAGMA foreign_keys=ON")
            self._db.execute("PRAGMA secure_delete=ON")
            self._db.executescript(SCHEMA)

    def close(self) -> None:
        with self._lock:
            self._db.close()

    # ------------------------------------------------------------ conversations

    def create(self, title: str | None = None) -> Conversation:
        now = _now()
        conv = Conversation(uuid.uuid4().hex, title, now, now)
        with self._lock, self._db:
            self._db.execute(
                "INSERT INTO conversations (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (conv.id, conv.title, conv.created_at, conv.updated_at),
            )
        return conv

    def all(self) -> list[Conversation]:
        with self._lock:
            rows = self._db.execute(
                """SELECT c.*, COUNT(m.id) AS n FROM conversations c
                   LEFT JOIN messages m ON m.conversation_id = c.id
                   GROUP BY c.id ORDER BY c.updated_at DESC"""
            ).fetchall()
        return [
            Conversation(r["id"], r["title"], r["created_at"], r["updated_at"], r["n"])
            for r in rows
        ]

    def exists(self, conv_id: str) -> bool:
        with self._lock:
            return (
                self._db.execute("SELECT 1 FROM conversations WHERE id = ?", (conv_id,)).fetchone()
                is not None
            )

    def get(self, conv_id: str) -> Conversation | None:
        with self._lock:
            row = self._db.execute(
                "SELECT * FROM conversations WHERE id = ?", (conv_id,)
            ).fetchone()
            if row is None:
                return None
            msgs = self._db.execute(
                "SELECT * FROM messages WHERE conversation_id = ? ORDER BY seq", (conv_id,)
            ).fetchall()
        messages = [
            StoredMessage(
                m["id"], m["role"], m["content"], m["status"],
                json.loads(m["sources"]) if m["sources"] else [], m["emergency"], m["error"],
                m["created_at"],
            )
            for m in msgs
        ]  # fmt: skip
        return Conversation(row["id"], row["title"], row["created_at"], row["updated_at"],
                            len(messages), messages)  # fmt: skip

    def rename(self, conv_id: str, title: str) -> bool:
        with self._lock, self._db:
            cur = self._db.execute(
                "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
                (title.strip(), _now(), conv_id),
            )
        return cur.rowcount == 1

    def delete(self, conv_id: str) -> bool:
        with self._lock, self._db:
            cur = self._db.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
        return cur.rowcount == 1

    def delete_all(self) -> None:
        with self._lock, self._db:
            self._db.execute("DELETE FROM conversations")

    # ------------------------------------------------------------ messages

    def add_message(
        self,
        conv_id: str,
        role: str,
        content: str,
        status: Status = "done",
        sources: list[dict[str, Any]] | None = None,
        emergency: str | None = None,
        error: str | None = None,
    ) -> StoredMessage:
        now = _now()
        msg = StoredMessage(
            uuid.uuid4().hex, role, content, status, sources or [], emergency, error, now
        )
        with self._lock, self._db:
            seq = self._db.execute(
                "SELECT COALESCE(MAX(seq), 0) + 1 FROM messages WHERE conversation_id = ?",
                (conv_id,),
            ).fetchone()[0]
            self._db.execute(
                """INSERT INTO messages (id, conversation_id, seq, role, content, status, sources,
                   emergency, error, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (msg.id, conv_id, seq, role, content, status,
                 json.dumps(msg.sources) if msg.sources else None, emergency, error, now),
            )  # fmt: skip
            title_sql = "COALESCE(title, ?)" if role == "user" else "title"
            params = (derive_title(content), now, conv_id) if role == "user" else (now, conv_id)
            self._db.execute(
                f"UPDATE conversations SET title = {title_sql}, updated_at = ? WHERE id = ?", params
            )
        return msg

    def history(self, conv_id: str, turns: int = HISTORY_TURNS) -> list[ChatMessage]:
        """Prior turns for the model: completed exchanges only, no emergency alerts or errors."""
        conv = self.get(conv_id)
        if conv is None:
            return []
        usable = [
            ChatMessage(m.role, m.content)  # type: ignore[arg-type]
            for m in conv.messages
            if m.content.strip()
            and not m.emergency
            and not (m.role == "assistant" and m.status == "error")
        ]
        return usable[-turns:]
