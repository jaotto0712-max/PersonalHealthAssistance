## ADDED Requirements

### Requirement: Single source of prompt text
The system prompt, retrieval instructions and no-context instructions SHALL each live in one text file under `training/`. The backend SHALL load them at startup, and the training data generator SHALL read the same files.

#### Scenario: Backend uses the shared files
- **WHEN** the backend builds a grounded prompt
- **THEN** the system message contains the exact contents of `training/system_prompt.txt` and `training/rag_instructions.txt`

### Requirement: Identical excerpt formatting
The training data generator SHALL format retrieved excerpts byte-for-byte identically to the backend's prompt builder.

#### Scenario: Formatter parity
- **WHEN** the same list of chunks (filename, page, text) is formatted by the training generator and by `pha.chat.prompt.format_excerpts`
- **THEN** both outputs are identical strings
