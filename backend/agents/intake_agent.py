"""Intake classifier agent.

Returns: category, intent, confidence, is_support_request, severity, urgency.
The classifier is also responsible for telling the orchestrator whether a turn
is a real support request (so we don't open a ticket for "hi").
"""

from __future__ import annotations

import json
import re

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from backend.config import get_settings
from backend.utils.logger import get_logger

logger = get_logger(__name__)

VALID_CATEGORIES = {"password", "software", "hardware", "network", "access", "other"}
VALID_SEVERITY = {"low", "medium", "high", "critical"}
VALID_URGENCY = {"low", "medium", "high"}

INTAKE_SYSTEM_PROMPT = """\
You are an IT support intake classifier. Analyze the user's message and return ONLY
valid JSON with these exact keys (no extra text, no code fences):

{
  "category": one of ["password","software","hardware","network","access","other"],
  "intent": short 2-5 word description of what the user needs,
  "confidence": float in 0.0..1.0 indicating how clearly the request is stated,
  "is_support_request": true if the user is asking for help with a real IT issue,
                        false for greetings, small talk, thanks, or unrelated chatter,
  "severity": one of ["low","medium","high","critical"] reflecting business impact
              (data loss, outage, blocking many users -> critical/high; informational
              how-to -> low),
  "urgency": one of ["low","medium","high"] reflecting time pressure
              (mentions of urgent, asap, immediately, can't work -> high)
}

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
    """LLM classifier for category / intent / confidence / severity / urgency."""

    def __init__(self) -> None:
        settings = get_settings()
        self.llm = ChatAnthropic(
            model=settings.chat_model,
            temperature=0,
            anthropic_api_key=settings.anthropic_api_key or None,
        )

    def run(self, state: dict) -> dict:
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
            if category not in VALID_CATEGORIES:
                category = "other"

            intent = str(parsed.get("intent", "")).strip() or "unclear"

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
            state["intent"] = "unclear"
            state["confidence"] = 0.3
            state["severity"] = "medium"
            state["urgency"] = "medium"
            # If we couldn't classify, treat it as a support request so we
            # don't drop a real issue on the floor.
            state["is_support_request"] = True

        return state
