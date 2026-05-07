# Workflow diagrams

This file shows **how a single chat turn flows through the system** for
each of the canonical user paths. Where [`architecture.md`](architecture.md)
shows the static topology, this file shows what actually moves and in
what order.

Every diagram below is annotated with the file/function the call lands
in, so you can grep the code path directly. Every diagram is also
covered by a deterministic scenario in
[`../tests/test_routing.py`](../tests/test_routing.py).

Contents:

1. [End-to-end pipeline (overview)](#1-end-to-end-pipeline-overview)
2. [Path A — Knowledge-only ("How do I clear my browser cache?")](#2-path-a--knowledge-only)
3. [Path B — Simulated automation ("I forgot my password")](#3-path-b--simulated-automation)
4. [Path C — Urgent escalation ("VPN is down for the whole team")](#4-path-c--urgent-escalation)
5. [Path D — Weak match + user is stuck ("I tried that but it still didn't work")](#5-path-d--weak-match--user-is-stuck)
6. [Path E — Non-support request ("Write me a poem about coffee")](#6-path-e--non-support-request)
7. [State lifecycle — what each node writes to AgentState](#7-state-lifecycle)
8. [Cross-transport: ticket via MCP vs ticket via HTTP](#8-cross-transport-ticket-via-mcp-vs-ticket-via-http)

---

## 1. End-to-end pipeline (overview)

The skeleton every path shares. Specific paths short-circuit at the
conditional edges shown in
[`architecture.md`](architecture.md#conditional-routing-detail).

```mermaid
sequenceDiagram
    autonumber
    actor U as User
    participant FE as Frontend (React)
    participant BE as Backend (FastAPI)
    participant G as LangGraph graph
    participant I as Intake Agent
    participant K as Knowledge Agent
    participant V as ChromaDB
    participant W as Workflow Agent
    participant OPS as IT Ops API
    participant DB as SQLite (tickets)
    participant E as Escalation Agent

    U->>FE: types message + clicks Send
    FE->>BE: POST /chat { message, session_id }
    BE->>G: process_message(...)
    G->>I: _intake.run(state)
    I-->>G: state += {category, intent, severity, urgency,<br/>confidence, is_support_request, requires_automation}

    alt is_support_request == False
        G-->>BE: short-circuit to final_response (Path E)
    else
        G->>K: _knowledge.run(state)
        K->>V: retrieve(query, n=3, category)
        V-->>K: chunks + distances
        K-->>G: state += {match_strength, sources, context, response}

        alt intent==ticket_request OR requires_automation
            G->>W: _workflow.run(state)
            W->>W: _run_automation(state)
            opt vpn_log_check
                W->>OPS: POST /api/v1/logs/analyze
                OPS-->>W: summary
            end
            opt status_check
                W->>OPS: GET /api/v1/tickets (filtered)
                OPS-->>W: tickets[]
            end
            W->>W: _should_create_ticket(state)
            opt ticket needed
                W->>OPS: POST /api/v1/tickets
                OPS->>DB: INSERT tickets/events/audit
                OPS-->>W: ticket
            end
            W-->>G: state += {automation_status, automation_simulated,<br/>automation_result, should_create_ticket, ticket}

            alt automation failed/manual OR severity=critical OR urgency=high
                G->>E: _escalation.run(state)
            end
        else user is stuck OR asks for human
            G->>E: _escalation.run(state)
        end

        opt escalation reached
            E->>OPS: POST /api/v1/tickets (if no ticket yet)
            E->>OPS: PATCH status=escalated, priority=critical
            OPS->>DB: INSERT events/audit
            OPS-->>E: updated ticket
            E-->>G: state += {escalated=true, ticket(priority=critical), response banner}
        end
    end

    G->>G: final_response_node(state)
    G-->>BE: final_state (with route_trace + final_route)
    BE-->>FE: AgentResponse JSON (content, sources,<br/>route_trace, ticket_decision_reason,<br/>automation_status, automation_simulated, …)
    FE-->>U: render bubble + sources + route trace strip<br/>+ chips (escalated, ticket, simulated)
```

**Code anchors:** `process_message` is in
[`backend/agents/orchestrator.py:215`](../backend/agents/orchestrator.py).
The graph is built in `_build_graph` at line 163.

---

## 2. Path A — Knowledge-only

**Scenario id:** `kb_browser_cache` —
_"How do I clear my browser cache?"_

```mermaid
sequenceDiagram
    autonumber
    participant BE as Backend
    participant G as LangGraph graph
    participant I as Intake Agent
    participant K as Knowledge Agent
    participant V as ChromaDB
    participant FR as final_response_node

    BE->>G: process_message("How do I clear my browser cache?")
    Note over G: route_trace = []
    G->>I: _intake.run
    Note right of I: category=software<br/>intent=knowledge_question<br/>severity=low, urgency=low<br/>requires_automation=False
    I-->>G: ✓
    Note over G: route_trace = [intake]
    Note over G: route_after_intake → "knowledge"

    G->>K: _knowledge.run
    K->>V: retrieve("…browser cache…")
    V-->>K: kb-014 (distance 0.21)
    Note right of K: match_strength=strong<br/>response = grounded answer with [kb-014]
    K-->>G: ✓
    Note over G: route_trace = [intake, knowledge]
    Note over G: route_after_knowledge → "final_response"<br/>(intent != ticket_request,<br/>requires_automation=False,<br/>user_is_stuck=False)

    G->>FR: final_response_node
    FR-->>G: response left as-is
    Note over G: route_trace = [intake, knowledge, final_response]
    G-->>BE: state {final_route=final_response,<br/>should_create_ticket=False,<br/>escalated=False, automation_status=None}
```

What the user sees: a numbered procedure with a citation block.
No ticket, no chip noise.

---

## 3. Path B — Simulated automation

**Scenario id:** `password_reset_automation` —
_"I forgot my password and need a reset link."_

```mermaid
sequenceDiagram
    autonumber
    participant BE as Backend
    participant G as LangGraph graph
    participant I as Intake Agent
    participant K as Knowledge Agent
    participant V as ChromaDB
    participant W as Workflow Agent
    participant FR as final_response_node

    BE->>G: process_message("I forgot my password…")
    G->>I: _intake.run
    Note right of I: category=password<br/>intent=password_reset<br/>severity=low, urgency=low<br/>requires_automation=True
    I-->>G: ✓

    G->>K: _knowledge.run
    K->>V: retrieve("…forgot my password…")
    V-->>K: kb-001 (distance 0.18)
    Note right of K: match_strength=strong
    K-->>G: ✓
    Note over G: route_after_knowledge → "workflow"<br/>(requires_automation=True)

    G->>W: _workflow.run
    W->>W: _run_automation(intent=password_reset)
    Note right of W: returns ("success",<br/>"[Simulated] Password reset eligibility…")<br/>automation_simulated=True
    W->>W: _should_create_ticket(state)
    Note right of W: severity=low, urgency=low<br/>match=strong → no ticket
    W-->>G: ✓
    Note over G: route_after_workflow → "final_response"<br/>(automation_status=success,<br/>severity != critical, urgency != high)

    G->>FR: final_response_node
    FR-->>G: response = grounded steps + automation_result
    G-->>BE: state {automation_status=success,<br/>automation_simulated=True,<br/>should_create_ticket=False, escalated=False}
```

What the user sees: the runbook steps, plus a `[Simulated]` line, plus
a "Simulated automation" chip under the bubble. No ticket — the
automation said it succeeded and the message wasn't urgent.

---

## 4. Path C — Urgent escalation

**Scenario id:** `urgent_vpn_outage_escalates` —
_"VPN is down for the whole team and nobody can work."_

```mermaid
sequenceDiagram
    autonumber
    participant BE as Backend
    participant G as LangGraph graph
    participant I as Intake Agent
    participant K as Knowledge Agent
    participant V as ChromaDB
    participant W as Workflow Agent
    participant OPS as IT Ops API
    participant DB as SQLite
    participant E as Escalation Agent
    participant FR as final_response_node

    BE->>G: process_message("VPN is down for the whole team…")
    G->>I: _intake.run
    Note right of I: category=vpn<br/>intent=vpn_log_check<br/>severity=critical, urgency=high<br/>requires_automation=True
    I-->>G: ✓

    G->>K: _knowledge.run
    K->>V: retrieve("…VPN is down…")
    V-->>K: kb-002 (distance 0.30)
    K-->>G: ✓ (match_strength=strong)
    Note over G: route_after_knowledge → "workflow"

    G->>W: _workflow.run
    W->>OPS: POST /api/v1/logs/analyze {service: "network_events"}
    OPS->>DB: read sample log file
    OPS-->>W: {summary: "VPN authentication errors…"}
    Note right of W: automation_status=success<br/>automation_simulated=False<br/>(vpn_log_check is real)

    W->>W: _should_create_ticket(state)
    Note right of W: ESCALATION_KEYWORDS regex matches<br/>"nobody can work"<br/>→ create_ticket=True<br/>reason="urgent/escalation language detected"

    W->>OPS: POST /api/v1/tickets {priority=critical, …}
    OPS->>DB: INSERT tickets, ticket_events, audit_logs
    OPS-->>W: TKT-XXXX
    W-->>G: ✓ ticket=TKT-XXXX
    Note over G: route_after_workflow → "escalation"<br/>(severity=critical OR urgency=high)

    G->>E: _escalation.run
    Note right of E: ticket already exists, skip _ensure_ticket
    E->>OPS: PATCH /api/v1/tickets/TKT-XXXX/status {new_status: "escalated"}
    OPS->>DB: UPDATE tickets, INSERT events
    OPS-->>E: updated ticket
    E->>OPS: PATCH /api/v1/tickets/TKT-XXXX/priority {new_priority: "critical"}
    OPS->>DB: UPDATE tickets, INSERT events
    OPS-->>E: updated ticket
    Note right of E: escalated=True<br/>response += "I could not resolve this confidently…<br/>Ticket TKT-XXXX has been opened with priority critical."
    E-->>G: ✓

    G->>FR: final_response_node
    FR-->>G: response left as-is
    G-->>BE: state {final_route=final_response,<br/>route_trace=[intake, knowledge, workflow, escalation, final_response],<br/>should_create_ticket=True, escalated=True,<br/>automation_status=success, automation_simulated=False}
```

What the user sees: the procedure + the log summary + an explicit
escalation banner with the ticket id + a red "Escalated" chip + an
amber ticket-id chip. Route trace shows all five nodes fired.

---

## 5. Path D — Weak match + user is stuck

**Scenario id:** `weak_kb_user_gets_stuck` —
follow-up turn _"I tried that but it still didn't work"_ after a prior
attempt at _"Outlook will not open this morning"_.

```mermaid
sequenceDiagram
    autonumber
    participant BE as Backend
    participant G as LangGraph graph
    participant I as Intake Agent
    participant K as Knowledge Agent
    participant V as ChromaDB
    participant E as Escalation Agent
    participant OPS as IT Ops API
    participant DB as SQLite
    participant FR as final_response_node

    Note over BE: history contains the previous user msg<br/>and the assistant's first attempt

    BE->>G: process_message("I tried that but it still didn't work")
    G->>I: _intake.run
    Note right of I: category=software<br/>intent=knowledge_question<br/>severity=medium, urgency=medium
    I-->>G: ✓

    G->>K: _knowledge.run
    K->>V: retrieve(...)
    V-->>K: top match distance > threshold
    K-->>G: ✓ (match_strength=weak)
    Note over G: route_after_knowledge:<br/>intent != ticket_request<br/>requires_automation=False<br/>_user_is_stuck = True (history has prior assistant<br/>turn AND msg matches "didn't work")<br/>→ "escalation"

    G->>E: _escalation.run
    Note right of E: no ticket yet — call _ensure_ticket
    E->>OPS: POST /api/v1/tickets {priority=critical, …}
    OPS->>DB: INSERT
    OPS-->>E: TKT-YYYY
    E->>OPS: PATCH status=escalated
    OPS->>DB: UPDATE
    E->>OPS: PATCH priority=critical
    OPS->>DB: UPDATE
    Note right of E: escalated=True<br/>response = banner referencing TKT-YYYY
    E-->>G: ✓

    G->>FR: final_response_node
    G-->>BE: state {route_trace=[intake, knowledge, escalation, final_response],<br/>escalated=True, should_create_ticket=True,<br/>automation_status=None}
```

What the user sees: an explicit escalation banner. No automation
attempted (it isn't an automatable intent). Route trace shows
`escalation` immediately after `knowledge` — the workflow node was
skipped because the user was stuck, not asking for an action.

---

## 6. Path E — Non-support request

**Scenario id:** `non_support_request` —
_"Can you write me a poem about coffee?"_

```mermaid
sequenceDiagram
    autonumber
    participant BE as Backend
    participant G as LangGraph graph
    participant I as Intake Agent
    participant FR as final_response_node

    BE->>G: process_message("Can you write me a poem about coffee?")
    G->>I: _intake.run
    Note right of I: category=other<br/>intent=non_support<br/>is_support_request=False
    I-->>G: ✓
    Note over G: route_after_intake → "final_response"<br/>(is_support_request=False short-circuits)

    G->>FR: final_response_node
    Note right of FR: state["response"] is None,<br/>so final_response_node injects<br/>the standard scope-clarifying message
    FR-->>G: ✓
    G-->>BE: state {route_trace=[intake, final_response],<br/>should_create_ticket=False,<br/>escalated=False, sources=[]}
```

What the user sees: a friendly "I can help with passwords, VPN,
software, hardware, network, access, email, or security…" scope
message. No KB lookup, no ticket, no escalation, no LLM-generated
poem (deliberate — out of scope for an IT assistant).

---

## 7. State lifecycle

`AgentState` (defined in
[`backend/agents/orchestrator.py:55`](../backend/agents/orchestrator.py))
is a single `TypedDict` that every node mutates. This diagram shows
which fields are _written_ by each node — read access is everywhere.

```mermaid
stateDiagram-v2
    direction LR
    [*] --> initial
    initial --> after_intake: Intake.run
    after_intake --> after_knowledge: Knowledge.run
    after_intake --> after_final: route_after_intake==final_response
    after_knowledge --> after_workflow: route_after_knowledge==workflow
    after_knowledge --> after_escalation: route_after_knowledge==escalation
    after_knowledge --> after_final: route_after_knowledge==final_response
    after_workflow --> after_escalation: route_after_workflow==escalation
    after_workflow --> after_final: route_after_workflow==final_response
    after_escalation --> after_final
    after_final --> [*]

    state initial {
      direction TB
      [*] --> i1
      i1: user_message
      i1 --> i2
      i2: session_id
      i2 --> i3
      i3: history
    }

    state after_intake {
      direction TB
      [*] --> a1
      a1: + category, intent
      a1 --> a2
      a2: + severity, urgency, confidence
      a2 --> a3
      a3: + is_support_request
      a3 --> a4
      a4: + requires_automation
      a4 --> a5
      a5: route_trace = [intake]
    }

    state after_knowledge {
      direction TB
      [*] --> k1
      k1: + match_strength
      k1 --> k2
      k2: + sources, context
      k2 --> k3
      k3: + response (grounded or best-effort)
      k3 --> k4
      k4: route_trace += [knowledge]
    }

    state after_workflow {
      direction TB
      [*] --> w1
      w1: + automation_status
      w1 --> w2
      w2: + automation_result
      w2 --> w3
      w3: + automation_simulated
      w3 --> w4
      w4: + should_create_ticket
      w4 --> w5
      w5: + ticket_decision_reason
      w5 --> w6
      w6: + ticket (maybe)
      w6 --> w7
      w7: + ops_api_unavailable
      w7 --> w8
      w8: route_trace += [workflow]
    }

    state after_escalation {
      direction TB
      [*] --> e1
      e1: ensure ticket
      e1 --> e2
      e2: PATCH status=escalated, priority=critical
      e2 --> e3
      e3: + escalated = True
      e3 --> e4
      e4: response += escalation banner
      e4 --> e5
      e5: route_trace += [escalation]
    }

    state after_final {
      direction TB
      [*] --> f1
      f1: response defaulted if empty
      f1 --> f2
      f2: route_trace += [final_response]
      f2 --> f3
      f3: response_time_ms, final_route stamped<br/>by process_message wrapper
    }
```

The "+" prefix means a field is being **written** at that node; reads
happen everywhere upstream.

---

## 8. Cross-transport: ticket via MCP vs ticket via HTTP

This is the diagram that proves the standardisation claim — both
transports converge on the **same** SQLite store. The arrows show what
the cross-transport proof test (`tests/test_mcp_proof.py`) actually
exercises.

```mermaid
sequenceDiagram
    autonumber
    actor User as End user (web)
    actor Eng as Engineer (VS Code / Claude Desktop)
    participant FE as Frontend (React)
    participant BE as Backend
    participant LG as LangGraph workflow agent
    participant CL as ItOpsClient (HTTP)
    participant OPS as IT Ops API (FastAPI)
    participant MCP as mcp_server (FastMCP/stdio)
    participant ST as mcp_server.store
    participant DB as SQLite (it_ops.db)

    rect rgba(96,165,250,0.10)
        Note over User,DB: Path 1 — ticket via the web chat (HTTP transport)
        User->>FE: types "VPN down…"
        FE->>BE: POST /chat
        BE->>LG: workflow node
        LG->>CL: create_ticket(payload)
        CL->>OPS: POST /api/v1/tickets<br/>(X-Internal-Token)
        OPS->>DB: INSERT tickets, ticket_events, audit_logs
        DB-->>OPS: row
        OPS-->>CL: ticket json
        CL-->>LG: TicketResult
        LG-->>BE: state.ticket
        BE-->>FE: AgentResponse (ticket_id, escalated)
        FE-->>User: chip "TKT-XXXX" + "Escalated"
    end

    rect rgba(244,114,182,0.10)
        Note over Eng,DB: Path 2 — same ticket visible via MCP transport
        Eng->>MCP: "list_tickets" (typed tool call over stdio)
        MCP->>ST: store.list_tickets()
        ST->>DB: SELECT * FROM tickets
        DB-->>ST: rows incl. TKT-XXXX
        ST-->>MCP: list[dict]
        MCP-->>Eng: typed result with TKT-XXXX
    end

    rect rgba(34,197,94,0.10)
        Note over Eng,DB: Path 3 — engineer mutates from VS Code, web sees it
        Eng->>MCP: "update_ticket_status TKT-XXXX resolved"
        MCP->>ST: store.update_ticket_status(...)
        ST->>DB: UPDATE tickets, INSERT ticket_events
        DB-->>ST: updated row
        ST-->>MCP: dict
        MCP-->>Eng: ack

        User->>FE: opens Tickets page
        FE->>BE: GET /tickets
        BE->>OPS: GET /api/v1/tickets
        OPS->>DB: SELECT * FROM tickets
        DB-->>OPS: rows (TKT-XXXX is now resolved)
        OPS-->>BE: list
        BE-->>FE: list
        FE-->>User: row "TKT-XXXX · resolved" appears
    end
```

**Code anchors:**

- HTTP transport entry: `services/it_ops_api/main.py:111` (`create_ticket`).
- MCP transport entry: `mcp_server/tools/__init__.py:14` (`@mcp.tool create_ticket`).
- Shared store: `mcp_server/store.py` (uses the same SQLModel engine
  declared in `services/it_ops_api/db.py`).

---

## How to verify these diagrams are accurate

Each diagram corresponds to a deterministic test scenario:

| Diagram         | Test                          | Command         |
| --------------- | ----------------------------- | --------------- |
| Path A          | `kb_browser_cache`            | `make test`     |
| Path B          | `password_reset_automation`   | `make test`     |
| Path C          | `urgent_vpn_outage_escalates` | `make test`     |
| Path D          | `weak_kb_user_gets_stuck`     | `make test`     |
| Path E          | `non_support_request`         | `make test`     |
| Cross-transport | full proof                    | `make test-mcp` |

If a diagram drifts from the code, the corresponding test scenario
fails. That's the contract.

See [`../tests/results/latest-summary.md`](../tests/results/latest-summary.md)
for the latest run; [`../docs/VALIDATION.md`](../docs/VALIDATION.md) for
the full methodology.
