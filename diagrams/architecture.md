# IT Support AI — Architecture

```mermaid
flowchart TD
    UI[React IT Support UI] --> API[FastAPI Backend]
    API --> G[LangGraph Orchestrator]
    G --> I[Intake Agent]
    I -->|support request| K[Knowledge Agent]
    I -->|non-support / low confidence| F[Final Response]
    I -->|low confidence + support| E[Escalation Agent]
    K -->|strong KB answer| F
    K -->|automation needed| W[Workflow Agent]
    K -->|weak/no match| E
    W -->|success| F
    W -->|failed/manual| E
    E --> F
    K --> V[ChromaDB Vector Store]
    W --> OPS[IT Ops API · FastAPI + SQLite]
    E --> OPS
    OPS --> SQL[(Tickets · Events · Audit)]
    MCP[MCP Server · FastMCP / stdio] --> SQL
    VSCode[VS Code Copilot Chat] --> MCP
    Claude[Claude Desktop] --> MCP
```

The same SQLite database is reachable through two transports:

- HTTP (`POST /api/v1/tickets`, …) for the web backend.
- MCP (`create_ticket`, `list_tickets`, `analyze_logs`, …) for VS Code and Claude Desktop.

That is the standardization point of the Model Context Protocol: the LangGraph
agent and an editor like VS Code call **the same tool contracts** without each
having to know the other's API.
