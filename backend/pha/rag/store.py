"""Persistent local vector store (Chroma) for document chunks."""

from dataclasses import dataclass
from pathlib import Path

import chromadb
from chromadb.config import Settings as ChromaSettings

from pha.rag.chunker import Chunk

COLLECTION = "user_docs"


@dataclass(frozen=True)
class StoredHit:
    text: str
    doc_id: str
    filename: str
    page: int
    chunk_index: int
    score: float  # cosine similarity, higher is more similar


class VectorStore:
    def __init__(self, path: Path):
        path.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(
            path=str(path), settings=ChromaSettings(anonymized_telemetry=False)
        )
        # embedding_function=None: we always pass vectors ourselves. Chroma's default
        # embedding function would otherwise download an ONNX model from the internet.
        self._collection = self._client.get_or_create_collection(
            COLLECTION, configuration={"hnsw": {"space": "cosine"}}, embedding_function=None
        )

    def add(
        self, doc_id: str, filename: str, chunks: list[Chunk], vectors: list[list[float]]
    ) -> None:
        if not chunks:
            return
        self._collection.add(
            ids=[f"{doc_id}:{c.index}" for c in chunks],
            embeddings=vectors,
            documents=[c.text for c in chunks],
            metadatas=[
                {"doc_id": doc_id, "filename": filename, "page": c.page, "chunk_index": c.index}
                for c in chunks
            ],
        )

    def query(self, vector: list[float], k: int) -> list[StoredHit]:
        if self.count() == 0:
            return []
        result = self._collection.query(
            query_embeddings=[vector], n_results=k, include=["documents", "metadatas", "distances"]
        )
        return [
            StoredHit(
                text=text,
                doc_id=str(meta["doc_id"]),
                filename=str(meta["filename"]),
                page=int(meta["page"]),
                chunk_index=int(meta["chunk_index"]),
                score=1.0 - float(distance),
            )
            for text, meta, distance in zip(
                result["documents"][0], result["metadatas"][0], result["distances"][0], strict=True
            )
        ]

    def delete_document(self, doc_id: str) -> None:
        self._collection.delete(where={"doc_id": doc_id})

    def doc_ids(self) -> set[str]:
        metadatas = self._collection.get(include=["metadatas"])["metadatas"] or []
        return {str(m["doc_id"]) for m in metadatas}

    def chunk_count(self, doc_id: str) -> int:
        return len(self._collection.get(where={"doc_id": doc_id}, include=[])["ids"])

    def count(self) -> int:
        return self._collection.count()

    def clear(self) -> None:
        for doc_id in self.doc_ids():
            self.delete_document(doc_id)
