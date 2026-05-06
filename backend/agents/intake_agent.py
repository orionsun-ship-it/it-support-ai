"""Intake classifier agent.

Returns a fixed contract: category, intent, confidence, severity, urgency,
is_support_request. Routing functions in the orchestrator depend on this
contract being predictable.
"""

from __future__ import annotations

import json
import re

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from backend.config import get_settings
from backend.utils.logger import get_logger

logger = get_logger(__name__)

CATEGORY_VALUES = {
    "password",
    "access",
    "software",
    "hardware",
    "network",
    "email",
    "vpn",
    "security",
    "other",
}

INTENT_VALUES = {
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
}

VALID_SEVERITY = {"low", "medium", "high", "critical"}
VALID_URGENCY = {"low", "medium", "high"}

AUTOMATABLE_INTENTS = {
    "password_reset",
    "account_unlock",
    "software_license_check",
    "software_install",
    "access_request",
    "vpn_log_check",
    "status_check",
}

INTAKE_SYSTEM_PROMPT = f"""\
You are an IT support intake classifier. Analyze the user's message and
return ONLY valid JSON (no code fences, no extra text) with these keys:

{{
  "category": one of {sorted(CATEGORY_VALUES)},
  "intent":   one of {sorted(INTENT_VALUES)},
  "confidence": float in 0.0..1.0 (use >= 0.8 only when the request is
                clearly stated and matches a single category/intent),
  "is_support_request": true if the user is asking about an IT issue,
                        false for greetings, small talk, jokes, or other
                        non-IT requests,
  "severity": one of ["low","medium","high","critical"] reflecting business
              impact (data loss, outage, blocking many users -> critical/high;
              informational how-to -> low),
  "urgency":  one of ["low","medium","high"] reflecting time pressure
              (urgent / asap / immediately / "can't work" -> high)
}}

Routing examples:
- "how do I clear my browser cache" -> category=software, intent=knowledge_question
- "I forgot my password" -> category=password, intent=password_reset
- "my account is locked" -> category=access, intent=account_unlock
- "I need Slack installed on my laptop" -> category=software, intent=software_install
- "I need access to the production database" -> category=access, intent=access_request
- "what's the status of my tickets?" -> category=other, intent=status_check
- "VPN is down for the whole team" -> category=vpn, intent=vpn_log_check, urgency=high, severity=critical
- "please open a ticket for my broken laptop" -> category=hardware, intent=ticket_request
- "tell me a joke" -> category=other, intent=non_support, is_support_request=false

Return JSON only.
"""


def _extract_json(text: str) -> dict | None:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None


class IntakeAgent:
    """Classifies the user's request into a fixed schema."""

    def __init__(self) -> None:
        settings = get_settings()
        self.llm = ChatAnthropic(
            model=settings.chat_model,
            temperature=0,
            anthropic_api_key=settings.anthropic_api_key or None,
        )

    def run(self, state: dict) -> dict:
        state.setdefault("route_trace", []).append("intake")

        user_message = state.get("user_message", "")
        try:
            response = self.llm.invoke(
                [
                    SystemMessage(content=INTAKE_SYSTEM_PROMPT),
                    HumanMessage(content=user_message),
                ]
            )
            raw = (
                response.content
                if isinstance(response.content, str)
                else str(response.content)
            )
            parsed = _extract_json(raw)
            if not parsed:
                raise ValueError(f"Could not parse JSON: {raw!r}")

            category = str(parsed.get("category", "other")).lower()
            if category not in CATEGORY_VALUES:
                category = "other"

            intent = str(parsed.get("intent", "unknown")).lower()
            if intent not in INTENT_VALUES:
                intent = "unknown"

            try:
                confidence = float(parsed.get("confidence", 0.5))
            except (TypeError, ValueError):
                confidence = 0.5
            confidence = max(0.0, min(1.0, confidence))

            severity = str(parsed.get("severity", "medium")).lower()
            if severity not in VALID_SEVERITY:
                severity = "medium"

            urgency = str(parsed.get("urgency", "medium")).lower()
            if urgency not in VALID_URGENCY:
                urgency = "medium"

            is_support_request = bool(parsed.get("is_support_request", True))

            state["category"] = category
            state["intent"] = intent
            state["confidence"] = confidence
            state["severity"] = severity
            state["urgency"] = urgency
            state["is_support_request"] = is_support_request
        except Exception as exc:  # noqa: BLE001
            logger.warning("IntakeAgent fell back to defaults: %s", exc)
            state["category"] = "other"
            state["intent"] = "unknown"
            state["confidence"] = 0.3
            state["severity"] = "medium"
            state["urgency"] = "medium"
            state["is_support_request"] = True

        # Mark whether this request might be eligible for an automation later.
        state["requires_automation"] = state["intent"] in AUTOMATABLE_INTENTS
        return state
