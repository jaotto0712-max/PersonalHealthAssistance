# Model card: phi3-medquad-v3 (and v2, v1)

**Status:** `phi3-medquad-v3` is the **app default** (2026-10-07). It answers 54 of 57 record
questions correctly (v2 46, base 47), including all 8 held-out follow-up questions, and keeps v2's
perfect grounding-probe score. v3 is v2 plus multi-turn conversations and the app's exact
document format (`openspec/changes/add-grounded-finetune-v3`). v2 (`phi3-medquad-v2`) was the
default until then. The first fine-tune, `phi3-medquad` (v1), learned MedQuAD's style but ignored
the user's documents. It is kept only as the comparison that motivated v2
(`openspec/changes/archive/2026-10-06-add-grounded-finetune-v2`).

Reports: `training/results/training_config.json` (v1), `training/results/v2/` and
`training/results/v3/` (`training_config.json`, `qualitative_samples.json`). Probe answers:
`training/results/grounding_probe_v1.json`, `grounding_probe_v2.json`, `grounding_probe_v3.json`
(probe revision 3, which adds column-layout lab questions; base and v2) and
`training/results/v3/grounding_probe.json` (the same probe; base, v2 and v3).

## Summary

| | v1 `phi3-medquad` | v2 `phi3-medquad-v2` | **v3 `phi3-medquad-v3`** |
|---|---|---|---|
| Base model | [`microsoft/Phi-3-mini-4k-instruct`](https://huggingface.co/microsoft/Phi-3-mini-4k-instruct) (3.8B, MIT) | same | same |
| Method | QLoRA (4-bit NF4 base) | LoRA on a bf16 base | same as v2 |
| Training data | MedQuAD, closed-book Q&A | template-cleaned MedQuAD in the app's retrieval format (RAFT-style) + synthetic personal records | v2 + multi-turn conversations, the app's lab extraction format, "Key Points" summaries removed |
| Served as | GGUF Q4_K_M via Ollama (~2.3 GB) | same | same |
| Baseline | `phi3-base`: same base and quantization, no adapter | same | same |

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

| Step | v1 | v2 (`--clean-templates --grounded`) | v3 (`… --v3`) |
|---|---|---|---|
| Raw Q&A pairs | 47,441 | 47,441 | 47,441 |
| Dropped: empty answers (removed for copyright) / short / duplicate | 31,034 / 12 / 48 | same | same |
| Dropped: GHR "These resources address…" lists | — | 1,085 | 1,085 |
| Dropped: GARD Human Phenotype Ontology symptom tables | — | 2,239 | 2,239 |
| Leading restated question stripped (kept) | — | 1,767 | 1,767 |
| CancerGov "Key Points" summary stripped (kept) | — | — | 290 |
| MedQuAD records kept | 16,347 | 13,023 | 13,023 |
| Train / validation / test | 13,079 / 1,645 / 1,623 | 12,953 / 1,523 / 1,297 (train/val include 2,500 / 250 synthetic) | 14,453 / 1,673 / 1,297 (train/val include 4,000 / 400 synthetic) |

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
- **v3 synthetic records** (`synthetic_records.generate_v3`, unit-tested in
  `training/tests/test_v3_data.py`): 4,000 examples, 2,234 of them multi-turn (system, earlier
  turns, question), the format the app sends with chat history. They cover follow-ups ("is that
  high?", "what's the range?", "what was it last time?", another test, a medication, the plan, a
  lab comment), three-turn chains, topic switches, and documents uploaded after an earlier
  "couldn't find". 60% of lab documents use the app's own extraction lines ("LDL: 162 mg/dL
  (reference <100), flagged High."), with older-results blocks, tests with no reference range,
  and absent medications. Off-topic questions and greetings are answered without citing
  unrelated excerpts. There are 367 distinct follow-up phrasings and several answer wordings per
  kind. The 8 held-out eval follow-ups are checked never to appear in the generated questions.
  v3 train mix: 4,665 closed-book, 4,228 oracle, 1,560 distractor-only, 4,000 synthetic.
- **Length:** v1 drops examples over 1,024 tokens (53); v2 and v3 use 2,048 tokens and drop none.

## Training

| | v1 | v2 | v3 |
|---|---|---|---|
| LoRA rank / alpha / dropout; targets | 16 / 32 / 0.05; `qkv_proj o_proj gate_up_proj down_proj` | same | same |
| LR / schedule / warmup / epochs | 2e-4 / cosine / 3% / 1 | same | same |
| Base precision | 4-bit NF4 (QLoRA) | **bf16** (`load_in_4bit=False`) | bf16 |
| Batch | 4 per GPU × 2 accumulation × 2 GPUs = 16 | 2 per GPU × 4 accumulation × 2 GPUs = 16 | same as v2 |
| Max sequence length | 1,024 | 2,048 | 2,048 |
| Optimizer | paged 8-bit AdamW | AdamW (the paged optimizer crashed under DDP on the L4s) | AdamW |
| Hardware | HiPerGator `hpg-turin`, 2× L4, DDP | same | same |
| Steps (best checkpoint) | 815 (800) | 810 (800) | 904 (904) |
| Validation loss (best) | 0.859 | 0.533 | 0.473 |
| Final train loss | 0.860 | 0.596 | 0.577 |

Validation losses are **not comparable** between versions: the datasets differ, and v2 and v3
targets include extractive, cited answers that are easier to predict. v1 and v2 also differ in base
precision (4-bit vs bf16) as well as data, so the improvement can't be credited to data alone.
v2 and v3 differ only in data. v3's validation loss was still falling at its last check, so a
second epoch might help a little; it wasn't tried.
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

**Probe revision 3** adds 5 questions on a column-layout lab report (19 questions in all). Results
(`training/results/v3/grounding_probe.json`):

| Model | Exact value | High/normal call | Cites right excerpt | Says "not found" |
|---|---|---|---|---|
| `phi3-base` | 16/16 | 11/12 | 14/16 | 3/3 |
| `phi3-medquad-v2` | 16/16 | 12/12 | 16/16 | 3/3 |
| **`phi3-medquad-v3`** | **16/16** | **12/12** | **16/16** | **3/3** |

v3 first scored 2/3 on "not found". It answered "Your medication list doesn't include Metformin
[1]" with no dose, which is correct, but the scorer didn't recognise "doesn't include". That
wording was added to both scorers before the final numbers above.

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

## Evaluation suite: v3 (2026-10-07)

All three models were re-run on the same, current pipeline (57 record questions, 200 MedQuAD).
Full results: [`eval/report/REPORT.md`](../eval/report/REPORT.md).

| | `phi3-base` | v2 | **v3** |
|---|---|---|---|
| Record questions, with documents (57) | 47 (82%) | 46 (81%) | **54 (95%)** |
| Follow-up questions (9) | **8** | 4 | 7 |
| Held-out follow-ups, wordings never in training (8) | 6 | 4 | **8** |
| Missing items ("not found", 4) | 4 | 3 | 4 |
| Previous result reported as current | 0/11 | 0/11 | 0/11 |
| Record questions, no retrieval (57) | 7 | 6 | 7 |
| MedQuAD ROUGE-L / embedding similarity (200) | 0.154 / 0.854 | 0.173 / 0.845 | 0.176 / 0.849 |
| Guard stops: records (114 answers) / MedQuAD (200) | 0 / 6 | 4 / 26 | **0** / 24 |
| MedQuAD answers in "Key Points" format | 0 | 9 | **0** |
| Time to first text / tokens per second | 0.72 s / 87 | 0.52 s / 88 | 0.48 s / 86 |

**Acceptance** (set before training): at least 46/57 overall, at least 6/8 held-out follow-ups,
no category below v2, grounding probe still perfect. All four were met.

- **The follow-up weakness is fixed.** v2 got 4 of 9 follow-ups and 4 of 8 held-out ones; v3 gets
  7 and 8. It now uses the retrieved excerpt in a conversation instead of saying it couldn't
  find it, quotes the report's own range, and cites it.
- **No category got worse.** Values, citations, current vs previous and same-name tests stay at
  100%; missing items rose from 3/4 to 4/4 (v3 no longer adds general metformin dosing).
- **v3 never tripped the guard on record questions** (v2: 4), and the "Key Points" imitation is
  gone from general answers.
- **v3's 3 misses are model errors:**
  - "When should I get it checked again?" cites the medication list's lab-visit date instead of
    the visit note's "recheck in 3 months".
  - "Has it changed since before?" after an eGFR question compares creatinine instead (correct
    values, wrong test).
  - "Is my urine creatinine normal?" starts with "Yes", then correctly says no reference range is
    listed, with one garbled word ("isn' endorsed").
- **General knowledge is unchanged** (similarity 0.845–0.854, within noise).

## Evaluation suite: v2 (2026-10-06)

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
- **Record answers follow templates:** v2 and v3 answer record questions in an extractive pattern
  learned from the synthetic data ("According to your lab report, your X was …"). v3 has several
  wordings per kind, but answers are still terse (e.g. v2 didn't add "prediabetes" when asked
  whether 6.1 % is in the diabetes range).
- **Copying the previous answer:** v2 and v3 sometimes repeat their previous answer word for word
  when the next message is vague ("ok cs", "why repeat"; v3 4 of 8, `phi3-base` 0 of 8). The app
  compares the start of each answer with earlier answers and, on a copy, asks once more without
  the chat history (`backend/pha/chat/orchestrator.py`).
- **Garbage after a poisoned history:** a chat holding the same copied answer 8 times made v3
  produce garbled text ("Yourpanding to help7ithway.sniets") on every try, with greedy decoding;
  without the history the answer was clean. The app now (1) drops exchanges whose answer repeats
  a later one before building the prompt, (2) treats words with a digit wedged inside
  ("yoursand4a4"), digit-led words ("3oclaimi") and words joined by a full stop as malformed in
  the guard (none in model answers across 149,749 calibration sentences), and (3) retries without
  history when the answer turns garbled before any text is shown. v3 also sometimes breaks a
  contraction ("I couldn' sat", "isn' endorsed"); single cases like that pass the guard.
- **Vague or garbled messages:** "hash" or "ok cs" retrieve unrelated excerpts (any text scores
  just above the 0.50 floor), and the fine-tuned models answer about one of them; for "ok cs" v3
  claimed there were no cholesterol results. The app now asks the user to rephrase when a message
  of at most 4 words contains no known word (MedQuAD vocabulary, the retrieved excerpts, common
  abbreviations), and suggests a spelling ("diebatic" → "diabetic"). It flagged none of the 57
  record, 1,297 MedQuAD test and 73 safety questions, nor 37 short real questions ("LDL?",
  "why?", "covid?"). Unknown long words with no close spelling (new brand names) still reach the
  model. A retrain could teach the model itself to ask.
- **Follow-ups that change the test:** v3 sometimes keeps the previous test in a conversation
  (asked "has it changed?" after an eGFR question, it compared creatinine), and once cited a
  medication list's visit date instead of the clinic note's recheck plan.
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
  (blood and urine creatinine), where the model answered with the urine value. The app now
  labels each by specimen and adds a note when a question could mean either. v2 also tended to
  say "within the range" when the reference is "not established"; v3 says no range is listed,
  though once it began such an answer with "Yes".
- **Coverage gaps:** MedQuAD's medication and supplement subsets had no answers in the public
  release, so drug knowledge comes from the base model.
- **Dated content:** NIH pages were collected around 2017–2019.
- **No safety fine-tuning:** emergencies and crises are handled by rules in the app.
- **Not medical advice.** Always consult a qualified clinician.

## Reproduce

```bash
backend/.venv/bin/python training/prepare_medquad.py --download --out data/medquad-v3 \
  --clean-templates --grounded --v3 --synthetic-train 4000 --synthetic-val 400
# GPU: training/train_lora.ipynb with VERSION = 3 (HiPerGator guide: training/hpc/README.md)
cd models && ollama create phi3-medquad-v3 -f Modelfile.medquad-v3 && ollama create phi3-base -f Modelfile.base
backend/.venv/bin/python training/grounding_probe.py phi3-base phi3-medquad-v3
make eval   # records, MedQuAD and safety sets; writes eval/report/REPORT.md
```

For v2, use `--out data/medquad-v2 --clean-templates --grounded --synthetic-train 2500
--synthetic-val 250` (no `--v3`) and `VERSION = 2`.
