"""
Notion MCP Provider — pages, databases, search.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.mcp.registry import MCPProvider, MCPTool, OAuthConfig, register_provider
from app.mcp.token_store import get_token

NOTION_OAUTH = OAuthConfig(
    authorize_url="https://api.notion.com/v1/oauth/authorize",
    token_url="https://api.notion.com/v1/oauth/token",
    client_id_env="NOTION_CLIENT_ID",
    client_secret_env="NOTION_CLIENT_SECRET",
    scopes=[],  # Notion uses integration-level permissions
    extra_params={"owner": "user"},
)

TOOLS = [
    MCPTool(
        name="search",
        description="Search across all Notion pages and databases the user has shared with the integration.",
        parameters={
            "type": "object",
            "required": ["query"],
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "default": 10},
            },
        },
    ),
    MCPTool(
        name="get_page",
        description="Get the content of a Notion page by ID.",
        parameters={
            "type": "object",
            "required": ["page_id"],
            "properties": {
                "page_id": {"type": "string"},
            },
        },
    ),
    MCPTool(
        name="create_page",
        description="Create a new page in a Notion database or as a child of another page.",
        parameters={
            "type": "object",
            "required": ["parent_id", "title"],
            "properties": {
                "parent_id": {"type": "string", "description": "Database or page ID"},
                "title": {"type": "string"},
                "content": {"type": "string", "description": "Page content as plain text"},
                "is_database": {"type": "boolean", "default": True},
            },
        },
    ),
    MCPTool(
        name="query_database",
        description="Query a Notion database to list its entries.",
        parameters={
            "type": "object",
            "required": ["database_id"],
            "properties": {
                "database_id": {"type": "string"},
                "limit": {"type": "integer", "default": 20},
            },
        },
    ),
]


async def execute_tool(tool_name: str, args: dict, user_id: str) -> Any:
    token_data = await get_token(user_id, "notion")
    if not token_data:
        return {"error": "Notion not connected. Please connect your Notion account first."}

    headers = {
        "Authorization": f"Bearer {token_data['access_token']}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }
    base = "https://api.notion.com/v1"

    async with httpx.AsyncClient() as client:
        if tool_name == "search":
            resp = await client.post(
                f"{base}/search",
                headers=headers,
                json={"query": args["query"], "page_size": args.get("limit", 10)},
            )
            if resp.status_code != 200:
                return {"error": f"Notion error: {resp.status_code}"}
            results = resp.json().get("results", [])
            return [
                {
                    "id": r["id"],
                    "type": r["object"],
                    "title": _extract_title(r),
                    "url": r.get("url", ""),
                }
                for r in results
            ]

        elif tool_name == "get_page":
            # Get page blocks (content)
            resp = await client.get(
                f"{base}/blocks/{args['page_id']}/children",
                headers=headers,
                params={"page_size": 50},
            )
            if resp.status_code != 200:
                return {"error": f"Notion error: {resp.status_code}"}
            blocks = resp.json().get("results", [])
            return [_extract_block_text(b) for b in blocks if _extract_block_text(b)]

        elif tool_name == "create_page":
            parent = (
                {"database_id": args["parent_id"]}
                if args.get("is_database", True)
                else {"page_id": args["parent_id"]}
            )
            body = {
                "parent": parent,
                "properties": {"title": {"title": [{"text": {"content": args["title"]}}]}},
            }
            if args.get("content"):
                body["children"] = [
                    {
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {"rich_text": [{"text": {"content": args["content"]}}]},
                    }
                ]
            resp = await client.post(f"{base}/pages", headers=headers, json=body)
            if resp.status_code not in (200, 201):
                return {"error": f"Notion create error: {resp.status_code}"}
            data = resp.json()
            return {"id": data["id"], "url": data.get("url", "")}

        elif tool_name == "query_database":
            resp = await client.post(
                f"{base}/databases/{args['database_id']}/query",
                headers=headers,
                json={"page_size": args.get("limit", 20)},
            )
            if resp.status_code != 200:
                return {"error": f"Notion error: {resp.status_code}"}
            results = resp.json().get("results", [])
            return [{"id": r["id"], "title": _extract_title(r), "url": r.get("url", "")} for r in results]

    return {"error": f"Unknown tool: {tool_name}"}


def _extract_title(page: dict) -> str:
    props = page.get("properties", {})
    for key, val in props.items():
        if val.get("type") == "title":
            titles = val.get("title", [])
            if titles:
                return titles[0].get("plain_text", "")
    return "(untitled)"


def _extract_block_text(block: dict) -> str:
    btype = block.get("type", "")
    content = block.get(btype, {})
    rich_text = content.get("rich_text", [])
    return " ".join(rt.get("plain_text", "") for rt in rich_text)


def register():
    register_provider(MCPProvider(
        id="notion",
        name="Notion",
        description="Pages, databases, and workspace search",
        icon="📝",
        oauth_config=NOTION_OAUTH,
        tools=TOOLS,
        scopes_required=[],
    ))
