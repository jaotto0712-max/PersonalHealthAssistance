## Why

Retrieval embeds only the latest message. A follow-up such as "What number should it be below?"
or "What was it last time?" has nothing in it to search with, so the right excerpt is not found.
The model then answers from general knowledge: in the evaluation, v2 answered the LDL follow-up
with general guidelines (130, 70) instead of the report's < 100. Embeddings are also weak on exact
short names (TSH, BUN, A1C, "urine creatinine"), the most common words in record questions.

## What Changes

- **Follow-up context:** when a message refers back ("it", "that", "last time", "what about…"),
  retrieval also searches with the previous user message. Results from both searches are merged
  by score. Prompts are unchanged; only what is retrieved changes.
- **Keyword search beside embeddings:** a small BM25 index over the stored chunks, fused with
  the vector results (reciprocal rank fusion). Keyword-only hits still have to pass the
  similarity floor, so unrelated chunks that share one word are not added.
- Both are measured on the `records` set, which gains 6 follow-up questions written before the
  change. Keyword search is kept only if it doesn't regress any category.

## Impact

- Code: `backend/pha/rag/retriever.py`, `backend/pha/rag/store.py`, `backend/pha/chat/orchestrator.py`.
- Eval: `eval/sets/records.jsonl` (+6 follow-ups).
