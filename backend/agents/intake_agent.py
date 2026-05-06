"""Intake classifier agent — turns a free-form user message into structured intent."""

from __future__ import annotations

import json
import re

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from backend.utils.logger import get_logger

load_dotenv()
logger = get_logger(__name__)

INTAKE_SYSTEM_PROMPT = (
    "You are an IT support intake classifier. Analyze the user's message and return ONLY "
    "valid JSON with these exact keys: category (one of: password, software, hardware, "
    "network, access, other), intent (a short 2-5 word description of what the user "
    "needs), confidence (float 0.0–1.0 based on how clearly the request is stated). "
    "Return no other text."
)


def _extract_json(text: str) -> dict | None:
    """Best-effort JSON extraction from a model response."""
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
    """Classifies the user's request into category / intent / confidence."""

    def __init__(self) -> None:
        self.llm = ChatAnthropic(model="claude-3-5-haiku-20241022", temperature=0)

    def run(self, state: dict) -> dict:
        user_message = state.get("user_message", "")
        try:
            response = self.llm.invoke(
                [
                    SystemMessage(content=INTAKE_SYSTEM_PROMPT),
                    HumanMessage(content=user_message),
                ]
            )
            raw = response.content if isinstance(response.content, str) else str(response.content)
            parsed = _extract_json(raw)
            if not parsed:
                raise ValueError(f"Intake agent could not parse JSON: {raw!r}")

            category = str(parsed.get("category", "other")).lower()
            if category not in {"password", "software", "hardware", "network", "access", "other"}:
                category = "other"

            intent = str(parsed.get("intent", "")).strip() or "unclear"
            confidence_raw = parsed.get("confidence", 0.5)
            try:
                confidence = float(confidence_raw)
            except (TypeError, ValueError):
                confidence = 0.5
            confidence = max(0.0, min(1.0, confidence))

            state["category"] = category
            state["intent"] = intent
            state["confidence"] = confidence
        except Exception as exc:  # noqa: BLE001
            logger.warning("IntakeAgent fell back to defaults: %s", exc)
            state["category"] = "other"
            state["intent"] = "unclear"
            state["confidence"] = 0.3

        return state
