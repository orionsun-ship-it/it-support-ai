# IT Support AI

A multi-agent IT support assistant. LangGraph orchestrates four agents
(intake → knowledge → workflow → escalation) with **conditional routing**, an
IT Ops API backed by SQLite, a sentence-transformers + ChromaDB knowledge
base, and a real **Model Context Protocol** server that exposes the same
ticketing/log tools to VS Code and Claude Desktop.

## Problem Statement

Internal IT teams receive repetitive requests: password resets, VPN
troubleshooting, software access, account unlocks. Many can be resolved from
known procedures or safe automations, while urgent or ambiguous cases need
human escalation. This project demonstrates how a routed multi-agent system,
grounded RAG, and a standardized tool layer (MCP) can resolve the resolvable
cases automatically and escalate the rest cleanly.

## Success Metrics

- Classify common IT requests into the correct category with at least 85%
  accuracy.
- Avoid creating tickets for knowledge-only questions.
- Create tickets for urgent, unresolved, or explicitly requested cases.
- Return grounded KB answers with source snippets.
- Route unresolved or critical cases to the escalation agent.

## Quickstart

```bash
make setup    # one-time: venv + pip + npm + .env from .env.example
make dev      # runs ops API (8001), backend (8000), frontend (5173)
```

Open http://localhost:5173. Edit `.env` to set `ANTHROPIC_API_KEY` (you'll be
reminded if you forget). The Claude model defaults to `claude-haiku-4-5-20251001`
— change `CHAT_MODEL` in `.env` to `claude-sonnet-4-6` or `claude-opus-4-6`
for harder questions.

To run the real MCP server (for VS Code / Claude Desktop demos), in a separate
terminal:

```bash
make mcp    # python -m mcp_server.server
```

Setup details, alternative paths, and clean-up are in
[`docs/MCP_VSCode_Demo.md`](docs/MCP_VSCode_Demo.md).

## Agent Architecture

- **Intake Agent** — classifies category, intent, severity, urgency, and
  confidence. Returns a fixed schema so routing stays predictable.
- **Knowledge Agent** — retrieves grounded IT support context from ChromaDB
  with a distance threshold; answers with citations on a strong match,
  declines and asks one clarifying question on a weak match.
- **Workflow Agent** — runs intent-based safe automations (password reset,
  account unlock, software license check, VPN log check) and creates a
  ticket only when needed.
- **Escalation Agent** — gated by explicit rules (low confidence, weak/no
  match, critical severity, high urgency, automation failed). Bumps ticket
  priority to `critical` and produces a specific human-handoff message.

See [`diagrams/architecture.md`](diagrams/architecture.md) for the full
flow.

## Conditional Routing

The LangGraph graph uses conditional edges, not a linear chain. The graph:

```
START → intake →┬─ non-support / low-confidence → final_response
                ├─ low-confidence + support     → escalation
                └─ otherwise                    → knowledge

knowledge →┬─ urgency=high or severity=critical → workflow
           ├─ weak / no KB match                → escalation
           ├─ automatable intent                → workflow
           └─ otherwise                         → final_response

workflow  →┬─ automation failed / manual        → escalation
           └─ otherwise                         → final_response

escalation → final_response → END
```

Example routes:

| Message                                            | Route                                                |
| -------------------------------------------------- | ---------------------------------------------------- |
| "How do I clear my browser cache?"                 | intake → knowledge → final_response                  |
| "I forgot my password"                             | intake → knowledge → workflow → final_response       |
| "VPN is down for the whole team"                   | intake → knowledge → workflow → escalation → final_response |
| "Tell me a joke"                                   | intake → final_response                              |

Each `/chat` response includes the actual route trace, the ticket-decision
reason, the automation status, and per-turn category/intent classification.
These fields are inspectable via `curl` and asserted by the test harness:

```bash
curl -s -X POST http://localhost:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"I forgot my password","session_id":"demo"}' | jq .
```

## MCP Integration

The repo includes a real MCP server (`mcp_server/server.py`) built on
`mcp.server.fastmcp.FastMCP`. It runs over stdio and exposes the same tools
the LangGraph agent uses internally.

Tools exposed:

- `create_ticket`, `list_tickets`, `update_ticket_status`, `update_ticket_priority`
- `analyze_logs`, `recent_errors`

Both transports — the HTTP IT Ops API and the MCP server — read and write the
same SQLite database (`services/it_ops_api/it_ops.db`). A ticket created from
VS Code Copilot Chat shows up in the web Tickets page, and vice versa.

