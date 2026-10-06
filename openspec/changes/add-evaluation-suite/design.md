## Context

Models available locally: `phi3-base`, `phi3-medquad` (v1), `phi3-medquad-v2` (current default), all Q4_K_M via Ollama. The pipeline has retrieval over Chroma, column-aware lab extraction with history chunks, rule-based emergency detection, a personal-question notice and a degeneration guard. Compute is a laptop, so sets stay small (records ~45, MedQuAD 200, safety ~60) and runs are cached.

## Decisions

**Run the real pipeline in-process.** `ChatOrchestrator` is built with the real `OllamaBackend(model)` and a `DocumentService` (real bge embedder) over a fresh temporary store holding every fixture document. Retrieval off means `retriever=None`. This measures exactly what users get, including guard stops and notices. The `no_documents` category uses an empty store.

**Item schema (records):** `{id, category, question, history?, expect: {values: [...], not_values?: [...], cite?: filename, absent?: bool, direction?: "high"|"low"|"normal", ambiguous_values?: [...]}}`. Scoring uses the normalized answer (control characters stripped):
- **value:** every expected value appears, and the first number in the answer is the first expected value.
- **not_values:** none appears as the first-stated value. This gives the previous-as-current rate.
- **cite:** a cited source has that filename.
- **direction:** high = high/above/elevated/outside and no claim it's normal (same rules as the grounding probe).
- **absent:** says not found and invents no value with units.
- **ambiguous:** mentions all candidate values, or asks a clarifying question naming the specimens.

**MedQuAD:** 200 items sampled from `data/medquad/test.jsonl`, stratified by question type with a fixed seed, and committed with attribution (CC BY 4.0). Scores:
- ROUGE-L F1 (LCS on lowercase word tokens, implemented directly)
- cosine similarity of bge embeddings between answer and reference

Answers are run closed-book (retrieval off) for every model.

**Safety:** detector-only metrics (deterministic, model-independent), plus a check that emergencies short-circuit the model in the full pipeline (no model call).

**Decoding:** the app's real settings. Grounded requests run at temperature 0; closed-book at 0.2 with seed 0, so runs are reproducible on the same machine.

**Caching:** results are keyed by (set, model, rag, item id, pipeline fingerprint = hash of prompt files + extractor version + model digest). Re-runs only compute missing items. `--fresh` ignores the cache.

**Report:** Markdown with tables per set and model, per-category records accuracy, guard stops, latency, the 5 worst examples per model (question, expected, answer), and environment (hardware, Ollama version, model digests).

## Risks / Trade-offs

- [Small sets, so noisy differences] → Report counts, not just percentages, and flag differences of 1–2 items as within noise.
- [Heuristic scorers can be wrong, as the probe scorer was twice] → Every scorer has unit tests built from real answers, and the report shows raw answers for failures so misjudgments are visible.
- [Fixture overlap with training] → Fixture layouts were deliberately excluded from v2's synthetic data (enforced by a test). MedQuAD items come from held-out topics.
