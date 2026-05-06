"""FastAPI application entrypoint for the IT Support AI backend."""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.agents.orchestrator import process_message
from backend.config import get_settings
from backend.models.schemas import (
    AgentResponse,
    ConversationTurn,
    FeedbackCreate,
    KBSource,
    SessionState,
    SystemMetrics,
    TicketCreate,
    TicketResponse,
    UserMessage,
)
from backend.rag.retriever import KnowledgeRetriever, seed_knowledge_base
from backend.services.it_ops_client import ItOpsClient
from backend.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()

app = FastAPI(title="IT Support AI Backend", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Content-Type", "Authorization"],
)


# ---------------------------------------------------------------------------
# In-memory state — fine for local dev. Phase-4 follow-up: move to Redis/DB.
# ---------------------------------------------------------------------------

sessions: Dict[str, SessionState] = {}
request_log: List[Dict[str, Any]] = []
app_start_time: datetime = datetime.now()
ops_client = ItOpsClient()


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------


@app.on_event("startup")
def _startup() -> None:
    # ---- Anthropic API key visibility ----
    import os

    settings_key = (settings.anthropic_api_key or "").strip()
    env_key = (os.environ.get("ANTHROPIC_API_KEY") or "").strip()
    if not settings_key and not env_key:
        logger.error(
            "ANTHROPIC_API_KEY is NOT loaded. Edit .env (no quotes, no spaces) "
            "and restart. Looked for it in %s and in the shell env.",
            settings.model_config.get("env_file"),
        )
    else:
        chosen = settings_key or env_key
        source = "settings/.env" if settings_key else "shell env"
        if chosen.startswith("sk-ant-"):
            logger.info(
                "ANTHROPIC_API_KEY loaded from %s (prefix=%s..., length=%d)",
                source,
                chosen[:10],
                len(chosen),
            )
        else:
            logger.warning(
                "ANTHROPIC_API_KEY found in %s but does NOT start with 'sk-ant-' "
                "(got prefix=%r, length=%d). Did you paste the wrong value?",
                source,
                chosen[:10],
                len(chosen),
            )
        # Make sure langchain-anthropic, which reads os.environ directly, can see it.
        if settings_key and not env_key:
            os.environ["ANTHROPIC_API_KEY"] = settings_key

    problems = settings.validate_runtime(require_llm=True)
    if problems:
        for p in problems:
            logger.error("config: %s", p)
        if settings.is_prod:
            sys.exit("Refusing to start in prod with invalid config")

    try:
        summary = seed_knowledge_base()
        logger.info("KB ingestion summary: %s", summary)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to seed knowledge base: %s", exc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_or_create_session(session_id: str) -> SessionState:
    session = sessions.get(session_id)
    if session is None:
        session = SessionState(session_id=session_id)
        sessions[session_id] = session
    return session


def _kb_sources_from_state(state: dict) -> list[KBSource]:
    out: list[KBSource] = []
    for s in state.get("sources") or []:
        try:
            out.append(KBSource(**s))
        except Exception:  # noqa: BLE001
            continue
    return out


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.post("/chat", response_model=AgentResponse)
def chat(payload: UserMessage) -> AgentResponse:
    session = _get_or_create_session(payload.session_id)
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
    sources = _kb_sources_from_state(state)

    session.history.append(ConversationTurn(role="user", content=payload.message))
    session.history.append(
        ConversationTurn(
            role="assistant",
            content=response_text,
            agent_name="it-support-ai",
            ticket_id=ticket_id,
            escalated=escalated,
            sources=sources,
        )
    )
    if escalated:
        session.escalated = True
    if ticket and ticket.get("ticket_id"):
        try:
            session.current_ticket = TicketResponse(**_normalize_ticket(ticket, payload.session_id))
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
        severity=state.get("severity"),
        urgency=state.get("urgency"),
        category=state.get("category"),
        intent=state.get("intent"),
        action_taken=automation_result,
        ticket_id=ticket_id,
        escalated=escalated,
        match_strength=state.get("match_strength"),
        sources=sources,
        route_trace=list(state.get("route_trace") or []),
        final_route=state.get("final_route"),
        ticket_decision_reason=state.get("ticket_decision_reason"),
        automation_status=state.get("automation_status"),
    )


def _normalize_ticket(ticket: dict, session_id: str) -> dict:
    return {
        "ticket_id": ticket["ticket_id"],
        "title": ticket.get("title", ""),
        "description": ticket.get("description", ""),
        "priority": ticket.get("priority", "medium"),
        "category": ticket.get("category", "other"),
        "severity": ticket.get("severity", "medium"),
        "urgency": ticket.get("urgency", "medium"),
        "session_id": ticket.get("session_id", session_id),
        "status": ticket.get("status", "open"),
        "created_at": ticket.get("created_at") or datetime.utcnow().isoformat(),
        "updated_at": ticket.get("updated_at"),
    }


