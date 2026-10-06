## Why

The fine-tuned model knows general medical facts but not the user's own lab results, visit notes, or discharge instructions. The brief requires grounding answers in documents the user uploads, using a local Chroma vector store, with nothing leaving the machine.

## What Changes

- Add a local document ingestion pipeline: accept PDF, TXT, MD, and DOCX files, extract text with page numbers, chunk it, embed it with a locally stored embedding model, and persist it in Chroma.
- Add a retrieval service returning the top-k relevant chunks with source metadata (filename, page, chunk id) and similarity scores, filtered by a relevance threshold.
- Add document management: list uploaded documents, delete one document (file + vectors), and clear all.
- Expose REST endpoints: `POST /api/documents`, `GET /api/documents`, `DELETE /api/documents/{id}`, `DELETE /api/documents`.
- Add a one-time script to download the embedding model into `models/embeddings/` so runtime never touches the network.

## Capabilities

### New Capabilities
- `document-ingestion`: Parsing, chunking, embedding, and storing uploaded documents locally.
- `document-retrieval`: Finding the most relevant chunks for a query, with citation metadata.
- `document-management`: Listing and deleting user documents and their stored data.

### Modified Capabilities
<!-- none -->

## Impact

- New backend modules: `pha/rag/{parsers,chunker,embedder,store,retriever}.py`, `pha/api/documents.py`.
- New dependencies: chromadb, sentence-transformers, pypdf, python-docx, python-multipart.
- New on-disk data: `data/uploads/`, `data/chroma/`, `models/embeddings/`.
- Depends on `setup-project-foundation`. Independent of `add-medquad-lora-finetune`.
