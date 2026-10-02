"""Test helpers: a deterministic fake embedder and a service wired to temp storage."""

import math
import re
import zlib
from pathlib import Path

from pha.config import REPO_ROOT
from pha.rag.registry import Registry
from pha.rag.service import DocumentService
from pha.rag.store import VectorStore

FIXTURES = REPO_ROOT / "eval" / "fixtures" / "docs"


class HashingEmbedder:
    """Bag-of-words hashed into a fixed vector: shared words => higher cosine similarity."""

    def __init__(self, dims: int = 512):
        self.dims = dims

    def _embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dims
        for token in re.findall(r"[a-z0-9]+", text.lower()):
            vec[zlib.crc32(token.encode()) % self.dims] += 1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


def make_service(root: Path, embedder=None, **overrides) -> DocumentService:
    params = dict(
        chunk_size=800,
        chunk_overlap=120,
        max_upload_bytes=20 * 1024 * 1024,
        top_k=4,
        min_score=0.1,  # the hashing embedder's scale, not the real model's
    )
    params.update(overrides)
    return DocumentService(
        embedder=embedder or HashingEmbedder(),
        store=VectorStore(root / "chroma"),
        registry=Registry(root / "documents.json"),
        uploads_dir=root / "uploads",
        **params,
    )


def fixture_bytes(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()
