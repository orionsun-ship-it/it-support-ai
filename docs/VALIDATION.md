# Validation & testing

This doc covers grading checkpoint **8 (Validation & Testing)**:
methodology, scenarios, results, and how to reproduce.

We run **three** harnesses, each with a different purpose:

| Harness                   | Run command     | Purpose                                               | Cost      | Determinism   |
| ------------------------- | --------------- | ----------------------------------------------------- | --------- | ------------- |
| Deterministic routing     | `make test`     | Asserts every conditional edge in the orchestrator    | Free      | 100 %         |
| MCP cross-transport proof | `make test-mcp` | Asserts MCP↔HTTP land in the same DB                  | Free      | 100 %         |
| Live-LLM accuracy         | `make test-llm` | Measures Claude's classification quality on real text | API spend | LLM-dependent |

CI / pre-merge: run `make test` and `make test-mcp`. Both are
deterministic, both are fast (<2 s combined), neither needs an API key.

Manual / pre-release: also run `make test-llm` for a sanity check on
classification quality.

All three write timestamped JSON reports to `tests/results/`. The
deterministic harness also writes a Markdown summary at
`tests/results/latest-summary.md`.

---

## 1. Deterministic routing harness — `tests/test_routing.py`

### 1.1 What it does

`tests/test_routing.py` builds 10 scenarios that cover every routing
branch in the LangGraph orchestrator. For each scenario it:

1. **Mocks the LLM-driven agents** (`IntakeAgent.run` and
   `KnowledgeAgent.run`) so their outputs are deterministic. The
   real `WorkflowAgent`, `EscalationAgent`, and the final-response node
   all run unchanged.
2. **Mocks the IT Ops API client** (`ItOpsClient`) so no service needs
   to be running. Tickets get a `DET-XXXXXXXX` id.
3. **Rebuilds the LangGraph compiled graph** with the patched agents
   wired in (LangGraph captures function references at compile time, so
   patching `.run` after import isn't enough — see the docstring inside
   `_run_scenario` for the gory details).
4. **Invokes `process_message`** for the scenario's user message.
5. **Asserts** the actual `route_trace`, `final_route`,
   `should_create_ticket`, `escalated`, `automation_status`,
   `automation_simulated`, and (where given) a substring of
   `ticket_decision_reason`.

### 1.2 Coverage — every branch is exercised

| Routing branch                                                      | Scenario                                                                                |
| ------------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| intake → final_response (non-support)                               | `non_support_request`                                                                   |
| intake → knowledge → final_response (KB strong, knowledge_question) | `kb_browser_cache`                                                                      |
| knowledge → workflow (requires_automation, simulated)               | `password_reset_automation`, `account_unlock_automation`, `software_install_automation` |
| knowledge → workflow (requires_automation, real subsystem)          | `urgent_vpn_outage_escalates`, `status_check_real_subsystem`                            |
| knowledge → workflow (intent==ticket_request)                       | `explicit_ticket_request`                                                               |
| knowledge → escalation (user is stuck)                              | `weak_kb_user_gets_stuck`                                                               |
| knowledge → escalation (explicit human handoff)                     | `explicit_human_handoff`                                                                |
| workflow → escalation (severity=critical / urgency=high)            | `urgent_vpn_outage_escalates`                                                           |
| workflow → final_response (success, low severity)                   | `password_reset_automation`, `software_install_automation`                              |
| workflow → final_response (ticket created, not urgent)              | `explicit_ticket_request`, `status_check_real_subsystem`                                |

### 1.3 Latest results (checked in)

A live copy of the most recent run is at
[`../tests/results/latest-summary.md`](../tests/results/latest-summary.md)
and the JSON at
[`../tests/results/latest.json`](../tests/results/latest.json).

```
10/10 scenarios passed (100.0%)
  route_trace_ok                  100.0%
  final_route_ok                  100.0%
  should_create_ticket_ok         100.0%
  escalated_ok                    100.0%
  automation_status_ok            100.0%
  automation_simulated_ok         100.0%
  ticket_decision_reason_ok       100.0%
```

Every axis at 100 %. If this drops below 100 %, the routing has a
regression — the harness is the canary.

### 1.4 Why we don't pretend live LLM accuracy = system correctness

A test that calls Claude on every run would conflate two failure modes:

- **System failure**: routing logic regressed, ticket conditions changed,
  schema drifted.
- **LLM failure**: a prompt rephrase landed differently this week,
  classification probabilities shifted, network blip mid-call.

The deterministic harness pins LLM output and tests only the
"system failure" mode. The live-LLM harness pins the system mode (same
routing) and measures the LLM-failure mode. Splitting them makes
regressions diagnosable.

---

## 2. MCP cross-transport proof — `tests/test_mcp_proof.py`

### 2.1 What it does

In <30 ms, end-to-end:

1. Sets `IT_OPS_DB_PATH` to a throwaway file in `tests/results/` so we
   don't pollute the dev DB.
2. Creates a ticket via `mcp_server.store.create_ticket(...)` (the
   function bound to the FastMCP `@tool create_ticket`).
