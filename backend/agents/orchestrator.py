"""LangGraph StateGraph that wires the four agents together."""

from __future__ import annotations

import time
from typing import Any, List, Literal, TypedDict

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
    severity: str | None
    urgency: str | None
    is_support_request: bool
    context: str | None
    context_scores: list | None
    match_strength: Literal["strong", "weak", "none"] | None
    sources: List[dict]
    response: str | None
    ticket: dict | None
    should_create_ticket: bool
    ticket_decision_reason: str | None
    ops_api_unavailable: bool
    escalated: bool
    automation_result: str | None
    response_time_ms: float


# Module-level singletons — heavy LLM/RAG handles, instantiated once.
_intake = IntakeAgent()
_knowledge = KnowledgeAgent()
_workflow = WorkflowAgent()
_escalation = EscalationAgent()


def _build_graph() -> Any:
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
    """Run a single user turn through the full agent graph."""
    start = time.perf_counter()
    initial_state: dict = {
        "user_message": user_message,
        "session_id": session_id,
        "history": history or [],
        "category": None,
        "intent": None,
        "confidence": 0.0,
        "severity": None,
        "urgency": None,
        "is_support_request": True,
        "context": None,
        "context_scores": None,
        "match_strength": None,
        "sources": [],
        "response": None,
        "ticket": None,
        "should_create_ticket": False,
        "ticket_decision_reason": None,
        "ops_api_unavailable": False,
        "escalated": False,
        "automation_result": None,
        "response_time_ms": 0.0,
    }

    final_state = graph.invoke(initial_state)
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    final_state["response_time_ms"] = elapsed_ms

    logger.info(
        "process_message session=%s category=%s confidence=%.2f severity=%s "
        "urgency=%s match=%s ticket=%s escalated=%s elapsed_ms=%.1f",
        session_id,
        final_state.get("category"),
        float(final_state.get("confidence") or 0.0),
        final_state.get("severity"),
        final_state.get("urgency"),
        final_state.get("match_strength"),
        (final_state.get("ticket") or {}).get("ticket_id"),
        final_state.get("escalated"),
        elapsed_ms,
    )
    return final_state


__all__ = ["graph", "process_message", "AgentState"]
