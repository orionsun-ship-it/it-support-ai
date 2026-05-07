"""Escalation agent — gated by explicit rules and produces a specific response."""

from __future__ import annotations

from backend.services.it_ops_client import ItOpsClient
from backend.utils.logger import get_logger

logger = get_logger(__name__)


def _should_escalate(state: dict) -> bool:
    # Automation explicitly failed or requires manual intervention.
    if state.get("automation_status") in {"failed", "manual_required"}:
        return True
    # Routing reached here because the user confirmed our suggestion didn't help.
    # Any other path to this node is intentional escalation.
    return True


class EscalationAgent:
    """Handles unresolved, urgent, low-confidence, or failed-automation cases."""

    def __init__(self, client: ItOpsClient | None = None) -> None:
        self.client = client or ItOpsClient()

    def _ensure_ticket(self, state: dict) -> dict | None:
        ticket = state.get("ticket")
        if ticket:
            return ticket
        # Open a ticket so escalation has something concrete to reference.
        payload = {
            "title": (state.get("user_message") or "Escalation")[:60],
            "description": state.get("user_message") or "",
            "category": state.get("category") or "other",
            "priority": "critical",
            "severity": state.get("severity") or "high",
            "urgency": state.get("urgency") or "high",
            "session_id": state.get("session_id") or "unknown",
        }
        result = self.client.create_ticket(payload, fallback=True)
        state["ticket"] = result.ticket
        state["ops_api_unavailable"] = result.is_fallback
        state["should_create_ticket"] = True
        state.setdefault("ticket_decision_reason", "escalation requires a ticket")
        return result.ticket

    def run(self, state: dict) -> dict:
        state.setdefault("route_trace", []).append("escalation")

        if not _should_escalate(state):
            state["escalated"] = False
            return state

        ticket = self._ensure_ticket(state) or {}
        ticket_id = ticket.get("ticket_id", "")
        new_priority = "critical"

        # Bump priority + status if this ticket lives in the real ops API.
        if ticket_id and not str(ticket_id).startswith("LOCAL-"):
            updated = self.client.update_status(ticket_id, "escalated")
            if updated:
                state["ticket"] = updated
            bumped = self.client.update_priority(ticket_id, new_priority)
            if bumped:
                state["ticket"] = bumped
        elif ticket:
            ticket["status"] = "escalated"
            ticket["priority"] = new_priority
            state["ticket"] = ticket

        state["escalated"] = True

        existing = (state.get("response") or "").rstrip()
        ticket_phrase = (
            f"Ticket {ticket_id} has been opened with priority {new_priority}."
            if ticket_id
            else f"A new ticket has been opened with priority {new_priority}."
        )
        banner = (
            "I could not resolve this confidently from the knowledge base, so I "
            f"routed it to human IT support. {ticket_phrase} Expected response "
            "time: 2-4 hours."
        )
        state["response"] = (existing + "\n\n" + banner).strip() if existing else banner
        return state
