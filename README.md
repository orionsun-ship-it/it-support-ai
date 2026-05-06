# IT Support AI

A multi-agent IT support assistant. LangGraph orchestrates four agents (intake → knowledge → workflow → escalation) on top of:

- a real **IT Ops API** (FastAPI + SQLModel + SQLite) that owns tickets, ticket events, and audit logs
- a **RAG knowledge base** (sentence-transformers + ChromaDB) ingested from JSON files under `backend/data/kb/`
- a **React + Vite** internal frontend

## Quickstart (two commands)

```bash
make setup    # one-time: venv + pip + npm + .env from .env.example
make dev      # runs all three services with one Ctrl+C to stop everything
```

Open http://localhost:5173. Edit `.env` to set `ANTHROPIC_API_KEY` (you'll be reminded if you forget).

If you don't have `make`, run `./scripts/dev.sh` after a manual setup:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
(cd frontend && npm install)
cp .env.example .env  # edit ANTHROPIC_API_KEY
./scripts/dev.sh
```

## Architecture

Three independent services:

1. **IT Ops API** — port `8001` — FastAPI service backed by SQLite (`services/it_ops_api/it_ops.db`). Handles tickets, ticket events, audit logs, and log analysis. Token-protected via `X-Internal-Token`.
2. **Backend** — port `8000` — FastAPI app hosting the LangGraph orchestrator. Talks to the ops API through a single typed client (`backend/services/it_ops_client.py`).
3. **Frontend** — port `5173` — React + Vite, proxies `/api/*` to the backend.

Agent flow on every chat turn:

```
intake → knowledge → workflow → escalation
```

The orchestrator only opens a ticket when it should: greetings and how-to questions answered by the KB do not create tickets. Tickets are only created for explicit escalations, weak/no-match KB results, or high-urgency messages. Priority is computed from severity + urgency, never from classifier confidence.

## Endpoints

Backend (`localhost:8000`):

- `POST /chat` — main chat endpoint, returns content + sources + match_strength
- `GET /tickets` / `POST /tickets`
- `GET /metrics` — uptime, request counts, escalations, KB status, ops-API status
- `GET /session/{id}`
- `GET /debug/retrieve?query=...` — disabled when `ENABLE_DEBUG_ENDPOINTS=false`
- `GET /health`

IT Ops API (`localhost:8001`, all `/api/v1/*` routes require `X-Internal-Token`):

- `POST /api/v1/tickets`, `GET /api/v1/tickets`, `GET /api/v1/tickets/{id}`
- `PATCH /api/v1/tickets/{id}/status`, `PATCH /api/v1/tickets/{id}/priority`
- `GET /api/v1/tickets/{id}/events`
- `POST /api/v1/logs/analyze`, `GET /api/v1/logs/recent_errors`
- `GET /health/live`, `GET /health/ready`

## Knowledge base ingestion

KB content lives in JSON files under `backend/data/kb/`. The default file `it_support.json` ships with 16 IT support docs. To add or edit content, change the JSON and re-run:

```bash
make ingest
```

The ingester chunks bodies, hashes each chunk, and only re-embeds new or changed chunks. Chunks whose source doc was removed from disk are deleted from Chroma.

## Tests

```bash
make test
```

Runs `tests/test_accuracy.py`, which invokes the full agent graph but mocks the ops API client so it doesn't need the ops service running. It still calls Claude Haiku, so it uses a small amount of API credit.

## Configuration

All env vars live in `.env`. See `.env.example` for the full list. The interesting ones:

- `ANTHROPIC_API_KEY` — required
- `IT_OPS_API_TOKEN` — shared secret between the backend and the ops API
- `RAG_DISTANCE_THRESHOLD` — distance below which a match is considered "strong" (default `0.85`)
- `ALLOWED_ORIGINS` — comma-separated CORS allowlist
- `ENABLE_DEBUG_ENDPOINTS` — gate `/debug/retrieve`
- `ENV=prod` — refuses to start without a real `IT_OPS_API_TOKEN`

## Project layout

```
it-support-ai/
├── backend/
│   ├── agents/           # intake, knowledge, workflow, escalation, orchestrator
│   ├── rag/              # embedder, vector_store, ingest, retriever
│   ├── services/         # typed it_ops_client
│   ├── models/schemas.py # pydantic models
│   ├── data/kb/          # JSON KB documents
│   ├── config.py         # pydantic-settings
│   └── main.py
├── services/
│   └── it_ops_api/       # FastAPI + SQLModel ticketing service
│       ├── main.py
│       ├── db.py
│       ├── models.py
│       ├── auth.py
│       ├── log_analyzer.py
│       └── sample_logs/
├── frontend/             # Vite + React
├── tests/                # accuracy harness with mocked ops client
├── scripts/dev.sh        # one-script runner
├── Makefile              # make setup / make dev / make test / make clean
├── requirements.txt      # pinned versions
└── .env.example
```

## Status

This is a capstone project — not production-ready. Module-level dicts still hold sessions and request metrics. CORS is open enough for local dev. Don't deploy this as-is. Future work: move sessions to Redis or the DB, add `pyproject.toml` and ruff/black/pytest configs, add Alembic migrations, and a docker-compose for full deploys.
