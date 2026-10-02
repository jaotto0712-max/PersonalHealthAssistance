## 1. Repository skeleton

- [x] 1.1 Create `backend/`, `frontend/`, `training/`, `eval/`, `models/`, `data/` directories with `.gitkeep` where needed
- [x] 1.2 Add `.gitignore` covering `models/**` (except `Modelfile`), `data/**`, `.env`, Python and Node build artifacts
- [x] 1.3 Add `README.md` skeleton: project summary, architecture sketch, medical disclaimer, prerequisites (Python, uv, Node, Ollama)

## 2. Backend bootstrap

- [x] 2.1 Initialize `backend/` with uv (`pyproject.toml`, package `pha`), add FastAPI, uvicorn, pydantic-settings
- [x] 2.2 Add ruff and pytest (with pytest-asyncio and httpx) as dev dependencies and configure them in `pyproject.toml`
- [x] 2.3 Implement `pha/config.py` settings object with `PHA_` prefix, `.env` support, and documented defaults
- [x] 2.4 Implement `pha/main.py` FastAPI app with `GET /api/health` returning status and version
- [x] 2.5 Add `.env.example` documenting every setting

## 3. Offline runtime policy

- [x] 3.1 Set `HF_HUB_OFFLINE`, `TRANSFORMERS_OFFLINE`, `ANONYMIZED_TELEMETRY` at the top of the app entrypoint before ML imports
- [x] 3.2 Validate at startup that bind host and Ollama URL host are loopback; fail fast with a clear message otherwise
- [x] 3.3 Add a pytest socket-guard fixture that rejects non-loopback connections and apply it to the backend test suite
- [x] 3.4 Write tests: health endpoint, settings defaults/overrides, loopback validation rejects `0.0.0.0` and remote Ollama

## 4. Frontend bootstrap

- [x] 4.1 Scaffold `frontend/` with Vite React-TS template
- [x] 4.2 Add Tailwind and a placeholder page that calls `/api/health` and displays the result
- [x] 4.3 Configure Vite dev proxy `/api` → `http://127.0.0.1:8000`
- [x] 4.4 Add a script that scans the production build for remote asset URLs and fails if any are found

## 5. Developer workflow

- [x] 5.1 Add `Makefile` targets: `setup`, `dev-backend`, `dev-frontend`, `dev`, `test`, `lint`
- [x] 5.2 Add GitHub Actions workflow running lint and tests for backend and frontend
- [x] 5.3 Verify `make setup && make test && make lint` passes on a clean clone
