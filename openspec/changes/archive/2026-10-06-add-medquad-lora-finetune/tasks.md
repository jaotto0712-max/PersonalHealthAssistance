## 1. Dataset preparation

- [x] 1.1 Add `training/prepare_medquad.py` that downloads or reads MedQuAD XML into records (question, answer, focus, qtype, source)
- [x] 1.2 Exclude subsets/records with removed or empty answers; normalize whitespace and strip markup
- [x] 1.3 Deduplicate exact pairs, drop too-short answers, truncate answers over the token budget
- [x] 1.4 Implement seeded group split by focus (80/10/10) and assert no focus overlap
- [x] 1.5 Render records into chat JSONL with the shared system prompt (`training/system_prompt.txt`, also used by backend)
- [x] 1.6 Emit `stats.json` and add unit tests for parsing, dedup, and split leakage

## 2. Fine-tuning notebook

- [x] 2.1 Create `training/train_lora.ipynb` with pinned installs (transformers, peft, trl, bitsandbytes, accelerate, datasets)
- [x] 2.2 Add a single config cell for all hyperparameters and the seed; mount Google Drive for checkpoints
- [x] 2.3 Load Phi-3-mini-4k-instruct in 4-bit NF4 and attach LoRA to `qkv_proj`, `o_proj`, `gate_up_proj`, `down_proj`
- [x] 2.4 Configure SFTTrainer with assistant-only loss, eval on validation every N steps, keep best checkpoint, resume support
- [x] 2.5 Run a 50-step smoke test, then full training; save adapter + `training_config.json`
- [x] 2.6 Add a qualitative cell comparing base vs adapter answers on ~10 held-out test questions

## 3. Export to Ollama

- [x] 3.1 Add merge step (fp16 base + adapter → `merge_and_unload`) in the notebook or `training/merge_adapter.py`
- [x] 3.2 Add `training/export_gguf.sh` pinning a llama.cpp commit: convert to f16 GGUF, quantize to Q4_K_M
- [x] 3.3 Run the same conversion for the unmodified base model to produce `phi3-base` GGUF
- [x] 3.4 Write `models/Modelfile.medquad` and `models/Modelfile.base` with Phi-3 template, stop tokens, temperature, num_ctx
- [x] 3.5 Register both models in local Ollama and verify clean output (no leaked template tokens) on sample questions

## 4. Documentation

- [x] 4.1 Write `training/model_card.md` (data + attribution, splits, hyperparameters, losses, limitations, not medical advice)
- [x] 4.2 Add a "Reproducing the model" section to README with Colab link and export commands
