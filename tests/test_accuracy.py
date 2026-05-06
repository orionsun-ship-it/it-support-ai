"""End-to-end accuracy harness.

Runs every scenario in test_scenarios.json through the orchestrator and writes
a summary report to tests/results/. The ops API is mocked out so this script
does NOT require a running services.it_ops_api process — it only needs the
ANTHROPIC_API_KEY and a seeded vector store.

Usage:
    python tests/test_accuracy.py
"""

from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.rag.retriever import seed_knowledge_base  # noqa: E402
from backend.services.it_ops_client import ItOpsClient, TicketResult  # noqa: E402

SCENARIOS_PATH = Path(__file__).parent / "test_scenarios.json"
RESULTS_DIR = Path(__file__).parent / "results"


# ---------------------------------------------------------------------------
# Patch the ops client BEFORE importing the orchestrator, so the singleton
# WorkflowAgent/EscalationAgent use the mock.
# ---------------------------------------------------------------------------


def _fake_ticket(payload: dict) -> dict:
    return {
        "ticket_id": "TEST-" + uuid.uuid4().hex[:8].upper(),
        "title": payload.get("title", ""),
        "description": payload.get("description", ""),
        "category": payload.get("category", "other"),
        "priority": payload.get("priority", "medium"),
        "severity": payload.get("severity", "medium"),
        "urgency": payload.get("urgency", "medium"),
        "session_id": payload.get("session_id", "test"),
        "status": "open",
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }


def _patch_client() -> None:
    ItOpsClient.create_ticket = lambda self, payload, fallback=True: TicketResult(  # type: ignore[assignment]
        ticket=_fake_ticket(payload), is_fallback=False
    )
    ItOpsClient.update_status = lambda self, ticket_id, new_status: {  # type: ignore[assignment]
        "ticket_id": ticket_id,
        "status": new_status,
    }
    ItOpsClient.update_priority = lambda self, ticket_id, new_priority: {  # type: ignore[assignment]
        "ticket_id": ticket_id,
        "priority": new_priority,
    }
    ItOpsClient.list_tickets = lambda self, **kw: []  # type: ignore[assignment]
    ItOpsClient.is_available = lambda self, timeout=2.0: True  # type: ignore[assignment]


_patch_client()
from backend.agents.orchestrator import process_message  # noqa: E402


def _load_scenarios() -> list[dict]:
    return json.loads(SCENARIOS_PATH.read_text()).get("scenarios", [])


def _evaluate(scenario: dict, state: dict) -> dict[str, Any]:
    actual_category = state.get("category")
    expected_category = scenario.get("expected_category")
    ticket = state.get("ticket") or {}
    has_ticket = bool(ticket.get("ticket_id"))
    escalated = bool(state.get("escalated"))
    response_text = (state.get("response") or "").lower()
    keywords = scenario.get("expected_kb_keywords") or []
    kw_hits = [kw for kw in keywords if kw.lower() in response_text]

    checks = {
        "category_match": actual_category == expected_category if expected_category else True,
        "is_support_request_match": (
            state.get("is_support_request") == scenario["expect_is_support_request"]
            if "expect_is_support_request" in scenario
            else True
        ),
        "ticket_match": has_ticket == bool(scenario.get("expect_ticket")),
        "escalation_match": escalated == bool(scenario.get("expect_escalation")),
        "kb_keyword_hit": (len(kw_hits) > 0) if keywords else True,
    }
    return {
        "id": scenario["id"],
        "user_message": scenario["user_message"],
        "expected_category": expected_category,
        "actual_category": actual_category,
        "is_support_request": state.get("is_support_request"),
        "match_strength": state.get("match_strength"),
        "severity": state.get("severity"),
        "urgency": state.get("urgency"),
        "expect_ticket": bool(scenario.get("expect_ticket")),
        "actual_ticket_id": ticket.get("ticket_id"),
        "ticket_decision_reason": state.get("ticket_decision_reason"),
        "expect_escalation": bool(scenario.get("expect_escalation")),
        "actual_escalation": escalated,
        "response_time_ms": float(state.get("response_time_ms") or 0.0),
        "kb_keywords_expected": keywords,
        "kb_keywords_hit": kw_hits,
        "checks": checks,
        "passed": all(checks.values()),
        "response_excerpt": (state.get("response") or "")[:240],
    }


def main() -> int:
    print("Seeding knowledge base if needed…")
    seed_knowledge_base()

    scenarios = _load_scenarios()
    print(f"Running {len(scenarios)} scenarios…\n")

    results: list[dict] = []
    for sc in scenarios:
        print(f"  - {sc['id']}: ", end="", flush=True)
        try:
            state = process_message(
                user_message=sc["user_message"],
                session_id=f"test-{sc['id']}",
                history=[],
            )
            evaluated = _evaluate(sc, state)
        except Exception as exc:  # noqa: BLE001
            evaluated = {
                "id": sc["id"],
                "user_message": sc["user_message"],
                "passed": False,
                "error": str(exc),
            }
        results.append(evaluated)
        print("PASS" if evaluated.get("passed") else "FAIL")

    total = len(results)
    passed = sum(1 for r in results if r.get("passed"))
    summary = {
        "timestamp": datetime.now().isoformat(),
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": (passed / total) if total else 0.0,
        "results": results,
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / f"accuracy-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    out_path.write_text(json.dumps(summary, indent=2))

    print(f"\n{passed}/{total} scenarios passed ({summary['pass_rate'] * 100:.1f}%)")
    print(f"Wrote report to {out_path}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
