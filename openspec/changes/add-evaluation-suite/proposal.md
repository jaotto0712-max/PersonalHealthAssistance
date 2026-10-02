## Why

A capstone has to show its parts actually help. We need evidence that LoRA fine-tuning improves medical Q&A over the base model, that RAG improves answers about the user's own documents, that safety checks fire when they should, and that the system is truly local. Without measurement, the demo is anecdotal.

## What Changes

- Add an evaluation harness that runs the real orchestrator against configurable model and RAG settings and records outputs, latency, and metrics.
- Add a 2×2 ablation: {`phi3-base`, `phi3-medquad`} × {RAG off, RAG on}.
- Add eval sets: the MedQuAD held-out test split (general knowledge), a synthetic personal-documents QA set with gold answers and gold source pages (grounding), and a safety prompt set (emergency recall and false-positive rate).
- Add metrics: ROUGE-L and BERTScore against references, citation precision/recall, retrieval hit@k, an LLM-free faithfulness heuristic plus a human-graded sample rubric, emergency recall/precision, and latency (TTFT, tokens/s).
- Add an end-to-end privacy check that runs a full upload → chat flow with outbound networking blocked and verifies no non-loopback connections.
- Generate a Markdown/HTML report with tables and charts for the README and showcase.

## Capabilities

### New Capabilities
- `model-evaluation`: Reproducible measurement of answer quality, grounding, safety, and performance across model/RAG configurations.
- `privacy-verification`: Automated proof that the full application runs with no outbound network traffic.

### Modified Capabilities
<!-- none -->

## Impact

- New `eval/` package: `run_eval.py`, `metrics/`, `sets/`, `report/`, results under `eval/results/` (gitignored except the final report).
- New dev deps: rouge-score, bert-score (with a locally cached scorer model), pandas, matplotlib.
- Uses `phi3-base` and `phi3-medquad` from `add-medquad-lora-finetune`, the RAG fixtures from `add-local-document-rag`, and the orchestrator from `add-rag-chat-orchestration`.
