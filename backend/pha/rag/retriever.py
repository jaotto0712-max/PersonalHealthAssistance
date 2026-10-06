"""Query-time retrieval: embed the question, search, threshold, and order."""

import re

from pha.rag.embedder import Embedder
from pha.rag.keyword import bm25_rank
from pha.rag.store import StoredHit, VectorStore

# Questions that ask about earlier results may see "history" chunks (older lab values).
# Everything else gets current results only: small models otherwise report old values as current.
HISTORY_QUERY = re.compile(
    r"\b(previous|previously|prior|before|earlier|last time|older|old|trend|trends|change|changed|"
    r"compare|compared|history|over time|used to)\b",
    re.IGNORECASE,
)
# Messages that lean on the previous turn ("What was it last time?", "And my HDL?"): on their
# own they carry nothing to search with, so the previous user message is searched with them.
FOLLOW_UP = re.compile(
    r"\b(it|its|that|this|those|these|they|them)\b|\b(what|how)\s+about\b|^\s*(and|also|so)\b",
    re.IGNORECASE,
)


RRF_K = 60  # reciprocal rank fusion constant (the usual default)


class Retriever:
    def __init__(
        self,
        embedder: Embedder,
        store: VectorStore,
        top_k: int,
        min_score: float,
        keyword: bool = True,
    ):
        self._embedder = embedder
        self._store = store
        self.top_k = top_k
        self.min_score = min_score
        self.keyword = keyword  # fuse BM25 keyword ranking with vector ranking

    def has_documents(self) -> bool:
        return self._store.count() > 0

    def search(
        self, query: str, k: int | None = None, previous: str | None = None
    ) -> list[StoredHit]:
        """`previous`: the user's previous message, used when `query` is a follow-up."""
        if not query.strip() or self._store.count() == 0:
            return []
        k = k or self.top_k
        wants_history = bool(HISTORY_QUERY.search(query))  # the new message decides, not context
        queries = [query]
        if previous and previous.strip() and FOLLOW_UP.search(query):
            # the earlier topic alone, and combined with the new detail ("…last time")
            queries += [previous.strip(), f"{previous.strip()} {query}"]
        vectors = [self._embedder.embed_query(q) for q in queries]
        best: dict[tuple[str, int], StoredHit] = {}
        for vector in vectors:
            for h in self._store.query(vector, k * 3):
                key = (h.doc_id, h.chunk_index)
                if key not in best or h.score > best[key].score:
                    best[key] = h
        if not self.keyword:
            relevant = [h for h in best.values() if self._allowed(h, wants_history)]
            return sorted(relevant, key=lambda h: h.score, reverse=True)[:k]

        # Keyword ranking over all chunks; keyword-only hits get their real cosine similarity
        # so the same floor applies to them.
        chunks = self._store.all_chunks()
        keyword_hits = [
            chunks[i] for i, _ in bm25_rank(" ".join(queries), [c.text for c in chunks])
        ]
        keyword_hits = keyword_hits[: k * 3]
        missing = [h for h in keyword_hits if (h.doc_id, h.chunk_index) not in best]
        for vector in vectors:
            for h in self._store.similarity(vector, missing):
                key = (h.doc_id, h.chunk_index)
                if key not in best or h.score > best[key].score:
                    best[key] = h
        fused: dict[tuple[str, int], float] = {}
        by_vector = sorted(best.values(), key=lambda h: h.score, reverse=True)
        for ranking in (by_vector, keyword_hits):
            for rank, h in enumerate(ranking):
                key = (h.doc_id, h.chunk_index)
                fused[key] = fused.get(key, 0.0) + 1.0 / (RRF_K + rank + 1)
        relevant = [h for h in best.values() if self._allowed(h, wants_history)]
        relevant.sort(key=lambda h: fused.get((h.doc_id, h.chunk_index), 0.0), reverse=True)
        return relevant[:k]

    def _allowed(self, hit: StoredHit, wants_history: bool) -> bool:
        return hit.score >= self.min_score and (wants_history or not hit.history)
