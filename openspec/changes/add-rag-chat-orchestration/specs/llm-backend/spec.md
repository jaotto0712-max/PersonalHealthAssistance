## ADDED Requirements

### Requirement: Local streaming generation
The system SHALL generate responses by streaming tokens from a model served by the local Ollama instance, using the model name from configuration.

#### Scenario: Tokens streamed
- **WHEN** the orchestrator requests generation for a prompt
- **THEN** the backend yields text tokens incrementally as Ollama produces them

#### Scenario: Model selectable by configuration
- **WHEN** `PHA_MODEL` is set to `phi3-base`
- **THEN** generation requests are sent to the `phi3-base` model

### Requirement: Generation parameters
The system SHALL send explicit generation options including context size (4096), maximum new tokens, and temperature from configuration.

#### Scenario: Options applied
- **WHEN** a generation request is sent to Ollama
- **THEN** the request includes `num_ctx`, `num_predict`, and `temperature` options

### Requirement: Availability reporting
The system SHALL report whether Ollama is reachable and whether the configured model is installed, via `GET /api/health`.

#### Scenario: Ollama down
- **WHEN** Ollama is not running and `GET /api/health` is called
- **THEN** the response indicates `llm: "unavailable"` with a hint to start Ollama

#### Scenario: Model missing
- **WHEN** Ollama is running but the configured model is not installed
- **THEN** the response indicates `llm: "model_missing"` and names the model

### Requirement: Test double
The system SHALL provide a fake LLM backend that returns deterministic output for automated tests without Ollama.

#### Scenario: Tests without Ollama
- **WHEN** the test suite runs with the fake backend
- **THEN** chat tests pass without any Ollama process
