## Context

Training happens on Colab, where the dataset is public and nothing private is involved. Inference happens locally through Ollama, which was chosen over raw transformers + peft for speed and memory on macOS. So the pipeline has to produce a portable artifact: Colab → adapter → merged fp16 → GGUF → Ollama.

```
 MedQuAD XML ─▶ prepare_medquad.py ─▶ train/val/test.jsonl (Phi-3 chat format)
                                              │
                         Colab (T4/A100) ─────┤
                                              ▼
            Phi-3-mini-4k-instruct (4-bit) + LoRA ──▶ adapter/ (safetensors)
                                              │
                    merge (fp16 base) ────────┘
                                              ▼
            convert_hf_to_gguf.py ─▶ f16.gguf ─▶ llama-quantize Q4_K_M
                                              ▼
                     ollama create phi3-medquad -f Modelfile.medquad
```

## Goals / Non-Goals

**Goals:**
- A reproducible pipeline with pinned versions and a fixed seed.
- No leakage between splits.
- A fine-tuned model that runs at interactive speed on an Apple Silicon laptop.

**Non-Goals:**
- State-of-the-art medical QA accuracy.
- Training on any user or patient data.
- RLHF/DPO or multi-dataset mixing (possible stretch goal).

## Decisions

**Base model: `microsoft/Phi-3-mini-4k-instruct`.** The brief names Phi-3-mini. The 4k-context variant is the best-supported option in llama.cpp and Ollama, and 4k tokens is enough for RAG with 4 chunks. The 128k variant uses rope scaling, which makes GGUF conversion and memory use more complex.

**Data source: the original MedQuAD XML (github.com/abachaa/MedQuAD), not just a Hugging Face mirror.** The XML carries `focus` and `qtype` metadata, which we need for leak-free splits. The subsets whose answers were removed for copyright reasons are excluded. A Hugging Face mirror can be a fallback if it preserves focus metadata.

**Group split by question focus (80/10/10).** MedQuAD has many near-identical questions per focus ("What is X?", "What causes X?"). A random split would leak answers between train and test. A seeded `GroupShuffleSplit` on `focus` fixes this.

**Cleaning:** strip HTML and whitespace, drop empty or very short answers, deduplicate exact (question, answer) pairs, and truncate answers longer than a token budget (around 700 tokens), so that examples fit within `max_seq_length=1024`.

**Chat format:** Each example becomes `system`, `user`, and `assistant` messages rendered with the tokenizer's chat template. The system prompt is the same consumer-health persona used at inference time in `add-rag-chat-orchestration`. Training and inference use identical prompt framing.

**QLoRA hyperparameters (starting point):**
- 4-bit NF4 base
- r=16, alpha=32, dropout=0.05
- target modules `qkv_proj`, `o_proj`, `gate_up_proj`, `down_proj` (Phi-3's fused projections)
- lr 2e-4 with cosine schedule and 3% warmup
- effective batch size 16
- 1–2 epochs
- fp16 on T4, bf16 on A100
- loss on assistant tokens only

Alternative: full fine-tune. Rejected because it doesn't fit Colab memory and the brief specifies LoRA.

**Merge in fp16, not 4-bit.** We reload the base model in fp16 on CPU or GPU, apply the adapter, and call `merge_and_unload()`. Merging into a 4-bit base would degrade weights.

**GGUF quantization: Q4_K_M** (about 2.3 GB), a good quality/speed balance on Mac. Q5_K_M is kept as an option if quality drops noticeably.

**Base model built with the same pipeline** (`phi3-base`). This ensures the evaluation comparison isolates the effect of LoRA, not quantization differences.

**Modelfile:** It sets Phi-3's template (`<|system|>…<|end|><|user|>…<|end|><|assistant|>`), stop tokens `<|end|>` and `<|endoftext|>`, temperature 0.2, and num_ctx 4096. The system prompt is *not* baked in, because the backend supplies it.

## Risks / Trade-offs

- [Colab session timeout mid-training] → Checkpoint every N steps to Google Drive and support resume.
- [llama.cpp conversion breaks on a Phi-3 config change] → Pin the llama.cpp commit and document the exact conversion command. The fallback is `unsloth`'s GGUF export.
- [Fine-tuning hurts general instruction-following or adds hallucinations] → Measure against `phi3-base` in `add-evaluation-suite`, and keep epochs low.
- [MedQuAD answers are long and encyclopedic, and the model learns to ramble] → Truncation plus `num_predict` and length guidance in the system prompt.
- [License] → MedQuAD content comes from NIH sites and is used for non-commercial education. Note the attribution in the model card.

## Open Questions

- Final epoch count and whether to use Q4_K_M or Q5_K_M, to be decided from validation loss and a quick qualitative check.
- Should the adapter be uploaded to a private Hugging Face repo for backup, or only to Google Drive?
