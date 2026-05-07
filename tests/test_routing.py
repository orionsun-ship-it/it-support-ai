"""Deterministic routing harness — runs the real orchestrator with mocked
agents and a mocked ops client. No LLM calls. No API spend. Reproducible.

Run with:

    python tests/test_routing.py            # one-shot, writes a JSON report
    make test                                # same thing, via the Makefile

Each scenario fixes the IntakeAgent's classification (category, intent,
severity, urgency, confidence, is_support_request) and the KnowledgeAgent's
output (match_strength, response text, sources). The orchestrator's real
routing functions and the real WorkflowAgent / EscalationAgent then run
unchanged. Every routing branch in
``backend/agents/orchestrator.py`` is covered by at least one scenario.

Each scenario asserts:

- ``route_trace`` (every node visited, in order)
- ``final_route``
- ``should_create_ticket``
- ``escalated``
- ``automation_status``
- ``automation_simulated`` (where applicable)
- ``ticket_decision_reason`` substring (where applicable)

A pass/fail JSON report is written to ``tests/results/`` and a human-readable
Markdown summary is written to ``tests/results/latest-summary.md``.
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Construction of langchain_anthropic.ChatAnthropic requires a non-empty key
# (Pydantic validation). The mocks below replace .run() on the agents, so the
# LLM is never invoked — but we still need a stub for construction. We force
# the value (don't use setdefault) because some shells export an empty
# ANTHROPIC_API_KEY which would otherwise pass through.
if not os.environ.get("ANTHROPIC_API_KEY"):
    os.environ["ANTHROPIC_API_KEY"] = "sk-ant-deterministic-stub"

from backend.services.it_ops_client import ItOpsClient, TicketResult  # noqa: E402

RESULTS_DIR = Path(__file__).parent / "results"


# ---------------------------------------------------------------------------
# Mock the ops client BEFORE importing the orchestrator (singletons capture
# the methods at import time).
# ---------------------------------------------------------------------------


def _fake_ticket(payload: dict) -> dict:
    return {
        "ticket_id": "DET-" + uuid.uuid4().hex[:8].upper(),
        "title": payload.get("title", ""),
        "description": payload.get("description", ""),
        "category": payload.get("category", "other"),
        "priority": payload.get("priority", "medium"),
        "severity": payload.get("severity", "medium"),
        "urgency": payload.get("urgency", "medium"),
        "session_id": payload.get("session_id", "test"),
        "status": "open",
        "created_at": datetime.now(UTC).isoformat(),
        "updated_at": datetime.now(UTC).isoformat(),
    }


def _patch_ops_client() -> None:
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
    ItOpsClient.list_tickets_for_session = lambda self, session_id: []  # type: ignore[assignment]
    ItOpsClient.is_available = lambda self, timeout=2.0: True  # type: ignore[assignment]
    ItOpsClient.analyze_logs = lambda self, service="network_events": {  # type: ignore[assignment]
        "summary": "VPN authentication errors detected; investigate ASAP."
    }


_patch_ops_client()

from backend.agents import orchestrator  # noqa: E402  isort:skip


# ---------------------------------------------------------------------------
# Mock the LLM-driven agents. The orchestrator's routing functions and the
# WorkflowAgent / EscalationAgent are exercised for real.
# ---------------------------------------------------------------------------


_AUTOMATABLE_INTENTS = {
    "password_reset",
    "account_unlock",
    "software_license_check",
    "software_install",
    "access_request",
    "vpn_log_check",
    "status_check",
}


def _make_intake_runner(fixture: dict):
    def _run(state: dict) -> dict:
        state.setdefault("route_trace", []).append("intake")
        state["category"] = fixture["category"]
        state["intent"] = fixture["intent"]
        state["confidence"] = float(fixture.get("confidence", 0.9))
        state["severity"] = fixture.get("severity", "medium")
        state["urgency"] = fixture.get("urgency", "medium")
        state["is_support_request"] = bool(fixture.get("is_support_request", True))
        state["requires_automation"] = state["intent"] in _AUTOMATABLE_INTENTS
        return state

    return _run


def _make_knowledge_runner(fixture: dict):
    sources_fixture = fixture.get("sources") or [
        {
            "doc_id": "kb-stub",
            "title": "Stub source",
            "category": fixture.get("category", "other"),
            "score": 0.9,
            "distance": 0.2,
            "snippet": "Mocked KB chunk for deterministic testing.",
            "chunk_id": "kb-stub::chunk-0",
        }
    ]

    def _run(state: dict) -> dict:
        state.setdefault("route_trace", []).append("knowledge")
        state["match_strength"] = fixture.get("match_strength", "strong")
        state["sources"] = sources_fixture
        state["context"] = "(mocked retrieval context)"
        state["response"] = fixture.get(
            "response",
            "Here are the standard troubleshooting steps for this category.",
        )
        return state

    return _run


# ---------------------------------------------------------------------------
# Scenarios — every routing branch is covered.
# ---------------------------------------------------------------------------

SCENARIOS: list[dict[str, Any]] = [
    {
        "id": "kb_browser_cache",
        "message": "How do I clear my browser cache?",
        "intake": {
            "category": "software",
            "intent": "knowledge_question",
            "severity": "low",
            "urgency": "low",
            "is_support_request": True,
        },
        "knowledge": {"match_strength": "strong"},
        "expected": {
            "final_route": "final_response",
            "route_trace": ["intake", "knowledge", "final_response"],
            "should_create_ticket": False,
            "escalated": False,
            # workflow node never ran, so automation_status stays unset.
            "automation_status": None,
            "automation_simulated": False,
        },
    },
    {
        "id": "password_reset_automation",
        "message": "I forgot my password and need a reset link.",
        "intake": {
            "category": "password",
            "intent": "password_reset",
            "severity": "low",
            "urgency": "low",
            "is_support_request": True,
        },
        "knowledge": {"match_strength": "strong"},
        "expected": {
            "final_route": "final_response",
            "route_trace": ["intake", "knowledge", "workflow", "final_response"],
            "should_create_ticket": False,
            "escalated": False,
            "automation_status": "success",
            "automation_simulated": True,
        },
    },
    {
        "id": "account_unlock_automation",
        "message": "My account is locked after too many failed logins.",
        "intake": {
            "category": "access",
            "intent": "account_unlock",
            "severity": "medium",
            "urgency": "medium",
            "is_support_request": True,
        },
        "knowledge": {"match_strength": "strong"},
        "expected": {
            "final_route": "final_response",
            "route_trace": ["intake", "knowledge", "workflow", "final_response"],
            "should_create_ticket": False,
            "escalated": False,
            "automation_status": "success",
            "automation_simulated": True,
        },
    },
    {
        "id": "urgent_vpn_outage_escalates",
        "message": "VPN is down for the whole team and nobody can work.",
        "intake": {
            "category": "vpn",
            "intent": "vpn_log_check",
            "severity": "critical",
            "urgency": "high",
            "is_support_request": True,
        },
        "knowledge": {"match_strength": "strong"},
        "expected": {
            "final_route": "final_response",
            "route_trace": [
                "intake",
                "knowledge",
                "workflow",
                "escalation",
                "final_response",
            ],
            "should_create_ticket": True,
            "escalated": True,
            "automation_status": "success",
            "automation_simulated": False,
            "ticket_reason_contains": "urgent",
        },
    },
    {
        "id": "explicit_ticket_request",
        "message": "Please create a ticket for my broken laptop screen.",
        "intake": {
            "category": "hardware",
            "intent": "ticket_request",
            "severity": "medium",
            "urgency": "medium",
            "is_support_request": True,
        },
        "knowledge": {"match_strength": "strong"},
        "expected": {
            "final_route": "final_response",
            "route_trace": ["intake", "knowledge", "workflow", "final_response"],
            "should_create_ticket": True,
            "escalated": False,
            "automation_status": "not_needed",
            "automation_simulated": False,
            "ticket_reason_contains": "explicit",
        },
    },
    {
        "id": "non_support_request",
        "message": "Can you write me a poem about coffee?",
        "intake": {
            "category": "other",
            "intent": "non_support",
            "severity": "low",
            "urgency": "low",
            "is_support_request": False,
        },
        "knowledge": {"match_strength": "none"},
        "expected": {
            "final_route": "final_response",
            "route_trace": ["intake", "final_response"],
            "should_create_ticket": False,
            "escalated": False,
            "automation_status": None,
            "automation_simulated": False,
        },
    },
    {
        "id": "weak_kb_user_gets_stuck",
        "message": "I tried that but it still didn't work.",
        "history": [
            {"role": "user", "content": "Outlook will not open this morning."},
            {
                "role": "assistant",
                "content": "Try Safe Mode and rebuild the profile.",
            },
        ],
        "intake": {
            "category": "software",
            "intent": "knowledge_question",
            "severity": "medium",
            "urgency": "medium",
            "is_support_request": True,
        },
        "knowledge": {"match_strength": "weak"},
        "expected": {
            "final_route": "final_response",
            "route_trace": [
                "intake",
                "knowledge",
                "escalation",
                "final_response",
            ],
            "should_create_ticket": True,
            "escalated": True,
            "automation_status": None,
            "automation_simulated": False,
        },
    },
    {
        "id": "explicit_human_handoff",
        "message": "I need to speak to a real person about this.",
        "history": [
            {"role": "user", "content": "VPN keeps dropping me."},
            {
                "role": "assistant",
                "content": "Try reinstalling Cisco Secure Client.",
            },
        ],
        "intake": {
            "category": "vpn",
            "intent": "knowledge_question",
            "severity": "medium",
            "urgency": "medium",
            "is_support_request": True,
        },
        "knowledge": {"match_strength": "strong"},
        "expected": {
            "final_route": "final_response",
            "route_trace": [
                "intake",
                "knowledge",
                "escalation",
                "final_response",
            ],
            "should_create_ticket": True,
            "escalated": True,
            "automation_status": None,
            "automation_simulated": False,
        },
    },
    {
        "id": "status_check_real_subsystem",
        "message": "What's the status of my open tickets?",
        "intake": {
            "category": "other",
            "intent": "status_check",
            "severity": "low",
            "urgency": "low",
            "is_support_request": True,
        },
        "knowledge": {"match_strength": "weak"},
        "expected": {
            "final_route": "final_response",
            "route_trace": ["intake", "knowledge", "workflow", "final_response"],
            "should_create_ticket": True,
            "escalated": False,
            "automation_status": "success",
            "automation_simulated": False,
            "ticket_reason_contains": "knowledge base",
        },
    },
    {
        "id": "software_install_automation",
        "message": "I need Slack installed on my laptop.",
        "intake": {
            "category": "software",
            "intent": "software_install",
            "severity": "low",
            "urgency": "low",
            "is_support_request": True,
        },
        "knowledge": {"match_strength": "strong"},
        "expected": {
            "final_route": "final_response",
            "route_trace": ["intake", "knowledge", "workflow", "final_response"],
            "should_create_ticket": False,
            "escalated": False,
            "automation_status": "success",
            "automation_simulated": True,
        },
    },
]


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def _evaluate(scenario: dict, state: dict) -> dict:
    expected = scenario["expected"]
    checks: dict[str, bool] = {}

    actual_trace = list(state.get("route_trace") or [])
    expected_trace = expected.get("route_trace")
    if expected_trace is not None:
        checks["route_trace"] = actual_trace == expected_trace

    if "final_route" in expected:
        checks["final_route"] = state.get("final_route") == expected["final_route"]
    if "should_create_ticket" in expected:
        checks["should_create_ticket"] = bool(
            state.get("should_create_ticket")
        ) == bool(expected["should_create_ticket"])
    if "escalated" in expected:
        checks["escalated"] = bool(state.get("escalated")) == bool(
            expected["escalated"]
        )
    if "automation_status" in expected:
        checks["automation_status"] = (
            state.get("automation_status") == expected["automation_status"]
        )
    if "automation_simulated" in expected:
        checks["automation_simulated"] = bool(
            state.get("automation_simulated")
        ) == bool(expected["automation_simulated"])
    if "ticket_reason_contains" in expected:
        reason = (state.get("ticket_decision_reason") or "").lower()
        checks["ticket_decision_reason"] = (
            expected["ticket_reason_contains"].lower() in reason
        )

    return {
        "id": scenario["id"],
        "user_message": scenario["message"],
        "expected": expected,
        "actual": {
            "category": state.get("category"),
            "intent": state.get("intent"),
            "severity": state.get("severity"),
            "urgency": state.get("urgency"),
            "match_strength": state.get("match_strength"),
            "should_create_ticket": bool(state.get("should_create_ticket")),
            "escalated": bool(state.get("escalated")),
            "automation_status": state.get("automation_status"),
            "automation_simulated": bool(state.get("automation_simulated")),
            "route_trace": actual_trace,
            "final_route": state.get("final_route"),
            "ticket_decision_reason": state.get("ticket_decision_reason"),
            "ticket_id": (state.get("ticket") or {}).get("ticket_id"),
            "response_time_ms": float(state.get("response_time_ms") or 0.0),
        },
        "checks": checks,
        "passed": all(checks.values()) if checks else True,
    }


def _run_scenario(scenario: dict) -> dict:
    """Run one scenario with mocked intake / knowledge.

    LangGraph captures the node action functions at compile time (it stores
    bound method references inside ``RunnableLambda``), so it isn't enough to
    replace ``orchestrator._intake.run`` after import — the graph still holds
    the original reference. We patch ``.run`` on the singletons *and* rebuild
    the compiled graph so the new functions are wired in.
    """
    intake_runner = _make_intake_runner(scenario["intake"])
    knowledge_runner = _make_knowledge_runner(scenario["knowledge"])

    original_intake_run = orchestrator._intake.run
    original_knowledge_run = orchestrator._knowledge.run
    original_graph = orchestrator.graph

    orchestrator._intake.run = intake_runner  # type: ignore[assignment]
    orchestrator._knowledge.run = knowledge_runner  # type: ignore[assignment]
    orchestrator.graph = orchestrator._build_graph()

    try:
        state = orchestrator.process_message(
            user_message=scenario["message"],
            session_id=f"det-{scenario['id']}",
            history=list(scenario.get("history", []) or []),
        )
    finally:
        orchestrator._intake.run = original_intake_run  # type: ignore[assignment]
        orchestrator._knowledge.run = original_knowledge_run  # type: ignore[assignment]
        orchestrator.graph = original_graph

    return _evaluate(scenario, state)


def _aggregate(results: list[dict]) -> dict:
    """Per-axis pass rate. We divide by the number of scenarios that actually
    declared that axis (not by the total scenario count) so optional axes
    aren't penalised for absence."""
    counters: dict[str, list[int]] = {}
    for r in results:
        for key, ok in r.get("checks", {}).items():
            counters.setdefault(key, []).append(int(bool(ok)))
    out: dict[str, float] = {}
    for key, values in counters.items():
        n = len(values) or 1
        out[f"{key}_ok"] = round(sum(values) / n, 4)
    return out


