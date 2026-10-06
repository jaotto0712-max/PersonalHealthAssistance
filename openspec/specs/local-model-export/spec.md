# local-model-export Specification

## Purpose
Merge the adapter, convert to GGUF Q4_K_M and register the fine-tuned and base models in local Ollama.

## Requirements
### Requirement: Adapter merge
The export pipeline SHALL merge the LoRA adapter into a full-precision (fp16) copy of the base model and save the merged model in Hugging Face format.

#### Scenario: Merged model loads
- **WHEN** the merged directory is loaded with transformers
- **THEN** it loads without requiring `peft` and generates text

### Requirement: GGUF conversion and quantization
The export pipeline SHALL convert the merged model to GGUF and quantize it (default Q4_K_M) using a pinned llama.cpp version.

#### Scenario: Quantized file produced
- **WHEN** the export script completes
- **THEN** `models/phi3-medquad-Q4_K_M.gguf` exists

### Requirement: Ollama registration
The project SHALL provide Modelfiles that register the fine-tuned model as `phi3-medquad` and an identically quantized base model as `phi3-base` in local Ollama, using the Phi-3 chat template and stop tokens.

#### Scenario: Fine-tuned model runs locally
- **WHEN** a user runs `ollama create phi3-medquad -f models/Modelfile.medquad` and then sends a medical question to `phi3-medquad`
- **THEN** the model returns an answer and stops at the end-of-turn token without emitting template tokens

#### Scenario: Base model available for comparison
- **WHEN** `ollama list` is run after setup
- **THEN** both `phi3-medquad` and `phi3-base` are listed

### Requirement: Export reproducibility
The export steps SHALL be scripted and documented so they can be re-run from an adapter directory without manual edits.

#### Scenario: Re-run export
- **WHEN** `training/export_gguf.sh <adapter_dir>` is executed on a machine with the documented prerequisites
- **THEN** it produces the GGUF file and registers the Ollama model

