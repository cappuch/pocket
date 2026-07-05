"""Session lifecycle and state management backed by Redis."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

import uuid

import redis.asyncio as redis

from app.config import settings
from app.models import Session

_pool: Optional[redis.Redis] = None


async def get_redis() -> redis.Redis:
    global _pool
    if _pool is None:
        _pool = redis.from_url(settings.redis_url, decode_responses=True)
    return _pool


def _session_key(session_id: str) -> str:
    return f"session:{session_id}"


async def create_session(user_id: str, metadata: dict | None = None) -> Session:
    r = await get_redis()
    session_id = str(uuid.uuid4())
    session = Session(
        session_id=session_id,
        user_id=user_id,
        active_generation_id=None,
        last_message_at=datetime.now(timezone.utc),
    )
    await r.set(_session_key(session_id), session.model_dump_json())
    # Also store conversation history
    await r.set(f"session:{session_id}:history", json.dumps([]))
    return session


async def get_session(session_id: str) -> Session | None:
    r = await get_redis()
    raw = await r.get(_session_key(session_id))
    if raw is None:
        return None
    return Session.model_validate_json(raw)


async def update_active_generation(session_id: str, generation_id: str) -> None:
    r = await get_redis()
    raw = await r.get(_session_key(session_id))
    if raw is None:
        return
    session = Session.model_validate_json(raw)
    session.active_generation_id = generation_id
    session.last_message_at = datetime.now(timezone.utc)
    await r.set(_session_key(session_id), session.model_dump_json())
    # Canonical key for cooperative cancellation checks
    await r.set(f"session:{session_id}:active_generation_id", generation_id)


async def get_active_generation_id(session_id: str) -> str | None:
    r = await get_redis()
    return await r.get(f"session:{session_id}:active_generation_id")


async def append_history(session_id: str, role: str, content: str) -> None:
    r = await get_redis()
    key = f"session:{session_id}:history"
    raw = await r.get(key)
    history = json.loads(raw) if raw else []
    history.append({"role": role, "content": content})
    # Keep last 50 messages for context window management
    history = history[-50:]
    await r.set(key, json.dumps(history))


async def get_history(session_id: str) -> list[dict]:
    r = await get_redis()
    raw = await r.get(f"session:{session_id}:history")
    return json.loads(raw) if raw else []