def _summary_markdown(summary: dict) -> str:
    lines: list[str] = []
    lines.append("# Deterministic routing — latest summary")
    lines.append("")
    lines.append(f"- Generated: `{summary['timestamp']}`")
    lines.append(f"- Total scenarios: **{summary['total']}**")
    lines.append(
        f"- Passed: **{summary['passed']}** · Failed: **{summary['failed']}** · "
        f"Pass rate: **{summary['pass_rate'] * 100:.1f}%**"
    )
    lines.append("")
    lines.append("## Per-axis pass rate")
    lines.append("")
    lines.append("| Check | Pass rate |")
    lines.append("| --- | --- |")
    for k, v in summary["aggregate"].items():
        lines.append(f"| `{k}` | {v * 100:.1f}% |")
    lines.append("")
    lines.append("## Per-scenario")
    lines.append("")
    lines.append(
        "| ID | Result | Final route | Trace | Ticket | Escalated | Automation |"
    )
    lines.append("| --- | --- | --- | --- | --- | --- | --- |")
    for r in summary["results"]:
        a = r.get("actual", {})
        trace = " → ".join(a.get("route_trace") or [])
        sim = " (sim)" if a.get("automation_simulated") else ""
        lines.append(
            f"| `{r['id']}` | "
            f"{'✅ pass' if r.get('passed') else '❌ fail'} | "
            f"`{a.get('final_route')}` | "
            f"`{trace}` | "
            f"{'yes' if a.get('should_create_ticket') else 'no'} | "
            f"{'yes' if a.get('escalated') else 'no'} | "
            f"`{a.get('automation_status')}{sim}` |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    print(f"Running {len(SCENARIOS)} deterministic routing scenarios…\n")
    results: list[dict] = []
    for sc in SCENARIOS:
        evaluated = _run_scenario(sc)
        results.append(evaluated)
        print(f"  - {sc['id']}: {'PASS' if evaluated['passed'] else 'FAIL'}")
        if not evaluated["passed"]:
            for check, ok in evaluated["checks"].items():
                if not ok:
                    print(
                        f"      · {check}: expected={evaluated['expected'].get(check)} "
                        f"actual={evaluated['actual'].get(check)}"
                    )

    total = len(results)
    passed = sum(1 for r in results if r.get("passed"))
    summary = {
        "timestamp": datetime.now().isoformat(),
        "harness": "deterministic-routing",
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": (passed / total) if total else 0.0,
        "aggregate": _aggregate(results),
        "results": results,
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / f"routing-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    out_path.write_text(json.dumps(summary, indent=2))
    (RESULTS_DIR / "latest-summary.md").write_text(_summary_markdown(summary))
    (RESULTS_DIR / "latest.json").write_text(json.dumps(summary, indent=2))

    print()
    print(f"{passed}/{total} scenarios passed ({summary['pass_rate'] * 100:.1f}%)")
    for k, v in summary["aggregate"].items():
        print(f"  {k:30s} {v * 100:6.1f}%")
    print(f"\nReport: {out_path}")
    print(f"Markdown summary: {RESULTS_DIR / 'latest-summary.md'}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
