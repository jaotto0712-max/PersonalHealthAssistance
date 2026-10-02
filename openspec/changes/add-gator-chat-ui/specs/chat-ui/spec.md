## ADDED Requirements

### Requirement: Streaming chat thread
The UI SHALL display a conversation thread where user messages appear immediately and assistant responses render progressively as tokens stream from `POST /api/chat`.

#### Scenario: Streaming answer
- **WHEN** the user sends a question
- **THEN** the user message appears in the thread and the assistant message grows incrementally until the `done` event

#### Scenario: Stop generation
- **WHEN** the user clicks Stop during streaming
- **THEN** the request is aborted, the partial answer remains visible marked as stopped, and the input is re-enabled

#### Scenario: New chat
- **WHEN** the user clicks New chat
- **THEN** the thread is cleared and subsequent requests send empty history

### Requirement: Citations and sources
The UI SHALL render `[n]` markers in answers as interactive citation chips and SHALL show an expandable sources list with filename, page, and snippet for each source.

#### Scenario: Citation chip navigation
- **WHEN** the user clicks the `[1]` chip in an answer
- **THEN** the sources list expands and source 1 is highlighted

#### Scenario: Uncited related sources
- **WHEN** sources are returned with `cited: false`
- **THEN** they appear under a "Related documents" label rather than as citations

### Requirement: Document upload and management
The UI SHALL provide a documents panel supporting drag-and-drop or file-picker upload, showing each document's name, status, and a delete action, plus a Clear all action with confirmation.

#### Scenario: Successful upload
- **WHEN** the user drops a PDF onto the upload area
- **THEN** a progress indicator shows and the document then appears in the list with status indexed

#### Scenario: Rejected upload
- **WHEN** the backend responds with 413 or 415
- **THEN** the UI shows a readable error naming the file and the reason

#### Scenario: Needs OCR status
- **WHEN** a document has status `needs_ocr`
- **THEN** the list shows a warning that its text could not be read

#### Scenario: Delete document
- **WHEN** the user deletes a document
- **THEN** it disappears from the list after the backend confirms

### Requirement: Persistent disclaimer
The UI SHALL display a persistent, non-dismissible banner stating that the assistant provides general information only, is not medical advice, and that emergencies require calling 911.

#### Scenario: Banner always visible
- **WHEN** the app is loaded on any viewport size
- **THEN** the disclaimer banner is visible without scrolling the page header area

### Requirement: Emergency alert presentation
When the backend flags a response as an emergency, the UI SHALL render a distinct alert card with prominent emergency actions instead of a normal chat bubble.

#### Scenario: Emergency card
- **WHEN** a `meta` event with `emergency: true` and category `self_harm` is received
- **THEN** the UI shows an alert card with "Call 911" and "Call or text 988" actions

### Requirement: Backend status indicator
The UI SHALL show model availability from `GET /api/health` and SHALL disable sending with an explanatory message when the model is unavailable.

#### Scenario: Ollama down
- **WHEN** health reports `llm: "unavailable"`
- **THEN** the header shows a red status and the composer explains that Ollama must be started

### Requirement: Single-origin local serving
The production build SHALL be served by the backend at `/` on the same local address as the API.

#### Scenario: Production start
- **WHEN** the frontend is built and the backend is started
- **THEN** opening `http://127.0.0.1:8000/` loads the app and API calls succeed without CORS configuration
