"""MCP cross-transport proof.

Demonstrates that the MCP server's tools and the IT Ops API's endpoints both
write to (and read from) the same SQLite database. We don't spin up the stdio
transport for this test — calling the same module functions
(``mcp_server.store``) that the FastMCP tools delegate to is sufficient to
prove the cross-transport claim end-to-end.

Steps:

1. Use ``mcp_server.store.create_ticket`` (the function bound to the
   ``@mcp.tool create_ticket``) to create a ticket. The ticket persists in
   ``services/it_ops_api/it_ops.db`` via SQLModel.
2. Use ``services.it_ops_api.main`` directly (TestClient) to GET that ticket
   through the HTTP transport. If the ticket is visible there, the same DB
   serves both transports.
3. Use ``mcp_server.store.update_ticket_status`` to flip the status to
   ``escalated``. Re-fetch via HTTP and confirm the change is visible there.
4. Use ``mcp_server.store.list_tickets`` to confirm the MCP transport sees
   the same row, with the new status.

This is a pure-Python, deterministic test — no LLM, no network. It writes a
report to ``tests/results/mcp-proof-*.json`` and a markdown summary.
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Use a separate, throwaway DB so the proof doesn't pollute dev data.
PROOF_DB = ROOT / "tests" / "results" / "mcp_proof.db"
os.environ["IT_OPS_DB_PATH"] = str(PROOF_DB)
# IT Ops API auth uses a token; force a stable test token before the modules
# import (the auth module reads it at import time).
os.environ["IT_OPS_API_TOKEN"] = "mcp-proof-token"

# Make sure the DB file is fresh for each run.
PROOF_DB.parent.mkdir(parents=True, exist_ok=True)
if PROOF_DB.exists():
    PROOF_DB.unlink()

from fastapi.testclient import TestClient  # noqa: E402

from mcp_server import store as mcp_store  # noqa: E402
from services.it_ops_api.main import app as ops_app  # noqa: E402

RESULTS_DIR = ROOT / "tests" / "results"


def _record(steps: list[dict], name: str, ok: bool, detail: dict) -> None:
    steps.append({"step": name, "ok": ok, **detail})


def main() -> int:
    steps: list[dict] = []
    started = datetime.now().isoformat()
    client = TestClient(ops_app)
    headers = {"X-Internal-Token": os.environ["IT_OPS_API_TOKEN"]}

    # 1. MCP transport creates a ticket directly via the shared store.
    payload = {
        "title": f"MCP cross-transport proof {uuid.uuid4().hex[:6]}",
        "description": "Created via MCP store.create_ticket; should be visible via HTTP.",
        "category": "network",
        "priority": "high",
        "severity": "high",
        "urgency": "high",
        "session_id": "mcp-proof",
    }
    mcp_ticket = mcp_store.create_ticket(payload)
    ticket_id = mcp_ticket["ticket_id"]
    _record(
        steps,
        "mcp_create_ticket",
        bool(ticket_id),
        {"ticket_id": ticket_id, "via": "mcp_server.store.create_ticket"},
    )

    # 2. HTTP transport fetches the same ticket.
    http_resp = client.get(f"/api/v1/tickets/{ticket_id}", headers=headers)
    http_ok = http_resp.status_code == 200
    http_data = http_resp.json() if http_ok else {"error": http_resp.text}
    same_id = http_ok and http_data.get("ticket_id") == ticket_id
    _record(
        steps,
        "http_get_returns_same_ticket",
        same_id,
        {
            "status_code": http_resp.status_code,
            "ticket_id_match": same_id,
            "via": "GET /api/v1/tickets/{ticket_id}",
        },
    )

    # 3. MCP transport updates the status; HTTP transport sees the change.
    mcp_updated = mcp_store.update_ticket_status(ticket_id, "escalated")
    http_after = client.get(f"/api/v1/tickets/{ticket_id}", headers=headers).json()
    status_ok = (
        mcp_updated.get("status") == "escalated"
        and http_after.get("status") == "escalated"
    )
    _record(
        steps,
        "mcp_update_visible_via_http",
        status_ok,
        {
            "mcp_status_after_update": mcp_updated.get("status"),
            "http_status_after_update": http_after.get("status"),
        },
    )

    # 4. MCP list_tickets sees the same row with the new status.
    mcp_listed = mcp_store.list_tickets()
    found = next((t for t in mcp_listed if t.get("ticket_id") == ticket_id), None)
    list_ok = found is not None and found.get("status") == "escalated"
    _record(
        steps,
        "mcp_list_sees_same_row",
        list_ok,
        {
            "mcp_total_tickets": len(mcp_listed),
            "found_in_list": found is not None,
            "found_status": (found or {}).get("status"),
        },
    )

    # 5. Bonus: HTTP transport's list endpoint also sees the row.
    http_list_resp = client.get("/api/v1/tickets", headers=headers)
    http_list = http_list_resp.json() if http_list_resp.status_code == 200 else []
    http_found = any(t.get("ticket_id") == ticket_id for t in http_list)
    _record(
        steps,
        "http_list_sees_same_row",
        http_found,
        {
            "http_total_tickets": len(http_list),
            "found_in_list": http_found,
        },
    )

    all_ok = all(s["ok"] for s in steps)
    summary = {
        "started_at": started,
        "ended_at": datetime.now().isoformat(),
        "harness": "mcp-cross-transport-proof",
        "ticket_id": ticket_id,
        "passed": all_ok,
        "steps": steps,
        "db_path": str(PROOF_DB),
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = RESULTS_DIR / f"mcp-proof-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    out.write_text(json.dumps(summary, indent=2))
    (RESULTS_DIR / "mcp-proof-latest.json").write_text(json.dumps(summary, indent=2))

    print(f"MCP cross-transport proof: {'PASS' if all_ok else 'FAIL'}")
    for s in steps:
        mark = "✓" if s["ok"] else "✗"
        print(f"  {mark} {s['step']}")
    print(f"\nReport: {out}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
