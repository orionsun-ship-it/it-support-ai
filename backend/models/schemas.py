"""Pydantic v2 models for the IT support multi-agent system."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class UserMessage(BaseModel):
    """A message sent by the user into the chat endpoint."""

    message: str
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.now)


class AgentResponse(BaseModel):
    """The response returned to the frontend after agents process a turn."""

    agent_name: str
    content: str
    confidence: float = Field(ge=0.0, le=1.0)
    action_taken: str | None = None
    ticket_id: str | None = None
    escalated: bool = False


class TicketCreate(BaseModel):
    """Payload for creating a support ticket."""

    title: str
    description: str
    priority: Literal["low", "medium", "high", "critical"]
    category: Literal["password", "software", "hardware", "network", "access", "other"]
    session_id: str


class TicketResponse(TicketCreate):
    """A ticket as returned by the MCP ticket tool — extends TicketCreate with server-set fields."""

    ticket_id: str
    status: str
    created_at: datetime


class ConversationTurn(BaseModel):
    """One turn of the conversation, stored in session history."""

    role: Literal["user", "assistant"]
    content: str
    agent_name: str | None = None
    ticket_id: str | None = None
    escalated: bool = False
    timestamp: datetime = Field(default_factory=datetime.now)


class SessionState(BaseModel):
    """In-memory state for a single user session."""

    session_id: str
    history: list[ConversationTurn] = Field(default_factory=list)
    current_ticket: TicketResponse | None = None
    escalated: bool = False


class SystemMetrics(BaseModel):
    """High-level system metrics returned by GET /metrics."""

    total_requests: int
    avg_response_time_ms: float
    total_tickets: int
    total_escalations: int
    kb_seeded: bool
    uptime_seconds: float
