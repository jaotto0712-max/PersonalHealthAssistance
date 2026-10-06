"""Persistent local vector store (Chroma) for document chunks."""

import dataclasses
from dataclasses import dataclass
from pathlib import Path

import chromadb
from chromadb.config import Settings as ChromaSettings

from pha.rag.chunker import Chunk
from pha.rag.lab_tables import HISTORY_PREFIX

COLLECTION = "user_docs"


@dataclass(frozen=True)
class StoredHit:
    text: str
    doc_id: str
    filename: str
    page: int
    chunk_index: int
    score: float  # cosine similarity, higher is more similar
    history: bool = False  # older (non-current) lab results


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
                {
                    "doc_id": doc_id,
                    "filename": filename,
                    "page": c.page,
                    "chunk_index": c.index,
                    "history": c.text.startswith(HISTORY_PREFIX),
                }
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
                history=bool(meta.get("history", False)),
            )
            for text, meta, distance in zip(
                result["documents"][0], result["metadatas"][0], result["distances"][0], strict=True
            )
        ]

    def all_chunks(self) -> list[StoredHit]:
        """Every stored chunk (score 0): the keyword index is built from these."""
        got = self._collection.get(include=["documents", "metadatas"])
        return [
            StoredHit(
                text=text,
                doc_id=str(meta["doc_id"]),
                filename=str(meta["filename"]),
                page=int(meta["page"]),
                chunk_index=int(meta["chunk_index"]),
                score=0.0,
                history=bool(meta.get("history", False)),
            )
            for text, meta in zip(got["documents"] or [], got["metadatas"] or [], strict=True)
        ]

    def similarity(self, vector: list[float], hits: list[StoredHit]) -> list[StoredHit]:
        """The same hits with their cosine similarity to `vector` filled in."""
        if not hits:
            return []
        ids = [f"{h.doc_id}:{h.chunk_index}" for h in hits]
        got = self._collection.get(ids=ids, include=["embeddings"])
        by_id = dict(zip(got["ids"], got["embeddings"], strict=True))
        norm_q = sum(v * v for v in vector) ** 0.5 or 1.0
        out = []
        for h, chunk_id in zip(hits, ids, strict=True):
            e = by_id[chunk_id]
            norm_e = sum(v * v for v in e) ** 0.5 or 1.0
            cosine = sum(a * b for a, b in zip(vector, e, strict=True)) / (norm_q * norm_e)
            out.append(dataclasses.replace(h, score=float(cosine)))
        return out

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
