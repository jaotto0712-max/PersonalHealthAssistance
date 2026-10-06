## Why

The capstone brief calls for specializing a lightweight open model on medical Q&A with LoRA, so the assistant answers health questions in a consumer-friendly, medically grounded style before any user documents are involved. The original paper for MedQuAD, a curated dataset of NIH-sourced Q&A pairs (*A Question-Entailment Approach to Question Answering*, BMC Bioinformatics 2019), is cited in the brief as the training source. MedAlpaca is its closest existing analog.

## What Changes

- Add a reproducible MedQuAD preparation pipeline: download, parse, clean, deduplicate, split by question focus, and format with the Phi-3 chat template.
- Add a Colab notebook that QLoRA-fine-tunes `microsoft/Phi-3-mini-4k-instruct` with `peft` + `trl`, logs metrics, and saves the LoRA adapter.
- Add an export pipeline that merges the adapter into the base model, converts it to GGUF with llama.cpp, quantizes to Q4_K_M, and produces an Ollama `Modelfile`.
- Register two local Ollama models: `phi3-medquad` (fine-tuned) and `phi3-base` (base model, same quantization) for later comparison.
- Record a model card documenting data, hyperparameters, metrics, and limitations.

## Capabilities

### New Capabilities
- `medquad-dataset-prep`: Turning raw MedQuAD into clean, leak-free, chat-formatted train/val/test splits.
- `lora-finetuning`: Parameter-efficient fine-tuning of Phi-3-mini on the prepared data, producing a versioned adapter and training report.
- `local-model-export`: Converting the fine-tuned model into a quantized GGUF served by local Ollama, along with a matching base-model build.

### Modified Capabilities
<!-- none -->

## Impact

- New `training/` contents: `prepare_medquad.py`, `train_lora.ipynb`, `export_gguf.sh`, `model_card.md`.
- New `models/Modelfile.medquad` and `models/Modelfile.base`. GGUF binaries stay gitignored.
- Requires a Colab GPU session (T4 or better) and a local llama.cpp checkout or `llama.cpp` pip tooling for conversion.
- Depends on `setup-project-foundation` for repo layout.
