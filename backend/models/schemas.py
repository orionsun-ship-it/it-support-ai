"""Pydantic v2 models for the IT support multi-agent system."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Category = Literal[
    "password",
    "access",
    "software",
    "hardware",
    "network",
    "email",
    "vpn",
    "security",
    "other",
]
Priority = Literal["low", "medium", "high", "critical"]
Severity = Literal["low", "medium", "high", "critical"]
Urgency = Literal["low", "medium", "high"]
Intent = Literal[
    "knowledge_question",
    "password_reset",
    "account_unlock",
    "software_license_check",
    "software_install",
    "access_request",
    "vpn_log_check",
    "ticket_request",
    "status_check",
    "non_support",
    "unknown",
]


class UserMessage(BaseModel):
    """A message sent by the user into the chat endpoint."""

    message: str
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.now)


class KBSource(BaseModel):
    """A retrieved knowledge base chunk surfaced to the frontend."""

    doc_id: str
    title: str
    category: str
    score: float
    distance: float
    snippet: str
    chunk_id: str = ""


class AgentResponse(BaseModel):
    """The response returned to the frontend after agents process a turn."""

    agent_name: str
    content: str
    confidence: float = Field(ge=0.0, le=1.0)
    severity: Severity | None = None
    urgency: Urgency | None = None
    category: str | None = None
    intent: str | None = None
    action_taken: str | None = None
    ticket_id: str | None = None
    escalated: bool = False
    match_strength: Literal["strong", "weak", "none"] | None = None
    sources: list[KBSource] = Field(default_factory=list)
    route_trace: list[str] = Field(default_factory=list)
    final_route: str | None = None
    ticket_decision_reason: str | None = None
    automation_status: str | None = None
    automation_simulated: bool = False


class TicketCreate(BaseModel):
    """Payload for creating a support ticket."""

    title: str
    description: str
    priority: Priority
    category: str
    severity: Severity = "medium"
    urgency: Urgency = "medium"
    session_id: str


class TicketResponse(TicketCreate):
    """A ticket as returned by the IT Ops API."""

    ticket_id: str
    status: str
    created_at: datetime
    updated_at: datetime | None = None


class ConversationTurn(BaseModel):
    """One turn of the conversation, stored in session history."""

    role: Literal["user", "assistant"]
    content: str
    agent_name: str | None = None
    ticket_id: str | None = None
    escalated: bool = False
    sources: list[KBSource] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.now)


class SessionState(BaseModel):
    session_id: str
    history: list[ConversationTurn] = Field(default_factory=list)
    current_ticket: TicketResponse | None = None
    escalated: bool = False


class FeedbackCreate(BaseModel):
    """Per-turn user feedback (thumbs up / thumbs down)."""

    session_id: str
    message_id: str
    sentiment: Literal["up", "down"]
    comment: str = ""


class SystemMetrics(BaseModel):
    total_requests: int
    avg_response_time_ms: float
    total_tickets: int
    total_escalations: int
    kb_seeded: bool
    uptime_seconds: float
    ops_api_available: bool = True
    satisfaction_score: float = 0.0
    feedback_total: int = 0
    feedback_up: int = 0
    feedback_down: int = 0
