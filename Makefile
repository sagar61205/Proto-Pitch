# ProtoPitch development commands. Run from the repository root.
# No API keys, local models or Docker are needed for: setup, start, dev, check.

UV := uv run --project backend
.DEFAULT_GOAL := help
.PHONY: help setup start dev dev-api dev-worker dev-web build-web check check-backend \
        check-frontend check-demo-shell api-types api-types-check sandbox-images sandbox-lock \
        sandbox-test e2e probe

help:
	@echo "make setup           install backend and frontend dependencies"
	@echo "make start           build the web interface and run ProtoPitch on http://127.0.0.1:8000"
	@echo "make dev             API, worker and web dev server with reload (http://127.0.0.1:5173)"
	@echo "make check           fast checks: format, lint, types, unit tests (before every commit)"
	@echo "make sandbox-images  build the hash-pinned sandbox image (needs Docker and network)"
	@echo "make sandbox-test    sandbox isolation suite (needs Docker and the sandbox image)"
	@echo "make e2e             browser smoke test against the real server"
	@echo "make probe           report whether prototype generation is available"

setup:
	cd backend && uv sync
	cd frontend && npm ci --no-fund --no-audit
	cd demo-shell && npm ci --no-fund --no-audit

build-web:
	cd frontend && npm run build

# One command from a fresh clone: installs what is missing, builds the UI, runs API + worker.
start: setup build-web
	$(UV) protopitch serve --with-worker

dev:
	$(MAKE) -j3 dev-api dev-worker dev-web

dev-api:
	cd backend && uv run uvicorn --factory protopitch.api.app:create_app --reload \
		--host 127.0.0.1 --port 8000 --no-access-log

dev-worker:
	$(UV) protopitch worker

dev-web:
	cd frontend && npm run dev

check: check-backend check-frontend check-demo-shell api-types-check

check-backend:
	cd backend && uv run ruff format --check . && uv run ruff check . && uv run mypy && uv run pytest

check-frontend:
	cd frontend && npm run typecheck && npm run lint && npm test

check-demo-shell:
	cd demo-shell && npm run typecheck && npm test

# The frontend's API types are generated from the backend's OpenAPI schema.
api-types:
	$(UV) protopitch openapi > frontend/openapi.json
	cd frontend && npm run api-types

api-types-check: api-types
	git diff --exit-code -- frontend/openapi.json frontend/src/api/schema.d.ts

sandbox-images:
	python3 scripts/build_sandbox_images.py

sandbox-lock:
	python3 scripts/build_sandbox_images.py --lock

sandbox-test:
	cd backend && uv run pytest -m docker

e2e: build-web
	cd frontend && npx playwright test --trace off

probe:
	$(UV) protopitch probe
