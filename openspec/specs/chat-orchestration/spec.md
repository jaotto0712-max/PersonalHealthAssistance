# chat-orchestration Specification

## Purpose
Assemble each answer: safety check, retrieval, grounded prompt, model streaming, citations and disclaimer.

## Requirements
### Requirement: Retrieval-augmented prompting
For each non-emergency message, the system SHALL retrieve relevant document chunks and include them as numbered excerpts with filename and page in the prompt, along with instructions to cite excerpts as `[n]`.

#### Scenario: Document-grounded answer
- **WHEN** a user who uploaded a lab report with "LDL 162 mg/dL" asks "is my LDL high?"
- **THEN** the prompt sent to the model contains that excerpt labeled with its number, filename, and page

#### Scenario: No relevant documents
- **WHEN** retrieval returns no chunks
- **THEN** the prompt contains no excerpt block and instructs the model to answer from general knowledge and state that no relevant user documents were found

### Requirement: Training-consistent system prompt
The system SHALL use the same base system prompt used during fine-tuning, extended with retrieval instructions.

#### Scenario: Shared prompt source
- **WHEN** the orchestrator builds a prompt
- **THEN** its system message begins with the contents of the shared system prompt file

### Requirement: Context budget
The system SHALL keep the total prompt within the model's context window minus the answer reserve, dropping the oldest history turns first and then the lowest-scoring chunks.

#### Scenario: Long history trimmed
- **WHEN** the client sends history that would exceed the budget
- **THEN** the oldest turns are omitted and the current message and top-scoring chunk are always included

### Requirement: Source attribution
After generation, the system SHALL return the list of retrieved sources, each with its citation number, document id, filename, page, score, snippet, and whether the answer cited it.

#### Scenario: Cited source marked
- **WHEN** the generated answer contains `[1]`
- **THEN** source 1 is returned with `cited: true`

#### Scenario: No explicit citation
- **WHEN** the answer contains no `[n]` markers but chunks were retrieved
- **THEN** all retrieved sources are returned with `cited: false`

### Requirement: Conversation history
The system SHALL accept prior turns from the client and include them in the prompt, and SHALL NOT persist conversations on the server.

#### Scenario: Follow-up question
- **WHEN** a user asks "what about my HDL?" after a turn about LDL
- **THEN** the previous turn is included in the prompt

#### Scenario: No server-side storage
- **WHEN** a chat request completes
- **THEN** no conversation content is written to disk by the backend

