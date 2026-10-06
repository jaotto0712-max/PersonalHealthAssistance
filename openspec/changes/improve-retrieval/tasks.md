## 1. Measurement first

- [x] 1.1 Add 6 follow-up record questions (before any retrieval change)
- [x] 1.2 Baseline: run them on the current retriever for all three models

## 2. Follow-up context

- [x] 2.1 Detect follow-ups (reference words, short messages) and search with the previous user message too; merge by best score
- [x] 2.2 Unit tests: follow-up retrieves the earlier topic's excerpt; a new topic isn't polluted
- [x] 2.3 Re-run `records`; report before/after

## 3. Keyword search

- [x] 3.1 BM25 over stored chunks, fused with vector results; similarity floor still applies
- [x] 3.2 Unit tests: exact short names (TSH, BUN) rank their chunk first
- [x] 3.3 Re-run `records`; keep only if no category regresses
