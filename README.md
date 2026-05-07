# IT Support AI

A multi-agent IT support assistant. LangGraph orchestrates four agents
(intake → knowledge → workflow → escalation) with **conditional routing**, an
IT Ops API backed by SQLite, a sentence-transformers + ChromaDB knowledge
base, and a real **Model Context Protocol** server that exposes the same
ticketing/log tools to VS Code and Claude Desktop.

This is a capstone project. See the [docs/](docs/) folder for product,
UX, MCP-proof, industry-comparison, validation, and presentation companions
that map 1:1 to the eight grading checkpoints. A grader who only reads
[`docs/PRESENTATION.md`](docs/PRESENTATION.md) will get the full picture.

## Repository tour 

| Checkpoint                                | Where                                                                       |
| ----------------------------------------- | --------------------------------------------------------------------------- |
| 1. Problem definition & use case clarity  | [docs/PRODUCT.md](docs/PRODUCT.md), this README "Problem statement"         |
| 2. Product ownership perspective          | [docs/PRODUCT.md](docs/PRODUCT.md) "Ownership", [docs/PRESENTATION.md](docs/PRESENTATION.md) |
| 3. Agent architecture & role definition   | [diagrams/architecture.md](diagrams/architecture.md), this README "Agents"  |
| 4. RAG integration & knowledge management | [docs/PRODUCT.md](docs/PRODUCT.md) "RAG", `backend/rag/`, `backend/data/kb/` |
| 5. Workflow automation                    | `backend/agents/workflow_agent.py`, this README "Simulated automations"     |
| 6. UX design & user experience            | [docs/UX.md](docs/UX.md), `frontend/src/`                                   |
| 7. Technical implementation (incl. MCP)   | [docs/MCP_PROOF.md](docs/MCP_PROOF.md), `mcp_server/`                       |
| 8. Validation & testing                   | [docs/VALIDATION.md](docs/VALIDATION.md), `tests/`                          |
| Industry context                          | [docs/INDUSTRY_COMPARISON.md](docs/INDUSTRY_COMPARISON.md)                  |

## Problem statement

Internal IT teams receive repetitive requests: password resets, VPN
troubleshooting, software access, account unlocks. Many can be resolved from
known procedures or safe automations, while urgent or ambiguous cases need
human escalation. This project demonstrates how a routed multi-agent system,
grounded RAG, and a standardized tool layer (MCP) can resolve the resolvable
cases automatically and escalate the rest cleanly.

Full pain-point analysis, target users, and SLA targets:
[docs/PRODUCT.md](docs/PRODUCT.md).

## Success metrics

The deterministic harness in `tests/test_routing.py` enforces all of these
on every run; the live-LLM harness in `tests/test_accuracy.py` measures
classification accuracy against Claude.

| Axis                                               | Target | Measured by                                   |
| -------------------------------------------------- | ------ | --------------------------------------------- |
| Correct route trace                                | 100%   | `tests/test_routing.py` `route_trace` check   |
| Correct ticket-creation decision                   | 100%   | `tests/test_routing.py` `should_create_ticket`|
| Correct escalation decision                        | 100%   | `tests/test_routing.py` `escalated`           |
| Correct automation status                          | 100%   | `tests/test_routing.py` `automation_status`   |
| Category classification (live LLM, fuzzier signal) | ≥ 85%  | `tests/test_accuracy.py`                      |
| MCP/HTTP cross-transport parity                    | 100%   | `tests/test_mcp_proof.py`                     |

A current sample report is at `tests/results/latest-summary.md` (regenerated
every time you run `make test`).

## Quickstart

This project pins **Python 3.11**. Install it (e.g. `brew install python@3.11`,
`pyenv install 3.11`, or the [python.org](https://python.org/downloads/)
installer) before running setup. The Makefile checks for `python3.11` on
your PATH and fails fast if it's missing.

```bash
make setup    # one-time: venv + pip + npm + .env from .env.example
make dev      # runs ops API (8001), backend (8000), frontend (5173)
```

Open http://localhost:5173. Edit `.env` to set `ANTHROPIC_API_KEY` (you'll be
reminded if you forget). The Claude model defaults to `claude-haiku-4-5-20251001`
— change `CHAT_MODEL` in `.env` to `claude-sonnet-4-6` or `claude-opus-4-6`
for harder questions.

