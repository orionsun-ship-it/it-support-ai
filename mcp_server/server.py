"""
MCP-style tool server (simplified).

This is a small FastAPI app that demonstrates the MCP pattern: standardized
tool access over HTTP. It is intentionally dependency-free beyond what the
backend already uses — no MCP SDK is required for the capstone. The endpoints
below mirror the tools that an MCP-compatible client would expose, and the
core agentic backend talks to this server via plain HTTP.

Run with:
    uvicorn mcp_server.server:app --port 8001 --reload
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from mcp_server.tools import log_tools, ticket_tools

app = FastAPI(title="IT Support MCP Tool Server", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class CreateTicketBody(BaseModel):
    title: str
    description: str
    category: str
    priority: str
    session_id: str


class UpdateStatusBody(BaseModel):
    new_status: str


class AnalyzeLogsBody(BaseModel):
    log_file: str
    severity: str | None = None
    last_n_lines: int = 20


# ---------------------------------------------------------------------------
# Ticket endpoints
# ---------------------------------------------------------------------------


@app.post("/tools/create_ticket")
def create_ticket_endpoint(body: CreateTicketBody) -> dict:
    """MCP tool: create_ticket — persists a new ticket and returns it."""
    return ticket_tools.create_ticket(
        title=body.title,
        description=body.description,
        category=body.category,
        priority=body.priority,
        session_id=body.session_id,
    )


@app.get("/tools/list_tickets")
def list_tickets_endpoint(
    category: str | None = None, status: str | None = None
) -> list[dict]:
    """MCP tool: list_tickets — returns the current ticket list with optional filters."""
    return ticket_tools.list_tickets(category=category, status=status)


@app.patch("/tools/tickets/{ticket_id}/status")
def update_ticket_status_endpoint(ticket_id: str, body: UpdateStatusBody) -> dict:
    """MCP tool: update_ticket_status — updates a ticket's status field."""
    updated = ticket_tools.update_ticket_status(ticket_id, body.new_status)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")
    return updated


# ---------------------------------------------------------------------------
# Log analysis endpoints
# ---------------------------------------------------------------------------


@app.post("/tools/analyze_logs")
def analyze_logs_endpoint(body: AnalyzeLogsBody) -> dict[str, Any]:
    """MCP tool: analyze_logs — parses one of the sample log files and returns matches."""
    try:
        return log_tools.analyze_logs(
            log_file=body.log_file,
            severity=body.severity,
            last_n_lines=body.last_n_lines,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/tools/recent_errors")
def recent_errors_endpoint() -> dict[str, Any]:
    """MCP tool: get_recent_errors — returns the most recent errors across log files."""
    return log_tools.get_recent_errors()


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@app.get("/health")
def health() -> dict[str, Any]:
    """Liveness probe."""
    return {"status": "ok", "server": "mcp_tool_server", "port": 8001}
