"""LangGraph StateGraph that wires the four agents together."""

from __future__ import annotations

import time
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from backend.agents.escalation_agent import EscalationAgent
from backend.agents.intake_agent import IntakeAgent
from backend.agents.knowledge_agent import KnowledgeAgent
from backend.agents.workflow_agent import WorkflowAgent
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class AgentState(TypedDict, total=False):
    user_message: str
    session_id: str
    history: list
    category: str | None
    intent: str | None
    confidence: float
    context: str | None
    context_scores: list | None
    response: str | None
    ticket: dict | None
    escalated: bool
    automation_result: str | None
    response_time_ms: float


# Instantiate agents once at module load — they hold lazy LLM clients and KB handles.
_intake = IntakeAgent()
_knowledge = KnowledgeAgent()
_workflow = WorkflowAgent()
_escalation = EscalationAgent()


def _build_graph():
    builder = StateGraph(AgentState)
    builder.add_node("intake", _intake.run)
    builder.add_node("knowledge", _knowledge.run)
    builder.add_node("workflow", _workflow.run)
    builder.add_node("escalation", _escalation.run)

    builder.add_edge(START, "intake")
    builder.add_edge("intake", "knowledge")
    builder.add_edge("knowledge", "workflow")
    builder.add_edge("workflow", "escalation")
    builder.add_edge("escalation", END)

    return builder.compile()


graph = _build_graph()


def process_message(
    user_message: str,
    session_id: str,
    history: list,
) -> dict:
    """Run a single user turn through the full agent graph.

    Returns the final AgentState dict including response, ticket, escalated, and
    response_time_ms.
    """
    start = time.perf_counter()

    initial_state: dict = {
        "user_message": user_message,
        "session_id": session_id,
        "history": history or [],
        "category": None,
        "intent": None,
        "confidence": 0.0,
        "context": None,
        "context_scores": None,
        "response": None,
        "ticket": None,
        "escalated": False,
        "automation_result": None,
        "response_time_ms": 0.0,
    }

    final_state = graph.invoke(initial_state)
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    final_state["response_time_ms"] = elapsed_ms

    logger.info(
        "process_message session=%s category=%s confidence=%.2f escalated=%s "
        "elapsed_ms=%.1f",
        session_id,
        final_state.get("category"),
        float(final_state.get("confidence") or 0.0),
        final_state.get("escalated"),
        elapsed_ms,
    )

    return final_state


__all__ = ["graph", "process_message", "AgentState"]
