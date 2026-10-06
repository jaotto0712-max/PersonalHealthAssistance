## Context

v1 results are in `training/model_card.md`. Validation loss improved (0.907 → 0.859), but grounded answering got worse than the base model. The app always runs in RAG mode: the system prompt carries numbered excerpts when retrieval finds any. v1 never saw that format, so the fine-tuned prior overrides the excerpts.

## Goals / Non-Goals

**Goals:**
- A fine-tuned model that is at least as grounded as `phi3-base`: it reads values from excerpts, compares them to reference ranges correctly, cites `[n]`, and says when something isn't in the documents.
- Keep the MedQuAD style gains; remove boilerplate and question-echo.
- Train and serve with identical prompt text.

**Non-Goals:**
- Fixing rare-disease factual accuracy, which is inherent to a 3.8B model. The evaluation suite measures it.
- Changing the app's retrieval or UI.

## Decisions

**Prompt text in files, loaded by both sides.** `training/system_prompt.txt` already works this way. `rag_instructions.txt` and `no_context_instructions.txt` follow. The training script re-implements the excerpt formatter (it is stdlib-only), and a backend test asserts its output equals `pha.chat.prompt.format_excerpts` for the same chunks.

**Template cleaning rules** (each is counted in `stats.json`):
- Drop answers that start with "These resources address the diagnosis or management" (GHR).
- Drop answers containing "Human Phenotype Ontology provides the following list" (GARD tables with made-up-looking percentages).
- If an answer starts with a question sentence ending in `?`, strip that sentence when the rest is still at least the minimum length.

**RAFT mix per MedQuAD record (seeded):**

| Share | Type | System prompt | Target |
|---|---|---|---|
| 45% | closed-book | base + no-context instructions | answer |
| 40% | oracle | base + RAG instructions + excerpts | gold chunks cited as `[n]` |
| 15% | distractor-only | base + RAG instructions + excerpts | "I couldn't find this in your documents." + answer |

- Oracle excerpts contain the gold passage, split into ≤800-character chunks the way the app chunks, plus 2 distractor chunks from *other focus groups in the same split* (no cross-split leakage), in shuffled order. The target reproduces the gold text with `[n]` after each chunk's content.
- Excerpt filenames and pages look like uploads: `<source>-<focus-slug>.pdf, p.N`.

**Synthetic personal records** (`synthetic_records.py`, seeded, fictional):
- **Lab panels:** 18 analytes with units, reference ranges and HIGH/LOW flags, in 3 layouts (dotted table, `Name: value unit (ref …)`, CSV-like).
- **Medication lists:** drug, dose, frequency, reason, and allergies.
- **Visit notes:** vitals and plan.
- **Questions:** value lookup, "is it high or low?", dose, allergy, vital sign. 20% ask about something absent from the documents.
- Answers state the value, the reference range and the correct direction (high/low/normal), with the citation. The direction is computed, never sampled, and unit-tested.
- Volume: 2,500 train, 250 val. Every example also includes 1–2 distractor documents.
- Layouts deliberately differ from `eval/fixtures` (no dotted lab tables, no pipe medication tables; enforced by a test), as do the patient names. The evaluation suite must use its own held-out layouts, so these overlap only in topic.

**Excerpt cap and lengths (measured):** the app retrieves `top_k=4` chunks, so a grounded example has at most 4 excerpts: up to 3 gold chunks, filled up with distractors. With that cap, the Phi-3 token lengths of the v2 train set are median 825, p95 1464 and max 1988. At 1536, 3.5% would be dropped, mostly long-passage oracle examples, which would bias the mix. **v2 therefore uses `max_length=2048`** and drops nothing. The validation pass is capped at 800 examples (`eval_subset`) to keep each evaluation around 5 minutes.

**Output:** `data/medquad-v2/`, plus a notebook preset `V2 = True` (`data_dir`, `output_dir=…/phi3-medquad-v2`, `max_length=2048`, `per_device_eval_batch_size=4`, `eval_subset=800`). The model exports as `phi3-medquad-v2` with `models/Modelfile.medquad-v2`.

**Acceptance gate:** `training/grounding_probe.py` runs a fixed set of record questions with known answers (value present, direction, absence) against Ollama models, and reports exact-value hits, correct direction, citations, and correct "not found". v2 becomes the app default only if it is ≥ `phi3-base` on the probe, with the full comparison in `add-evaluation-suite`.

## Risks / Trade-offs

- [Extractive answers: copying passages with citations] → Intended for record questions. Closed-book examples (45%) keep the free-form style.
- [Synthetic records are templated; the model may overfit the layouts] → 3 layouts, random analyte subsets and orders, and evaluation on held-out layouts.
- [Longer sequences: slower training, more memory] → v2 has about 2× the tokens of v1 (median 825 vs ~400 per example), so expect about 3.5–4 h on 2× L4. Batch 4 per GPU at up to 2048 tokens fits in 4-bit on an L4. If memory runs out, fall back to 2 per GPU with 4 accumulation steps.
- [The model says "couldn't find" too often] → Only 15% distractor-only and 20% absent-record examples; the probe measures false "not found".

## Open Questions

- Whether 1 epoch is enough for the mixed data. The probe and validation loss decide whether a second epoch is worth it.
