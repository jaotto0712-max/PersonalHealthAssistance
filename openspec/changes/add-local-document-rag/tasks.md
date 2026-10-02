## 1. Dependencies and model assets

- [x] 1.1 Add chromadb (pinned), sentence-transformers, pypdf, python-docx, python-multipart to backend
- [x] 1.2 Add `scripts/fetch_embeddings.py` to download `BAAI/bge-small-en-v1.5` into `models/embeddings/`
- [x] 1.3 Add RAG settings: chunk size/overlap, top-k, score threshold, upload size limit, paths

## 2. Ingestion pipeline

- [x] 2.1 Implement `pha/rag/parsers.py` (PDF per page, DOCX, TXT/MD) returning `[(page, text)]`; detect image-only PDFs
- [x] 2.2 Implement `pha/rag/chunker.py` page-aware recursive splitter with overlap
- [x] 2.3 Implement `pha/rag/embedder.py` `Embedder` interface + sentence-transformers implementation loaded once at startup
- [x] 2.4 Implement `pha/rag/store.py` wrapping Chroma PersistentClient (telemetry off, cosine) with add/query/delete-by-doc
- [x] 2.5 Implement document registry (JSON or SQLite in `data/`) with id, filename, hash, size, pages, chunks, status, timestamp
- [x] 2.6 Implement ingest service: validate, sanitize, store file, parse, chunk, embed, persist, dedupe by hash

## 3. Retrieval

- [x] 3.1 Implement `pha/rag/retriever.py` returning scored chunks with metadata, applying threshold and ordering
- [x] 3.2 Add unit tests with a fixture document verifying the expected chunk is retrieved and unrelated queries filter out

## 4. API and management

- [x] 4.1 Add `POST /api/documents` (multipart) with 201/413/415 responses
- [x] 4.2 Add `GET /api/documents`, `DELETE /api/documents/{id}`, `DELETE /api/documents`
- [x] 4.3 Implement startup reconciliation of files vs vectors in app lifespan
- [x] 4.4 API tests: upload/list/delete/clear, path traversal filename, duplicate upload, oversized and wrong type, all under socket guard

## 5. Fixtures

- [x] 5.1 Create synthetic (non-real) sample health documents in `eval/fixtures/docs/` (lab report PDF, visit summary TXT, med list DOCX)
