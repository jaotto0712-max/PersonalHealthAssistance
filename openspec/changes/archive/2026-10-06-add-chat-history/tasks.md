## 1. Backend

- [x] 1.1 `pha/chats/store.py`: SQLite schema (WAL, foreign keys, secure_delete), CRUD, title derivation, message append and update
- [x] 1.2 `pha/api/conversations.py`: list/create/get/rename/delete/delete-all; settings `PHA_CHATS_PATH`; app wiring
- [x] 1.3 Chat: optional `conversation_id`; server-side history; persist user + assistant (done/stopped/error, sources, emergency); 404 for unknown ids
- [x] 1.4 Tests: store, API, persistence incl. stop/guard/error, stateless path writes nothing, secure delete

## 2. Frontend

- [x] 2.1 API types and http + mock clients for conversations; chat request carries `conversation_id`
- [x] 2.2 `useConversations` hook; `useChat` hydration from stored messages and lazy create on first send
- [x] 2.3 Sidebar tabs (Chats | Documents): list, open, rename, delete, delete all; mobile drawer; URL hash restore
- [x] 2.4 Tests: list/open/new/rename/delete/delete-all, reload restore, stored emergency + sources render

## 3. Docs and check

- [x] 3.1 README and footer privacy text; `.env.example`
- [x] 3.2 Live end-to-end in a browser: two chats, reload, reopen, follow-up uses history, delete
