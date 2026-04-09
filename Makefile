.PHONY: setup dev stop

setup:
	docker compose up -d qdrant
	ollama pull qwen2.5:3b
	cd backend && pip install -r requirements.txt
	cd frontend && npm install

dev:
	docker compose up -d qdrant
	cd backend && uvicorn app.main:app --reload --port 8000 &
	cd frontend && npm run dev

stop:
	docker compose down
	pkill -f uvicorn || true