3. Boots the FastAPI ops API in-process via `fastapi.testclient.TestClient`
   and `GET`s the ticket via the HTTP transport. Asserts same id.
4. Updates status to `escalated` via the MCP store; re-fetches via HTTP;
   asserts the new status is visible.
5. Lists via MCP and via HTTP — both see the same row.

### 2.2 Latest results (checked in)

`tests/results/mcp-proof-latest.json` — current run: **5/5 steps pass**.
See [`MCP_PROOF.md`](MCP_PROOF.md) for the full interpretation.

### 2.3 Why this is a real proof, not a slide

The same `engine` (in `services/it_ops_api/db.py`) and the same
`Ticket` SQLModel are imported by both `mcp_server/store.py` and
`services/it_ops_api/main.py`. The test goes both directions on each
mutation, so the assertion really is "writes from one transport are
observable from the other transport in the same logical store."

---

## 3. Live-LLM accuracy harness — `tests/test_accuracy.py`

### 3.1 What it does

Runs the 8 scenarios in `tests/test_scenarios.json` through the full
orchestrator — Claude Haiku is called for the Intake and Knowledge
agents, the IT Ops client is mocked. Each scenario asserts:

- `expected_category`
- `expected_ticket` / `expected_escalation`
- `expected_final_route` (where given)
- `expected_automation_status` (where given)

This is the harness that measures how robust intake classification
actually is on natural-sounding user messages. It costs ~8 Claude API
calls per run (2 LLM calls per scenario × 8 scenarios — Intake + Knowledge),
which is on the order of a few cents on Haiku.

### 3.2 When to run it

- Pre-release sanity check.
- After tweaking the Intake prompt / schema.
- After changing the KB content materially.

The live-LLM harness target is **≥ 85 % per-axis accuracy**. Variance
between runs is expected; one outlier doesn't mean the prompt is broken.
Three consecutive runs below target = real regression.

### 3.3 Reading the report

Each run writes `tests/results/accuracy-YYYYMMDD-HHMMSS.json`. The
top-level `aggregate` block has the per-axis pass rates. The
`results[]` array has per-scenario detail, including:

- `actual_category` vs `expected_category`
- `actual_ticket` / `actual_escalation`
- `route_trace` (inspect this when ticket / escalation is wrong)
- `match_strength` (inspect this when the route looks fine but the
  answer is bad)
- `response_time_ms` (latency monitoring)

---

## 4. How to add a new scenario

For deterministic routing (`tests/test_routing.py`):

```python
{
    "id": "my_new_branch",
    "message": "User-visible message text",
    "history": [],   # optional prior turns
    "intake": {
        "category": "...",
        "intent": "...",
        "severity": "low|medium|high|critical",
        "urgency": "low|medium|high",
        "is_support_request": True,
    },
    "knowledge": {"match_strength": "strong|weak|none"},
    "expected": {
        "final_route": "final_response",
        "route_trace": ["intake", "knowledge", ...],
        "should_create_ticket": False,
        "escalated": False,
        "automation_status": "success" | "not_needed" | None,
        "automation_simulated": False,
        # optional:
        "ticket_reason_contains": "explicit",
    },
},
```

For live-LLM (`tests/test_scenarios.json`): same shape, but the intake
and knowledge sections are replaced by Claude. Add `expected_*` fields
for whatever you want to assert.

For MCP (`tests/test_mcp_proof.py`): the harness is a single happy-path
walkthrough; if you add a new tool to the MCP server, add a step that
asserts the new tool's effect is visible on the HTTP side too.

---

## 5. Performance budget

The deterministic harness runs **all 10 scenarios in <50 ms** on a
laptop, including LangGraph compilation and SQLite warm-up. The MCP
proof runs in **<30 ms**. These are CI-friendly.

The live-LLM harness depends on Claude latency. With Haiku, expect
**~3–5 s per scenario**, ~30 s total for 8 scenarios. With Opus, plan for
~30 s per scenario.

The `/chat` endpoint's response time is exposed via `response_time_ms`
on every API response and aggregated under `/metrics`. Target: **median
< 3 s** with Claude Haiku on Wi-Fi.

---

## 6. What's not validated (yet) — and why that's fine

- **Production-grade automation correctness.** Most automations are
  simulated stubs (see the README's table). Once those land as real
  adapters, each adapter gets its own test pyramid.
- **Concurrent ticket writes under load.** SQLite is single-writer; a
  pilot with concurrent users would move to Postgres and add a load
  test there. The unit-level correctness is independent of the storage
  engine.
- **LLM-prompt-injection resistance** (e.g. KB document instructing the
  model to bypass routing). The architecture limits blast radius
  (Workflow agent only acts on Intake's structured output, not on raw
  LLM text), but a dedicated red-team pass is phase-2 work.
- **Per-tenant isolation.** Single-tenant for the capstone; phase-2
  work.

These are explicitly called out in the README's "Status" section so
nobody mistakes their absence for a hidden problem.
