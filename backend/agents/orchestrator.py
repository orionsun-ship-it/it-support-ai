"""LangGraph orchestrator with true conditional routing.

Branching:

    START
      ↓
    intake
      ├── is_support_request == False           → final_response
      └── otherwise                             → knowledge

    knowledge
      ├── intent == ticket_request              → workflow
      ├── requires_automation                   → workflow
      ├── user already tried & stuck            → escalation
      └── otherwise                             → final_response

    workflow
      ├── automation failed / manual_required   → escalation
      ├── severity=critical OR urgency=high     → escalation
      └── otherwise                             → final_response

    escalation → final_response → END

Escalation triggers:
- The automation step explicitly fails or requires manual approval, OR
- The originating request is critical-severity or high-urgency (a ticket
  alone is not enough — a human handoff is also needed), OR
- The user has confirmed the suggested fix did not resolve the issue.
"""

from __future__ import annotations

import time
from typing import Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from backend.agents.escalation_agent import EscalationAgent
from backend.agents.intake_agent import IntakeAgent
from backend.agents.knowledge_agent import KnowledgeAgent
from backend.agents.workflow_agent import WorkflowAgent
from backend.utils.logger import get_logger

logger = get_logger(__name__)

_STUCK_PHRASES = (
    "still not working",
    "still broken",
    "didn't work",
    "did not work",
    "doesn't work",
    "does not work",
    "no luck",
    "still the same",
    "same issue",
    "same problem",
    "same error",
    "still happening",
    "not fixed",
    "still stuck",
    "tried that",
    "already tried",
    "not resolved",
    "not solved",
    "still failing",
)


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
    match_strength: Literal["strong", "weak", "none"] | None
    sources: list[dict]
    response: str | None
    ticket: dict | None
    should_create_ticket: bool
    ticket_decision_reason: str | None
    automation_status: (
        Literal["not_needed", "success", "failed", "manual_required"] | None
    )
    automation_result: str | None
    automation_simulated: bool
    ops_api_unavailable: bool
    escalated: bool
    response_time_ms: float
    route_trace: list[str]
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


def _user_is_stuck(state: AgentState) -> bool:
    """Return True if the user has already tried our suggestion and it failed."""
    history = state.get("history") or []
    user_msg = (state.get("user_message") or "").lower()

    # Explicit escalation / human request is always honoured.
    if any(
        w in user_msg
        for w in ("escalate", "human agent", "real person", "speak to someone")
    ):
        return True

    # Only consider "still stuck" signals when there's at least one prior exchange.
    has_prior_assistant = any(h.get("role") == "assistant" for h in history)
    if not has_prior_assistant:
        return False

    return any(phrase in user_msg for phrase in _STUCK_PHRASES)


def route_after_intake(state: AgentState) -> str:
    if not state.get("is_support_request", True):
        return "final_response"
    # Always try the knowledge base first; escalation happens only after the
    # user confirms the suggestion didn't resolve their issue.
    return "knowledge"


def route_after_knowledge(state: AgentState) -> str:
    if state.get("intent") == "ticket_request":
        return "workflow"
    if state.get("requires_automation"):
        return "workflow"
    # Only escalate when the user has already tried our answer and is still stuck.
    if _user_is_stuck(state):
        return "escalation"
    return "final_response"


def route_after_workflow(state: AgentState) -> str:
    if state.get("automation_status") in {"failed", "manual_required"}:
        return "escalation"
    # Critical severity or high urgency cases need human follow-up even when
    # the automation step reports success — a real engineer should pick the
    # ticket up regardless of the canned fix.
    if state.get("severity") == "critical" or state.get("urgency") == "high":
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
        "match_strength": None,
        "sources": [],
        "response": None,
        "ticket": None,
        "should_create_ticket": False,
        "ticket_decision_reason": None,
        "automation_status": None,
        "automation_result": None,
        "automation_simulated": False,
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
