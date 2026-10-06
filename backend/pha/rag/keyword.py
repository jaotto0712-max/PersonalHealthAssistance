"""Keyword (BM25) ranking over the stored chunks, to sit beside vector search.

Embeddings are weak on exact short names: "TSH", "BUN", "A1C", "urine creatinine". BM25 rewards
chunks that contain the query's rare words. Personal document sets are small (hundreds of
chunks), so the index is rebuilt per query instead of being stored.
"""

import math
import re
from collections import Counter

TOKEN = re.compile(r"[a-z0-9]+(?:[./][a-z0-9]+)*")
STOPWORDS = {
    "a", "an", "and", "are", "be", "did", "do", "does", "for", "how", "i", "in", "is", "it",
    "me", "my", "of", "on", "or", "should", "that", "the", "this", "to", "was", "were", "what",
    "when", "which", "with", "you", "your", "am", "have", "has", "had", "can", "about", "much",
    "many", "there", "their", "they", "too", "result", "results", "level", "levels", "value",
}  # fmt: skip
K1, B = 1.5, 0.75


def tokens(text: str) -> list[str]:
    return [t for t in TOKEN.findall(text.lower()) if t not in STOPWORDS]


def bm25_rank(query: str, documents: list[str]) -> list[tuple[int, float]]:
    """(document index, score) for documents sharing at least one query term, best first."""
    terms = set(tokens(query))
    if not terms or not documents:
        return []
    docs = [Counter(tokens(d)) for d in documents]
    avg_len = sum(sum(d.values()) for d in docs) / len(docs) or 1.0
    n = len(docs)
    df = {t: sum(1 for d in docs if t in d) for t in terms}
    scored = []
    for i, d in enumerate(docs):
        length = sum(d.values())
        score = 0.0
        for t in terms:
            if tf := d.get(t, 0):
                idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
                score += idf * tf * (K1 + 1) / (tf + K1 * (1 - B + B * length / avg_len))
        if score > 0:
            scored.append((i, score))
    return sorted(scored, key=lambda x: x[1], reverse=True)
