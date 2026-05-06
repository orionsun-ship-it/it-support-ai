"""Pydantic schemas for MCP tool inputs (used as type hints in tools.py)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Category = Literal[
    "password", "access", "software", "hardware", "network", "email", "vpn",
    "security", "other"
]
Priority = Literal["low", "medium", "high", "critical"]
Severity = Literal["low", "medium", "high", "critical"]
Urgency = Literal["low", "medium", "high"]


class CreateTicketInput(BaseModel):
    title: str = Field(..., description="Short ticket title (max 60 chars)")
    description: str = Field(..., description="Full description of the issue")
    category: Category = "other"
    priority: Priority = "medium"
    severity: Severity = "medium"
    urgency: Urgency = "medium"
    session_id: str = Field(default="mcp-client")
