"""Thin functional wrapper over the shared SQLite store.

The web backend talks to the SQLModel-backed store via the FastAPI ops API.
The MCP server uses these helpers to read and write the same tables directly,
so both transports (HTTP and MCP/stdio) end up in the same database file.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlmodel import select

from services.it_ops_api.db import engine, init_db
from services.it_ops_api.log_analyzer import analyze_logs as _analyze_logs
from services.it_ops_api.log_analyzer import get_recent_errors as _get_recent_errors
from services.it_ops_api.models import AuditLog, Ticket, TicketEvent
from sqlmodel import Session


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_ticket(payload: dict[str, Any]) -> dict[str, Any]:
    """Create a ticket. Returns the persisted row as a plain dict."""
    init_db()
    with Session(engine) as session:
        ticket = Ticket(
            title=payload["title"],
            description=payload.get("description", ""),
            category=payload.get("category", "other"),
            priority=payload.get("priority", "medium"),
            severity=payload.get("severity", "medium"),
            urgency=payload.get("urgency", "medium"),
            session_id=payload.get("session_id", "mcp-client"),
        )
        session.add(ticket)
        session.add(
            TicketEvent(
                ticket_id=ticket.ticket_id,
                event_type="created",
                detail=f"priority={ticket.priority} severity={ticket.severity}",
                actor="mcp",
            )
        )
        session.add(
            AuditLog(
                actor="mcp",
                action="tickets.create",
                target=ticket.ticket_id,
                detail=f"category={ticket.category}",
            )
        )
        session.commit()
        session.refresh(ticket)
        return ticket.model_dump(mode="json")


def list_tickets(
    category: str | None = None, status: str | None = None
) -> list[dict[str, Any]]:
    init_db()
    with Session(engine) as session:
        stmt = select(Ticket)
        if category:
            stmt = stmt.where(Ticket.category == category)
        if status:
            stmt = stmt.where(Ticket.status == status)
        rows = session.exec(stmt.order_by(Ticket.created_at.desc())).all()
        return [r.model_dump(mode="json") for r in rows]


def update_ticket_status(ticket_id: str, status: str) -> dict[str, Any]:
    init_db()
    with Session(engine) as session:
        ticket = session.get(Ticket, ticket_id)
        if ticket is None:
            raise ValueError(f"Ticket not found: {ticket_id}")
        old = ticket.status
        ticket.status = status
        ticket.updated_at = datetime.utcnow()
        session.add(ticket)
        session.add(
            TicketEvent(
                ticket_id=ticket.ticket_id,
                event_type="status_changed",
                detail=f"{old} -> {status}",
                actor="mcp",
            )
        )
        session.commit()
        session.refresh(ticket)
        return ticket.model_dump(mode="json")


def update_ticket_priority(ticket_id: str, priority: str) -> dict[str, Any]:
    init_db()
    with Session(engine) as session:
        ticket = session.get(Ticket, ticket_id)
        if ticket is None:
            raise ValueError(f"Ticket not found: {ticket_id}")
        old = ticket.priority
        ticket.priority = priority
        ticket.updated_at = datetime.utcnow()
        session.add(ticket)
        session.add(
            TicketEvent(
                ticket_id=ticket.ticket_id,
                event_type="priority_changed",
                detail=f"{old} -> {priority}",
                actor="mcp",
            )
        )
        session.commit()
        session.refresh(ticket)
        return ticket.model_dump(mode="json")


def analyze_logs(log_file: str, severity: str | None = None) -> dict[str, Any]:
    """Wraps services.it_ops_api.log_analyzer.analyze_logs."""
    return _analyze_logs(log_file=log_file, severity=severity, last_n_lines=20)


def recent_errors(limit: int = 5) -> dict[str, Any]:
    """Wraps services.it_ops_api.log_analyzer.get_recent_errors."""
    data = _get_recent_errors(last_n_lines=max(limit, 5))
    flattened: list[str] = []
    for entries in data.get("by_file", {}).values():
        flattened.extend(entries)
    flattened = flattened[:limit]
    return {
        "total_errors": data.get("total_errors", 0),
        "errors": flattened,
        "most_recent_error": data.get("most_recent_error"),
    }
