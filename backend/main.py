"""FastAPI application entrypoint for the IT Support AI backend."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, List

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.agents.orchestrator import process_message
from backend.models.schemas import (
    AgentResponse,
    ConversationTurn,
    SessionState,
    SystemMetrics,
    TicketCreate,
    TicketResponse,
    UserMessage,
)
from backend.rag.retriever import KnowledgeRetriever, seed_knowledge_base
from backend.utils.logger import get_logger

load_dotenv()
logger = get_logger(__name__)

MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8001")

app = FastAPI(title="IT Support AI Backend", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# In-memory state ----------------------------------------------------------

sessions: Dict[str, SessionState] = {}
request_log: List[Dict[str, Any]] = []
app_start_time: datetime = datetime.now()


# Startup ------------------------------------------------------------------


@app.on_event("startup")
def _startup() -> None:
    try:
        seed_knowledge_base()
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to seed knowledge base on startup: %s", exc)


# Helpers ------------------------------------------------------------------


def _get_or_create_session(session_id: str) -> SessionState:
    session = sessions.get(session_id)
    if session is None:
        session = SessionState(session_id=session_id)
        sessions[session_id] = session
    return session


def _check_mcp_available(timeout: float = 2.0) -> bool:
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.get(f"{MCP_SERVER_URL}/health")
            return resp.status_code == 200
    except httpx.RequestError:
        return False


# Endpoints ----------------------------------------------------------------


@app.post("/chat", response_model=AgentResponse)
def chat(payload: UserMessage) -> AgentResponse:
    """Main chat endpoint — runs the user's message through the agent graph."""
    session = _get_or_create_session(payload.session_id)

    # Last 10 turns to keep prompt size manageable.
    history_models = session.history[-10:]
    history = [{"role": t.role, "content": t.content} for t in history_models]

    try:
        state = process_message(
            user_message=payload.message,
            session_id=payload.session_id,
            history=history,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("process_message failed: %s", exc)
        raise HTTPException(
            status_code=500, detail=f"Agent pipeline failed: {exc}"
        ) from exc

    response_text = state.get("response") or "(no response)"
    confidence = float(state.get("confidence") or 0.0)
    automation_result = state.get("automation_result")
    ticket = state.get("ticket") or {}
    ticket_id = ticket.get("ticket_id")
    escalated = bool(state.get("escalated"))
    response_time_ms = float(state.get("response_time_ms") or 0.0)

    # Update session
    session.history.append(
        ConversationTurn(role="user", content=payload.message)
    )
    session.history.append(
        ConversationTurn(
            role="assistant",
            content=response_text,
            agent_name="it-support-ai",
            ticket_id=ticket_id,
            escalated=escalated,
        )
    )
    if escalated:
        session.escalated = True
    if ticket and ticket.get("ticket_id"):
        try:
            session.current_ticket = TicketResponse(
                ticket_id=ticket["ticket_id"],
                title=ticket.get("title", ""),
                description=ticket.get("description", ""),
                priority=ticket.get("priority", "medium"),
                category=ticket.get("category", "other"),
                session_id=ticket.get("session_id", payload.session_id),
                status=ticket.get("status", "open"),
                created_at=datetime.fromisoformat(ticket["created_at"])
                if isinstance(ticket.get("created_at"), str)
                else (ticket.get("created_at") or datetime.now()),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not coerce ticket into TicketResponse: %s", exc)

    request_log.append(
        {
            "timestamp": datetime.now().isoformat(),
            "response_time_ms": response_time_ms,
            "escalated": escalated,
        }
    )

    return AgentResponse(
        agent_name="it-support-ai",
        content=response_text,
        confidence=confidence,
        action_taken=automation_result,
        ticket_id=ticket_id,
        escalated=escalated,
    )


@app.get("/session/{session_id}", response_model=SessionState)
def get_session(session_id: str) -> SessionState:
    session = sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    return session


@app.get("/tickets")
def list_tickets() -> list[dict]:
    """Proxies the MCP server's list_tickets. Falls back to session state if MCP is down."""
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(f"{MCP_SERVER_URL}/tools/list_tickets")
            resp.raise_for_status()
            return resp.json()
    except httpx.RequestError as exc:
        logger.warning("MCP list_tickets unreachable, falling back: %s", exc)
        fallback: list[dict] = []
        for sess in sessions.values():
            if sess.current_ticket is not None:
                fallback.append(sess.current_ticket.model_dump(mode="json"))
        return fallback
    except httpx.HTTPStatusError as exc:
        logger.warning("MCP list_tickets HTTP error: %s", exc)
        raise HTTPException(status_code=502, detail="MCP server returned an error") from exc


@app.post("/tickets", response_model=TicketResponse)
def create_ticket(payload: TicketCreate) -> TicketResponse:
    """Proxy ticket creation through the MCP server."""
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.post(
                f"{MCP_SERVER_URL}/tools/create_ticket",
                json=payload.model_dump(),
            )
            resp.raise_for_status()
            data = resp.json()
            return TicketResponse(
                ticket_id=data["ticket_id"],
                title=data["title"],
                description=data["description"],
                priority=data["priority"],
                category=data["category"],
                session_id=data["session_id"],
                status=data["status"],
                created_at=datetime.fromisoformat(data["created_at"])
                if isinstance(data["created_at"], str)
                else data["created_at"],
            )
    except httpx.RequestError as exc:
        logger.error("MCP create_ticket unreachable: %s", exc)
        raise HTTPException(
            status_code=503, detail="MCP server is not reachable"
        ) from exc
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/metrics", response_model=SystemMetrics)
def metrics() -> SystemMetrics:
    total_requests = len(request_log)
    if total_requests > 0:
        avg_response_time = sum(r["response_time_ms"] for r in request_log) / total_requests
    else:
        avg_response_time = 0.0

    total_escalations = sum(1 for r in request_log if r["escalated"])

    # Total tickets from MCP, fallback to session-local counts.
    total_tickets = 0
    try:
        with httpx.Client(timeout=2.0) as client:
            resp = client.get(f"{MCP_SERVER_URL}/tools/list_tickets")
            resp.raise_for_status()
            total_tickets = len(resp.json())
    except httpx.RequestError:
        total_tickets = sum(1 for s in sessions.values() if s.current_ticket is not None)

    try:
        kb_seeded = KnowledgeRetriever().count() > 0
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not query KB count: %s", exc)
        kb_seeded = False

    uptime_seconds = (datetime.now() - app_start_time).total_seconds()

    return SystemMetrics(
        total_requests=total_requests,
        avg_response_time_ms=avg_response_time,
        total_tickets=total_tickets,
        total_escalations=total_escalations,
        kb_seeded=kb_seeded,
        uptime_seconds=uptime_seconds,
    )


@app.get("/debug/retrieve")
def debug_retrieve(query: str) -> dict:
    """Debug endpoint — remove or restrict before production."""
    retriever = KnowledgeRetriever()
    raw = retriever.retrieve_with_scores(query, n_results=3)
    formatted = retriever.retrieve(query, n_results=3)
    return {
        "query": query,
        "results": [
            {"text": r["text"], "distance": r["distance"], "metadata": r["metadata"]}
            for r in raw
        ],
        "formatted_context": formatted,
    }


@app.get("/health")
def health() -> dict:
    try:
        kb_seeded = KnowledgeRetriever().count() > 0
    except Exception:  # noqa: BLE001
        kb_seeded = False
    return {
        "status": "ok",
        "kb_seeded": kb_seeded,
        "mcp_available": _check_mcp_available(),
    }
