"""Pydantic v2 models for the IT support multi-agent system."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Literal, Optional

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
    severity: Optional[Severity] = None
    urgency: Optional[Urgency] = None
    category: Optional[str] = None
    intent: Optional[str] = None
    action_taken: Optional[str] = None
    ticket_id: Optional[str] = None
    escalated: bool = False
    match_strength: Optional[Literal["strong", "weak", "none"]] = None
    sources: List[KBSource] = Field(default_factory=list)
    route_trace: List[str] = Field(default_factory=list)
    final_route: Optional[str] = None
    ticket_decision_reason: Optional[str] = None
    automation_status: Optional[str] = None


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
    updated_at: Optional[datetime] = None


class ConversationTurn(BaseModel):
    """One turn of the conversation, stored in session history."""

    role: Literal["user", "assistant"]
    content: str
    agent_name: Optional[str] = None
    ticket_id: Optional[str] = None
    escalated: bool = False
    sources: List[KBSource] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.now)


class SessionState(BaseModel):
    session_id: str
    history: List[ConversationTurn] = Field(default_factory=list)
    current_ticket: Optional[TicketResponse] = None
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
