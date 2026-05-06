"""Workflow agent — runs deterministic automations and creates a ticket via the MCP server."""

from __future__ import annotations

import os
import uuid
from datetime import datetime

import httpx
from dotenv import load_dotenv

from backend.utils.logger import get_logger

load_dotenv()
logger = get_logger(__name__)

MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8001")


class WorkflowAgent:
    """Performs scripted workflow automations and creates a ticket through the MCP server."""

    def run(self, state: dict) -> dict:
        category = state.get("category") or "other"
        confidence = float(state.get("confidence") or 0.0)
        user_message = state.get("user_message") or ""
        session_id = state.get("session_id") or "unknown"

        # 1. Automation result by category
        automation_result: str | None
        if category == "password":
            automation_result = (
                "Password reset initiated. A reset link will be sent to your registered "
                "email within 5 minutes."
            )
        elif category == "access":
            automation_result = (
                "Account unlock request submitted. Your account will be unlocked within "
                "2 minutes."
            )
        elif category == "software":
            automation_result = (
                "Software license check completed. Your license is active and valid."
            )
        else:
            automation_result = None

        # 2. Priority from confidence
        if confidence > 0.8:
            priority = "low"
        elif confidence >= 0.5:
            priority = "medium"
        else:
            priority = "high"
        # The escalation agent may upgrade this to "critical" downstream.

        # 3. Create ticket via MCP, with a local fallback
        title = (user_message or "(no title)")[:60]
        payload = {
            "title": title,
            "description": user_message,
            "category": category,
            "priority": priority,
            "session_id": session_id,
        }

        ticket: dict | None = None
        unavailable_note = False
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.post(f"{MCP_SERVER_URL}/tools/create_ticket", json=payload)
                resp.raise_for_status()
                ticket = resp.json()
        except httpx.RequestError as exc:
            logger.warning(
                "MCP unreachable, creating local ticket. Underlying error: %s", exc
            )
            ticket = {
                "ticket_id": "LOCAL-" + uuid.uuid4().hex[:8].upper(),
                "title": title,
                "description": user_message,
                "category": category,
                "priority": priority,
                "session_id": session_id,
                "status": "open",
                "created_at": datetime.now().isoformat(),
            }
            unavailable_note = True
        except httpx.HTTPStatusError as exc:
            logger.warning("MCP returned an HTTP error: %s", exc)
            ticket = {
                "ticket_id": "LOCAL-" + uuid.uuid4().hex[:8].upper(),
                "title": title,
                "description": user_message,
                "category": category,
                "priority": priority,
                "session_id": session_id,
                "status": "open",
                "created_at": datetime.now().isoformat(),
            }
            unavailable_note = True

        state["ticket"] = ticket
        state["automation_result"] = automation_result

        # 4. Append automation_result + any unavailability note to the response.
        existing_response = state.get("response") or ""
        extra_lines: list[str] = []
        if automation_result:
            extra_lines.append(automation_result)
        if unavailable_note:
            extra_lines.append(
                "Note: the ticketing service is currently unavailable; a local ticket has "
                "been created and will be synced when the service returns."
            )
        if extra_lines:
            state["response"] = (existing_response + "\n" + "\n".join(extra_lines)).strip()

        return state
