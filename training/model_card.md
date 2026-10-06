# Model card: phi3-medquad-v2 (and v1)

**Status:** `phi3-medquad-v2` is the **app default** (2026-10-06). It matches or beats the
unmodified base model on every grounding-probe measure. The first fine-tune, `phi3-medquad` (v1),
learned MedQuAD's style but ignored the user's documents. It is kept only as the comparison that
motivated v2 (`openspec/changes/archive/2026-10-06-add-grounded-finetune-v2`).

Reports: `training/results/training_config.json` (v1), `training/results/v2/training_config.json`
(v2). Samples: `training/results/qualitative_samples.json`, `training/results/v2/qualitative_samples.json`.
Probe answers: `training/results/grounding_probe_v1.json`, `training/results/grounding_probe_v2.json`,
and `training/results/grounding_probe_v3.json` (adds column-layout lab questions).

## Summary

| | v1 `phi3-medquad` | **v2 `phi3-medquad-v2`** |
|---|---|---|
| Base model | [`microsoft/Phi-3-mini-4k-instruct`](https://huggingface.co/microsoft/Phi-3-mini-4k-instruct) (3.8B, MIT) | same |
| Method | QLoRA (4-bit NF4 base) | LoRA on a bf16 base |
| Training data | MedQuAD, closed-book Q&A | template-cleaned MedQuAD in the app's retrieval format (RAFT-style) + synthetic personal records |
| Served as | GGUF Q4_K_M via Ollama (~2.3 GB) | GGUF Q4_K_M via Ollama (~2.3 GB) |
| Baseline | `phi3-base`: same base and quantization, no adapter | same |

Built for the UF AI Passport, Clinical Application track, Project 7 (student capstone).

## Intended use

General, consumer-level health *information* inside the Personal Health Assistant. The app runs
fully on the user's device and grounds answers in the user's own documents (RAG). The model is
**not** a medical device and must not be used for diagnosis, treatment decisions, or emergencies.
The app adds a rule-based emergency check and a mandatory disclaimer around it.

**Out of scope:** clinical decision support, prescribing or dosing advice, use without a human
clinician in the loop for any personal medical decision, and non-English input.

## Data

MedQuAD: Ben Abacha A. & Demner-Fushman D., *"A question-entailment approach to question
answering."* BMC Bioinformatics 20, 511 (2019). https://github.com/abachaa/MedQuAD (CC BY 4.0),
pinned at commit `577bd37`. NIH sources: GARD, GHR, MedlinePlus, NIDDK, NINDS, NHLBI, CDC,
CancerGov, NIHSeniorHealth.

Preparation (`training/prepare_medquad.py`, deterministic, seed 13):

| Step | v1 | v2 (`--clean-templates --grounded`) |
|---|---|---|
| Raw Q&A pairs | 47,441 | 47,441 |
| Dropped: empty answers (removed for copyright) / short / duplicate | 31,034 / 12 / 48 | same |
| Dropped: GHR "These resources address…" lists | — | 1,085 |
| Dropped: GARD Human Phenotype Ontology symptom tables | — | 2,239 |
| Leading restated question stripped (kept) | — | 1,767 |
| MedQuAD records kept | 16,347 | 13,023 |
| Train / validation / test | 13,079 / 1,645 / 1,623 | 12,953 / 1,523 / 1,297 (train/val include 2,500 / 250 synthetic) |

- **Leak-free split (both):** whole *focus topics* (e.g. a disease) go to one split, so the test
  set measures generalization to unseen conditions.
- **v2 training mix** (train split): 4,730 closed-book (no excerpts), 4,152 *oracle* (the answer
  passage among distractor excerpts; the target cites `[n]`), 1,571 *distractor-only* (target:
  "I couldn't find information about this in your documents…" then a general answer), and 2,500
  *synthetic records*. Prompts are byte-identical to the app's (`training/prompt_format.py`,
  enforced by `backend/tests/test_prompt_parity.py`). Distractors come only from the same split,
  and at most 4 excerpts are used per example (the app's `top_k`).
- **Synthetic records** (`training/synthetic_records.py`): fictional lab panels (18 analytes,
  3 layouts), medication lists and visit notes. Questions cover values, high/low checks, doses,
  allergies, vitals, and absent items (20%). Every high/low statement is computed from the
  displayed value and unit-tested. Layouts deliberately differ from `eval/fixtures`, so the probe
  below is held-out.
- **Length:** v1 drops examples over 1,024 tokens (53); v2 uses 2,048 tokens and drops none.

## Training

| | v1 | v2 |
|---|---|---|
| LoRA rank / alpha / dropout; targets | 16 / 32 / 0.05; `qkv_proj o_proj gate_up_proj down_proj` | same |
| LR / schedule / warmup / epochs | 2e-4 / cosine / 3% / 1 | same |
| Base precision | 4-bit NF4 (QLoRA) | **bf16** (`load_in_4bit=False`) |
| Batch | 4 per GPU × 2 accumulation × 2 GPUs = 16 | 2 per GPU × 4 accumulation × 2 GPUs = 16 |
| Max sequence length | 1,024 | 2,048 |
| Optimizer | paged 8-bit AdamW | AdamW (the paged optimizer crashed under DDP on the L4s) |
| Hardware | HiPerGator `hpg-turin`, 2× L4, DDP | same |
| Steps (best checkpoint) | 815 (800) | 810 (800) |
| Validation loss (best) | 0.859 | 0.533 |
| Final train loss | 0.860 | 0.596 |

Validation losses are **not comparable** between versions: the datasets differ, and v2 targets
include extractive, cited answers that are easier to predict. v1 and v2 also differ in base
precision (4-bit vs bf16) as well as data, so the improvement can't be credited to data alone.
Held-out test metrics (ROUGE-L and embedding similarity on 200 MedQuAD test questions) and
the 43-question record benchmark are in [`eval/report/REPORT.md`](../eval/report/REPORT.md).

## Grounding probe (record questions): the acceptance gate

`training/grounding_probe.py` sends 14 questions about the evaluation fixtures (layouts never seen
in training) to each model in the app's exact prompt format, greedy decoding. 11 questions have
an answer in the documents; 3 ask about items that aren't there. A direction is counted only when
the correct value is also stated. Text is normalized as the app shows it (control characters
stripped).

| Model | Exact value | High/normal call | Cites right excerpt | Says "not found" |
|---|---|---|---|---|
| `phi3-base` | 11/11 | 6/7 | 9/11 | 3/3 |
| `phi3-medquad` (v1) | 2/11 | 1/7 | 1/11 | 1/3 |
| **`phi3-medquad-v2`** | **11/11** | **7/7** | **11/11** | **3/3** |

The base model's one direction error: HDL 48 mg/dL "falls below the recommended range of over 40".
v2: "48 mg/dL [1], which is within the reference range (>40)".

**Full app, real retrieval** (fixture documents uploaded, `phi3-medquad-v2`): LDL "Yes… 162 mg/dL
[1], which is above the reference range (<100)"; A1C 6.1 % above < 5.7 %; atorvastatin 20 mg
nightly; penicillin allergy. All exact and cited. A follow-up ("Is that A1C in the diabetes
range?") used the history correctly. Questions with no relevant documents get "I couldn't find…"
plus a general answer, and absent lab values are never invented. Time to first token: 0.1–0.9 s on
an Apple M3 Max. (v1 on the same setup called that LDL "in the desirable range".)

## Output quality (20 held-out closed-book questions, unseen diseases)

| | `phi3-base` | v1 | v2 |
|---|---|---|---|
| Leaked template tokens | 0 | 0 | 0 |
| Stopped naturally (≤ 512 tokens) | 16/20 | 17/20 | **19/20** |
| Boilerplate or echoed question | 0/20 | 5/20 | **0/20** |
| Looping answers (> 15% repeated 4-word sequences) | 0/20 | 1/20 | 2/20 |

- **v2 fixed v1's template copying**: no resource lists, symptom tables or restated questions. It
  keeps concise, plain reference style and no longer over-refuses.
- **Rare-disease facts remain unreliable** in all three models (e.g. v1: juvenile primary
  osteoporosis → COL1A1, but it's LRP5; base: vitamin D-dependent rickets → PHEX, wrong; v2 got
  that one right). This is expected at 3.8B parameters; it's why the app grounds answers in the
  user's documents and shows sources.

## Evaluation suite (2026-10-06)

Full results, with every failure and its raw answer, are in
[`eval/report/REPORT.md`](../eval/report/REPORT.md). Every number comes from the real app pipeline
(retrieval, prompts, guard, safety rules) on an Apple M3 Max.

| | `phi3-base` | v1 | **v2** |
|---|---|---|---|
| Record questions, with documents (49) | 40 (82%) | 11 (22%) | **42 (86%)** |
| Record questions, no retrieval (49) | 7 | 7 | 6 |
| Follow-up questions (9, part of the 49) | **8** | 3 | 4 |
| Previous result reported as current | 0/11 | 0/11 | 0/11 |
| MedQuAD ROUGE-L / embedding similarity (200) | 0.155 / 0.856 | 0.167 / 0.845 | 0.174 / 0.846 |
| Guard stops (249 answers) | 6 | 44 | 26 |
| Time to first text / tokens per second | 0.70 s / 88 | 0.56 s / 87 | 0.50 s / 88 |

- **v2 is the best model on the user's records.** It gets every value, citation, current vs
  previous and same-name question right. Without retrieval all models score about 13%, so the
  gain comes from reading the documents, not from memorized facts.
- **v2 is weak in multi-turn follow-ups (4/9; base 8/9).** The right excerpt is retrieved, but v2:
  - ignores it ("What was it last time?" with only the older BUN result retrieved: "I couldn't
    find any older creatinine or eGFR result")
  - quotes general thresholds instead of the report (LDL: 160/240 rather than the report's < 100)
  - drops citation markers

  Its training examples were single-turn, so this needs multi-turn v3 data.
- **What changed after the first run** (on the original 43 questions, v2 38 → 40):
  - **Same-name tests:** blood and urine creatinine are labelled by specimen. When a question
    doesn't say which, the app adds a note listing both values. No extraction wording made v2
    mention both by itself (a 4-variant probe), so the app states it.
  - **"Not established" ranges:** now a separate sentence ("The lab gives no reference range
    for this test."). v2 still writes "within the reference range" for that test, a training
    template that needs v3 data.
  - **Retrieval:** follow-ups also search with the previous user message, and BM25 keyword
    ranking is fused with vectors. Neither changed a score on this set. Follow-up search
    changed which excerpts were retrieved, but the misses above are the model's. Keyword search
    changed 1 of 49 retrievals: the 5-document fixture set is too small to show a benefit.
    Both are kept (no regression).
- **Remaining v2 misses (7/49) are model errors, not scorer mistakes:** the five follow-ups above,
  the no-range wording, and metformin. For metformin, v2 correctly says it isn't listed, then
  gives general dosing (out of scope, with a garbled number).
- **General answers barely differ** between models (similarity 0.845–0.856, within noise).
  Fine-tuning changed answer style, not medical knowledge.
- **v2 imitates MedQuAD's "Key Points" format.** That format repeats its points as headings, and
  the guard stops those answers at the repeat (25 of 200 MedQuAD answers). Users see no
  repetition, but the answers are shorter than ideal.
- **Safety rules (model-independent):** the first rules caught 30 of 34 emergencies (target 95%).
  The misses were indirect phrasings, including self-harm ("I'm thinking of taking all my pills
  to end it"). The rules were broadened by mechanism: verb forms, "can barely breathe", "chest
  feels tight", intent phrases. They were checked on 21 new phrasings, including dosing
  look-alikes such as "should I take all my pills at once in the morning?". Now: 45/45 caught,
  1 false alarm in 28 ("suicide prevention training", accepted). That is optimistic, because
  the new phrasings were written alongside the fix.

## Limitations and risks

- **Small, quantized model:** can be wrong while sounding confident. The app shows the cited
  sources so users can check answers against their own records.
- **Record answers follow templates:** v2 answers record questions in a fixed, extractive pattern
  learned from the synthetic data ("According to your lab report, your X was …"), and sometimes
  uses the synthetic analyte names (e.g. "vitamin D, 25-hydroxy"). It's accurate, but it may be
  terser than ideal (e.g. it didn't add "prediabetes" when asked whether 6.1 % is in the diabetes
  range).
- **Degeneration in long answers without documents:** looping in 5/36 samples (`phi3-base`: word
  salad in 2/36). The app's degeneration guard (`backend/pha/chat/guard.py`) stops such answers
  before the repeated or garbled text is shown; in a live check of 36 answers, users saw 0 loops.
- **General answers can contain confident nonsense** (e.g. calling systolic pressure "the first,
  upper, or left heart sound"). The guard catches form, not facts. Answers from the user's own
  documents (the probe above) are far more reliable than general answers.
- **No "I can't see your records" from the model:** neither model reliably says it lacks the
  user's documents when none are retrieved (0/12 each). The app adds that sentence itself for
  personal questions.
- **Rare stray bytes:** v2 emitted one control character inside a word in 14 probe answers. The
  backend strips C0/C1 control characters from streamed tokens.
- **Real lab reports:** the app extracts column-layout lab tables (current vs previous results)
  and keeps older values out of plain questions. On one real commercial lab report, 10 of 11
  record questions were correct. The miss was a report listing two tests with the same name
  (blood and urine creatinine), where the model answered with the urine value. It also tends to
  say "above the range" when the reference is "not established".
- **Coverage gaps:** MedQuAD's medication and supplement subsets had no answers in the public
  release, so drug knowledge comes from the base model.
- **Dated content:** NIH pages were collected around 2017–2019.
- **No safety fine-tuning:** emergencies and crises are handled by rules in the app.
- **Not medical advice.** Always consult a qualified clinician.

## Reproduce

```bash
backend/.venv/bin/python training/prepare_medquad.py --download --out data/medquad-v2 \
  --clean-templates --grounded --synthetic-train 2500 --synthetic-val 250
# GPU: training/train_lora.ipynb with V2 = True (HiPerGator guide: training/hpc/README.md)
cd models && ollama create phi3-medquad-v2 -f Modelfile.medquad-v2 && ollama create phi3-base -f Modelfile.base
backend/.venv/bin/python training/grounding_probe.py phi3-base phi3-medquad-v2
```
