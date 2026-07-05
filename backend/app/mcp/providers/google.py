"""
Google MCP Provider — Gmail, Calendar, Drive, Contacts.
Registers tools that let the LLM read/send emails, manage calendar events,
search drive files, and look up contacts on behalf of the user.
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from app.mcp.registry import MCPProvider, MCPTool, OAuthConfig, register_provider
from app.mcp.token_store import get_token

# --- OAuth config ---

GOOGLE_OAUTH = OAuthConfig(
    authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
    token_url="https://oauth2.googleapis.com/token",
    client_id_env="GOOGLE_CLIENT_ID",
    client_secret_env="GOOGLE_CLIENT_SECRET",
    scopes=[
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.send",
        "https://www.googleapis.com/auth/calendar",
        "https://www.googleapis.com/auth/drive.readonly",
        "https://www.googleapis.com/auth/contacts.readonly",
    ],
    extra_params={"include_granted_scopes": "true"},
)

# --- Tool definitions ---

TOOLS = [
    MCPTool(
        name="gmail_list_messages",
        description="List recent emails from the user's Gmail inbox. Can filter by query (e.g. 'from:boss@co.com', 'is:unread', 'subject:meeting').",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Gmail search query"},
                "max_results": {"type": "integer", "default": 10},
            },
        },
    ),
    MCPTool(
        name="gmail_read_message",
        description="Read the full content of a specific email by message ID.",
        parameters={
            "type": "object",
            "required": ["message_id"],
            "properties": {
                "message_id": {"type": "string", "description": "Gmail message ID"},
            },
        },
    ),
    MCPTool(
        name="gmail_send",
        description="Send an email on behalf of the user.",
        parameters={
            "type": "object",
            "required": ["to", "subject", "body"],
            "properties": {
                "to": {"type": "string", "description": "Recipient email address"},
                "subject": {"type": "string"},
                "body": {"type": "string", "description": "Email body (plain text)"},
            },
        },
    ),
    MCPTool(
        name="calendar_list_events",
        description="List upcoming calendar events. Defaults to next 7 days.",
        parameters={
            "type": "object",
            "properties": {
                "days_ahead": {"type": "integer", "default": 7},
                "max_results": {"type": "integer", "default": 10},
            },
        },
    ),
    MCPTool(
        name="calendar_create_event",
        description="Create a new calendar event.",
        parameters={
            "type": "object",
            "required": ["summary", "start", "end"],
            "properties": {
                "summary": {"type": "string", "description": "Event title"},
                "start": {"type": "string", "description": "ISO 8601 datetime"},
                "end": {"type": "string", "description": "ISO 8601 datetime"},
                "description": {"type": "string"},
                "attendees": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of attendee email addresses",
                },
            },
        },
    ),
    MCPTool(
        name="drive_search",
        description="Search Google Drive files by name or content.",
        parameters={
            "type": "object",
            "required": ["query"],
            "properties": {
                "query": {"type": "string", "description": "Search query for Drive files"},
                "max_results": {"type": "integer", "default": 10},
            },
        },
    ),
    MCPTool(
        name="contacts_search",
        description="Search the user's Google Contacts.",
        parameters={
            "type": "object",
            "required": ["query"],
            "properties": {
                "query": {"type": "string", "description": "Name or email to search"},
            },
        },
    ),
]


# --- Tool execution ---

async def execute_tool(tool_name: str, args: dict, user_id: str) -> Any:
    """Execute a Google tool with the user's stored OAuth token."""
    token_data = await get_token(user_id, "google")
    if not token_data:
        return {"error": "Google not connected. Please connect your Google account first."}

    access_token = token_data["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    async with httpx.AsyncClient() as client:
        if tool_name == "gmail_list_messages":
            return await _gmail_list(client, headers, args)
        elif tool_name == "gmail_read_message":
            return await _gmail_read(client, headers, args)
        elif tool_name == "gmail_send":
            return await _gmail_send(client, headers, args)
        elif tool_name == "calendar_list_events":
            return await _calendar_list(client, headers, args)
        elif tool_name == "calendar_create_event":
            return await _calendar_create(client, headers, args)
        elif tool_name == "drive_search":
            return await _drive_search(client, headers, args)
        elif tool_name == "contacts_search":
            return await _contacts_search(client, headers, args)

    return {"error": f"Unknown tool: {tool_name}"}


async def _gmail_list(client: httpx.AsyncClient, headers: dict, args: dict) -> Any:
    query = args.get("query", "")
    max_results = args.get("max_results", 10)
    resp = await client.get(
        "https://gmail.googleapis.com/gmail/v1/users/me/messages",
        headers=headers,
        params={"q": query, "maxResults": max_results},
    )
    if resp.status_code != 200:
        return {"error": f"Gmail API error: {resp.status_code}"}

    messages = resp.json().get("messages", [])
    # Fetch snippets for each message
    results = []
    for msg in messages[:max_results]:
        detail = await client.get(
            f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{msg['id']}",
            headers=headers,
            params={"format": "metadata", "metadataHeaders": ["From", "Subject", "Date"]},
        )
        if detail.status_code == 200:
            data = detail.json()
            hdrs = {h["name"]: h["value"] for h in data.get("payload", {}).get("headers", [])}
            results.append({
                "id": msg["id"],
                "from": hdrs.get("From", ""),
                "subject": hdrs.get("Subject", ""),
                "date": hdrs.get("Date", ""),
                "snippet": data.get("snippet", ""),
            })
    return results


async def _gmail_read(client: httpx.AsyncClient, headers: dict, args: dict) -> Any:
    msg_id = args["message_id"]
    resp = await client.get(
        f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{msg_id}",
        headers=headers,
        params={"format": "full"},
    )
    if resp.status_code != 200:
        return {"error": f"Gmail API error: {resp.status_code}"}
    data = resp.json()
    return {
        "id": data["id"],
        "snippet": data.get("snippet", ""),
        "payload": data.get("payload", {}),
    }


async def _gmail_send(client: httpx.AsyncClient, headers: dict, args: dict) -> Any:
    import base64
    raw_msg = f"To: {args['to']}\r\nSubject: {args['subject']}\r\n\r\n{args['body']}"
    encoded = base64.urlsafe_b64encode(raw_msg.encode()).decode()
    resp = await client.post(
        "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
        headers=headers,
        json={"raw": encoded},
    )
    if resp.status_code != 200:
        return {"error": f"Gmail send error: {resp.status_code}"}
    return {"status": "sent", "id": resp.json().get("id")}


async def _calendar_list(client: httpx.AsyncClient, headers: dict, args: dict) -> Any:
    from datetime import datetime, timedelta, timezone
    days = args.get("days_ahead", 7)
    now = datetime.now(timezone.utc)
    time_min = now.isoformat()
    time_max = (now + timedelta(days=days)).isoformat()

    resp = await client.get(
        "https://www.googleapis.com/calendar/v3/calendars/primary/events",
        headers=headers,
        params={
            "timeMin": time_min,
            "timeMax": time_max,
            "maxResults": args.get("max_results", 10),
            "singleEvents": "true",
            "orderBy": "startTime",
        },
    )
    if resp.status_code != 200:
        return {"error": f"Calendar API error: {resp.status_code}"}

    events = resp.json().get("items", [])
    return [
        {
            "id": e["id"],
            "summary": e.get("summary", "(no title)"),
            "start": e.get("start", {}).get("dateTime", e.get("start", {}).get("date")),
            "end": e.get("end", {}).get("dateTime", e.get("end", {}).get("date")),
            "attendees": [a.get("email") for a in e.get("attendees", [])],
        }
        for e in events
    ]


async def _calendar_create(client: httpx.AsyncClient, headers: dict, args: dict) -> Any:
    event_body = {
        "summary": args["summary"],
        "start": {"dateTime": args["start"]},
        "end": {"dateTime": args["end"]},
    }
    if args.get("description"):
        event_body["description"] = args["description"]
    if args.get("attendees"):
        event_body["attendees"] = [{"email": e} for e in args["attendees"]]

    resp = await client.post(
        "https://www.googleapis.com/calendar/v3/calendars/primary/events",
        headers=headers,
        json=event_body,
    )
    if resp.status_code not in (200, 201):
        return {"error": f"Calendar create error: {resp.status_code}"}
    data = resp.json()
    return {"status": "created", "id": data["id"], "link": data.get("htmlLink")}


async def _drive_search(client: httpx.AsyncClient, headers: dict, args: dict) -> Any:
    resp = await client.get(
        "https://www.googleapis.com/drive/v3/files",
        headers=headers,
        params={
            "q": f"name contains '{args['query']}' or fullText contains '{args['query']}'",
            "pageSize": args.get("max_results", 10),
            "fields": "files(id,name,mimeType,webViewLink,modifiedTime)",
        },
    )
    if resp.status_code != 200:
        return {"error": f"Drive API error: {resp.status_code}"}
    return resp.json().get("files", [])


async def _contacts_search(client: httpx.AsyncClient, headers: dict, args: dict) -> Any:
    resp = await client.get(
        "https://people.googleapis.com/v1/people:searchContacts",
        headers=headers,
        params={
            "query": args["query"],
            "readMask": "names,emailAddresses,phoneNumbers",
            "pageSize": 10,
        },
    )
    if resp.status_code != 200:
        return {"error": f"Contacts API error: {resp.status_code}"}
    results = resp.json().get("results", [])
    return [
        {
            "name": r.get("person", {}).get("names", [{}])[0].get("displayName", ""),
            "emails": [e.get("value") for e in r.get("person", {}).get("emailAddresses", [])],
            "phones": [p.get("value") for p in r.get("person", {}).get("phoneNumbers", [])],
        }
        for r in results
    ]


# --- Registration ---

def register():
    provider = MCPProvider(
        id="google",
        name="Google",
        description="Gmail, Google Calendar, Google Drive, and Contacts",
        icon="🔵",
        oauth_config=GOOGLE_OAUTH,
        tools=TOOLS,
        scopes_required=GOOGLE_OAUTH.scopes,
    )
    register_provider(provider)
