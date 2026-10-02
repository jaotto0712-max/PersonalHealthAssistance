"""Query-time retrieval: embed the question, search, threshold, and order."""

from pha.rag.embedder import Embedder
from pha.rag.store import StoredHit, VectorStore


class Retriever:
    def __init__(self, embedder: Embedder, store: VectorStore, top_k: int, min_score: float):
        self._embedder = embedder
        self._store = store
        self.top_k = top_k
        self.min_score = min_score

    def search(self, query: str, k: int | None = None) -> list[StoredHit]:
        if not query.strip() or self._store.count() == 0:
            return []
        hits = self._store.query(self._embedder.embed_query(query), k or self.top_k)
        relevant = [h for h in hits if h.score >= self.min_score]
        return sorted(relevant, key=lambda h: h.score, reverse=True)
