## Why

The fine-tuned model and the document store are independent pieces. The brief's third build phase is "query-time retrieval integrating fine-tuned model outputs with document chunks": one pipeline that retrieves context, builds a grounded prompt, streams an answer with citations, and applies basic health-safety guardrails.

## What Changes

- Add an `LLMBackend` interface with an Ollama implementation that streams tokens from the local `phi3-medquad` model, plus a fake backend for tests.
- Add the chat orchestrator: emergency check → retrieve → build prompt within a token budget → stream generation → attach sources and disclaimer.
- Add a minimal safety layer: rule-based emergency and crisis detection that short-circuits generation with urgent-care guidance, and a disclaimer attached to every response.
- Add `POST /api/chat` streaming Server-Sent Events (`meta`, `token`, `sources`, `done`, `error`), stateless with client-sent history.
- Extend `GET /api/health` to report Ollama reachability and model availability.

## Capabilities

### New Capabilities
- `llm-backend`: Talking to the locally served model, with streaming, timeouts, and availability checks.
- `chat-orchestration`: Combining retrieval, prompt construction, history, and generation into grounded, cited answers.
- `safety-guardrails`: Emergency/crisis detection and mandatory medical disclaimer.
- `chat-api`: The streaming HTTP contract the UI consumes.

### Modified Capabilities
<!-- none: health endpoint extension is captured in llm-backend availability requirement -->

## Impact

- New backend modules: `pha/llm/{base,ollama,fake}.py`, `pha/chat/{orchestrator,prompt}.py`, `pha/safety/{emergency,disclaimer}.py`, `pha/api/chat.py`.
- New dependency: httpx (async streaming to Ollama), sse-starlette.
- Reuses `training/system_prompt.txt` from `add-medquad-lora-finetune` so inference framing matches training.
- Depends on `add-local-document-rag` (retriever) and `add-medquad-lora-finetune` (Ollama model). It can be developed against the fake LLM and `phi3-base` before fine-tuning finishes.