@app.get("/session/{session_id}", response_model=SessionState)
def get_session(session_id: str) -> SessionState:
    session = sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    return session


@app.get("/tickets")
def list_tickets() -> list[dict]:
    return ops_client.list_tickets()


@app.post("/tickets", response_model=TicketResponse)
def create_ticket_endpoint(payload: TicketCreate) -> TicketResponse:
    result = ops_client.create_ticket(payload.model_dump(), fallback=False)
    data = result.ticket
    return TicketResponse(**_normalize_ticket(data, payload.session_id))


@app.get("/metrics", response_model=SystemMetrics)
def metrics() -> SystemMetrics:
    total_requests = len(request_log)
    avg_response = (
        sum(r["response_time_ms"] for r in request_log) / total_requests
        if total_requests
        else 0.0
    )
    total_escalations = sum(1 for r in request_log if r["escalated"])

    ops_available = ops_client.is_available(timeout=2.0)
    total_tickets = len(ops_client.list_tickets()) if ops_available else 0

    try:
        kb_seeded = KnowledgeRetriever().count() > 0
    except Exception as exc:  # noqa: BLE001
        logger.warning("KB count failed: %s", exc)
        kb_seeded = False

    fb = ops_client.feedback_summary() if ops_available else {}

    return SystemMetrics(
        total_requests=total_requests,
        avg_response_time_ms=avg_response,
        total_tickets=total_tickets,
        total_escalations=total_escalations,
        kb_seeded=kb_seeded,
        uptime_seconds=(datetime.now() - app_start_time).total_seconds(),
        ops_api_available=ops_available,
        satisfaction_score=float(fb.get("satisfaction_score") or 0.0),
        feedback_total=int(fb.get("total") or 0),
        feedback_up=int(fb.get("thumbs_up") or 0),
        feedback_down=int(fb.get("thumbs_down") or 0),
    )


@app.post("/feedback")
def submit_feedback(payload: FeedbackCreate) -> dict:
    """Record a thumbs-up / thumbs-down on an assistant turn."""
    result = ops_client.submit_feedback(
        session_id=payload.session_id,
        message_id=payload.message_id,
        sentiment=payload.sentiment,
        comment=payload.comment,
    )
    if result is None:
        raise HTTPException(
            status_code=503, detail="ops API is not reachable"
        )
    return result


@app.patch("/tickets/{ticket_id}/status")
def update_ticket_status(ticket_id: str, payload: dict) -> dict:
    """Proxy a ticket status update to the ops API (used by the UI)."""
    new_status = (payload or {}).get("new_status")
    if not new_status:
        raise HTTPException(status_code=400, detail="new_status is required")
    result = ops_client.update_status(ticket_id, new_status)
    if result is None:
        raise HTTPException(
            status_code=503, detail="ops API is not reachable"
        )
    return result


@app.get("/sources")
def list_sources() -> dict:
    """List every KB document on disk (the source of truth, not the vector index)."""
    kb_dir = Path(settings.kb_dir)
    docs: list[dict] = []
    files: list[str] = []
    if kb_dir.exists():
        for path in sorted(kb_dir.glob("*.json")):
            files.append(path.name)
            try:
                payload = json.loads(path.read_text())
            except Exception as exc:  # noqa: BLE001
                logger.warning("Could not parse %s: %s", path, exc)
                continue
            entries = (
                payload.get("documents", [])
                if isinstance(payload, dict) and "documents" in payload
                else (payload if isinstance(payload, list) else [payload])
            )
            for d in entries:
                if not isinstance(d, dict):
                    continue
                docs.append(
                    {
                        "doc_id": d.get("doc_id") or d.get("id", ""),
                        "title": d.get("title", ""),
                        "category": d.get("category", "other"),
                        "source": d.get("source", "internal-kb"),
                        "version": d.get("version", ""),
                        "updated_at": d.get("updated_at", ""),
                        "body": d.get("body") or d.get("text", ""),
                        "source_file": path.name,
                    }
                )
    return {
        "kb_dir": str(kb_dir),
        "files": files,
        "total": len(docs),
        "documents": docs,
    }


@app.get("/debug/retrieve")
def debug_retrieve(query: str) -> dict:
    """Debug endpoint — disabled when ENABLE_DEBUG_ENDPOINTS=false."""
    if not settings.enable_debug_endpoints:
        raise HTTPException(status_code=404, detail="Not found")
    retriever = KnowledgeRetriever()
    result = retriever.retrieve(query, n_results=3)
    return {
        "query": query,
        "match_strength": result.match_strength,
        "sources": [s.to_dict() for s in result.sources],
        "formatted_context": KnowledgeRetriever.format_context(result),
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
        "ops_api_available": ops_client.is_available(),
    }
