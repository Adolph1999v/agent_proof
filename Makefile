SHELL := /bin/bash

PYTHON_VERSION := 3.12
VENV := .venv
PYTHON := $(VENV)/bin/python
UV_ENV := UV_CACHE_DIR=$(CURDIR)/.uv-cache UV_PYTHON_INSTALL_DIR=$(CURDIR)/.python
BACKEND_PORT ?= 8000
FRONTEND_PORT ?= 5173

.PHONY: help setup lock dev dev-backend dev-frontend test test-backend test-frontend lint lint-backend lint-frontend build check phase3-smoke

help:
	@echo "AgentProof commands"
	@echo "  make setup          Install isolated Python and frontend dependencies"
	@echo "  make dev            Start both services and open AgentProof in the browser"
	@echo "  make test           Run backend and frontend tests"
	@echo "  make lint           Run Python linting and frontend type checks"
	@echo "  make build          Build the frontend production bundle"
	@echo "  make check          Run lint, tests, and the production build"
	@echo "  make phase3-smoke   Run one synthetic smoke case against a loaded local model"
	@echo "  make lock           Regenerate requirements.txt with uv"

setup:
	$(UV_ENV) uv python install $(PYTHON_VERSION)
	$(UV_ENV) uv venv --python $(PYTHON_VERSION) $(VENV)
	UV_CACHE_DIR=$(CURDIR)/.uv-cache uv pip install --python $(PYTHON) -r requirements.txt
	cd frontend && npm install

lock:
	UV_CACHE_DIR=$(CURDIR)/.uv-cache uv pip compile pyproject.toml --extra dev --output-file requirements.txt

dev:
	$(PYTHON) scripts/dev.py --backend-port $(BACKEND_PORT) --frontend-port $(FRONTEND_PORT)

dev-backend:
	$(PYTHON) -m uvicorn agentproof.app:app --app-dir backend --host 127.0.0.1 --port $(BACKEND_PORT) --reload

dev-frontend:
	cd frontend && VITE_API_TARGET=http://127.0.0.1:$(BACKEND_PORT) npm run dev -- --host 127.0.0.1 --port $(FRONTEND_PORT)

test: test-backend test-frontend

test-backend:
	$(PYTHON) -m pytest backend/tests

test-frontend:
	cd frontend && npm test

lint: lint-backend lint-frontend

lint-backend:
	$(PYTHON) -m ruff check backend scripts

lint-frontend:
	cd frontend && npm run lint

build:
	cd frontend && npm run build

check: lint test build

phase3-smoke:
	PYTHONPATH=$(CURDIR)/backend $(PYTHON) scripts/phase3_smoke.py