Setup details, alternative paths, and clean-up are in
[`docs/MCP_VSCode_Demo.md`](docs/MCP_VSCode_Demo.md). The end-to-end proof
that MCP and HTTP land in the same database is in
[`docs/MCP_PROOF.md`](docs/MCP_PROOF.md).

## Agents

- **Intake Agent** — classifies category, intent, severity, urgency, and
  confidence. Returns a fixed schema so routing stays predictable.
  Implemented in `backend/agents/intake_agent.py`.
- **Knowledge Agent** — retrieves grounded IT support context from ChromaDB
  with a distance threshold; answers with citations on a strong match,
  and falls back to a "best-effort general answer + check-in question" on
  weak/no match (so the user gets help instead of an immediate handoff).
  Implemented in `backend/agents/knowledge_agent.py`.
- **Workflow Agent** — runs intent-based safe automations (password reset,
  account unlock, software license check, software install, access request,
  VPN log check, status check) and creates a ticket only when needed.
  Implemented in `backend/agents/workflow_agent.py`.
- **Escalation Agent** — gated by routing rules (the user explicitly asks
  for a human, the user confirms a suggested fix didn't work, automation
  failed or requires manual approval, or the request is critical-severity
  / high-urgency). Bumps ticket priority to `critical` and produces a
  specific human-handoff message.
  Implemented in `backend/agents/escalation_agent.py`.

See [`diagrams/architecture.md`](diagrams/architecture.md) for the full
flow.

## Conditional routing

The LangGraph graph uses conditional edges, not a linear chain. The actual
implementation in `backend/agents/orchestrator.py`:

```
START → intake →┬─ is_support_request == False  → final_response
                └─ otherwise                    → knowledge

knowledge →┬─ intent == ticket_request                 → workflow
           ├─ requires_automation                      → workflow
           ├─ user already tried & is stuck / asks
           │  for a human ("escalate", "real person",
           │  "still didn't work", …)                  → escalation
           └─ otherwise                                → final_response

workflow  →┬─ automation failed / manual_required     → escalation
           ├─ severity == critical OR urgency == high  → escalation
           └─ otherwise                                → final_response

escalation → final_response → END
```

Why escalate from `workflow` on critical / high urgency even after a
successful automation? Because a successful automation alone doesn't
mean the underlying incident is resolved — a "VPN is down for the whole
team" report deserves a human pickup even if the canned log-check
completed.

Example routes (every one of these is enforced by
`tests/test_routing.py`):

| Message                                          | Route                                                       |
| ------------------------------------------------ | ----------------------------------------------------------- |
| "How do I clear my browser cache?"               | intake → knowledge → final_response                         |
| "I forgot my password and need a reset link."    | intake → knowledge → workflow → final_response              |
| "VPN is down for the whole team and nobody can work." | intake → knowledge → workflow → escalation → final_response |
| "Please create a ticket for my broken laptop screen." | intake → knowledge → workflow → final_response             |
| "I tried that but it still didn't work."         | intake → knowledge → escalation → final_response            |
| "Can you write me a poem about coffee?"          | intake → final_response                                     |

Each `/chat` response includes the actual route trace, the ticket-decision
reason, the automation status, and per-turn category/intent classification.
These fields are inspectable via `curl`, asserted by the test harness, and
**rendered in the chat UI under each assistant message** (click "Route trace"
to expand) so a grader can see exactly which agents fired and why.

```bash
curl -s -X POST http://localhost:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"I forgot my password","session_id":"demo"}' | jq .
```

## Simulated automations (be honest about what's real)

