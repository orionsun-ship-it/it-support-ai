# MCP demo — VS Code & Claude Desktop

This project exposes its IT support tools through a real Model Context
Protocol server (`mcp_server/server.py`, FastMCP, stdio transport). The same
tools are available to:

- The LangGraph agent inside the FastAPI backend (in-process, via
  `backend/services/it_ops_client.py` for HTTP and `mcp_server/store.py` for
  the shared SQLite store).
- Any MCP client that speaks stdio — VS Code Copilot Chat, Claude Desktop,
  the MCP Inspector.

## Tools exposed

| Tool                     | Purpose                                                     |
| ------------------------ | ----------------------------------------------------------- |
| `create_ticket`          | Open a ticket. Persisted to the shared SQLite store.        |
| `list_tickets`           | List tickets, optionally filtered by category/status.       |
| `update_ticket_status`   | open → in_progress → escalated → resolved.                  |
| `update_ticket_priority` | low / medium / high / critical.                             |
| `analyze_logs`           | Summarize one of the sample log files.                      |
| `recent_errors`          | Most recent ERROR-level events across all sample log files. |

## Run the MCP server

You only need this running while a client is connected to it. The web app
itself does not depend on it being up — the backend goes through HTTP.

```bash
make mcp
# equivalent to:  python -m mcp_server.server
```

The process binds to stdio and waits silently for an MCP client. There is no
HTTP port.

## Connect from VS Code Copilot Chat

VS Code 1.91+ supports MCP natively in Copilot Chat. Create
`.vscode/mcp.json` at the project root with this content:

```json
{
  "servers": {
    "it-support-tools": {
      "type": "stdio",
      "command": "${workspaceFolder}/.venv/bin/python",
      "args": ["-m", "mcp_server.server"],
      "cwd": "${workspaceFolder}",
      "env": { "PYTHONPATH": "${workspaceFolder}" }
    }
  }
}
```

Reload VS Code. In Copilot Chat, the tools panel will list `create_ticket`,
`list_tickets`, etc. Try:

> Use the IT support tools to open a ticket: title "Wi-Fi flaky in conference
> room B", category network, priority medium. Then list all tickets.

VS Code will prompt for permission, run `create_ticket` over MCP, then run
`list_tickets`. Open the web app's Tickets page (`http://localhost:5173`) —
the new ticket is there too, because both transports point at the same
database.

## Connect from Claude Desktop

Edit Claude Desktop's config (macOS path:
`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "it-support-tools": {
      "command": "/absolute/path/to/it-support-ai/.venv/bin/python",
      "args": ["-m", "mcp_server.server"],
      "cwd": "/absolute/path/to/it-support-ai",
      "env": { "PYTHONPATH": "/absolute/path/to/it-support-ai" }
    }
  }
}
```

Replace `/absolute/path/to/it-support-ai` with the actual path. Restart
Claude Desktop. The tools appear under the slash-tools menu in any new
conversation.

## MCP standardizes tool access — side-by-side

The same `create_ticket` capability, two transports, identical contracts.

**Direct REST (legacy):**

```python
httpx.post(
    "http://localhost:8001/api/v1/tickets",
    headers={"X-Internal-Token": token},
    json={
        "title": "Reset password",
        "description": "User cannot log in",
        "category": "password",
        "priority": "medium",
        "severity": "medium",
        "urgency": "medium",
        "session_id": "client-demo",
    },
)
```

Each integration must learn the URL, the auth header, the JSON shape, and
the error contract.

**MCP:**

```python
# From VS Code Copilot Chat or Claude Desktop, the user just says:
# "Open a ticket: title=..., category=password, priority=medium"
# The client discovers the tool from the server's manifest, including types,
# descriptions, and required arguments. No bespoke client code.
```

The server publishes a typed manifest; every MCP client (VS Code, Claude
Desktop, MCP Inspector, future clients) speaks the same protocol. Adding a
new client requires zero changes to this project.

## Optional appendix — connect to public MCP servers

The same VS Code / Claude Desktop config supports public MCP servers, e.g.
the official GitHub MCP server. Add another entry under `mcpServers`:

```json
"github": {
  "command": "npx",
  "args": ["-y", "@modelcontextprotocol/server-github"],
  "env": { "GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_..." }
}
```

Generate a fine-scoped PAT at <https://github.com/settings/tokens>. Reload
the client. Now your editor can `create_issue`, `list_repos`, etc. through
GitHub's MCP server, exactly the same way it talks to this project's IT
support server. That is the practical demonstration of MCP standardizing
tool access across vendors.

A Jira equivalent works the same way — see
<https://github.com/sooperset/mcp-atlassian>.
