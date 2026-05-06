# IT Support AI

A multi-agent AI IT support system built with LangGraph, FastAPI, ChromaDB, a local MCP-style tool server, and a React + Vite frontend.

## Architecture

The system runs as **three independent processes**:

1. **MCP Tool Server** (port `8001`) — A simplified MCP-style tool server that exposes ticket and log analysis tools over HTTP. This demonstrates the same standardized tool-access pattern used in production MCP integrations (e.g. VS Code → GitHub/Jira).
2. **FastAPI Backend** (port `8000`) — Hosts the LangGraph orchestrator and four specialized agents (intake, knowledge, workflow, escalation). Calls the MCP server for ticket and log tools, and uses ChromaDB for RAG.
3. **React Frontend** (port `5173`) — A clean, utilitarian internal IT tool UI built with Vite. Proxies `/api/*` to the FastAPI backend.

## Setup

```bash
# Install Python dependencies
pip install -r requirements.txt

# Copy and fill out environment variables
cp .env.example .env
# Edit .env and set ANTHROPIC_API_KEY

# Install frontend dependencies
cd frontend
npm install
cd ..
```

## Running the system

Start the three processes in this **order**, each in its own terminal:

### 1. Start the MCP tool server (port 8001)

```bash
uvicorn mcp_server.server:app --port 8001 --reload
```

Sanity check:

```bash
curl http://localhost:8001/health
```

### 2. Start the FastAPI backend (port 8000)

```bash
uvicorn backend.main:app --port 8000 --reload
```

On first start the backend will seed the ChromaDB knowledge base with ~15 IT support documents. Subsequent starts skip seeding.

Sanity check:

```bash
curl http://localhost:8000/health
```

### 3. Start the React frontend (port 5173)

```bash
cd frontend
npm run dev
```

Open http://localhost:5173 in your browser.

## Key endpoints

Backend (`localhost:8000`):

- `POST /chat` — main chat endpoint
- `GET /tickets` — list tickets (proxied from MCP server)
- `POST /tickets` — create a ticket
- `GET /metrics` — system metrics
- `GET /session/{session_id}` — session state
- `GET /debug/retrieve?query=...` — RAG debug
- `GET /health` — health check (also reports MCP availability)

MCP server (`localhost:8001`):

- `POST /tools/create_ticket`
- `GET /tools/list_tickets`
- `PATCH /tools/tickets/{ticket_id}/status`
- `POST /tools/analyze_logs`
- `GET /tools/recent_errors`
- `GET /health`

## Testing

```bash
python tests/test_accuracy.py
```

Test scenarios live in `tests/test_scenarios.json` and results are written to `tests/results/`.
