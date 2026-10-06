# Evaluation sets

| File | Items | What it measures |
|---|---|---|
| `records.jsonl` | 43 | Questions about the user's own (fictional) documents in `eval/fixtures/docs`, each tagged with a failure category seen during development: `value`, `citation`, `direction`, `absent`, `followup`, `current_vs_previous`, `same_name_ambiguity`, `no_documents`. `docs` lists which fixtures are uploaded for that question (`[]` = nothing uploaded). |
| `medquad.jsonl` | 200 | Closed-book medical knowledge: a stratified sample (seed 7) of the template-cleaned **held-out test split** (topics never seen in training). |
| `safety.jsonl` | 52 | Emergency-detector positives (with category) and hard negatives. Several phrasings are new, i.e. not in the backend unit tests. |

All documents are synthetic and fictional. No real patient data is used.

**MedQuAD attribution:** Ben Abacha A. & Demner-Fushman D., *"A question-entailment approach to question answering."* BMC Bioinformatics 20, 511 (2019). https://github.com/abachaa/MedQuAD, licensed CC BY 4.0. Questions and reference answers in `medquad.jsonl` are from MedQuAD, with whitespace normalized and boilerplate removed by `training/prepare_medquad.py --clean-templates`.
