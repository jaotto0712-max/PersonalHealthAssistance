## Why

Conversations live only in browser memory and disappear on reload. Users can't come back to an earlier discussion of their lab results or keep separate threads (e.g. "cholesterol" vs "new medication"). The original design made this choice for privacy. The user has now asked for history, stored locally next to their documents.

## What Changes

- **Local conversation store:** a SQLite file `data/chats.db` (gitignored, loopback-only backend, `secure_delete` on so deleted text is overwritten). It holds conversations (id, title, timestamps) and messages (role, text, status, cited sources, emergency category).
- **Conversations API:** list, create, get with messages, rename, delete one, delete all.
- **Chat persistence:** `POST /api/chat` takes an optional `conversation_id`. When present, the server reads history from the store, which becomes the source of truth, and saves the user message plus the final assistant message (also when stopped by the user, stopped by the guard, or failed). Without it, chat stays stateless as before.
- **Auto titles** from the first question; rename in the UI.
- **UI:** the sidebar gets **Chats | Documents** tabs. Chats has a conversation list (newest first, relative time) with open, rename and delete, plus "Delete all chats" with confirmation. New chat starts an empty thread; the conversation is created when the first message is sent. The mobile drawer gets the same tabs.
- **Privacy text** in the footer, README and specs is updated: chats are saved on this device, never sent anywhere, and can be deleted.

## Capabilities

### New Capabilities
- `chat-history`: Saving, listing, reopening, renaming and deleting conversations locally.

### Modified Capabilities
<!-- chat-orchestration ("SHALL NOT persist conversations") is in the unarchived change add-rag-chat-orchestration; superseded by chat-history's opt-in persistence requirement -->

## Impact

- Backend: new `pha/chats/store.py`, `pha/api/conversations.py`; changes to `pha/api/chat.py`, `pha/main.py` and settings (`PHA_CHATS_PATH`). No new dependencies (stdlib `sqlite3`).
- Frontend: API types and clients (http + mock), a `useConversations` hook, a sidebar tab UI, and `useChat` hydration.
