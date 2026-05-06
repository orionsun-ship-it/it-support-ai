"""MCP tool definitions exposed by mcp_server.server."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from mcp_server import store

mcp = FastMCP("it-support-tools")


@mcp.tool()
def create_ticket(
    title: str,
    description: str,
    category: str = "other",
    priority: str = "medium",
    severity: str = "medium",
    urgency: str = "medium",
    session_id: str = "mcp-client",
) -> dict[str, Any]:
    """Create an IT support ticket in the shared store."""
    return store.create_ticket(
        {
            "title": title,
            "description": description,
            "category": category,
            "priority": priority,
            "severity": severity,
            "urgency": urgency,
            "session_id": session_id,
        }
    )


@mcp.tool()
def list_tickets(
    category: str | None = None, status: str | None = None
) -> list[dict[str, Any]]:
    """List IT support tickets, optionally filtered by category and/or status."""
    return store.list_tickets(category=category, status=status)


@mcp.tool()
def update_ticket_status(ticket_id: str, new_status: str) -> dict[str, Any]:
    """Update the status of an existing ticket (open, in_progress, escalated, resolved)."""
    return store.update_ticket_status(ticket_id, new_status)


@mcp.tool()
def update_ticket_priority(ticket_id: str, new_priority: str) -> dict[str, Any]:
    """Update the priority of an existing ticket (low, medium, high, critical)."""
    return store.update_ticket_priority(ticket_id, new_priority)


@mcp.tool()
def analyze_logs(log_file: str, severity: str | None = None) -> dict[str, Any]:
    """Analyze a sample IT log file (app_errors, auth_events, network_events)."""
    return store.analyze_logs(log_file=log_file, severity=severity)


@mcp.tool()
def recent_errors(limit: int = 5) -> dict[str, Any]:
    """Return recent ERROR-level entries across all sample log files."""
    return store.recent_errors(limit=limit)
