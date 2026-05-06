"""
End-to-end accuracy harness for the IT support agent pipeline.

Runs every scenario in test_scenarios.json through the orchestrator's
process_message function and writes a summary report to tests/results/.

Usage:
    python tests/test_accuracy.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.agents.orchestrator import process_message  # noqa: E402
from backend.rag.retriever import seed_knowledge_base  # noqa: E402

SCENARIOS_PATH = Path(__file__).parent / "test_scenarios.json"
RESULTS_DIR = Path(__file__).parent / "results"


def _load_scenarios() -> list[dict]:
    data = json.loads(SCENARIOS_PATH.read_text())
    return data.get("scenarios", [])


def _evaluate(scenario: dict, state: dict) -> dict:
    expected_category = scenario["expected_category"]
    actual_category = state.get("category")

    confidence = float(state.get("confidence") or 0.0)
    min_confidence = float(scenario.get("expected_min_confidence") or 0.0)

    ticket = state.get("ticket") or {}
    has_ticket = bool(ticket.get("ticket_id"))
    escalated = bool(state.get("escalated"))

    response_text = (state.get("response") or "").lower()
    keywords = scenario.get("expected_kb_keywords") or []
    kw_hits = [kw for kw in keywords if kw.lower() in response_text]

    checks = {
        "category_match": actual_category == expected_category,
        "confidence_meets_min": confidence >= min_confidence,
        "ticket_match": has_ticket == bool(scenario.get("expect_ticket")),
        "escalation_match": escalated == bool(scenario.get("expect_escalation")),
        "kb_keyword_hit": len(kw_hits) > 0 if keywords else True,
    }
    passed = all(checks.values())

    return {
        "id": scenario["id"],
        "user_message": scenario["user_message"],
        "expected_category": expected_category,
        "actual_category": actual_category,
        "confidence": confidence,
        "expected_min_confidence": min_confidence,
        "expect_ticket": bool(scenario.get("expect_ticket")),
        "actual_ticket_id": ticket.get("ticket_id"),
        "expect_escalation": bool(scenario.get("expect_escalation")),
        "actual_escalation": escalated,
        "response_time_ms": float(state.get("response_time_ms") or 0.0),
        "kb_keywords_expected": keywords,
        "kb_keywords_hit": kw_hits,
        "checks": checks,
        "passed": passed,
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
