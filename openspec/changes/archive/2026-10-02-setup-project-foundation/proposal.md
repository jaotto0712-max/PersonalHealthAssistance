## Why

The repository is empty. Every later capstone change (fine-tuning, RAG, orchestration, UI, evaluation) needs a shared layout, toolchain, and configuration model, plus a single enforced definition of what "local-only" means. If we settle these up front, the later changes won't each invent their own conventions or quietly add network dependencies.

## What Changes

- Create the monorepo layout: `backend/`, `frontend/`, `training/`, `eval/`, `models/`, `data/`.
- Bootstrap the Python backend package (`pha`) with uv, ruff, pytest, and a FastAPI app exposing `GET /api/health`.
- Bootstrap the frontend with Vite + React + TypeScript + Tailwind (empty shell only; the real UI comes in `add-gator-chat-ui`).
- Add central, environment-driven settings (Ollama URL, model name, Chroma path, embedding model path, bind host).
- Define and enforce the offline runtime policy: loopback-only binding, telemetry disabled, Hugging Face offline mode, and a startup self-check.
- Add a developer `Makefile` (`make setup`, `make dev`, `make test`, `make lint`) and a README skeleton with the medical disclaimer.
- Add `.gitignore` rules so model weights, vector stores, uploaded documents, and datasets are never committed.

## Capabilities

### New Capabilities
- `project-scaffold`: Repository layout, toolchains, configuration, and developer commands that all other capabilities build on.
- `offline-runtime-policy`: Guarantees that the running application makes no outbound network connections and keeps user data on the local machine.

### Modified Capabilities
<!-- none: no existing specs -->

## Impact

- New dependencies: Python 3.11, uv, FastAPI, uvicorn, pydantic-settings, ruff, pytest; Node 20+, Vite, React, TypeScript, Tailwind.
- External runtime prerequisite: Ollama installed locally (used from `add-rag-chat-orchestration` onward).
- No existing code is affected (greenfield).
