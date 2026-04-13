.PHONY: setup dev stop

VENV := .venv
UVICORN := $(VENV)/bin/uvicorn

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
