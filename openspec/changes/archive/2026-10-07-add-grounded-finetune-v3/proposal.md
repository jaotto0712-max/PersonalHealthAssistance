## Why

The evaluation (`eval/report/REPORT.md`, 49 record questions) leaves `phi3-medquad-v2` with
failures that come from its training data, not from the app:

- **Multi-turn follow-ups: 4/9 (base model 8/9).** Every v2 training example was single-turn.
  Given the right excerpt, v2 ignores it ("What was it last time?"), quotes general thresholds
  instead of the report, or drops citations.
- **"Not established" ranges:** v2 writes "within the reference range" for a test with no range.
  It is a learned answer template, and no extraction wording changed it (4-variant probe).
- **Absent medications:** v2 says the drug isn't listed, then gives general dosing.
- **"Key Points" answers:** v2 copies MedQuAD's CancerGov format, which repeats its points as
  headings; the guard stops 25/200 answers at the repeat.

v2 also never saw the app's real extraction format: lab lines such as "Creatinine: 1.31 mg/dL
(reference 0.76-1.27), flagged High." and "Older results from … (not current): …" blocks.

## What Changes

- **Synthetic conversations (4,000 examples; 2,234 multi-turn, 22 kinds):**
  - follow-ups: is-that-high/low/normal, neutral ("Should I be worried?"), range, previous result,
    another test, medication reason/start/frequency, visit plan, lab comments
  - three-turn chains, topic switches, follow-ups after "couldn't find"
  - documents arriving mid-conversation: earlier turns say "I can't see your records", and the
    next answer must use the newly retrieved report
- **Variety over templates:** 367 distinct follow-up questions (the first draft had 44) and
  several answer wordings per kind, so the model learns the task rather than one template.
- **Lab documents in the app's extraction format** (60%), including older-results blocks, lab
  comments and no-range tests (264 no-range examples). Answers quote references exactly as printed.
- **Absent medications** answered without a dose; **off-topic messages and greetings** answered
  without summarising the retrieved excerpts.
- **MedQuAD:** 290 duplicated "Key Points" summaries removed.
- **App (shipped alongside):** history words widened so every "previous result" phrasing in the
  training data also retrieves the older-results excerpt in the app.
- **Notebook:** `VERSION = 3`; v2's recorded training settings (bf16, effective batch 16).

**Held-out check:** 8 new eval follow-ups (`followup_heldout`) were written before the phrasing pools.
A test asserts none appears in 20,000 generated examples. 4 of the 9 original follow-ups do appear in
training, so the `followup` score is partly memorization and is reported separately.

**Acceptance** (eval `records` with documents, 57 questions; v2 baseline in brackets):
- total ≥ 46/57 [v2 46]
- `followup_heldout` ≥ 6/8 [v2 4, base 6]
- no category below v2
- grounding probe still 11/11 values, 7/7 calls, 11/11 citations

**Result (2026-10-07): accepted.** v3 54/57 [46]; `followup_heldout` 8/8 [4]; every category equal
to or above v2; grounding probe (revision 3, 19 questions) 16/16 values, 12/12 calls, 16/16
citations, 3/3 "not found". `phi3-medquad-v3` is now the app default.

## Impact

- `training/synthetic_records.py`, `training/prepare_medquad.py`, `training/train_lora.ipynb`,
  `training/tests/`, `models/Modelfile.medquad-v3`.
- Needs one GPU run (HiPerGator, as for v2) and GGUF export.
- Eval fixtures are only partly held out: their patients and values never appear in training, but
  v3 trains on the app's extraction format, which the fixtures also pass through. Report results
  with that caveat (v2 could claim unseen layouts; v3 cannot).
