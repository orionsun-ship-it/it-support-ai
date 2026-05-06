.PHONY: help setup dev backend ops frontend ingest test clean

help:
	@echo "IT Support AI — common commands"
	@echo ""
	@echo "  make setup    Create venv, install Python + npm deps, copy .env"
	@echo "  make dev      Start ops API (8001), backend (8000), and frontend (5173)"
	@echo "  make ops      Run only the IT Ops API on :8001"
	@echo "  make backend  Run only the backend on :8000"
	@echo "  make frontend Run only the frontend on :5173"
	@echo "  make ingest   Re-run the KB ingestion pipeline"
	@echo "  make test     Run the accuracy harness (uses live LLM)"
	@echo "  make clean    Remove venv, node_modules, chroma_db, and the SQLite db"

setup:
	@if [ ! -d .venv ]; then python3 -m venv .venv; fi
	. .venv/bin/activate && pip install --upgrade pip && pip install -r requirements.txt
	cd frontend && npm install
	@if [ ! -f .env ]; then cp .env.example .env; echo "[setup] Created .env — edit and set ANTHROPIC_API_KEY"; fi
	@echo "[setup] Done. Run 'make dev' to start all three services."

dev:
	./scripts/dev.sh

ops:
	. .venv/bin/activate && uvicorn services.it_ops_api.main:app --port 8001 --reload

backend:
	. .venv/bin/activate && uvicorn backend.main:app --port 8000 --reload

frontend:
	cd frontend && npm run dev

ingest:
	. .venv/bin/activate && python -m backend.rag.ingest

test:
	. .venv/bin/activate && python tests/test_accuracy.py

clean:
	rm -rf .venv chroma_db services/it_ops_api/it_ops.db services/it_ops_api/it_ops.db-* frontend/node_modules
