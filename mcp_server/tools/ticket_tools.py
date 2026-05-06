"""Ticket tool implementations exposed by the MCP-style tool server."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path

TICKETS_FILE = Path(__file__).resolve().parent.parent / "data" / "tickets.json"


def _load() -> list[dict]:
    if not TICKETS_FILE.exists():
        TICKETS_FILE.parent.mkdir(parents=True, exist_ok=True)
        TICKETS_FILE.write_text("[]")
        return []
    try:
        return json.loads(TICKETS_FILE.read_text() or "[]")
    except json.JSONDecodeError:
        return []


def _save(tickets: list[dict]) -> None:
    TICKETS_FILE.parent.mkdir(parents=True, exist_ok=True)
    TICKETS_FILE.write_text(json.dumps(tickets, indent=2, default=str))


def create_ticket(
    title: str,
    description: str,
    category: str,
    priority: str,
    session_id: str,
) -> dict:
    """Create a new ticket and persist it to disk. Returns the ticket dict."""
    ticket_id = "TKT-" + uuid.uuid4().hex[:8].upper()
    ticket = {
        "ticket_id": ticket_id,
        "title": title,
        "description": description,
        "category": category,
        "priority": priority,
        "session_id": session_id,
        "status": "open",
        "created_at": datetime.now().isoformat(),
    }
    tickets = _load()
    tickets.append(ticket)
    _save(tickets)
    return ticket


def list_tickets(category: str | None = None, status: str | None = None) -> list[dict]:
    """Return all tickets, optionally filtered by category and/or status."""
    tickets = _load()
    if category:
        tickets = [t for t in tickets if t.get("category") == category]
    if status:
        tickets = [t for t in tickets if t.get("status") == status]
    return tickets


def update_ticket_status(ticket_id: str, new_status: str) -> dict | None:
    """Update a ticket's status. Returns the updated ticket or None if not found."""
    tickets = _load()
    for t in tickets:
        if t.get("ticket_id") == ticket_id:
            t["status"] = new_status
            t["updated_at"] = datetime.now().isoformat()
            _save(tickets)
            return t
    return None
