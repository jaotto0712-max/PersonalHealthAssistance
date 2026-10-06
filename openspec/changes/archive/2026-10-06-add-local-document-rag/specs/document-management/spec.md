## ADDED Requirements

### Requirement: List documents
The system SHALL expose `GET /api/documents` returning each document's id, filename, size, page count, chunk count, status, and upload time.

#### Scenario: List after upload
- **WHEN** two documents have been uploaded
- **THEN** `GET /api/documents` returns both records

### Requirement: Delete a document
The system SHALL expose `DELETE /api/documents/{id}` which removes the document's stored file and all of its chunks from the vector store.

#### Scenario: Document fully removed
- **WHEN** a user deletes a document
- **THEN** the file no longer exists on disk, no chunks with that document id remain in Chroma, and subsequent retrieval never returns its content

#### Scenario: Unknown document
- **WHEN** a delete is requested for an id that does not exist
- **THEN** the system responds with HTTP 404

### Requirement: Clear all documents
The system SHALL expose `DELETE /api/documents` which removes all uploaded files and all stored chunks.

#### Scenario: Clear all
- **WHEN** a user clears all documents
- **THEN** `GET /api/documents` returns an empty list and the vector collection is empty

### Requirement: Storage consistency on startup
The system SHALL reconcile the document registry, stored files, and vector entries at startup, treating the registry as the source of truth: it SHALL remove registry records whose file is missing, uploaded files with no registry record, and chunks whose document is not registered. Registered documents with no chunks (status `needs_ocr`) SHALL be kept.

#### Scenario: Orphaned chunks cleaned
- **WHEN** the app starts and Chroma contains chunks for a document id whose upload directory is missing
- **THEN** those chunks are deleted

#### Scenario: Scanned document kept
- **WHEN** the app starts and a registered `needs_ocr` document has its file but no chunks
- **THEN** the document remains listed
