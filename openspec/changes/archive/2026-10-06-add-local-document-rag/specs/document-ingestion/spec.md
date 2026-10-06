## ADDED Requirements

### Requirement: Supported upload formats
The system SHALL accept uploads of PDF, TXT, MD, and DOCX files up to 20 MB and SHALL reject other types or larger files with a descriptive error.

#### Scenario: Valid PDF accepted
- **WHEN** a user uploads a 2 MB text-based PDF
- **THEN** the system responds with HTTP 201 and a document record with status `indexed`

#### Scenario: Unsupported type rejected
- **WHEN** a user uploads a `.exe` file
- **THEN** the system responds with HTTP 415 and does not store the file

#### Scenario: Oversized file rejected
- **WHEN** a user uploads a 25 MB PDF
- **THEN** the system responds with HTTP 413 and does not store the file

### Requirement: Text extraction with page tracking
The system SHALL extract text from uploaded documents preserving page numbers where the format provides them.

#### Scenario: Page numbers retained
- **WHEN** a 3-page PDF is ingested
- **THEN** every stored chunk has a `page` metadata value between 1 and 3

#### Scenario: Image-only PDF flagged
- **WHEN** a PDF with no extractable text is uploaded
- **THEN** the document record has status `needs_ocr` and no chunks are stored

### Requirement: Chunking and local embedding
The system SHALL split extracted text into overlapping chunks that do not cross page boundaries, embed them with a locally stored embedding model, and persist them in a local Chroma collection with document id, filename, page, and chunk index metadata.

#### Scenario: Chunks persisted
- **WHEN** a document is ingested
- **THEN** the Chroma collection contains one entry per chunk, each tagged with the document's id

#### Scenario: Embedding model loaded from disk
- **WHEN** ingestion runs with networking disabled
- **THEN** embedding succeeds using the model in `models/embeddings/`

### Requirement: Duplicate upload detection
The system SHALL detect a re-upload of byte-identical content and return the existing document record instead of creating a duplicate.

#### Scenario: Same file uploaded twice
- **WHEN** the same file is uploaded a second time
- **THEN** the response references the original document id and the chunk count in the store is unchanged

### Requirement: Safe file storage
The system SHALL store uploaded files under a server-generated directory per document and SHALL NOT use client-supplied paths.

#### Scenario: Path traversal filename
- **WHEN** a file named `../../etc/passwd.txt` is uploaded
- **THEN** the file is stored inside `data/uploads/<doc_id>/` with a sanitized name
