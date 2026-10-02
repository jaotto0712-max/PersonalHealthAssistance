## Context

All components exist by this stage. The questions evaluators will ask:
1. Did LoRA help?
2. Did RAG help?
3. Is it safe?
4. Is it really private?
5. Is it fast enough?

Compute is local (Ollama on a Mac), so eval sizes must stay modest (~200 MedQuAD items, ~40 doc QA items, ~60 safety prompts).

```
                    ┌──────────── RAG off ────────────┬──────────── RAG on ─────────────┐
   phi3-base        │ A: baseline                     │ B: base + docs                  │
   phi3-medquad     │ C: LoRA only                    │ D: full system (capstone)       │
                    └─────────────────────────────────┴─────────────────────────────────┘
   MedQuAD test  → A vs C   (does fine-tuning help general medical QA?)
   Doc QA set    → A/C vs B/D (does RAG help personal questions?), B vs D (does LoRA hurt grounding?)
   Safety set    → rule layer only (model-independent)
   Privacy       → D end-to-end with network blocked
```

## Goals / Non-Goals

**Goals:**
- Reproducible numbers from one command.
- Honest reporting, including regressions.
- Artifacts ready for the showcase.

**Non-Goals:**
- Clinical validation or claims of medical accuracy.
- LLM-as-judge with an external API (that would violate local-only). A local judge is optional and out of scope by default.
- Large-scale benchmarks such as MedQA or PubMedQA (possible stretch goal).

## Decisions

**Harness calls the orchestrator in-process**, not over HTTP. This avoids SSE parsing and lets us toggle RAG and model per run. A thin HTTP path is still exercised by the privacy E2E test.

**Each run writes JSONL** (`id, config, question, answer, sources, latency_ms, ttft_ms, tokens`), and metrics are computed in a separate step, so outputs can be re-scored without regenerating. Generation uses temperature 0 and a fixed seed where Ollama supports it.

**MedQuAD subset:** a stratified sample of ~200 items from the leak-free test split, stratified by question type.

**Metrics:**
- ROUGE-L F1
- BERTScore F1, using `roberta-large` or `distilbert-base-uncased` cached locally, chosen by runtime budget

These are imperfect for long-form medical answers, so they are complemented by a human rubric on 30 sampled items per config. Each item is rated on correctness, completeness, and safety (0–2 each) by the student, with configs blinded.

**Doc QA set:** synthetic patient documents (lab panel, discharge summary, medication list, visit note), entirely fictional. Each question has a gold answer string or value and gold `(filename, page)`. The set also includes:
- unanswerable questions (the answer is not in the docs), to test "I couldn't find that"
- distractor questions

Metrics:
- retrieval hit@k (gold page in retrieved chunks)
- citation precision/recall (cited sources vs gold)
- answer correctness (normalized exact or contains match for values; rubric for free text)
- abstention accuracy on unanswerables

**Faithfulness heuristic:** For numeric claims in answers (values with units), check that each one appears in a retrieved chunk. This is a cheap hallucination detector for lab values.

**Safety set:** ~40 emergency paraphrases across categories, plus ~20 hard negatives (negated mentions, past history, informational questions like "what are signs of a stroke?"). Report recall and precision per category. Recall is the priority metric, with a target of ≥95%.

**Latency:** TTFT and tokens/s from Ollama eval stats on the dev machine, reported with hardware specs.

**Privacy E2E:** Start the backend (with real Ollama and the real embedder) in a subprocess and run a pytest session that:
1. installs a socket guard in the backend process via a startup hook enabled by `PHA_NET_GUARD=1`, which raises on and logs any non-loopback connect
2. uploads a fixture doc, chats, and deletes the doc
3. asserts the guard log is empty and the delete removed all traces

Optional manual add-on: run with Wi-Fi off and capture a screen recording for the showcase.

**Report:** `eval/report/build_report.py` renders Markdown (and a static HTML page) with the 2×2 table, per-metric bar charts, safety confusion matrix, latency, and qualitative examples, including failures.

## Risks / Trade-offs

- [Automatic metrics don't capture medical correctness] → Human rubric sample, and report limitations explicitly.
- [Eval run is slow on a laptop (4 configs × ~240 items)] → Cache outputs, allow `--limit`, and run overnight if needed.
- [BERTScore model download violates offline] → Evaluation is a dev-time tool: pre-download once, then run with HF offline mode, same as the app.
- [Self-graded rubric bias] → Blind config labels during grading, and optionally ask a peer to grade a subset.
- [Results show LoRA hurts RAG grounding] → This is still a valid finding: report it and list mitigations (mix context-grounded training data) as future work.

## Open Questions

- Will a mentor or TA provide a grading rubric for the showcase that the report should map to? Mentors are still TBA on the brief.
