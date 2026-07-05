"""
MCP Tool Executor — routes tool calls from the LLM to the correct provider.
Tool names use the format: {provider_id}__{tool_name}
"""

from __future__ import annotations

import json
from typing import Any

from app.mcp.providers import google, spotify, github, notion, slack

# Map provider ID to its execute_tool function
_executors: dict[str, Any] = {
    "google": google.execute_tool,
    "spotify": spotify.execute_tool,
    "github": github.execute_tool,
    "notion": notion.execute_tool,
    "slack": slack.execute_tool,
}


async def execute(tool_call_name: str, args: dict, user_id: str) -> str:
    """
    Execute an MCP tool call. Returns JSON string for the LLM.
    tool_call_name format: {provider_id}__{tool_name}
    """
    parts = tool_call_name.split("__", 1)
    if len(parts) != 2:
        return json.dumps({"error": f"Invalid MCP tool format: {tool_call_name}"})

    provider_id, tool_name = parts
    executor = _executors.get(provider_id)
    if executor is None:
        return json.dumps({"error": f"Unknown provider: {provider_id}"})

    result = await executor(tool_name, args, user_id)
    return json.dumps(result, default=str)


def init_providers():
    """Register all providers. Call once at startup."""
    google.register()
    spotify.register()
    github.register()
    notion.register()
    slack.register()
