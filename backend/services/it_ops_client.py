"""Typed client for the IT Ops API.

One place to call the ops API. Includes timeouts, a small retry loop, and a
"degraded" mode that returns sentinel responses if the service is unreachable
so the agent pipeline can keep running.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx

from backend.config import get_settings
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class ItOpsUnavailable(RuntimeError):
    """Raised when the ops API is unreachable AND no fallback was requested."""


@dataclass
class TicketResult:
    ticket: dict
    is_fallback: bool


def _local_fallback_ticket(payload: dict) -> dict:
    """Build a synthetic ticket so the agent pipeline can continue."""
    return {
        "ticket_id": "LOCAL-" + uuid.uuid4().hex[:8].upper(),
        "title": payload.get("title", ""),
        "description": payload.get("description", ""),
        "category": payload.get("category", "other"),
        "priority": payload.get("priority", "medium"),
        "severity": payload.get("severity", "medium"),
        "urgency": payload.get("urgency", "medium"),
        "status": "open",
        "session_id": payload.get("session_id", "unknown"),
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }


class ItOpsClient:
    """Small HTTP client for /api/v1/* on the IT Ops API."""

    def __init__(
        self,
        base_url: str | None = None,
        token: str | None = None,
        timeout: float = 5.0,
        retries: int = 2,
    ) -> None:
        s = get_settings()
        self.base_url = (base_url or s.it_ops_api_url).rstrip("/")
        self.token = token or s.it_ops_api_token
        self.timeout = timeout
        self.retries = retries

    @property
    def _headers(self) -> dict[str, str]:
        return {"Content-Type": "application/json", "X-Internal-Token": self.token}

    def _request(self, method: str, path: str, **kw: Any) -> httpx.Response:
        last_exc: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    resp = client.request(
                        method,
                        f"{self.base_url}{path}",
                        headers=self._headers,
                        **kw,
                    )
                    resp.raise_for_status()
                    return resp
            except httpx.RequestError as exc:
                last_exc = exc
                if attempt < self.retries:
                    time.sleep(0.2 * (attempt + 1))
                    continue
            except httpx.HTTPStatusError as exc:
                # 5xx: retry. 4xx: bubble up.
                last_exc = exc
                if exc.response.status_code >= 500 and attempt < self.retries:
                    time.sleep(0.2 * (attempt + 1))
                    continue
                raise
        assert last_exc is not None
        raise last_exc

    # -- Tickets ----------------------------------------------------------

    def create_ticket(self, payload: dict, *, fallback: bool = True) -> TicketResult:
        try:
            resp = self._request("POST", "/api/v1/tickets", json=payload)
            return TicketResult(ticket=resp.json(), is_fallback=False)
        except httpx.RequestError as exc:
            logger.warning("ops-api unreachable for create_ticket: %s", exc)
            if fallback:
                return TicketResult(
                    ticket=_local_fallback_ticket(payload), is_fallback=True
                )
            raise ItOpsUnavailable(str(exc)) from exc

    def list_tickets(
        self, *, category: str | None = None, status: str | None = None
    ) -> list[dict]:
        params: dict[str, str] = {}
        if category:
            params["category"] = category
        if status:
            params["status"] = status
        try:
            resp = self._request("GET", "/api/v1/tickets", params=params)
            return resp.json()
        except httpx.RequestError as exc:
            logger.warning("ops-api unreachable for list_tickets: %s", exc)
            return []

    def list_tickets_for_session(self, session_id: str) -> list[dict]:
        """Return tickets that belong to the given session."""
        all_tickets = self.list_tickets()
        return [t for t in all_tickets if t.get("session_id") == session_id]

    def update_status(self, ticket_id: str, new_status: str) -> dict | None:
        try:
            resp = self._request(
                "PATCH",
                f"/api/v1/tickets/{ticket_id}/status",
                json={"new_status": new_status, "actor": "agent"},
            )
            return resp.json()
        except httpx.RequestError as exc:
            logger.warning("ops-api unreachable for status update: %s", exc)
            return None

    def update_priority(self, ticket_id: str, new_priority: str) -> dict | None:
        try:
            resp = self._request(
                "PATCH",
                f"/api/v1/tickets/{ticket_id}/priority",
                json={"new_priority": new_priority, "actor": "agent"},
            )
            return resp.json()
        except httpx.RequestError as exc:
            logger.warning("ops-api unreachable for priority update: %s", exc)
            return None

    def delete_ticket(self, ticket_id: str) -> bool:
        """Delete a ticket. Returns True on success, False if not found or ops unreachable."""
        try:
            self._request("DELETE", f"/api/v1/tickets/{ticket_id}")
            return True
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return False
            raise
        except httpx.RequestError as exc:
            logger.warning("ops-api unreachable for delete_ticket: %s", exc)
            return False

    def analyze_logs(self, service: str = "network_events") -> dict:
        """Best-effort log analysis — returns the dict the ops API produces, or
        a minimal placeholder if unreachable."""
        try:
            resp = self._request(
                "POST",
                "/api/v1/logs/analyze",
                json={"log_file": service, "last_n_lines": 20},
            )
            return resp.json()
        except httpx.RequestError as exc:
            logger.warning("ops-api unreachable for analyze_logs: %s", exc)
            return {"summary": "Log analyzer offline; manual check required."}

    # -- Feedback ---------------------------------------------------------

    def submit_feedback(
        self,
        *,
        session_id: str,
        message_id: str,
        sentiment: str,
        comment: str = "",
    ) -> dict | None:
        try:
            resp = self._request(
                "POST",
                "/api/v1/feedback",
                json={
                    "session_id": session_id,
                    "message_id": message_id,
                    "sentiment": sentiment,
                    "comment": comment,
                },
            )
            return resp.json()
        except httpx.RequestError as exc:
            logger.warning("ops-api unreachable for submit_feedback: %s", exc)
            return None

    def feedback_summary(self) -> dict:
        try:
            resp = self._request("GET", "/api/v1/feedback/summary")
            return resp.json()
        except httpx.RequestError as exc:
            logger.warning("ops-api unreachable for feedback_summary: %s", exc)
            return {"total": 0, "thumbs_up": 0, "thumbs_down": 0, "satisfaction_score": 0.0}

    def is_available(self, timeout: float = 2.0) -> bool:
        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.get(f"{self.base_url}/health/ready")
                return resp.status_code == 200
        except httpx.RequestError:
            return False
