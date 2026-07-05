"""
Spotify MCP Provider — Music playback control, search, playlists.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.mcp.registry import MCPProvider, MCPTool, OAuthConfig, register_provider
from app.mcp.token_store import get_token

SPOTIFY_OAUTH = OAuthConfig(
    authorize_url="https://accounts.spotify.com/authorize",
    token_url="https://accounts.spotify.com/api/token",
    client_id_env="SPOTIFY_CLIENT_ID",
    client_secret_env="SPOTIFY_CLIENT_SECRET",
    scopes=[
        "user-read-playback-state",
        "user-modify-playback-state",
        "user-read-currently-playing",
        "playlist-read-private",
        "playlist-modify-public",
        "playlist-modify-private",
        "user-library-read",
    ],
)

TOOLS = [
    MCPTool(
        name="now_playing",
        description="Get the user's currently playing track on Spotify.",
        parameters={"type": "object", "properties": {}},
    ),
    MCPTool(
        name="search_tracks",
        description="Search Spotify for tracks by name, artist, or album.",
        parameters={
            "type": "object",
            "required": ["query"],
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "default": 5},
            },
        },
    ),
    MCPTool(
        name="play_track",
        description="Play a specific track by Spotify URI.",
        parameters={
            "type": "object",
            "required": ["uri"],
            "properties": {
                "uri": {"type": "string", "description": "Spotify track URI (spotify:track:...)"},
            },
        },
    ),
    MCPTool(
        name="pause",
        description="Pause the user's Spotify playback.",
        parameters={"type": "object", "properties": {}},
    ),
    MCPTool(
        name="skip_next",
        description="Skip to the next track.",
        parameters={"type": "object", "properties": {}},
    ),
    MCPTool(
        name="list_playlists",
        description="List the user's Spotify playlists.",
        parameters={
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "default": 20},
            },
        },
    ),
]


async def execute_tool(tool_name: str, args: dict, user_id: str) -> Any:
    token_data = await get_token(user_id, "spotify")
    if not token_data:
        return {"error": "Spotify not connected. Please connect your Spotify account first."}

    headers = {"Authorization": f"Bearer {token_data['access_token']}"}
    base = "https://api.spotify.com/v1"

    async with httpx.AsyncClient() as client:
        if tool_name == "now_playing":
            resp = await client.get(f"{base}/me/player/currently-playing", headers=headers)
            if resp.status_code == 204:
                return {"status": "nothing_playing"}
            if resp.status_code != 200:
                return {"error": f"Spotify error: {resp.status_code}"}
            data = resp.json()
            item = data.get("item", {})
            return {
                "track": item.get("name"),
                "artist": ", ".join(a["name"] for a in item.get("artists", [])),
                "album": item.get("album", {}).get("name"),
                "is_playing": data.get("is_playing"),
            }

        elif tool_name == "search_tracks":
            resp = await client.get(
                f"{base}/search",
                headers=headers,
                params={"q": args["query"], "type": "track", "limit": args.get("limit", 5)},
            )
            if resp.status_code != 200:
                return {"error": f"Spotify search error: {resp.status_code}"}
            tracks = resp.json().get("tracks", {}).get("items", [])
            return [
                {
                    "name": t["name"],
                    "artist": ", ".join(a["name"] for a in t["artists"]),
                    "uri": t["uri"],
                    "album": t["album"]["name"],
                }
                for t in tracks
            ]

        elif tool_name == "play_track":
            resp = await client.put(
                f"{base}/me/player/play",
                headers=headers,
                json={"uris": [args["uri"]]},
            )
            return {"status": "playing" if resp.status_code in (200, 204) else f"error:{resp.status_code}"}

        elif tool_name == "pause":
            resp = await client.put(f"{base}/me/player/pause", headers=headers)
            return {"status": "paused" if resp.status_code in (200, 204) else f"error:{resp.status_code}"}

        elif tool_name == "skip_next":
            resp = await client.post(f"{base}/me/player/next", headers=headers)
            return {"status": "skipped" if resp.status_code in (200, 204) else f"error:{resp.status_code}"}

        elif tool_name == "list_playlists":
            resp = await client.get(
                f"{base}/me/playlists",
                headers=headers,
                params={"limit": args.get("limit", 20)},
            )
            if resp.status_code != 200:
                return {"error": f"Spotify error: {resp.status_code}"}
            playlists = resp.json().get("items", [])
            return [{"name": p["name"], "id": p["id"], "tracks": p["tracks"]["total"]} for p in playlists]

    return {"error": f"Unknown tool: {tool_name}"}


def register():
    register_provider(MCPProvider(
        id="spotify",
        name="Spotify",
        description="Music playback, search, and playlist management",
        icon="🎵",
        oauth_config=SPOTIFY_OAUTH,
        tools=TOOLS,
        scopes_required=SPOTIFY_OAUTH.scopes,
    ))