Most automations in this capstone are **stubs** that return canned success
strings. They are tagged `automation_simulated: true` in the API response,
their text is prefixed `[Simulated]`, and the chat UI surfaces a
`Simulated automation` chip on every such turn. Two intents do call real
subsystems:

| Intent                  | Status      | What actually happens                                                    |
| ----------------------- | ----------- | ------------------------------------------------------------------------ |
| `password_reset`        | Simulated   | Returns a canned "[Simulated] Password reset link sent" message.         |
| `account_unlock`        | Simulated   | Returns a canned "[Simulated] Account unlock submitted" message.         |
| `software_license_check`| Simulated   | Returns a canned "[Simulated] License is active" message.                |
| `software_install`      | Simulated   | Returns a canned "[Simulated] Install request submitted" message.        |
| `access_request`        | Simulated   | Returns a canned "[Simulated] Access request submitted" message.         |
| `vpn_log_check`         | **Real**    | Reads sample log files via the IT Ops API `/api/v1/logs/analyze` route.  |
| `status_check`          | **Real**    | Queries the actual ticket DB via the IT Ops API.                         |

In a production deployment the simulated paths would call enterprise
identity, asset-management, and access-management systems via their own
adapters. The architecture treats automations as a list of pluggable
intent handlers, so adding a real one is a localised change in
`backend/agents/workflow_agent.py`.

## MCP integration

The repo includes a real MCP server (`mcp_server/server.py`) built on
`mcp.server.fastmcp.FastMCP`. It runs over stdio and exposes the same tools
the LangGraph agent uses internally.

Tools exposed:

- `create_ticket`, `list_tickets`, `update_ticket_status`, `update_ticket_priority`
- `analyze_logs`, `recent_errors`

Both transports — the HTTP IT Ops API and the MCP server — read and write
the same SQLite database (`services/it_ops_api/it_ops.db`). A ticket created
from VS Code Copilot Chat shows up in the web Tickets page, and vice versa.

Three layers of evidence for graders:

1. **Code** — `mcp_server/store.py` shows the shared store helpers wrapped
   by both the FastMCP tools and the FastAPI ops API.
2. **Doc** — [`docs/MCP_VSCode_Demo.md`](docs/MCP_VSCode_Demo.md) walks
   through wiring VS Code Copilot Chat / Claude Desktop to the server.
3. **Test** — `tests/test_mcp_proof.py` (run via `make test-mcp`) creates a
   ticket via the MCP store, fetches it via the HTTP API, mutates it via
   MCP, re-fetches via HTTP, and writes a JSON report.
   [`docs/MCP_PROOF.md`](docs/MCP_PROOF.md) explains the proof step-by-step.

The optional appendix in `docs/MCP_VSCode_Demo.md` shows wiring the
official GitHub MCP server into the same client to demonstrate that the
same protocol works across vendors — that is the standardisation story.

## Knowledge base

KB content lives in JSON files under `backend/data/kb/` (default:
`it_support.json`, **130 documents** spanning password, access, software,
hardware, network, email, vpn, security, mobile, remote, printing,
endpoint, storage, collaboration, onboarding, compliance, and operations
categories). The ingestion pipeline chunks each body, hashes each chunk
with SHA-256, and only re-embeds new or changed chunks. Run after edits:

```bash
make ingest
```

Retrieval uses sentence-transformers (`all-MiniLM-L6-v2` by default) +
ChromaDB. The `KnowledgeRetriever` adds a category filter (when intake
confidence ≥ 0.7), a distance threshold for "strong vs weak" classification,
and a keyword-rescue path for known error tokens (e.g. `1603`, hex codes,
`PAGE_FAULT_IN_NONPAGED_AREA`) so we don't lose the right doc to a fuzzy
embedding miss. See `backend/rag/retriever.py`.

## Endpoints

Backend (`localhost:8000`):

- `POST /chat` — main chat endpoint; returns content, sources, route trace,
  ticket decision reason, automation status / simulated flag, etc.
