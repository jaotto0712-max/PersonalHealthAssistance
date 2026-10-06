.PHONY: setup dev dev-mock dev-backend dev-frontend build start test test-backend test-training test-frontend lint medquad eval eval-report

setup:
	cd backend && uv sync
	cd frontend && npm install

# Runs backend (127.0.0.1:8000) and frontend (127.0.0.1:5173) together; Ctrl+C stops both.
dev:
	$(MAKE) -j2 dev-backend dev-frontend

dev-backend:
	cd backend && uv run python -m pha --reload

dev-frontend:
	cd frontend && npm run dev

# Frontend only, against the in-memory mock API (no backend or Ollama needed).
dev-mock:
	cd frontend && npm run dev:mock

build:
	cd frontend && npm run build

# Production-style: build the UI, then serve UI + API together at http://127.0.0.1:8000
start: build
	cd backend && uv run python -m pha

test: test-backend test-training test-frontend

test-backend:
	cd backend && uv run pytest -q

test-training:
	cd backend && uv run pytest -q ../training/tests ../eval/tests -p no:cacheprovider

# Full evaluation (cached; needs the Ollama models) and the Markdown report
eval:
	backend/.venv/bin/python -m eval.run_eval
	backend/.venv/bin/python -m eval.report

eval-report:
	backend/.venv/bin/python -m eval.report

# Download pinned MedQuAD and write data/medquad/{train,val,test}.jsonl + stats.json
medquad:
	cd backend && uv run python ../training/prepare_medquad.py --download

test-frontend: build
	cd frontend && npm test && npm run check:offline

lint:
	cd backend && uv run ruff check . ../training ../eval && uv run ruff format --check . ../training ../eval
	cd frontend && npm run lint && npm run typecheck
