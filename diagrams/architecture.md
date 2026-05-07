# IT Support AI — Architecture

## High-level system

```mermaid
flowchart TD
    UI[React IT Support UI]:::ui --> API[FastAPI Backend]:::api
    API --> G[LangGraph Orchestrator]:::orch
    G --> I[Intake Agent]:::agent
    I -->|is_support_request=false| F[Final Response]:::final
    I -->|otherwise| K[Knowledge Agent]:::agent
    K -->|intent=ticket_request| W[Workflow Agent]:::agent
    K -->|requires_automation| W
    K -->|user is stuck / asks for human| E[Escalation Agent]:::agent
    K -->|otherwise| F
    W -->|automation failed/manual| E
    W -->|severity=critical OR urgency=high| E
    W -->|otherwise| F
    E --> F

    K --> V[(ChromaDB Vector Store)]:::store
    W --> OPS[IT Ops API · FastAPI + SQLite]:::api
    E --> OPS
    OPS --> SQL[(Tickets · Events · Audit · Feedback)]:::store

    MCP[MCP Server · FastMCP / stdio]:::mcp --> SQL
    VSCode[VS Code Copilot Chat]:::client --> MCP
    Claude[Claude Desktop]:::client --> MCP

    classDef ui fill:#eff6ff,stroke:#2563eb,color:#1e40af;
    classDef api fill:#ecfeff,stroke:#0891b2,color:#155e75;
    classDef orch fill:#f5f3ff,stroke:#7c3aed,color:#5b21b6;
    classDef agent fill:#f0fdf4,stroke:#16a34a,color:#15803d;
    classDef final fill:#fef3c7,stroke:#d97706,color:#92400e;
    classDef store fill:#f1f5f9,stroke:#475569,color:#0f172a;
    classDef mcp fill:#fdf2f8,stroke:#db2777,color:#9d174d;
    classDef client fill:#fff7ed,stroke:#ea580c,color:#9a3412;
```

The same SQLite database is reachable through two transports:

- HTTP (`POST /api/v1/tickets`, …) for the web backend.
- MCP (`create_ticket`, `list_tickets`, `analyze_logs`, …) for VS Code
  Copilot Chat and Claude Desktop.

That is the standardisation point of the Model Context Protocol: the
LangGraph agent and an editor like VS Code call **the same tool contracts**
without each having to know the other's API.

## Conditional routing detail

```mermaid
flowchart LR
    S([START]) --> I[intake]
    I -->|is_support_request=false| FR[final_response]

    I -->|support| K[knowledge]
    K -->|intent=ticket_request| W[workflow]
    K -->|requires_automation| W
    K -->|stuck or asks for human| E[escalation]
    K -->|otherwise| FR

    W -->|automation failed/manual_required| E
    W -->|severity=critical OR urgency=high| E
    W -->|otherwise| FR

    E --> FR
    FR --> FIN([END])
```

Every conditional edge above is unit-tested in `tests/test_routing.py` —
each branch has at least one scenario that walks through it, with the
expected `route_trace` checked literally.

## State carried between agents

`AgentState` (in `backend/agents/orchestrator.py`) carries:

- `category`, `intent`, `confidence`, `severity`, `urgency`,
  `is_support_request`, `requires_automation` — set by Intake.
- `match_strength`, `sources`, `context` — set by Knowledge.
- `automation_status`, `automation_result`, `automation_simulated`,
  `should_create_ticket`, `ticket_decision_reason`, `ticket`,
  `ops_api_unavailable` — set by Workflow.
- `escalated`, `ticket` (priority bumped) — set by Escalation.
- `route_trace`, `final_route`, `response_time_ms` — appended by every
  node and stamped by `process_message`.

The `/chat` API response surfaces the diagnostic fields verbatim so the
chat UI can render them under each turn (the "Route trace" strip in
`frontend/src/pages/ChatPage.jsx`).

## Why this layout

- **One agent = one decision.** Intake classifies, Knowledge retrieves,
  Workflow acts, Escalation hands off. Each agent has a small fixed
  contract over `AgentState`. New behaviours plug into the existing
  agent that owns that decision.
- **Routing is data, not heuristics buried in agent bodies.** Routing
  functions in `orchestrator.py` are pure: they read state and return a
  node name. Tests can exercise them in isolation.
- **MCP is the integration boundary.** The same store that the LangGraph
  agent writes to via the HTTP ops API is the one MCP clients read from
  and write to over stdio. No second source of truth.