- `GET /tickets` / `POST /tickets` / `DELETE /tickets/{id}` /
  `PATCH /tickets/{id}/status`
- `POST /feedback` — thumbs up/down on an assistant turn
- `GET /metrics` — uptime, request counts, escalations, KB status, ops-API
  status, satisfaction
- `GET /sources` — every KB document on disk
- `GET /session/{id}`
- `GET /debug/retrieve?query=...` — gated by `ENABLE_DEBUG_ENDPOINTS`
- `GET /health`

IT Ops API (`localhost:8001`, all `/api/v1/*` routes require `X-Internal-Token`):

- `POST /api/v1/tickets`, `GET /api/v1/tickets`, `GET /api/v1/tickets/{id}`
- `PATCH /api/v1/tickets/{id}/status`, `PATCH /api/v1/tickets/{id}/priority`
- `DELETE /api/v1/tickets/{id}`
- `GET /api/v1/tickets/{id}/events`
- `POST /api/v1/logs/analyze`, `GET /api/v1/logs/recent_errors`
- `POST /api/v1/feedback`, `GET /api/v1/feedback/summary`
- `GET /health/live`, `GET /health/ready`

## Validation

Two harnesses, two purposes.

```bash
make test        # deterministic — no LLM calls, runs in <1s, asserts every
                 # routing branch. This is the one CI should run on every PR.

make test-mcp    # MCP cross-transport proof — creates a ticket via MCP,
                 # reads it back via HTTP, mutates via MCP, re-reads via
                 # HTTP. Pure-Python, no transport spin-up needed.

make test-llm    # live-LLM accuracy harness — calls Claude through
                 # langchain-anthropic, measures classification quality.
                 # Costs a small amount per run.
```

Each harness writes a timestamped JSON report and a `latest-*.json` /
`latest-summary.md` sibling under `tests/results/`. A current example is
checked in. Methodology, scenarios, and per-axis pass rates live in
[`docs/VALIDATION.md`](docs/VALIDATION.md).

## Configuration

All env vars live in `.env`. See `.env.example`. Notable ones:

- `ANTHROPIC_API_KEY` — required for the live backend and `make test-llm`.
  Not required for `make test` or `make test-mcp` (they don't call Claude).
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
│   ├── data/kb/          # JSON KB documents (130 docs)
│   ├── config.py
│   └── main.py
├── services/
│   └── it_ops_api/       # FastAPI + SQLModel ticketing service
├── mcp_server/           # Real MCP server (FastMCP / stdio)
│   ├── server.py         # entry point: `python -m mcp_server.server`
│   ├── tools/__init__.py # @mcp.tool definitions
│   └── store.py          # shared functional wrapper over the SQLite store
├── frontend/             # Vite + React (calm enterprise UI, route-trace strip)
├── tests/
│   ├── test_routing.py     # deterministic, no LLM
│   ├── test_mcp_proof.py   # MCP↔HTTP cross-transport
│   ├── test_accuracy.py    # live-LLM (costs API spend)
│   ├── test_scenarios.json # scenarios for the live-LLM harness
│   └── results/            # JSON + markdown reports
├── docs/
│   ├── PRODUCT.md
│   ├── UX.md
│   ├── MCP_PROOF.md
│   ├── INDUSTRY_COMPARISON.md
│   ├── PRESENTATION.md
│   ├── VALIDATION.md
│   └── MCP_VSCode_Demo.md
├── diagrams/architecture.md
├── scripts/dev.sh
├── Makefile
├── pyproject.toml        # black + ruff config (target py311)
├── .python-version       # 3.11 (read by pyenv & Makefile)
├── requirements.txt
├── requirements-dev.txt
└── .env.example
```

## Status

Capstone project — not deployed. Sessions and request metrics are still
in-process for simplicity. Don't deploy this as-is; for production move
sessions to Redis or Postgres, restrict CORS to explicit origins, rotate
`IT_OPS_API_TOKEN`, and replace the simulated automations with real
adapters as listed in the table above.
