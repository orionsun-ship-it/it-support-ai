"""Real Model Context Protocol server exposing IT support tools.

The tools share the same SQLite store used by services.it_ops_api, so a ticket
created through MCP (e.g. from VS Code or Claude Desktop) appears in the web
app's Tickets page and vice versa.
"""
