## ADDED Requirements

### Requirement: Loopback-only binding
The backend SHALL bind only to a loopback address and SHALL refuse to start if configured with a non-loopback bind host or a non-loopback Ollama URL.

#### Scenario: Non-loopback host rejected
- **WHEN** the backend is started with `PHA_HOST=0.0.0.0`
- **THEN** startup fails with an error explaining that only loopback addresses are allowed

#### Scenario: Remote Ollama rejected
- **WHEN** `PHA_OLLAMA_URL=http://example.com:11434` is configured
- **THEN** startup fails with an error explaining that the model server must be local

### Requirement: Telemetry and hub access disabled
The backend SHALL disable third-party telemetry (including Chroma anonymized telemetry) and SHALL run Hugging Face libraries in offline mode.

#### Scenario: Offline flags set at startup
- **WHEN** the backend process starts
- **THEN** `HF_HUB_OFFLINE`, `TRANSFORMERS_OFFLINE` are `1` and `ANONYMIZED_TELEMETRY` is `False` before any ML library is imported

### Requirement: No outbound network connections
The running application SHALL NOT open network connections to non-loopback addresses.

#### Scenario: Socket guard in tests
- **WHEN** the backend test suite runs with a socket guard that raises on non-loopback connections
- **THEN** no test fails due to an outbound connection attempt

### Requirement: No remote frontend assets
The frontend build SHALL NOT reference fonts, scripts, stylesheets, or images hosted on remote origins.

#### Scenario: Built assets are self-contained
- **WHEN** the production frontend build output is scanned for `http://` or `https://` asset URLs
- **THEN** no remote asset references are found
