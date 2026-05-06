"""End-to-end accuracy harness for the routed agent pipeline.

Mocks the IT Ops API client so the harness does not need the ops API to be
running. Calls the real Claude model via langchain-anthropic. Writes a
timestamped report to tests/results/.

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
# Patch the ops client BEFORE importing the orchestrator so the singletons use
# the mock.
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
    ItOpsClient.analyze_logs = lambda self, service="network_events": {  # type: ignore[assignment]
        "summary": "VPN authentication errors detected; investigate ASAP."
    }


_patch_client()
from backend.agents.orchestrator import process_message  # noqa: E402


def _load_scenarios() -> list[dict]:
    return json.loads(SCENARIOS_PATH.read_text()).get("scenarios", [])


def _evaluate(scenario: dict, state: dict) -> dict[str, Any]:
    actual_category = state.get("category")
    expected_category = scenario.get("expected_category")
    has_ticket = bool(state.get("should_create_ticket"))
    escalated = bool(state.get("escalated"))
    final_route = state.get("final_route")
    automation_status = state.get("automation_status")

    checks = {
        "category_match": (
            actual_category == expected_category if expected_category else True
        ),
        "ticket_match": has_ticket == bool(scenario.get("expected_ticket")),
        "escalation_match": escalated == bool(scenario.get("expected_escalation")),
        "final_route_match": (
            final_route == scenario["expected_final_route"]
            if "expected_final_route" in scenario
            else True
        ),
        "automation_status_match": (
            automation_status == scenario["expected_automation_status"]
            if "expected_automation_status" in scenario
            else True
        ),
    }

    return {
        "id": scenario["id"],
        "user_message": scenario["message"],
        "expected_category": expected_category,
        "actual_category": actual_category,
        "is_support_request": state.get("is_support_request"),
        "match_strength": state.get("match_strength"),
        "severity": state.get("severity"),
        "urgency": state.get("urgency"),
        "intent": state.get("intent"),
        "expected_ticket": bool(scenario.get("expected_ticket")),
        "actual_ticket": has_ticket,
        "actual_ticket_id": (state.get("ticket") or {}).get("ticket_id"),
        "expected_escalation": bool(scenario.get("expected_escalation")),
        "actual_escalation": escalated,
        "expected_final_route": scenario.get("expected_final_route"),
        "actual_final_route": final_route,
        "route_trace": state.get("route_trace"),
        "automation_status": automation_status,
        "expected_automation_status": scenario.get("expected_automation_status"),
        "ticket_decision_reason": state.get("ticket_decision_reason"),
        "response_time_ms": float(state.get("response_time_ms") or 0.0),
        "checks": checks,
        "passed": all(checks.values()),
        "response_excerpt": (state.get("response") or "")[:240],
    }


def _aggregate(results: list[dict]) -> dict:
    n = len(results) or 1
    counts = {"category": 0, "ticket": 0, "escalation": 0, "final_route": 0, "auto": 0}
    for r in results:
        c = r.get("checks", {})
        counts["category"] += int(c.get("category_match", False))
        counts["ticket"] += int(c.get("ticket_match", False))
        counts["escalation"] += int(c.get("escalation_match", False))
        counts["final_route"] += int(c.get("final_route_match", False))
        counts["auto"] += int(c.get("automation_status_match", False))
    return {
        "category_accuracy": counts["category"] / n,
        "ticket_accuracy": counts["ticket"] / n,
        "escalation_accuracy": counts["escalation"] / n,
        "route_accuracy": counts["final_route"] / n,
        "automation_accuracy": counts["auto"] / n,
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
                user_message=sc["message"],
                session_id=f"test-{sc['id']}",
                history=[],
            )
            evaluated = _evaluate(sc, state)
        except Exception as exc:  # noqa: BLE001
            evaluated = {
                "id": sc["id"],
                "user_message": sc["message"],
                "passed": False,
                "error": str(exc),
            }
        results.append(evaluated)
        print("PASS" if evaluated.get("passed") else "FAIL")

    total = len(results)
    passed = sum(1 for r in results if r.get("passed"))
    aggregate = _aggregate(results)
    summary = {
        "timestamp": datetime.now().isoformat(),
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": (passed / total) if total else 0.0,
        "aggregate": aggregate,
        "results": results,
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / f"accuracy-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    out_path.write_text(json.dumps(summary, indent=2))

    print(f"\n{passed}/{total} scenarios passed ({summary['pass_rate'] * 100:.1f}%)")
    for k, v in aggregate.items():
        print(f"  {k:22s} {v * 100:.1f}%")
    print(f"Wrote report to {out_path}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
