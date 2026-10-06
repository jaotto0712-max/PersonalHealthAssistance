## Context

Users upload a handful of personal health documents (lab reports, visit summaries, medication lists). Volume is small (tens of documents, at most thousands of chunks), so simplicity beats scale. Everything must run offline on a laptop.

```
 upload ─▶ validate (type/size) ─▶ save data/uploads/<doc_id>/<name>
                │
                ▼
         parse → [(page, text)] ─▶ chunk (≈800 chars, 120 overlap, page-aware)
                                         │
                                         ▼
                         embed (bge-small-en-v1.5, local, normalized)
                                         │
                                         ▼
                     Chroma collection "user_docs" (cosine)
                     metadata: doc_id, filename, page, chunk_index

 query ─▶ embed ─▶ Chroma top-k (k=4) ─▶ drop below threshold ─▶ [Chunk + score]
```

## Goals / Non-Goals

**Goals:**
- Reliable text extraction for typical digital PDFs and text formats.
- Citations precise to the page.
- Deletion that removes every trace of a document.

**Non-Goals:**
- OCR for scanned or image PDFs. It is detected and reported, not processed.
- Multi-user isolation or encryption at rest (single local user. Disk encryption is the OS's job).
- Hybrid BM25 search or rerankers (possible later improvement).

## Decisions

**Embedding model: `BAAI/bge-small-en-v1.5` via sentence-transformers.** It is about 130 MB, fast on CPU and MPS, and has strong retrieval quality for its size. It is downloaded once by `scripts/fetch_embeddings.py` into `models/embeddings/` and loaded by path at runtime. Alternatives:
- `all-MiniLM-L6-v2`: weaker retrieval.
- Ollama `nomic-embed-text`: viable and avoids torch, but couples RAG to Ollama availability and complicates testing. Kept behind an `Embedder` interface so it can be swapped in.

**Chroma `PersistentClient` with `anonymized_telemetry=False`, one collection, cosine space.** Chroma is simple and embedded (no server), and the brief names it.

**Chunking: recursive character splitting at about 800 characters with 120 overlap, never crossing page boundaries.** Each chunk carries its page number. That size fits 4 chunks (about 800 tokens) comfortably inside Phi-3's 4k context alongside the system prompt and history. It is kept configurable.

**Document identity: `doc_id = uuid4`**, plus a SHA-256 content hash. Re-uploading an identical file returns the existing document instead of duplicating it.

**Parsers:**
- pypdf for PDF (per page)
- python-docx for DOCX (treated as page 1, or split by headings)
- UTF-8 reading for TXT/MD

A PDF yielding almost no text gets status `needs_ocr` and is not indexed.

**Upload limits:** an allowlist of extensions and MIME types and a 20 MB size cap. Filenames are sanitized, and files are stored under the doc_id directory to prevent path traversal.

**Relevance threshold:** Chunks with cosine similarity below a configurable minimum (`PHA_MIN_SCORE`, default **0.50**) are dropped.

*Measured during implementation* with bge-small-en-v1.5 on the fixture documents. BGE similarities are compressed: the right chunk ranked first for every real question (0.55–0.78), but unrelated questions still scored 0.37–0.51 ("how do vaccines work?" 0.51, "tips for running a marathon" 0.49, "capital of France" 0.37). The originally planned 0.35 would filter almost nothing, so the default is 0.50 until `add-evaluation-suite` tunes it on a labeled set. Relative cut-offs (e.g. within 0.1 of the top hit) are an alternative to evaluate there. An empty result is valid. The orchestrator then answers from model knowledge and says that no relevant documents were found.

**Ingestion runs in a worker thread** (`run_in_threadpool`) so the API stays responsive. Documents are small, so synchronous completion before the response is acceptable, and there is no job queue.

**API record shape (shared with the UI):** `GET /api/documents` items and `POST /api/documents` responses use `{id, filename, size_bytes, pages, chunks, status: "indexed"|"needs_ocr", uploaded_at (ISO 8601)}`. Errors use FastAPI's `{"detail": "<human-readable reason>"}`. The UI (`frontend/src/api/types.ts`) already depends on this shape.

## Risks / Trade-offs

- [Scanned PDFs yield no text] → Flag them as `needs_ocr` and surface that in the UI. OCR (e.g. Tesseract) is a possible stretch goal.
- [Tables in lab reports extract poorly from PDF] → Keep page-level citations so the user can verify. Consider `pdfplumber` if quality is poor.
- [Embedding model first-load latency (~2–5 s)] → Load it once at app startup (lifespan) and reuse it.
- [Chroma and SQLite version friction on macOS] → Pin the chromadb version and test in CI.
- [Delete leaves orphans if a crash happens mid-operation] → Delete vectors first, then files. A startup reconciliation removes orphans in either direction.

## Open Questions

- Should documents be scoped per chat session or global for the user? Proposed: global (simpler, and it matches "my health records").
