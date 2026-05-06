"""Escalation agent — applies escalation rules and bumps the ticket if needed."""

from __future__ import annotations

import re

from backend.services.it_ops_client import ItOpsClient
from backend.utils.logger import get_logger

logger = get_logger(__name__)

ESCALATION_KEYWORDS = re.compile(
    r"\b(urgent|critical|emergency|asap|immediately|cannot work|can't work|outage|"
    r"data loss|production down)\b",
    re.IGNORECASE,
)


def _should_escalate(state: dict) -> bool:
    confidence = float(state.get("confidence") or 0.0)
    user_message = state.get("user_message") or ""
    category = state.get("category") or "other"
    severity = state.get("severity") or "medium"
    urgency = state.get("urgency") or "medium"

    if ESCALATION_KEYWORDS.search(user_message):
        return True
    if severity == "critical" or urgency == "high":
        return True
    if confidence < 0.4:
        return True
    if category == "hardware" and confidence < 0.6:
        return True
    if state.get("match_strength") == "none" and state.get("is_support_request", True):
        return True
    return False


class EscalationAgent:
    """Decides whether a turn should be escalated to a human IT technician."""

    def __init__(self, client: ItOpsClient | None = None) -> None:
        self.client = client or ItOpsClient()

    def run(self, state: dict) -> dict:
        escalated = _should_escalate(state)
        state["escalated"] = bool(escalated)

        if not escalated:
            return state

        ticket = state.get("ticket") or {}
        ticket_id = ticket.get("ticket_id")
        new_priority = "critical"

        if ticket_id and not str(ticket_id).startswith("LOCAL-"):
            updated = self.client.update_status(ticket_id, "escalated")
            if updated:
                state["ticket"] = updated
            bumped = self.client.update_priority(ticket_id, new_priority)
            if bumped:
                state["ticket"] = bumped
        elif ticket:
            # Local fallback — update in place.
            ticket["status"] = "escalated"
            ticket["priority"] = new_priority
            state["ticket"] = ticket

        existing = state.get("response") or ""
        ticket_phrase = (
            f"Ticket {ticket_id} is now {new_priority} priority."
            if ticket_id
            else "A new ticket will be opened at critical priority."
        )
        banner = (
            f"\n\n⚠️ This issue has been escalated to a human IT technician. "
            f"{ticket_phrase} Expected response time: 2-4 hours."
        )
        state["response"] = existing + banner

        return state
