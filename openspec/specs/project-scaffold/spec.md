# project-scaffold Specification

## Purpose

Defines the repository layout, toolchains, centralized configuration, and developer commands that every other Personal Health Assistant capability builds on.

## Requirements

### Requirement: Repository layout
The repository SHALL contain top-level directories `backend/`, `frontend/`, `training/`, `eval/`, `models/`, and `data/`, and SHALL git-ignore model weights, vector stores, uploaded documents, and raw datasets.

#### Scenario: Large artifacts are not tracked
- **WHEN** a GGUF file is placed in `models/` and a file in `data/uploads/`
- **THEN** `git status` does not list either file as untracked

### Requirement: Backend health endpoint
The backend SHALL expose `GET /api/health` that returns HTTP 200 with a JSON body containing `status` and the application version.

#### Scenario: Health check succeeds
- **WHEN** the backend is running and a client requests `GET /api/health`
- **THEN** the response status is 200 and the body contains `"status": "ok"`

### Requirement: Centralized configuration
The backend SHALL load all runtime settings from a single typed settings object populated from `PHA_`-prefixed environment variables or a `.env` file, with documented defaults.

#### Scenario: Default settings
- **WHEN** the backend starts with no `PHA_` variables set
- **THEN** it uses `127.0.0.1:8000` for its own bind address and `http://127.0.0.1:11434` for Ollama

#### Scenario: Override via environment
- **WHEN** `PHA_MODEL=phi3-base` is set
- **THEN** the settings object reports `model == "phi3-base"`

### Requirement: Developer commands
The repository SHALL provide commands to install dependencies, run backend and frontend in development mode, run tests, and run linters.

#### Scenario: Fresh setup
- **WHEN** a developer runs `make setup` on a clean clone with Python, uv, and Node installed
- **THEN** backend and frontend dependencies are installed without errors

#### Scenario: Tests and lint pass on scaffold
- **WHEN** a developer runs `make test` and `make lint`
- **THEN** both commands exit with status 0

### Requirement: Frontend shell
The frontend SHALL be a Vite + React + TypeScript + Tailwind application whose dev server proxies `/api` requests to the backend.

#### Scenario: Proxy to backend
- **WHEN** the frontend dev server is running and the browser requests `/api/health`
- **THEN** the request is served by the backend
