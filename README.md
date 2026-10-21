# Personal Health Assistant 🐊

UF AI Passport — Clinical Application Track, **Project 7 (Capstone)**.
Brief: <https://uf-aibhs.github.io/AI-Passport-Impact-Project/clinical-application-project-07-capstone-health-assistant/>

A fully **local** health assistant: Phi-3-mini fine-tuned with LoRA on MedQuAD, grounded at query
time in documents you upload (RAG over Chroma). Your questions and documents never leave your machine.

> ⚠️ **Medical disclaimer** — This is a student project that provides general health information only.
> It is **not** a substitute for professional medical advice, diagnosis, or treatment.
> In an emergency, call **911**. For a mental-health crisis, call or text **988**.
>
> Not affiliated with or endorsed by the University of Florida or UF Health.

## Screenshots

| Grounded answer with citations | Emergency guidance |
|---|---|
| ![Answer citing the user's lab report](docs/screenshots/02-grounded-answer-desktop.png) | ![Emergency alert card](docs/screenshots/03-emergency-desktop.png) |

| Welcome | Mobile chat | Mobile documents |
|---|---|---|
| ![Welcome screen](docs/screenshots/01-welcome-desktop.png) | ![Mobile chat](docs/screenshots/04-chat-mobile.png) | ![Mobile documents drawer](docs/screenshots/05-documents-drawer-mobile.png) |

_Screenshots use the built-in mock API (`make dev-mock`); answers shown are illustrative, not real model output._

## Features

- **Chat with your own records.** Upload PDF, TXT, MD or DOCX files. Answers are grounded in the
  most relevant excerpts and cite them (`[1]`, `[2]`), and you can open each source.
- **Lab reports read correctly.** Column-layout lab tables become one clear line per result
  (value, unit, reference, flag). Older results are kept separately and used only when you ask
  about earlier values.
- **Safety first.** Emergencies and crises get 911/988 guidance by rule, without calling the
  model. Every answer carries a disclaimer. A guard stops looping or garbled output while it
  streams, an answer that copies an earlier one is regenerated, and
  short unclear messages get a request to rephrase (with a spelling suggestion) instead of a guess.
- **Saved conversations.** Multiple chats in a local SQLite database, with rename, delete and
  delete-all.
- **Fully local.** Loopback only, offline model libraries, no telemetry. This is verified by an
  end-to-end test (see [Privacy guarantees](#privacy-guarantees)).

## Architecture

```
                ┌──────────────────────────── LOCAL MACHINE ────────────────────────────┐
  browser ───▶  │  React UI ──/api (SSE)──▶ FastAPI ──▶ emergency rules ──▶ 911/988 card│
                │                              │                                        │
                │                              ├──▶ Retriever ──▶ Chroma (local vectors)│
                │                              │       ▲  bge-small embeddings          │
                │                              │       └─ uploads: parse → lab tables   │
                │                              │                  → chunk → embed       │
                │                              ├──▶ Ollama (127.0.0.1:11434)            │
                │                              │      phi3-medquad-v3 (LoRA, Q4_K_M)    │
                │                              │      → degeneration guard → stream     │
                │                              └──▶ SQLite chat history (data/chats.db) │
                └───────────────────────────────────────────────────────────────────────┘
  Training (one-time, public + synthetic data only): HiPerGator 2× L4 (or Colab)
      → LoRA adapter → merge → GGUF Q4_K_M → Ollama
```

## Repository layout

| Path        | Contents                                                     |
|-------------|--------------------------------------------------------------|
| `backend/`  | FastAPI app (Python package `pha`) and tests                 |
| `frontend/` | Vite + React + TypeScript + Tailwind UI                      |
| `training/` | MedQuAD preparation, LoRA notebook, GGUF export              |
| `eval/`     | Evaluation sets, harness, scorers, and report                |
| `models/`   | GGUF weights + Ollama Modelfiles (weights are gitignored)    |
| `data/`     | Chroma store, uploads, datasets (gitignored)                 |
| `openspec/` | Proposals, designs, specs, and task lists                    |

## Prerequisites

- Python 3.11 (managed automatically by [uv](https://docs.astral.sh/uv/))
- Node.js 20+
- [Ollama](https://ollama.com/) (needed from the chat feature onward)

## Quick start

```bash
make setup     # install backend + frontend dependencies
make dev       # backend on 127.0.0.1:8000, frontend on 127.0.0.1:5173
make dev-mock  # UI only, against an in-memory mock API (no backend/Ollama needed)
make start     # build the UI and serve UI + API together at http://127.0.0.1:8000
make test      # run all tests
make lint      # ruff + oxlint + tsc
```

Without `make`:

```bash
cd backend && uv sync && uv run uvicorn pha.main:app --host 127.0.0.1 --port 8000 --reload
cd frontend && npm install && npm run dev        # or: npm run dev:mock
```

Configuration is via `PHA_`-prefixed environment variables or `backend/.env` — see `backend/.env.example`.

## Running with a local model

The default model is **`phi3-medquad-v3`**: Phi-3-mini with a LoRA fine-tune on cleaned MedQuAD,
grounded examples and multi-turn conversations about personal records, Q4_K_M. It answers 54 of
57 record questions correctly (`phi3-base` 47, v2 46), including every held-out follow-up, and
scores perfectly on the grounding probe (16/16 exact values, 12/12 high/normal calls, 16/16
citations, 3/3 "not found"). `phi3-medquad-v2` was the previous default. The first fine-tune,
`phi3-medquad` (v1), ignored the user's documents and is kept only for comparison. See
[`training/model_card.md`](training/model_card.md). Any installed Ollama model works for development:

```bash
PHA_MODEL=llama3.2 make dev          # or: PHA_MODEL=llama3.2 make start
PHA_LLM_BACKEND=fake make dev        # no Ollama at all: canned answers, real retrieval
```

One-time setup for document search: `cd backend && uv run python scripts/fetch_embeddings.py`.

### Measured performance

Apple M3 Max, `llama3.2` (3.2B, Q4_K_M) via Ollama 0.32, three fixture documents indexed,
retrieval top-4 with bge-small-en-v1.5:

| Metric | Result |
|---|---|
| Time to first token (warm model) | 0.25–0.7 s |
| Generation speed | ~110 tokens/s |
| Emergency response (no model call) | ~15 ms |
| Backend startup (embedding model load) | ~3 s |

With `phi3-medquad-v2` on the same machine: time to first token 0.1–0.9 s, about 106 tokens/s.
`phi3-medquad-v3` runs at the same speed (eval run: 0.48 s median to first text, v2 0.52 s).

## Reproducing the model

`phi3-medquad-v3` is Phi-3-mini fine-tuned with LoRA on template-cleaned MedQuAD rendered in the app's
retrieval format (RAFT-style), plus synthetic personal-record questions and multi-turn conversations
in the app's chat-history format. See [`training/model_card.md`](training/model_card.md).

1. **Data:** `make medquad` writes the v1 splits. For v3, run `backend/.venv/bin/python training/prepare_medquad.py --download --out data/medquad-v3 --clean-templates --grounded --v3 --synthetic-train 4000 --synthetic-val 400`. The notebook does this for you (`VERSION = 3`; `VERSION = 2` rebuilds v2).
2. **Train (GPU):** open [`training/train_lora.ipynb`](training/train_lora.ipynb) on UF HiPerGator (guide: [`training/hpc/README.md`](training/hpc/README.md); v2 and v3 were trained on 2× L4, about 1 epoch) or on Colab. Smoke-test, restart the kernel, then run in full. The notebook saves the adapter, merges it, and exports `phi3-medquad-v3` (and `phi3-base` if missing) as GGUF Q4_K_M.
3. **Install locally:** copy the `.gguf` files into `models/`, then run `cd models && ollama create phi3-medquad-v3 -f Modelfile.medquad-v3 && ollama create phi3-base -f Modelfile.base`.
4. **Check:** `backend/.venv/bin/python training/grounding_probe.py phi3-base phi3-medquad-v3`.

You can also export locally with `training/export_gguf.sh <hf_dir_or_id> <name>`, which uses a pinned llama.cpp and needs cmake. Add `REGISTER=1` to also run `ollama create`.

The training code lives in `training/lora_pipeline.py`. It is smoke-tested end to end on CPU with a tiny Phi-3 (`training/tests/test_lora_pipeline.py`, which needs the training stack installed) before any GPU time is spent.

## Evaluation

`make eval` runs three test sets through the real pipeline: retrieval, prompts, guards and the
local Ollama models. It then writes [`eval/report/REPORT.md`](eval/report/REPORT.md).

| Set | Size | What it checks |
|---|---|---|
| `records` | 57 | questions about the fixture records: values, citations, high/low calls, missing items, follow-ups (9, plus 8 held-out wordings never used in training), current vs previous results, same-name tests (blood vs urine), no documents |
| `medquad` | 200 | held-out MedQuAD questions on unseen topics: ROUGE-L and embedding similarity to NIH answers |
| `safety` | 73 | emergency and crisis rules: 45 emergencies, 28 look-alikes that must not trigger |

**Results (2026-10-07):**

| | `phi3-base` | v2 | **v3 (default)** |
|---|---|---|---|
| Record questions, with documents | 47/57 | 46/57 | **54/57** |
| Held-out follow-ups | 6/8 | 4/8 | **8/8** |
| Previous result reported as current | 0/11 | 0/11 | 0/11 |
| MedQuAD similarity to NIH answers | 0.854 | 0.845 | 0.849 |

v2's weak spot was multi-turn follow-ups. v3 was trained on conversations to fix it, and the
acceptance targets set before training were all met. The first emergency rules missed 4 of 34
test emergencies; after broadening them, all 45 are caught, with 1 false alarm in 28
look-alikes. Details: [`training/model_card.md`](training/model_card.md#evaluation-suite-v3-2026-10-07).

Each set runs for `phi3-base`, v1, v2 and v3, with retrieval on and off (v1 was last run on 49 questions). Results are cached per pipeline
fingerprint, so re-runs only ask what changed. `make eval-report` rebuilds the report from cached
answers, re-applying the current scorer. Fixtures are synthetic: no real patient data is used.

## Privacy guarantees

- **Your data stays on this computer.** Uploaded documents (`data/uploads`, `data/chroma`) and
  saved chats (`data/chats.db`) live under `data/`, which git ignores. The backend only listens on
  loopback. Delete chats one by one or with *Delete all chats*, and documents with *Clear all documents*.
  Deleted chat text is overwritten in the database (SQLite `secure_delete`). For protection at rest,
  use your OS's disk encryption.
- Backend and model server must bind to loopback addresses; startup fails otherwise.
- Hugging Face libraries run in offline mode; Chroma telemetry is disabled.
- The backend test suite runs under a socket guard that rejects non-loopback connections.
- **Verified end to end:** `backend/tests/test_privacy.py` starts the real backend with
  `PHA_NET_GUARD=1`, which refuses and logs every non-loopback connection or DNS lookup. It then
  uploads a document, chats with the local model, and deletes both. The test asserts that zero
  outbound attempts were logged and that the file, vectors and retrieval results are gone. It
  needs Ollama and the embedding model, and is skipped when either is missing. You can run the
  app the same way: `PHA_NET_GUARD=1 PHA_NET_GUARD_LOG=../data/netguard.log make dev`.
- The frontend bundles all fonts and assets; the build is scanned for remote URLs.
