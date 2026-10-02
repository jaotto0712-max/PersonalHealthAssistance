"""Embedding models. All implementations return L2-normalized vectors."""

from pathlib import Path
from typing import Protocol

# BGE v1.5 retrieves better when queries (not passages) carry this instruction.
BGE_QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "


class Embedder(Protocol):
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class EmbeddingModelMissing(RuntimeError):
    pass


class SentenceTransformerEmbedder:
    """Loads a sentence-transformers model from a local directory (never from the network)."""

    def __init__(self, model_dir: Path, query_instruction: str = BGE_QUERY_INSTRUCTION):
        if not (model_dir / "config.json").is_file():
            raise EmbeddingModelMissing(
                f"Embedding model not found at {model_dir}. "
                "Run `uv run python scripts/fetch_embeddings.py` in backend/ once."
            )
        from sentence_transformers import SentenceTransformer  # heavy import, deferred

        self._model = SentenceTransformer(str(model_dir), local_files_only=True)
        self._query_instruction = query_instruction

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors = self._model.encode(texts, normalize_embeddings=True, batch_size=32)
        return vectors.tolist()

    def embed_query(self, text: str) -> list[float]:
        vector = self._model.encode(self._query_instruction + text, normalize_embeddings=True)
        return vector.tolist()