Connect VS Code or Claude Desktop to it by following
[`docs/MCP_VSCode_Demo.md`](docs/MCP_VSCode_Demo.md). It also includes an
optional appendix for wiring the official GitHub MCP server into the same
client to demonstrate that the same protocol works across vendors — that is
the standardization story.

## Knowledge base

KB content lives in JSON files under `backend/data/kb/` (default:
`it_support.json`, 16 docs). The ingestion pipeline chunks each body, hashes
each chunk with SHA-256, and only re-embeds new or changed chunks. Run after
edits:

```bash
make ingest
```

## Endpoints

Backend (`localhost:8000`):

- `POST /chat` — main chat endpoint; returns content, sources, route trace,
  ticket decision reason, automation status, etc.
- `GET /tickets` / `POST /tickets`
- `GET /metrics` — uptime, request counts, escalations, KB status, ops-API status
- `GET /sources` — every KB document on disk
- `GET /session/{id}`
- `GET /debug/retrieve?query=...` — gated by `ENABLE_DEBUG_ENDPOINTS`
- `GET /health`

IT Ops API (`localhost:8001`, all `/api/v1/*` routes require `X-Internal-Token`):

- `POST /api/v1/tickets`, `GET /api/v1/tickets`, `GET /api/v1/tickets/{id}`
- `PATCH /api/v1/tickets/{id}/status`, `PATCH /api/v1/tickets/{id}/priority`
- `GET /api/v1/tickets/{id}/events`
- `POST /api/v1/logs/analyze`, `GET /api/v1/logs/recent_errors`
- `GET /health/live`, `GET /health/ready`

## Validation

Test scenarios cover:

- Knowledge-only troubleshooting (browser cache, error 1603, Outlook)
- Password reset (automation expected)
- Account unlock (automation expected)
- Critical VPN outage (ticket + escalation expected)
- Explicit ticket request
- Non-support requests (no ticket, no escalation)

Run them:

```bash
make test
```

The harness mocks the ops API client (so it doesn't need the ops service
running), but does call Claude through `langchain-anthropic` — expect a small
amount of API spend per run. A timestamped JSON report is written to
`tests/results/`. The summary prints per-axis accuracy:

```
category_accuracy        87.5%
ticket_accuracy          100.0%
escalation_accuracy      100.0%
route_accuracy           87.5%
automation_accuracy      100.0%
```

## Configuration

All env vars live in `.env`. See `.env.example`. Notable ones:

- `ANTHROPIC_API_KEY` — required.
- `CHAT_MODEL` — default `claude-haiku-4-5-20251001`. Other valid:
  `claude-sonnet-4-6`, `claude-opus-4-6`.
- `IT_OPS_API_TOKEN` — shared secret between backend and ops API.
- `RAG_DISTANCE_THRESHOLD` — distance below which a match counts as "strong"
  (default `0.85`).
- `ALLOWED_ORIGINS` — comma-separated CORS allowlist.
- `ENABLE_DEBUG_ENDPOINTS` — gate `/debug/retrieve`.

## Project layout

```
it-support-ai/
├── backend/
│   ├── agents/           # intake, knowledge, workflow, escalation, orchestrator
│   ├── rag/              # embedder, vector_store, ingest, retriever
│   ├── services/         # it_ops_client (HTTP)
│   ├── models/schemas.py
│   ├── data/kb/          # JSON KB documents
│   ├── config.py
│   └── main.py
├── services/
│   └── it_ops_api/       # FastAPI + SQLModel ticketing service
├── mcp_server/           # Real MCP server (FastMCP / stdio)
│   ├── server.py         # entry point: `python -m mcp_server.server`
│   ├── tools/__init__.py # @mcp.tool definitions
│   └── store.py          # shared functional wrapper over the SQLite store
├── frontend/             # Vite + React (calm enterprise UI)
├── tests/                # accuracy harness with mocked ops client
├── docs/MCP_VSCode_Demo.md
├── diagrams/architecture.md
├── scripts/dev.sh
├── Makefile
├── pyproject.toml        # black + ruff config
├── requirements.txt
├── requirements-dev.txt
└── .env.example
```

## Status

Capstone project — not deployed. Sessions and request metrics are still
in-process for simplicity. Don't deploy this as-is; for production move
sessions to Redis or Postgres, restrict CORS to explicit origins, and rotate
`IT_OPS_API_TOKEN`.
