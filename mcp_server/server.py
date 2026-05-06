"""Entrypoint for the Model Context Protocol server.

Run over stdio (the standard MCP transport):

    python -m mcp_server.server

Connect from VS Code Copilot Chat (.vscode/mcp.json) or Claude Desktop
(claude_desktop_config.json). See docs/MCP_VSCode_Demo.md for full configs.
"""

from __future__ import annotations

from mcp_server.tools import mcp


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
