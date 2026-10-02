## Context

This is a greenfield repo for UF AI Passport Project 7. The system has three runtime processes on one machine (React dev server or static build, FastAPI backend, and Ollama) plus an offline training workflow that runs on Colab. The defining constraint is privacy: user documents and questions must never leave the device.

## Goals / Non-Goals

**Goals:**
- One-command setup and dev loop for both backend and frontend.
- A single settings object that every backend module reads from.
- Offline guarantees that are enforced by code, not just documented.

**Non-Goals:**
- Containerization or cloud deployment.
- Authentication or multi-user support (single local user).
- Any model, RAG, or UI functionality (later changes).

## Decisions

**Monorepo with top-level `backend/`, `frontend/`, `training/`, `eval/`.**
Each area has a different toolchain, and keeping them as siblings stops them from interfering with each other. Alternative: separate repos. Rejected because it adds overhead for a single-student capstone.

```
PersonalHealthAssistance/
├── backend/            # FastAPI app, python package `pha`
│   ├── pha/            # config.py, main.py, api/, (later) rag/, llm/, safety/
│   └── tests/
├── frontend/           # Vite + React + TS + Tailwind
├── training/           # Colab notebooks + data prep scripts
├── eval/               # evaluation harness and question sets
├── models/             # GGUF + Modelfile            (gitignored except Modelfile)
├── data/               # chroma/, uploads/, medquad/  (gitignored)
└── Makefile
```

**uv for Python, npm for frontend.** uv gives fast, reproducible lockfiles. npm avoids requiring an extra tool like pnpm.

**pydantic-settings with a `PHA_` env prefix and a `.env` file.** This gives typed config with sensible defaults (`PHA_OLLAMA_URL=http://127.0.0.1:11434`, `PHA_MODEL=phi3-medquad`, `PHA_CHROMA_DIR=data/chroma`, `PHA_EMBED_MODEL_DIR=models/embeddings/bge-small-en-v1.5`, `PHA_HOST=127.0.0.1`, `PHA_PORT=8000`).

**Offline enforcement in three layers:**
1. *Environment:* At process start the backend sets `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`, and `ANONYMIZED_TELEMETRY=False` before importing any ML library.
2. *Configuration validation:* The backend refuses to start if `PHA_HOST` or the host in `PHA_OLLAMA_URL` is not a loopback address.
3. *Test:* A pytest fixture patches `socket.socket.connect` to fail on non-loopback addresses, and the API test suite runs under it. `add-evaluation-suite` extends this to a full end-to-end check.

Alternative: rely on documentation only. Rejected because "Local-only" is a core requirement of the brief, so it has to be verifiable.

**Frontend assets bundled locally.** No Google Fonts or CDN scripts. Fonts come from `@fontsource/*` npm packages.

## Risks / Trade-offs

- [A library adds hidden telemetry later, e.g. Chroma or Hugging Face] → Disable it via env and settings. The socket-guard test catches regressions.
- [Developers on Windows lack `make`] → Each Make target is a thin wrapper, and the README shows the raw commands too.
- [Model and data files committed by accident (multi-GB)] → Strict `.gitignore`, and the README explains where artifacts live.

## Open Questions

- Python 3.11 vs 3.12: pick whichever Chroma and sentence-transformers wheels support cleanly on macOS arm64 at implementation time.
