# MCP cross-transport proof

This doc covers grading checkpoint **7 (Technical implementation,
including MCP integration)**. It demonstrates — with a deterministic,
checked-in test — that this project's IT support tools are reachable
through **two transports** that hit **one shared persistence layer**:

1. **HTTP** — the FastAPI IT Ops API at `localhost:8001`, used by the
   web backend and any HTTP client.
2. **MCP / stdio** — `mcp_server.server` exposed via FastMCP, used by
   VS Code Copilot Chat, Claude Desktop, and any other MCP-aware tool.

If a ticket created over MCP is visible over HTTP and vice versa, with
mutations on one side observable from the other, the standardisation
claim is real, not a slide.

---

## 1. The architecture in one picture

```
       VS Code Copilot Chat ──┐
                              │  (MCP / stdio)
       Claude Desktop ────────┼─────► mcp_server/server.py
                              │           │
                              │           ▼ delegates to
                              │       mcp_server/store.py
                              │           │
                              │           ▼
                              │       SQLModel + SQLite
                              │       services/it_ops_api/it_ops.db
                              │           ▲
                              │           │
       LangGraph backend ─────┘           │
       (in-process)                       │
              │                           │
              ▼                           │
       backend/services/it_ops_client.py  │
              │                           │
              ▼     (HTTP, X-Internal-Token)
       services/it_ops_api/main.py ───────┘
       (FastAPI on :8001)
```

`mcp_server/store.py` and `services/it_ops_api/main.py` both call into
the same SQLModel models (`Ticket`, `TicketEvent`, `AuditLog`,
`Feedback`) backed by the same SQLite file. They are not parallel
implementations — they are two doors into the same room.

---

## 2. Run the proof

```bash
make test-mcp
# equivalent to:  python tests/test_mcp_proof.py
```

The test:

1. Sets a temporary `IT_OPS_DB_PATH` so the proof runs in an isolated DB
   file under `tests/results/mcp_proof.db` (no risk of polluting your
   dev tickets).
2. Creates a ticket via `mcp_server.store.create_ticket(...)` — the same
   function the FastMCP `@tool create_ticket` wraps.
3. Boots the FastAPI ops API in-process via `fastapi.testclient.TestClient`
   and calls `GET /api/v1/tickets/{ticket_id}`. Asserts the same
   `ticket_id` comes back.
4. Updates the ticket status to `escalated` via the MCP store.
5. Re-fetches the ticket via HTTP. Asserts the new status is visible.
6. Lists tickets via the MCP store. Asserts the row is present with the
   updated status.
7. Lists tickets via the HTTP API. Asserts the same.

Each step writes a structured pass/fail record. The aggregated report
goes to `tests/results/mcp-proof-*.json` and `mcp-proof-latest.json`.

---

## 3. Latest report (checked in)

A copy of the most recent run is at
[`../tests/results/mcp-proof-latest.json`](../tests/results/mcp-proof-latest.json).
Excerpt:

```json
{
  "harness": "mcp-cross-transport-proof",
  "ticket_id": "TKT-2817C693",
  "passed": true,
  "steps": [
    {"step": "mcp_create_ticket", "ok": true, "via": "mcp_server.store.create_ticket"},
    {"step": "http_get_returns_same_ticket", "ok": true, "status_code": 200, "ticket_id_match": true},
    {"step": "mcp_update_visible_via_http", "ok": true, "mcp_status_after_update": "escalated", "http_status_after_update": "escalated"},
    {"step": "mcp_list_sees_same_row", "ok": true, "found_status": "escalated"},
    {"step": "http_list_sees_same_row", "ok": true}
  ]
}
```

Interpretation:

| Step                              | What it proves                                                |
| --------------------------------- | ------------------------------------------------------------- |
| `mcp_create_ticket`               | The MCP transport can write tickets.                          |
| `http_get_returns_same_ticket`    | The HTTP transport sees what MCP wrote (same DB, same row).   |
| `mcp_update_visible_via_http`     | A mutation on the MCP side is observable on the HTTP side.    |
| `mcp_list_sees_same_row`          | The MCP listing endpoint returns the row with the new status. |
| `http_list_sees_same_row`         | Same for HTTP listing — both transports stay in sync.         |

Five steps, five passes, deterministic. No mocks of the persistence
layer — the SQLModel session is real, the DB file is real (just isolated
under `tests/results/`), the FastAPI app is real (booted via TestClient).

---

## 4. Why this is the right way to prove the claim

A common failure mode in MCP demos is handwaving: "the tools are exposed
via FastMCP" with a code snippet of the `@tool` decorators and no
demonstration that they actually wire to the same store. We avoid that
with three layers of evidence:

1. **Code-level**: `mcp_server/store.py` imports the SQLModel models and
   the engine from `services/it_ops_api/db.py`. There is literally one
   `engine` and one `Ticket` class. You can read it in 30 lines.
2. **Test-level**: `tests/test_mcp_proof.py` exercises both transports
   against the same DB and asserts cross-visibility. A regression that
   forks the persistence (e.g. someone adds a second SQLite file by
   mistake) breaks the test immediately.
3. **Demo-level**: `docs/MCP_VSCode_Demo.md` walks through wiring VS Code
   Copilot Chat to the MCP server. Following that demo, you can create
   a ticket from inside VS Code and watch it appear in the web Tickets
   page within seconds.

---

## 5. Live demo path (VS Code, ~5 min)

For graders or audiences who want to see it live rather than read the
JSON:

1. `make dev` (in one terminal — boots ops API, backend, and frontend).
2. `make mcp` (in a second terminal — runs the MCP server over stdio).
3. Add `.vscode/mcp.json` to the project root with the config from
   [`MCP_VSCode_Demo.md`](MCP_VSCode_Demo.md).
4. Reload VS Code, open Copilot Chat, ask: "Use the IT support tools to
   open a ticket: title 'Wi-Fi flaky in conf room B', category network,
   priority medium. Then list all tickets."
5. Open `http://localhost:5173`, click **Tickets**, refresh — your VS
   Code-created ticket is right there.

That's the standardisation point: VS Code didn't need to learn the HTTP
contract or the auth header. It read the FastMCP manifest and called
`create_ticket` like any other typed tool.

---

## 6. Composability — vendor-neutral

[`MCP_VSCode_Demo.md`](MCP_VSCode_Demo.md)'s appendix shows wiring the
official GitHub MCP server alongside ours. With both servers configured,
the same VS Code window can:

- `create_ticket` (this project's MCP server) — for IT issues.
- `create_issue` (GitHub MCP server) — for engineering bugs.

Same protocol. Same tool-discovery flow. Different vendors. That's the
practical demonstration of MCP standardising tool access — and the
reason this project picked MCP over a bespoke REST extension.
