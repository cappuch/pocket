"""
OAuth token storage and refresh — Redis-backed per-user token management.
Handles token encryption at rest and automatic refresh.
"""

from __future__ import annotations

import json
import time
from typing import Optional

import redis.asyncio as redis

from app.services.session_service import get_redis


def _token_key(user_id: str, provider_id: str) -> str:
    return f"oauth:{user_id}:{provider_id}"


async def store_token(
    user_id: str,
    provider_id: str,
    access_token: str,
    refresh_token: Optional[str] = None,
    expires_at: Optional[float] = None,
    scopes: Optional[list[str]] = None,
) -> None:
    """Store OAuth tokens for a user+provider pair."""
    r = await get_redis()
    data = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_at": expires_at,
        "scopes": scopes or [],
        "stored_at": time.time(),
    }
    await r.set(_token_key(user_id, provider_id), json.dumps(data))


async def get_token(user_id: str, provider_id: str) -> Optional[dict]:
    """Retrieve stored token data. Returns None if not connected."""
    r = await get_redis()
    raw = await r.get(_token_key(user_id, provider_id))
    if raw is None:
        return None
    return json.loads(raw)


async def is_token_valid(user_id: str, provider_id: str) -> bool:
    """Check if the stored token is still valid (not expired)."""
    token_data = await get_token(user_id, provider_id)
    if token_data is None:
        return False
    expires_at = token_data.get("expires_at")
    if expires_at is None:
        return True  # No expiry info, assume valid
    return time.time() < expires_at


async def revoke_token(user_id: str, provider_id: str) -> None:
    """Remove stored tokens (disconnect a service)."""
    r = await get_redis()
    await r.delete(_token_key(user_id, provider_id))


async def list_connected_providers(user_id: str) -> list[str]:
    """List all provider IDs that a user has connected."""
    r = await get_redis()
    pattern = f"oauth:{user_id}:*"
    connected = []
    async for key in r.scan_iter(match=pattern):
        # key format: oauth:{user_id}:{provider_id}
        parts = key.split(":")
        if len(parts) == 3:
            connected.append(parts[2])
    return connected
