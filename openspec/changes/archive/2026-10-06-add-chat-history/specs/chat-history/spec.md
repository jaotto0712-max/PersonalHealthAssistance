## ADDED Requirements

### Requirement: Local conversation storage
The backend SHALL store conversations and their messages only in a local SQLite file under the data directory, with secure deletion enabled, and SHALL NOT send them anywhere.

#### Scenario: Saved locally
- **WHEN** a chat request with a `conversation_id` completes
- **THEN** the user message and the assistant message (text, status, cited sources) are rows in `data/chats.db`

#### Scenario: Stateless without an id
- **WHEN** a chat request has no `conversation_id`
- **THEN** nothing is written to the conversation store

### Requirement: Conversation management API
The backend SHALL expose endpoints to list (newest first), create, read with messages, rename, delete one, and delete all conversations.

#### Scenario: Reopen a conversation
- **WHEN** the client requests `GET /api/conversations/{id}` for a saved conversation
- **THEN** it receives the messages in order with their roles, text, statuses, sources and emergency categories

#### Scenario: Delete
- **WHEN** a conversation is deleted
- **THEN** it and all its messages are removed, and later requests for it return 404

### Requirement: Server-side history
When a chat request includes a `conversation_id`, the server SHALL build the model's history from the stored messages of that conversation and SHALL ignore client-supplied history.

#### Scenario: Follow-up uses stored history
- **WHEN** the user asks a follow-up in a reopened conversation
- **THEN** the prompt includes that conversation's earlier turns from the store

### Requirement: Outcome persistence
The assistant message SHALL be saved with status `done`, `stopped`, or `error`, including when the user stops generation, the degeneration guard stops it, or the model fails.

#### Scenario: User presses Stop
- **WHEN** the client disconnects mid-answer
- **THEN** the partial answer is saved with status `stopped`

### Requirement: Titles
A new conversation's title SHALL be derived from its first user message (at most about 60 characters on a word boundary) and SHALL be renamable.

#### Scenario: Auto title
- **WHEN** the first message is "What does my cholesterol result mean?"
- **THEN** the conversation title is "What does my cholesterol result mean?"

### Requirement: History UI
The UI SHALL list conversations in the sidebar, open one to show its full thread (including source lists and emergency cards), start new chats, rename and delete conversations, delete all with confirmation, and reopen the active conversation after a page reload.

#### Scenario: Reload keeps the conversation
- **WHEN** the user reloads the page during a saved conversation
- **THEN** the same conversation is displayed
