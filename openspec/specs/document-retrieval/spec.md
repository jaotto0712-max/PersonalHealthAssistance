# document-retrieval Specification

## Purpose
Retrieve the most relevant chunks of the user's documents for a question, using local embeddings and Chroma.

## Requirements
### Requirement: Top-k semantic retrieval
The system SHALL embed a query with the same local model used for ingestion and return up to k (default 4) most similar chunks, each with text, document id, filename, page, and similarity score.

#### Scenario: Relevant chunk returned
- **WHEN** a document containing "Hemoglobin A1C: 6.1%" is indexed and the query is "what was my A1C?"
- **THEN** the results include the chunk containing that line, with its filename and page

### Requirement: Relevance threshold
The system SHALL discard results whose similarity score is below a configurable threshold and SHALL return an empty list when nothing qualifies.

#### Scenario: Unrelated query
- **WHEN** only a cholesterol lab report is indexed and the query is "how do vaccines work?"
- **THEN** the retrieval result is empty or contains only chunks above the threshold

#### Scenario: No documents indexed
- **WHEN** no documents have been uploaded and a query is made
- **THEN** retrieval returns an empty list without error

### Requirement: Deterministic ordering
The system SHALL return results ordered by descending similarity score.

#### Scenario: Ordered results
- **WHEN** retrieval returns multiple chunks
- **THEN** each chunk's score is greater than or equal to the next chunk's score

