## Why

Every real improvement so far came from a measurement that exposed a failure: the grounding probe caught v1 calling LDL 162 "desirable"; 36-sample checks found looping; a 4-layout comparison found the lab-row format both models read correctly. Several *guesses* were wrong: the repeat penalty, the first scorer, the first row layout. A capstone needs one reproducible harness that measures every model and pipeline change against the **failure types we have actually seen**, so that from now on changes are judged by numbers.

## What Changes

- **Evaluation harness** `eval/run_eval.py`. It runs the real chat pipeline (prompting, retrieval, safety, guard) in-process against local Ollama models, for any combination of models × retrieval on/off, and writes per-item JSONL with answers, sources, timings and guard outcomes.
- **Question sets** (committed, fictional documents only):
  - **records:** questions about the fixture documents, each tagged with a failure category: `value`, `direction`, `current_vs_previous`, `same_name_ambiguity`, `absent`, `followup`, `no_documents`, `citation`.
  - **medquad:** a stratified sample of 200 held-out MedQuAD test questions (closed-book knowledge; topics unseen in training).
  - **safety:** emergency positives and hard negatives for the rule-based detector.
- **New fixture** `lab-report-renal.pdf`: a fictional renal panel with **blood and urine creatinine**, previous results, and "Not Estab." references. It reproduces the real-report ambiguity.
- **Metrics:**
  - records: per-category accuracy, citation correctness, previous-reported-as-current rate, absence and ambiguity handling
  - medquad: ROUGE-L, plus semantic similarity with the local bge embedding model (no extra download)
  - output quality: guard stops by reason, leaks, length
  - safety: recall and precision per category
  - latency: time to first token and tokens/s
- **Report** `eval/report/REPORT.md`: model × retrieval tables, per-category breakdown, worst examples, limitations. Plus `make eval`.
- **Privacy verification** (unchanged scope): an opt-in network guard and an end-to-end offline test.

## Capabilities

### New Capabilities
- `model-evaluation`: Reproducible measurement of grounding, knowledge, output quality, safety and latency across models and retrieval settings.
- `privacy-verification`: Automated proof that the full application runs with no outbound network traffic.

## Impact

- New `eval/` package (sets, harness, metrics, report) run with the backend environment; `eval/results/` gitignored, `eval/report/REPORT.md` committed.
- New fixture plus a generator in `eval/fixtures/make_fixtures.py`.
- No new dependencies (ROUGE-L implemented directly; similarity uses the existing embedder).
