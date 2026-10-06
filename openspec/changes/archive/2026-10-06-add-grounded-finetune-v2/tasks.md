## 1. Safety default and shared prompts

- [x] 1.1 Switch the app default model to `phi3-base`; update `.env.example`, README and the config test
- [x] 1.2 Move retrieval and no-context instructions into `training/rag_instructions.txt` and `training/no_context_instructions.txt`; backend loads them
- [x] 1.3 Test that the training excerpt formatter is byte-identical to `pha.chat.prompt.format_excerpts`

## 2. Data

- [x] 2.1 `--clean-templates` in `prepare_medquad.py` (resource lists, HPO tables, echoed questions) with counts in `stats.json`
- [x] 2.2 `--grounded` RAFT rendering (closed-book / oracle / distractor-only) with same-split distractors and app-style chunking
- [x] 2.3 `training/synthetic_records.py`: labs, medications and visit notes in 3 layouts; value/direction/dose/allergy/vitals/absent questions
- [x] 2.4 Unit tests: cleaning, RAFT rendering, no leakage, direction correctness, absent items, determinism
- [x] 2.5 Generate `data/medquad-v2/` and report stats and token lengths (Phi-3 tokenizer) at `max_length=1536`

## 3. Training and export

- [x] 3.1 Notebook `V2` preset (data, output, max_length, eval batch) and HPC guide note
- [x] 3.2 `models/Modelfile.medquad-v2`
- [x] 3.3 Run v2 on HiPerGator (2× L4), export `phi3-medquad-v2`, register in Ollama

## 4. Acceptance

- [x] 4.1 `training/grounding_probe.py` with held-out record questions; baseline results for `phi3-base` and `phi3-medquad`
- [x] 4.2 Run the probe on `phi3-medquad-v2`; record v1/v2/base results in the model card; switch the default only if v2 ≥ base
