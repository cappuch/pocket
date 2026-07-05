"""
Slack MCP Provider — messaging, channels, search.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.mcp.registry import MCPProvider, MCPTool, OAuthConfig, register_provider
from app.mcp.token_store import get_token

SLACK_OAUTH = OAuthConfig(
    authorize_url="https://slack.com/oauth/v2/authorize",
    token_url="https://slack.com/api/oauth.v2.access",
    client_id_env="SLACK_CLIENT_ID",
    client_secret_env="SLACK_CLIENT_SECRET",
    scopes=[
        "channels:read",
        "channels:history",
        "chat:write",
        "search:read",
        "users:read",
        "im:read",
        "im:history",
    ],
    extra_params={"user_scope": "search:read"},
)

TOOLS = [
    MCPTool(
        name="list_channels",
        description="List Slack channels the user is a member of.",
        parameters={
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "default": 20},
            },
        },
    ),
    MCPTool(
        name="read_channel",
        description="Read recent messages from a Slack channel.",
        parameters={
            "type": "object",
            "required": ["channel_id"],
            "properties": {
                "channel_id": {"type": "string"},
                "limit": {"type": "integer", "default": 15},
            },
        },
    ),
    MCPTool(
        name="send_message",
        description="Send a message to a Slack channel.",
        parameters={
            "type": "object",
            "required": ["channel_id", "text"],
            "properties": {
                "channel_id": {"type": "string"},
                "text": {"type": "string"},
            },
        },
    ),
    MCPTool(
        name="search_messages",
        description="Search Slack messages across all channels.",
        parameters={
            "type": "object",
            "required": ["query"],
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "default": 10},
            },
        },
    ),
]


async def execute_tool(tool_name: str, args: dict, user_id: str) -> Any:
    token_data = await get_token(user_id, "slack")
    if not token_data:
        return {"error": "Slack not connected. Please connect your Slack account first."}

    headers = {"Authorization": f"Bearer {token_data['access_token']}"}
    base = "https://slack.com/api"

    async with httpx.AsyncClient() as client:
        if tool_name == "list_channels":
            resp = await client.get(
                f"{base}/conversations.list",
                headers=headers,
                params={"types": "public_channel,private_channel", "limit": args.get("limit", 20)},
            )
            data = resp.json()
            if not data.get("ok"):
                return {"error": data.get("error", "unknown")}
            return [{"id": c["id"], "name": c["name"], "topic": c.get("topic", {}).get("value", "")} for c in data.get("channels", [])]

        elif tool_name == "read_channel":
            resp = await client.get(
                f"{base}/conversations.history",
                headers=headers,
                params={"channel": args["channel_id"], "limit": args.get("limit", 15)},
            )
            data = resp.json()
            if not data.get("ok"):
                return {"error": data.get("error", "unknown")}
            return [{"user": m.get("user", "bot"), "text": m.get("text", ""), "ts": m["ts"]} for m in data.get("messages", [])]

        elif tool_name == "send_message":
            resp = await client.post(
                f"{base}/chat.postMessage",
                headers=headers,
                json={"channel": args["channel_id"], "text": args["text"]},
            )
            data = resp.json()
            if not data.get("ok"):
                return {"error": data.get("error", "unknown")}
            return {"status": "sent", "ts": data.get("ts")}

        elif tool_name == "search_messages":
            resp = await client.get(
                f"{base}/search.messages",
                headers=headers,
                params={"query": args["query"], "count": args.get("limit", 10)},
            )
            data = resp.json()
            if not data.get("ok"):
                return {"error": data.get("error", "unknown")}
            matches = data.get("messages", {}).get("matches", [])
            return [{"channel": m.get("channel", {}).get("name", ""), "text": m.get("text", ""), "user": m.get("username", "")} for m in matches]

    return {"error": f"Unknown tool: {tool_name}"}


def register():
    register_provider(MCPProvider(
        id="slack",
        name="Slack",
        description="Channels, messages, and workspace search",
        icon="💬",
        oauth_config=SLACK_OAUTH,
        tools=TOOLS,
        scopes_required=SLACK_OAUTH.scopes,
    ))
