"""ORM models for the IT Ops API: tickets, ticket_events, audit_logs."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlmodel import Field, SQLModel


def _ticket_id() -> str:
    return "TKT-" + uuid.uuid4().hex[:8].upper()


class Ticket(SQLModel, table=True):
    __tablename__ = "tickets"

    ticket_id: str = Field(default_factory=_ticket_id, primary_key=True)
    title: str
    description: str
    category: str  # password, software, hardware, network, access, other
    priority: str  # low, medium, high, critical
    severity: str = "medium"  # low, medium, high, critical (separate from priority)
    urgency: str = "medium"  # low, medium, high
    status: str = "open"  # open, in_progress, escalated, resolved, closed
    session_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class TicketEvent(SQLModel, table=True):
    __tablename__ = "ticket_events"

    id: int | None = Field(default=None, primary_key=True)
    ticket_id: str = Field(index=True, foreign_key="tickets.ticket_id")
    event_type: str  # created, status_changed, priority_changed, comment
    detail: str = ""
    actor: str = "system"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AuditLog(SQLModel, table=True):
    __tablename__ = "audit_logs"

    id: int | None = Field(default=None, primary_key=True)
    actor: str
    action: str  # e.g. tickets.create, tickets.status_change
    target: str = ""  # e.g. ticket_id
    detail: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Feedback(SQLModel, table=True):
    """Per-turn user feedback (thumbs up / thumbs down) for satisfaction tracking."""

    __tablename__ = "feedback"

    id: int | None = Field(default=None, primary_key=True)
    session_id: str = Field(index=True)
    message_id: str = Field(index=True)  # frontend-generated id of the assistant turn
    sentiment: str  # "up" | "down"
    comment: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
