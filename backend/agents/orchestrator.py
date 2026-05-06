"""LangGraph orchestrator with true conditional routing.

Branching:

    START
      ↓
    intake
      ├── is_support_request == False                       → final_response
      ├── confidence < 0.55 OR category in {None, "other"}  → escalation
      └── otherwise                                          → knowledge

    knowledge
      ├── urgency == high OR severity == critical           → workflow
      ├── match_strength in {"weak","none"}                 → escalation
      ├── requires_automation                               → workflow
      └── otherwise                                          → final_response

    workflow
      ├── automation failed OR manual_required              → escalation
      ├── should_create_ticket  -> include in answer        → final_response
      └── otherwise                                          → final_response

    escalation → final_response → END
"""

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
    requires_automation: bool
    context: str | None
    context_scores: list | None
    match_strength: Literal["strong", "weak", "none"] | None
    sources: List[dict]
    response: str | None
    ticket: dict | None
    should_create_ticket: bool
    ticket_decision_reason: str | None
    automation_status: Literal["not_needed", "success", "failed", "manual_required"] | None
    automation_result: str | None
    ops_api_unavailable: bool
    escalated: bool
    response_time_ms: float
    route_trace: List[str]
    final_route: str | None


# Module-level singletons; agents hold heavy LLM and KB handles.
_intake = IntakeAgent()
_knowledge = KnowledgeAgent()
_workflow = WorkflowAgent()
_escalation = EscalationAgent()


# ---------------------------------------------------------------------------
# Final response node
# ---------------------------------------------------------------------------


def final_response_node(state: AgentState) -> AgentState:
    state.setdefault("route_trace", []).append("final_response")
    if not state.get("response"):
        state["response"] = (
            "I can help with IT support questions about passwords, VPN, "
            "software, hardware, network, access, email, or security. Could "
            "you tell me more about what you need?"
        )
    return state


# ---------------------------------------------------------------------------
# Routing functions — pure: read state, return the next node name.
# ---------------------------------------------------------------------------


def route_after_intake(state: AgentState) -> str:
    if not state.get("is_support_request", True):
        return "final_response"

    confidence = float(state.get("confidence") or 0.0)
    urgency = state.get("urgency")
    severity = state.get("severity")
    category = state.get("category")

    # Always route urgent/critical through knowledge so we still try to answer.
    if urgency == "high" or severity == "critical":
        return "knowledge"

    # Fall straight to escalation when intake is uncertain.
    if confidence < 0.55 or category in {None, "unknown", "other"}:
        return "escalation"

    return "knowledge"


def route_after_knowledge(state: AgentState) -> str:
    if state.get("urgency") == "high" or state.get("severity") == "critical":
        return "workflow"
    if state.get("match_strength") in {"weak", "none"}:
        return "escalation"
    if state.get("requires_automation"):
        return "workflow"
    return "final_response"


def route_after_workflow(state: AgentState) -> str:
    if state.get("automation_status") in {"failed", "manual_required"}:
        return "escalation"
    return "final_response"


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------


def _build_graph() -> Any:
    builder = StateGraph(AgentState)

    builder.add_node("intake", _intake.run)
    builder.add_node("knowledge", _knowledge.run)
    builder.add_node("workflow", _workflow.run)
    builder.add_node("escalation", _escalation.run)
    builder.add_node("final_response", final_response_node)

    builder.add_edge(START, "intake")

    builder.add_conditional_edges(
        "intake",
        route_after_intake,
        {
            "knowledge": "knowledge",
            "escalation": "escalation",
            "final_response": "final_response",
        },
    )
    builder.add_conditional_edges(
        "knowledge",
        route_after_knowledge,
        {
            "workflow": "workflow",
            "escalation": "escalation",
            "final_response": "final_response",
        },
    )
    builder.add_conditional_edges(
        "workflow",
        route_after_workflow,
        {
            "escalation": "escalation",
            "final_response": "final_response",
        },
    )

    builder.add_edge("escalation", "final_response")
    builder.add_edge("final_response", END)

    return builder.compile()


graph = _build_graph()


# ---------------------------------------------------------------------------
# Entrypoint used by the FastAPI backend
# ---------------------------------------------------------------------------


def process_message(
    user_message: str,
    session_id: str,
    history: list,
) -> dict:
    """Run a single user turn through the agent graph."""
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
        "requires_automation": False,
        "context": None,
        "context_scores": None,
        "match_strength": None,
        "sources": [],
        "response": None,
        "ticket": None,
        "should_create_ticket": False,
        "ticket_decision_reason": None,
        "automation_status": None,
        "automation_result": None,
        "ops_api_unavailable": False,
        "escalated": False,
        "response_time_ms": 0.0,
        "route_trace": [],
        "final_route": None,
    }

    final_state = graph.invoke(initial_state)
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    final_state["response_time_ms"] = elapsed_ms

    trace = final_state.get("route_trace") or []
    final_state["final_route"] = trace[-1] if trace else None

    logger.info(
        "session=%s category=%s intent=%s route=%s match=%s automation=%s "
        "ticket=%s escalated=%s elapsed_ms=%.1f",
        session_id,
        final_state.get("category"),
        final_state.get("intent"),
        " -> ".join(trace),
        final_state.get("match_strength"),
        final_state.get("automation_status"),
        bool(final_state.get("ticket")),
        final_state.get("escalated"),
        elapsed_ms,
    )
    return final_state


__all__ = [
    "graph",
    "process_message",
    "AgentState",
    "route_after_intake",
    "route_after_knowledge",
    "route_after_workflow",
    "final_response_node",
]
