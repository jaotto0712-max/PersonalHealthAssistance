## 1. LLM backend

- [x] 1.1 Define `LLMBackend` protocol (`stream`, `health`) in `pha/llm/base.py`
- [x] 1.2 Implement `OllamaBackend` with httpx async streaming to `/api/chat`, options (`num_ctx`, `num_predict`, `temperature`), timeouts, cancellation
- [x] 1.3 Implement `FakeLLM` for tests; select backend via settings
- [x] 1.4 Extend `/api/health` with Ollama reachability and model-installed check (`/api/tags`)

## 2. Safety layer

- [x] 2.1 Implement `pha/safety/emergency.py` with categorized patterns and negation window
- [x] 2.2 Write fixed urgent-care messages per category (911 / ER; 988 for self-harm)
- [x] 2.3 Implement `pha/safety/disclaimer.py` constant and include no-diagnosis/no-prescribing rules in system prompt
- [x] 2.4 Unit tests: ≥30 positive paraphrases across categories, ≥15 negatives including negated mentions

## 3. Prompt and orchestration

- [x] 3.1 Implement `pha/chat/prompt.py`: load shared system prompt, add RAG instructions, numbered excerpt block, history
- [x] 3.2 Implement token budget estimator and trimming (oldest history first, then lowest-score chunks)
- [x] 3.3 Implement `pha/chat/orchestrator.py`: emergency check → retrieve → build → stream → parse `[n]` → sources → done
- [x] 3.4 Unit tests with FakeLLM: grounded prompt contents, empty retrieval path, trimming, citation parsing, no disk writes

## 4. Chat API

- [x] 4.1 Add request/response models and validation (message length, history caps, roles)
- [x] 4.2 Implement `POST /api/chat` SSE with `meta`/`token`/`sources`/`done`/`error` events via sse-starlette
- [x] 4.3 Cancel upstream generation on client disconnect
- [x] 4.4 API tests: event order, emergency flow, 422 validation, llm_unavailable error, all under socket guard

## 5. Manual verification

- [x] 5.1 With Ollama running `phi3-medquad` (or `phi3-base` interim), upload a fixture lab report and verify a cited answer via curl
- [x] 5.2 Measure time-to-first-token and tokens/sec on the dev machine and record in README
