## Context

This is the point where the fine-tuned model and retrieval meet. Constraints:
- Phi-3-mini-4k has about 4096 tokens shared by system prompt, context, history, and answer.
- Ollama serves at `127.0.0.1:11434`.
- The UI needs token streaming plus structured metadata (sources, safety flags).

```
 POST /api/chat {message, history[]}
        │
        ▼
 ┌──────────────────┐  emergency?  ┌───────────────────────────────────┐
 │ safety.emergency │─────yes─────▶│ stream fixed urgent-care message  │──▶ done
 └────────┬─────────┘              └───────────────────────────────────┘
          no
          ▼
 retriever.search(message) ──▶ chunks[0..k] (may be empty)
          │
          ▼
 prompt.build(system, chunks→[1]..[k], trimmed history, message)  ≤ budget
          │
          ▼
 llm.stream(prompt) ──token──token──token──▶ SSE "token" events
          │
          ▼
 SSE "sources" (only chunks actually cited, else all retrieved) ─▶ SSE "done" {disclaimer}
```

## Goals / Non-Goals

**Goals:**
- Grounded answers that cite the user's documents when relevant.
- Graceful behavior when no documents match.
- A first token in under about 2 s on Apple Silicon.

**Non-Goals:**
- Server-side conversation persistence (the client holds history).
- Agentic tool use, query rewriting, or multi-hop retrieval.
- ML-based safety classifiers. The rules are intentionally simple and transparent.

## Decisions

**Ollama `/api/chat` with `stream: true` over httpx.AsyncClient.** It is native to Ollama and supports a messages array, so Ollama applies the Modelfile template. Alternative: the OpenAI-compatible endpoint. It works too, but the native API exposes `num_ctx` and eval stats, which are useful for evaluation.

**An `LLMBackend` protocol** (`stream(messages, options) -> AsyncIterator[str]`, `health()`). It has an Ollama implementation and a `FakeLLM` for deterministic tests. The model name comes from settings, so `phi3-base` and `phi3-medquad` can be swapped for evaluation.

**Prompt layout:**
- system = the shared persona from `training/system_prompt.txt` plus RAG instructions ("Use the numbered excerpts from the user's documents when relevant. Cite as [n]. If the excerpts don't contain the answer, say so and answer from general knowledge. Never invent values from the user's records.")
- context block = "User documents:\n[1] (labs.pdf, p.2) …"
- then trimmed history, then the user message

Context is placed in the *system* turn rather than the user turn, which keeps the user message identical to training. This is to be validated by evaluation. The alternative is context in the user turn.

**Token budget (approximate, from a chars/4 heuristic or the tokenizer from GGUF metadata):**
- system + instructions: ~350
- context: ≤1600
- history: ≤900 (most recent turns first, dropping the oldest)
- answer reserve: 768 (`num_predict`)
- `num_ctx` = 4096

If the context overflows, the lowest-scoring chunks are dropped first.

**Citations:** The model is asked to cite with `[n]`. After generation, the orchestrator parses `[n]` markers and emits the `sources` event, marking the cited chunks. If none were cited, all retrieved chunks are sent as "related". Sources are sent after the tokens, so the UI can link the markers.

**Emergency detection:** a curated regex/phrase list covering:
- chest pain or pressure
- trouble breathing
- stroke signs (FAST)
- severe bleeding
- suicidal ideation or self-harm
- overdose or poisoning
- anaphylaxis
- loss of consciousness
- seizure

Each pattern maps to a category. A match short-circuits the LLM and returns a fixed message: call 911 or go to the nearest ER; for self-harm, also call or text 988 (Suicide & Crisis Lifeline). The response is flagged `emergency: true` with the category in `meta`.

Alternative: LLM-based classification. Rejected because it's slower, less predictable, and harder to test. Rules favor recall, and a false positive only adds a care prompt.

Negation like "no chest pain" is handled with a short negation window to reduce false positives. Ambiguous cases still trigger.

**Disclaimer:** A constant string included in the `done` event (and shown persistently in the UI). The backend always sends it, so API consumers can't miss it.

**SSE via sse-starlette.** Events:
- `meta {emergency, retrieved_count, model}`
- `token {text}` (repeated)
- `sources {items:[{n, doc_id, filename, page, score, snippet, cited}]}`
- `done {disclaimer, usage}`
- `error {code, message}`

Alternative: WebSockets. That's more complexity than a one-way stream needs.

**Stateless API:** The client sends `history` (last N turns). The server validates and caps it. This keeps the backend simple and leaves chats only in browser memory, which is good for privacy.

## Risks / Trade-offs

- [The small model ignores citation instructions or hallucinates values] → Use explicit instructions with low temperature (0.2). Evaluation measures citation and faithfulness, and the UI always shows sources for user verification.
- [Fine-tuning on MedQuAD (no context) weakens context-following] → Evaluation compares LoRA+RAG with base+RAG. If it regresses, consider mixing a small context-grounded set into training (follow-up).
- [Emergency keyword list misses phrasing] → Favor broad patterns, unit-test many paraphrases, and keep the persistent UI banner with 911 as a backstop.
- [Ollama not running] → `/api/health` reports it, and `/api/chat` returns an `error` event with code `llm_unavailable` and a fix-it hint.
- [Token estimate drift] → A conservative budget, and `num_ctx` is set explicitly.

## Open Questions

- Should emergency messages *also* include a model answer below the warning? Proposed: no for self-harm or overdose; possibly for others later.
