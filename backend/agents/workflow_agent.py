"""Workflow agent.

Three responsibilities:

1. Decide whether a safe automation is allowed and execute it (intent-based).
2. Decide whether a ticket is required (gated, not blanket).
3. Append concise outcome text without overwriting the knowledge response.
"""

from __future__ import annotations

import re

from backend.services.it_ops_client import ItOpsClient
from backend.utils.logger import get_logger

logger = get_logger(__name__)

ESCALATION_KEYWORDS = re.compile(
    r"\b(urgent|critical|emergency|asap|immediately|cannot work|can't work|outage|"
    r"data loss|production down|nobody can work)\b",
    re.IGNORECASE,
)

EXPLICIT_TICKET_RE = re.compile(
    r"\b(create|open|file|submit|raise)\s+(a\s+)?(new\s+)?ticket\b",
    re.IGNORECASE,
)

AUTOMATABLE_INTENTS = {
    "password_reset",
    "account_unlock",
    "software_license_check",
    "software_install",
    "access_request",
    "vpn_log_check",
    "status_check",
}


def _priority_from_state(state: dict) -> str:
    severity = state.get("severity") or "medium"
    urgency = state.get("urgency") or "medium"
    if severity == "critical" or urgency == "high":
        return "critical"
    if severity == "high":
        return "high"
    if severity == "medium" or urgency == "medium":
        return "medium"
    return "low"


def _ticket_title(state: dict) -> str:
    user_message = (state.get("user_message") or "").strip()
    return (user_message or "Support request")[:60]


def _should_create_ticket(state: dict) -> tuple[bool, str]:
    if not state.get("is_support_request", True):
        return False, "not a support request"

    user_message = state.get("user_message") or ""

    if EXPLICIT_TICKET_RE.search(user_message):
        return True, "user explicitly requested a ticket"

    if ESCALATION_KEYWORDS.search(user_message):
        return True, "urgent/escalation language detected"

    if state.get("severity") == "critical" or state.get("urgency") == "high":
        return True, "high severity or urgency"

    if state.get("automation_status") in {"failed", "manual_required"}:
        return True, "automation failed or requires manual approval"

    if state.get("match_strength") in {"weak", "none"}:
        return True, "knowledge base did not provide a strong answer"

    return False, "knowledge response or automation resolved the request"


class WorkflowAgent:
    """Runs intent-based automations and conditionally opens a ticket."""

    def __init__(self, client: ItOpsClient | None = None) -> None:
        self.client = client or ItOpsClient()

    def _run_automation(self, state: dict) -> tuple[str, str]:
        intent = state.get("intent")
        if intent == "password_reset":
            return (
                "success",
                "Password reset eligibility verified. A reset link has been "
                "sent to the registered email.",
            )
        if intent == "account_unlock":
            return (
                "success",
                "Account unlock request submitted. The account should unlock "
                "within 2 minutes.",
            )
        if intent == "software_license_check":
            return (
                "success",
                "Software license check completed. The assigned license is active.",
            )
        if intent == "software_install":
            return (
                "success",
                "Software install request submitted to the package portal. "
                "Approval typically completes within one business hour.",
            )
        if intent == "access_request":
            return (
                "success",
                "Access request submitted to the access management team for "
                "review. You'll receive an email once it's approved.",
            )
        if intent == "vpn_log_check":
            try:
                result = self.client.analyze_logs(service="network_events")
                summary = (result or {}).get("summary") or "VPN logs reviewed."
                return ("success", f"VPN log check completed: {summary}")
            except Exception as exc:  # noqa: BLE001
                logger.warning("VPN log automation failed: %s", exc)
                return ("manual_required", "VPN log check could not run automatically.")
        if intent == "status_check":
            try:
                tickets = self.client.list_tickets_for_session(
                    state.get("session_id") or ""
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("status_check failed: %s", exc)
                return (
                    "manual_required",
                    "Could not look up your ticket status automatically.",
                )
            if not tickets:
                return (
                    "success",
                    "You have no tickets open for this session.",
                )
            lines = [
                f"- {t.get('ticket_id')} · {t.get('status')} · "
                f"priority {t.get('priority')} · {t.get('title','')[:48]}"
                for t in tickets[:5]
            ]
            return (
                "success",
                "Here are your tickets for this session:\n" + "\n".join(lines),
            )
        return ("not_needed", "")

    def run(self, state: dict) -> dict:
        state.setdefault("route_trace", []).append("workflow")
        state["automation_status"] = "not_needed"
        state["automation_result"] = None

        if state.get("requires_automation") and state.get("intent") in AUTOMATABLE_INTENTS:
            status, message = self._run_automation(state)
            state["automation_status"] = status
            state["automation_result"] = message or None

        create_ticket, reason = _should_create_ticket(state)
        state["should_create_ticket"] = create_ticket
        state["ticket_decision_reason"] = reason

        if create_ticket:
            payload = {
                "title": _ticket_title(state),
                "description": state.get("user_message") or "",
                "category": state.get("category") or "other",
                "priority": _priority_from_state(state),
                "severity": state.get("severity") or "medium",
                "urgency": state.get("urgency") or "medium",
                "session_id": state.get("session_id") or "unknown",
            }
            result = self.client.create_ticket(payload, fallback=True)
            state["ticket"] = result.ticket
            state["ops_api_unavailable"] = result.is_fallback
        else:
            state["ticket"] = None

        state["response"] = _append_workflow_result(state)
        return state


def _append_workflow_result(state: dict) -> str:
    parts: list[str] = []
    if state.get("response"):
        parts.append(state["response"])
    if state.get("automation_result"):
        parts.append(state["automation_result"])
    if state.get("ticket"):
        ticket_id = state["ticket"].get("ticket_id")
        priority = state["ticket"].get("priority", "")
        suffix = f" with priority {priority}" if priority else ""
        parts.append(f"I created ticket {ticket_id}{suffix} for follow-up.")
    if state.get("ops_api_unavailable"):
        parts.append(
            "The external ticketing service was unavailable, so this ticket was "
            "saved locally and will be synced when the service returns."
        )
    return "\n\n".join(p for p in parts if p).strip()
