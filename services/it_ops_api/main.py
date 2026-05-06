"""IT Ops API — the real ticketing service that replaces the old MCP demo.

FastAPI + SQLModel/SQLite. Token-protected. CORS restricted to the configured
backend origin. Run with:

    uvicorn services.it_ops_api.main:app --port 8001 --reload
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlmodel import Session, select

from services.it_ops_api.auth import require_service_token
from services.it_ops_api.db import get_session, init_db
from services.it_ops_api.log_analyzer import analyze_logs, get_recent_errors
from services.it_ops_api.models import AuditLog, Ticket, TicketEvent

app = FastAPI(title="IT Ops API", version="1.0.0")

# CORS is restricted — this service only ever talks to the backend, never
# directly to the browser.
_ALLOWED = [
    o.strip()
    for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:8000").split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Content-Type", "X-Internal-Token"],
)


@app.on_event("startup")
def _startup() -> None:
    init_db()


# ---------------------------------------------------------------------------
# Pydantic request/response shapes
# ---------------------------------------------------------------------------


class TicketCreateBody(BaseModel):
    title: str
    description: str
    category: str
    priority: str
    severity: str = "medium"
    urgency: str = "medium"
    session_id: str


class StatusUpdateBody(BaseModel):
    new_status: str
    actor: str = "system"


class PriorityUpdateBody(BaseModel):
    new_priority: str
    actor: str = "system"


class AnalyzeLogsBody(BaseModel):
    log_file: str
    severity: Optional[str] = None
    last_n_lines: int = 20


# ---------------------------------------------------------------------------
# Health (public — used by readiness probes)
# ---------------------------------------------------------------------------


@app.get("/health/live")
def health_live() -> dict:
    return {"status": "ok"}


@app.get("/health/ready")
def health_ready(session: Session = Depends(get_session)) -> dict:
    try:
        session.exec(select(Ticket).limit(1))
        db_ok = True
    except Exception:
        db_ok = False
    return {"status": "ok" if db_ok else "degraded", "db": db_ok}


# ---------------------------------------------------------------------------
# Tickets (token-protected)
# ---------------------------------------------------------------------------


@app.post("/api/v1/tickets", dependencies=[Depends(require_service_token)])
def create_ticket(
    body: TicketCreateBody, session: Session = Depends(get_session)
) -> dict:
    ticket = Ticket(
        title=body.title,
        description=body.description,
        category=body.category,
        priority=body.priority,
        severity=body.severity,
        urgency=body.urgency,
        session_id=body.session_id,
    )
    session.add(ticket)
    session.add(
        TicketEvent(
            ticket_id=ticket.ticket_id,
            event_type="created",
            detail=f"priority={body.priority} severity={body.severity}",
            actor="agent",
        )
    )
    session.add(
        AuditLog(
            actor="agent",
            action="tickets.create",
            target=ticket.ticket_id,
            detail=f"category={body.category}",
        )
    )
    session.commit()
    session.refresh(ticket)
    return ticket.model_dump(mode="json")


@app.get("/api/v1/tickets", dependencies=[Depends(require_service_token)])
def list_tickets(
    category: Optional[str] = Query(default=None),
    status_: Optional[str] = Query(default=None, alias="status"),
    session: Session = Depends(get_session),
) -> List[dict]:
    stmt = select(Ticket)
    if category:
        stmt = stmt.where(Ticket.category == category)
    if status_:
        stmt = stmt.where(Ticket.status == status_)
    rows = session.exec(stmt.order_by(Ticket.created_at.desc())).all()
    return [r.model_dump(mode="json") for r in rows]


@app.get("/api/v1/tickets/{ticket_id}", dependencies=[Depends(require_service_token)])
def get_ticket(ticket_id: str, session: Session = Depends(get_session)) -> dict:
    ticket = session.get(Ticket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")
    return ticket.model_dump(mode="json")


@app.patch(
    "/api/v1/tickets/{ticket_id}/status",
    dependencies=[Depends(require_service_token)],
)
def update_status(
    ticket_id: str,
    body: StatusUpdateBody,
    session: Session = Depends(get_session),
) -> dict:
    ticket = session.get(Ticket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")
    old = ticket.status
    ticket.status = body.new_status
    ticket.updated_at = datetime.utcnow()
    session.add(ticket)
    session.add(
        TicketEvent(
            ticket_id=ticket.ticket_id,
            event_type="status_changed",
            detail=f"{old} -> {body.new_status}",
            actor=body.actor,
        )
    )
    session.add(
        AuditLog(
            actor=body.actor,
            action="tickets.status_change",
            target=ticket.ticket_id,
            detail=f"{old} -> {body.new_status}",
        )
    )
    session.commit()
    session.refresh(ticket)
    return ticket.model_dump(mode="json")


@app.patch(
    "/api/v1/tickets/{ticket_id}/priority",
    dependencies=[Depends(require_service_token)],
)
def update_priority(
    ticket_id: str,
    body: PriorityUpdateBody,
    session: Session = Depends(get_session),
) -> dict:
    ticket = session.get(Ticket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")
    old = ticket.priority
    ticket.priority = body.new_priority
    ticket.updated_at = datetime.utcnow()
    session.add(ticket)
    session.add(
        TicketEvent(
            ticket_id=ticket.ticket_id,
            event_type="priority_changed",
            detail=f"{old} -> {body.new_priority}",
            actor=body.actor,
        )
    )
    session.add(
        AuditLog(
            actor=body.actor,
            action="tickets.priority_change",
            target=ticket.ticket_id,
            detail=f"{old} -> {body.new_priority}",
        )
    )
    session.commit()
    session.refresh(ticket)
    return ticket.model_dump(mode="json")


@app.get(
    "/api/v1/tickets/{ticket_id}/events",
    dependencies=[Depends(require_service_token)],
)
def get_events(ticket_id: str, session: Session = Depends(get_session)) -> List[dict]:
    rows = session.exec(
        select(TicketEvent)
        .where(TicketEvent.ticket_id == ticket_id)
        .order_by(TicketEvent.created_at.asc())
    ).all()
    return [r.model_dump(mode="json") for r in rows]


# ---------------------------------------------------------------------------
# Log analysis (token-protected)
# ---------------------------------------------------------------------------


@app.post("/api/v1/logs/analyze", dependencies=[Depends(require_service_token)])
def logs_analyze(body: AnalyzeLogsBody) -> dict:
    try:
        return analyze_logs(
            log_file=body.log_file,
            severity=body.severity,
            last_n_lines=body.last_n_lines,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/v1/logs/recent_errors", dependencies=[Depends(require_service_token)])
def logs_recent_errors() -> dict:
    return get_recent_errors()
