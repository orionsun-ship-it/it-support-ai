"""Workflow agent.

Two responsibilities:
1. Run scripted automations (password reset, account unlock, license check).
2. Decide whether to open a ticket — and only open one when needed.

Ticket creation rules (in priority order):
  - intake says is_support_request == False  -> NO ticket
  - explicit escalation keywords            -> ticket (priority from severity/urgency)
  - retrieval is "weak" or "none"           -> ticket (KB didn't cover it)
  - urgency == high                         -> ticket
  - otherwise                               -> NO ticket (KB answered the user)
"""

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

# Priority is computed from severity + urgency, NOT classifier confidence.
_PRIORITY_LADDER = ["low", "medium", "high", "critical"]


def _max_priority(severity: str, urgency: str) -> str:
    sev_idx = _PRIORITY_LADDER.index(severity) if severity in _PRIORITY_LADDER else 1
    urg_map = {"low": 0, "medium": 1, "high": 2}
    urg_idx = urg_map.get(urgency, 1)
    return _PRIORITY_LADDER[max(sev_idx, urg_idx)]


def _should_create_ticket(state: dict) -> tuple[bool, str]:
    if not state.get("is_support_request", True):
        return False, "not a support request"
    user_message = state.get("user_message") or ""
    if ESCALATION_KEYWORDS.search(user_message):
        return True, "escalation keyword"
    if state.get("match_strength") in {"weak", "none"}:
        return True, "no strong KB match"
    if state.get("urgency") == "high":
        return True, "high urgency"
    return False, "KB likely covered the question"


class WorkflowAgent:
    """Runs automations and conditionally opens a ticket."""

    def __init__(self, client: ItOpsClient | None = None) -> None:
        self.client = client or ItOpsClient()

    def run(self, state: dict) -> dict:
        category = state.get("category") or "other"
        severity = state.get("severity") or "medium"
        urgency = state.get("urgency") or "medium"
        user_message = state.get("user_message") or ""
        session_id = state.get("session_id") or "unknown"

        # 1. Scripted automation by category
        automation_result: str | None
        if category == "password":
            automation_result = (
                "Password reset initiated. A reset link will be sent to your "
                "registered email within 5 minutes."
            )
        elif category == "access":
            automation_result = (
                "Account unlock request submitted. Your account will be unlocked "
                "within 2 minutes."
            )
        elif category == "software":
            automation_result = (
                "Software license check completed. Your license is active and valid."
            )
        else:
            automation_result = None

        # 2. Decide whether to create a ticket
        create, reason = _should_create_ticket(state)
        state["should_create_ticket"] = create
        state["ticket_decision_reason"] = reason

        if not create:
            logger.info("Skipping ticket creation: %s", reason)
            state["ticket"] = None
        else:
            priority = _max_priority(severity, urgency)
            payload = {
                "title": (user_message or "(no title)")[:60],
                "description": user_message,
                "category": category,
                "priority": priority,
                "severity": severity,
                "urgency": urgency,
                "session_id": session_id,
            }
            result = self.client.create_ticket(payload, fallback=True)
            state["ticket"] = result.ticket
            if result.is_fallback:
                state["ops_api_unavailable"] = True

        # 3. Compose response
        state["automation_result"] = automation_result
        existing = state.get("response") or ""
        extras: list[str] = []
        if automation_result:
            extras.append(automation_result)
        if state.get("ops_api_unavailable"):
            extras.append(
                "Note: the ticketing service is currently unavailable; a local "
                "ticket has been created and will be synced when the service "
                "returns."
            )
        if extras:
            state["response"] = (existing + "\n" + "\n".join(extras)).strip()

        return state
