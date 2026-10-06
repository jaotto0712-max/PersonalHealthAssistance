## ADDED Requirements

### Requirement: Streaming chat endpoint
The system SHALL expose `POST /api/chat` accepting `{message, history}` and responding with a Server-Sent Events stream of `meta`, `token`, `sources`, and `done` events in that order.

#### Scenario: Normal streamed response
- **WHEN** a client posts a valid message
- **THEN** it receives one `meta` event, one or more `token` events, one `sources` event, and one `done` event

#### Scenario: Emergency response
- **WHEN** a client posts an emergency message
- **THEN** the `meta` event has `emergency: true` and the `token` events contain the fixed urgent-care message

### Requirement: Input validation
The system SHALL reject empty messages, messages over 4000 characters, and history over 20 turns or with invalid roles, with HTTP 422.

#### Scenario: Empty message
- **WHEN** a client posts `{"message": ""}`
- **THEN** the response status is 422

### Requirement: Error events
If generation fails mid-stream or the model is unavailable, the system SHALL emit an `error` event with a machine-readable code and human-readable message and then close the stream.

#### Scenario: Ollama unavailable
- **WHEN** Ollama is not running and a chat request is made
- **THEN** the stream contains an `error` event with code `llm_unavailable`

### Requirement: Client cancellation
The system SHALL stop generation when the client disconnects.

#### Scenario: User stops generation
- **WHEN** the client closes the connection during streaming
- **THEN** the backend cancels the Ollama request
