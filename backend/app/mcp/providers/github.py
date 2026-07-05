"""
GitHub MCP Provider — repos, issues, PRs, notifications.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.mcp.registry import MCPProvider, MCPTool, OAuthConfig, register_provider
from app.mcp.token_store import get_token

GITHUB_OAUTH = OAuthConfig(
    authorize_url="https://github.com/login/oauth/authorize",
    token_url="https://github.com/login/oauth/access_token",
    client_id_env="GITHUB_CLIENT_ID",
    client_secret_env="GITHUB_CLIENT_SECRET",
    scopes=["repo", "read:user", "notifications"],
    extra_params={"allow_signup": "false"},
)

TOOLS = [
    MCPTool(
        name="list_repos",
        description="List the user's GitHub repositories.",
        parameters={
            "type": "object",
            "properties": {
                "sort": {"type": "string", "enum": ["updated", "pushed", "created"], "default": "updated"},
                "limit": {"type": "integer", "default": 10},
            },
        },
    ),
    MCPTool(
        name="list_issues",
        description="List issues for a repository.",
        parameters={
            "type": "object",
            "required": ["repo"],
            "properties": {
                "repo": {"type": "string", "description": "owner/repo format"},
                "state": {"type": "string", "enum": ["open", "closed", "all"], "default": "open"},
                "limit": {"type": "integer", "default": 10},
            },
        },
    ),
    MCPTool(
        name="create_issue",
        description="Create a new issue in a repository.",
        parameters={
            "type": "object",
            "required": ["repo", "title"],
            "properties": {
                "repo": {"type": "string", "description": "owner/repo format"},
                "title": {"type": "string"},
                "body": {"type": "string"},
                "labels": {"type": "array", "items": {"type": "string"}},
            },
        },
    ),
    MCPTool(
        name="list_prs",
        description="List pull requests for a repository.",
        parameters={
            "type": "object",
            "required": ["repo"],
            "properties": {
                "repo": {"type": "string"},
                "state": {"type": "string", "enum": ["open", "closed", "all"], "default": "open"},
            },
        },
    ),
    MCPTool(
        name="notifications",
        description="Get the user's unread GitHub notifications.",
        parameters={
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "default": 15},
            },
        },
    ),
]


async def execute_tool(tool_name: str, args: dict, user_id: str) -> Any:
    token_data = await get_token(user_id, "github")
    if not token_data:
        return {"error": "GitHub not connected. Please connect your GitHub account first."}

    headers = {
        "Authorization": f"Bearer {token_data['access_token']}",
        "Accept": "application/vnd.github+json",
    }
    base = "https://api.github.com"

    async with httpx.AsyncClient() as client:
        if tool_name == "list_repos":
            resp = await client.get(
                f"{base}/user/repos",
                headers=headers,
                params={"sort": args.get("sort", "updated"), "per_page": args.get("limit", 10)},
            )
            if resp.status_code != 200:
                return {"error": f"GitHub error: {resp.status_code}"}
            return [{"name": r["full_name"], "description": r.get("description", ""), "url": r["html_url"]} for r in resp.json()]

        elif tool_name == "list_issues":
            resp = await client.get(
                f"{base}/repos/{args['repo']}/issues",
                headers=headers,
                params={"state": args.get("state", "open"), "per_page": args.get("limit", 10)},
            )
            if resp.status_code != 200:
                return {"error": f"GitHub error: {resp.status_code}"}
            return [{"number": i["number"], "title": i["title"], "state": i["state"], "url": i["html_url"]} for i in resp.json()]

        elif tool_name == "create_issue":
            body = {"title": args["title"]}
            if args.get("body"):
                body["body"] = args["body"]
            if args.get("labels"):
                body["labels"] = args["labels"]
            resp = await client.post(f"{base}/repos/{args['repo']}/issues", headers=headers, json=body)
            if resp.status_code != 201:
                return {"error": f"GitHub error: {resp.status_code}"}
            data = resp.json()
            return {"number": data["number"], "url": data["html_url"]}

        elif tool_name == "list_prs":
            resp = await client.get(
                f"{base}/repos/{args['repo']}/pulls",
                headers=headers,
                params={"state": args.get("state", "open"), "per_page": 10},
            )
            if resp.status_code != 200:
                return {"error": f"GitHub error: {resp.status_code}"}
            return [{"number": p["number"], "title": p["title"], "state": p["state"], "url": p["html_url"]} for p in resp.json()]

        elif tool_name == "notifications":
            resp = await client.get(
                f"{base}/notifications",
                headers=headers,
                params={"per_page": args.get("limit", 15)},
            )
            if resp.status_code != 200:
                return {"error": f"GitHub error: {resp.status_code}"}
            return [{"repo": n["repository"]["full_name"], "title": n["subject"]["title"], "type": n["subject"]["type"]} for n in resp.json()]

    return {"error": f"Unknown tool: {tool_name}"}


def register():
    register_provider(MCPProvider(
        id="github",
        name="GitHub",
        description="Repositories, issues, pull requests, and notifications",
        icon="🐙",
        oauth_config=GITHUB_OAUTH,
        tools=TOOLS,
        scopes_required=GITHUB_OAUTH.scopes,
    ))
