"""Escalation agent — applies escalation rules and bumps the ticket if needed."""

from __future__ import annotations

import os

import httpx
from dotenv import load_dotenv

from backend.utils.logger import get_logger

load_dotenv()
logger = get_logger(__name__)

MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8001")

ESCALATION_KEYWORDS = ("urgent", "critical", "emergency", "asap", "immediately")


class EscalationAgent:
    """Decides whether a turn should be escalated to a human IT technician."""

    def run(self, state: dict) -> dict:
        confidence = float(state.get("confidence") or 0.0)
        user_message = (state.get("user_message") or "").lower()
        category = state.get("category") or "other"

        rule_low_confidence = confidence < 0.4
        rule_keyword = any(kw in user_message for kw in ESCALATION_KEYWORDS)
        rule_hardware = category == "hardware" and confidence < 0.6

        escalated = rule_low_confidence or rule_keyword or rule_hardware
        state["escalated"] = bool(escalated)

        if not escalated:
            return state

        ticket = state.get("ticket") or {}
        ticket_id = ticket.get("ticket_id", "(no ticket)")

        if ticket and ticket.get("ticket_id"):
            try:
                with httpx.Client(timeout=5.0) as client:
                    resp = client.patch(
                        f"{MCP_SERVER_URL}/tools/tickets/{ticket['ticket_id']}/status",
                        json={"new_status": "escalated"},
                    )
                    if resp.status_code == 200:
                        ticket = resp.json()
                        state["ticket"] = ticket
            except httpx.RequestError as exc:
                logger.warning(
                    "Could not mark ticket %s as escalated via MCP: %s",
                    ticket_id,
                    exc,
                )
                # Best-effort: also update the in-memory copy
                ticket["status"] = "escalated"
                state["ticket"] = ticket

        existing = state.get("response") or ""
        banner = (
            f"\n\n⚠️ This issue has been escalated to a human IT technician. "
            f"Ticket {ticket_id} is now priority. Expected response time: 2-4 hours."
        )
        state["response"] = existing + banner

        return state
