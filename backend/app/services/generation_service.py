"""Generation orchestration — implements "latest message wins" cancellation."""

from __future__ import annotations

from typing import AsyncGenerator

import redis.asyncio as redis

from app.config import settings
from app.services import session_service, llm_service

# In-memory version counters (per session). In production, store in Redis.
_generation_versions: dict[str, int] = {}


async def start_generation(session_id: str, user_content: str) -> tuple[str, AsyncGenerator]:
    """
    Start a new generation for a session. Returns (generation_id, stream).
    Automatically invalidates any previous generation.
    """
    # Increment version
    version = _generation_versions.get(session_id, 0) + 1
    _generation_versions[session_id] = version
    generation_id = f"{session_id}:{version}"

    # Mark as active (this implicitly cancels previous generations)
    await session_service.update_active_generation(session_id, generation_id)

    # Append user message to history
    await session_service.append_history(session_id, "user", user_content)

    # Create the async generator
    stream = llm_service.generate_response(session_id, generation_id)

    return generation_id, stream


async def cancel_generation(session_id: str) -> bool:
    """Explicitly cancel the active generation for a session."""
    r = await session_service.get_redis()
    # Set active_generation_id to a sentinel that no worker will match
    await r.set(f"session:{session_id}:active_generation_id", "cancelled")
    return True


def was_replacing_previous(session_id: str) -> bool:
    """Check if this generation replaced a previous one."""
    return _generation_versions.get(session_id, 0) > 1
