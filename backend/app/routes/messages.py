import asyncio
import json
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query
from sse_starlette.sse import EventSourceResponse

from app.models import (
    BatchRequest,
    CancelRequest,
    MessageAccepted,
    SendMessageRequest,
)
from app.services import generation_service, session_service

router = APIRouter(prefix="/messages", tags=["messages"])

# Store active generators so /stream can pick them up
_active_streams: dict[str, object] = {}


@router.post("", status_code=202, response_model=MessageAccepted)
async def send_message(req: SendMessageRequest):
    session = await session_service.get_session(req.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    was_replacing = generation_service.was_replacing_previous(req.session_id)

    generation_id, stream = await generation_service.start_generation(
        req.session_id, req.message.content
    )

    # Store stream for SSE pickup
    _active_streams[req.session_id] = stream

    return MessageAccepted(
        session_id=req.session_id,
        message_id=req.message.client_message_id,
        generation_id=generation_id,
        status="replacing_previous" if was_replacing else "queued",
    )


@router.get("/stream")
async def stream_messages(session_id: str = Query(...)):
    session = await session_service.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    stream = _active_streams.get(session_id)
    if stream is None:
        raise HTTPException(status_code=404, detail="No active generation")

    async def event_generator():
        try:
            async for chunk in stream:
                yield {
                    "event": "message",
                    "data": json.dumps(chunk),
                }
                if chunk.get("done"):
                    break
        finally:
            _active_streams.pop(session_id, None)

    return EventSourceResponse(event_generator())


@router.post("/cancel")
async def cancel_generation(req: CancelRequest):
    session = await session_service.get_session(req.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    await generation_service.cancel_generation(req.session_id)
    return {"status": "cancelled", "session_id": req.session_id}


@router.post("/batch", status_code=202)
async def send_batch(req: BatchRequest):
    """
    Accept burst messages and coalesce them into a single generation.
    Combines all message contents with newlines.
    """
    session = await session_service.get_session(req.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    # Coalesce all messages into one input
    combined = "\n".join(msg.content for msg in req.messages)

    generation_id, stream = await generation_service.start_generation(
        req.session_id, combined
    )

    _active_streams[req.session_id] = stream

    return {
        "status": "accepted",
        "session_id": req.session_id,
        "generation_id": generation_id,
        "coalesced_count": len(req.messages),
    }
