## Context

The backend already keeps user data on disk under `data/` (uploads, Chroma, document registry), bound to loopback, and the test suite runs under a socket guard. Chat history joins that local data.

## Decisions

**SQLite via stdlib `sqlite3`.** One file `data/chats.db`, with WAL, `foreign_keys=ON` and `secure_delete=ON` (deleted rows are zeroed, not just unlinked). Access goes through a lock with `check_same_thread=False`; calls are short and run in FastAPI's threadpool.

```
conversations(id TEXT PK, title TEXT, created_at TEXT, updated_at TEXT)
messages(id TEXT PK, conversation_id TEXT REFERENCES conversations ON DELETE CASCADE,
         seq INTEGER, role TEXT, content TEXT, status TEXT,       -- done|stopped|error
         sources TEXT /* JSON */, emergency TEXT, created_at TEXT)
```

**The server is the source of truth for history** when `conversation_id` is given. The client's `history` field is ignored in that case, which prevents drift between tabs, and the server sends the last turns through the existing prompt budget. Stateless chat (no `conversation_id`) keeps working for tests and the API.

**When things are written:**
- The user message is written before generation, so a crash doesn't lose the question.
- The assistant message is written in a `finally` with status `done`, `stopped` (client stop, guard stop or disconnect) or `error`, plus the sources and emergency category.
- Emergency replies are stored too, so reopening shows the alert card.
- `updated_at` is bumped on every message.

**Titles** come from the first user message, whitespace-collapsed and cut at about 60 characters on a word boundary. Renaming is `PATCH`.

**API:**
- `GET /api/conversations` returns `[{id, title, created_at, updated_at, message_count}]`, newest first.
- `POST /api/conversations` → 201.
- `GET /api/conversations/{id}` returns `{…, messages:[…]}`.
- `PATCH /api/conversations/{id}` with `{title}` (1–120 characters).
- `DELETE /api/conversations/{id}` → 204 or 404; `DELETE /api/conversations` → 204.
- Chat with an unknown `conversation_id` returns 404 before streaming.

**UI:**
- The sidebar has tabs (Chats | Documents) rather than two stacked lists, which fits the 320 px sidebar and the mobile drawer.
- The active conversation id is kept in the URL hash (`#c=<id>`), so a reload reopens the same chat. No other persistent client state.
- The conversation is created lazily on first send, so empty "New chat" sessions never leave rows behind.

## Risks / Trade-offs

- [Health conversations at rest in a plain SQLite file] → Same protection as the uploaded documents: user-owned `data/`, OS disk encryption, delete one or delete all, and `secure_delete`. Documented in the README and footer.
- [Long conversations exceed the model context] → The existing prompt budget already trims to recent turns; the full thread stays visible in the UI.
- [Concurrent writes from two tabs] → Writes are serialized through the lock. The last writer wins on titles.
