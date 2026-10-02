## ADDED Requirements

### Requirement: Runtime network guard
The backend SHALL support an opt-in network guard mode that blocks and logs any attempted connection to a non-loopback address for the lifetime of the process.

#### Scenario: Outbound attempt blocked
- **WHEN** the backend runs with the guard enabled and any code attempts to connect to a public IP
- **THEN** the connection is refused and the attempt is recorded in the guard log

### Requirement: End-to-end offline verification
An automated test SHALL start the full backend with the network guard enabled, upload a document, perform a chat that uses retrieval and the local model, delete the document, and assert that zero outbound connection attempts were recorded.

#### Scenario: Clean privacy run
- **WHEN** the end-to-end privacy test runs against a correctly configured system
- **THEN** the guard log is empty and the test passes

#### Scenario: Regression detected
- **WHEN** a dependency attempts telemetry during the end-to-end flow
- **THEN** the test fails and reports the attempted destination

### Requirement: Data removal verification
The end-to-end test SHALL verify that after deleting a document, its file and all its vectors are gone and retrieval no longer returns its content.

#### Scenario: No residue after delete
- **WHEN** the uploaded test document is deleted
- **THEN** no file remains under its upload directory, no Chroma entries reference its id, and a query for its unique content returns nothing
