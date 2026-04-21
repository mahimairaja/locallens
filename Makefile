.PHONY: all setup dev stop test test-quick lint clean docs docs-build rust-dev rust-build rust-test bench

VENV := .venv
UVICORN := $(VENV)/bin/uvicorn
PYTHON := $(shell test -x $(VENV)/bin/python && echo $(VENV)/bin/python || echo python3)

all: setup

setup:
	docker compose up -d qdrant
	ollama pull qwen2.5:3b
	test -d $(VENV) || uv venv $(VENV)
	uv pip install --python $(VENV)/bin/python -r backend/requirements.txt
	cd frontend && npm install

dev:
	docker compose up -d qdrant
	cd backend && ../$(UVICORN) app.main:app --reload --port 8000 &
	cd frontend && npm run dev

stop:
	docker compose down
	pkill -f uvicorn || true

test:
	@curl -sf http://localhost:6333/healthz >/dev/null 2>&1 || docker compose up -d qdrant
	pip install -e ".[test]" --quiet
	pytest tests/ -v --tb=short

test-quick:
	@curl -sf http://localhost:6333/healthz >/dev/null 2>&1 || docker compose up -d qdrant
	pip install -e ".[test]" --quiet
	pytest tests/ -v --tb=short -m "not slow"

lint:
	@command -v ruff >/dev/null 2>&1 && ruff check . || echo "ruff not installed, skipping lint"

docs:
	cd docs && npm run docs:dev

docs-build:
	cd docs && npm run docs:build

rust-dev:
	maturin develop --release

rust-build:
	maturin build --release

rust-test:
	cargo test

bench:
	$(PYTHON) scripts/bench_pipeline.py --files 200 --mock-embed

clean:
	@echo "Removing caches and build artifacts..."
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache
	rm -rf dist build
	@if [ -d data/qdrant ]; then \
		printf "Remove data/qdrant? [y/N] "; \
		read ans; \
		if [ "$$ans" = "y" ] || [ "$$ans" = "Y" ]; then \
			rm -rf data/qdrant; \
			echo "Removed data/qdrant"; \
		fi; \
	fi
