## Why

The v1 LoRA model (`phi3-medquad`) learned MedQuAD's style but **stopped following retrieved documents**. In the app it called an LDL of 162 mg/dL (reference < 100) "in the desirable range", where the base model answered 4/4 record questions correctly with citations (`training/model_card.md` → Findings). Two causes:
- v1 trained only on closed-book Q&A, with no excerpts in the prompt.
- 20% of its answers were dataset boilerplate, and 25% restated the question.

The capstone's premise, a fine-tuned model *plus* RAG, needs a model that is better at both.

## What Changes

- The app default model becomes `phi3-base` until a fine-tune beats it on grounded answers (done).
- **Shared prompt text.** The retrieval instructions move out of backend code into `training/rag_instructions.txt` and `training/no_context_instructions.txt`. Training and inference then use byte-identical prompts, enforced by a test.
- **Template cleaning** (`--clean-templates`): drop GHR "These resources address…" resource lists, drop GARD Human Phenotype Ontology symptom tables, and strip answers that start by restating the question.
- **Grounded training mix**, following RAFT (Zhang et al. 2024, *Retrieval Augmented Fine Tuning*). MedQuAD examples are rendered in the app's exact RAG format:
  - closed-book (no excerpts)
  - oracle (the answer passage plus distractor excerpts; the target cites `[n]`)
  - distractor-only (the target says the answer wasn't found in the documents, then answers generally)
- **Synthetic personal records:** fictional lab panels, medication lists and visit notes in varied layouts, with questions whose answers state the value, compare it to the reference range in the correct direction, and cite. These target the observed failure directly.
- **v2 training preset** in the notebook (`max_length=1536`), exported as `phi3-medquad-v2` with its own Modelfile.
- **Grounding probe** (`training/grounding_probe.py`): a quick, repeatable check of record questions with known answers, run against any Ollama model.

## Capabilities

### New Capabilities
- `grounded-training-data`: Template cleaning, RAFT-style grounded examples, and synthetic personal-record Q&A for fine-tuning.
- `prompt-consistency`: One source of truth for the system and retrieval prompt text used by training and inference.

### Modified Capabilities
<!-- none archived yet; medquad-dataset-prep lives in the active change add-medquad-lora-finetune -->

## Impact

- `training/prepare_medquad.py` (new options), new `training/synthetic_records.py`, `training/grounding_probe.py`, two prompt text files, `models/Modelfile.medquad-v2`, and a notebook preset.
- `backend/pha/chat/prompt.py` loads the instruction text from files (same behavior).
- One more GPU run on HiPerGator (2× L4, about 2–3 h at the longer sequence length).
