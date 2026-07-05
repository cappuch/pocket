from fastapi import APIRouter, HTTPException

from app.models import CreateSessionRequest, Session
from app.services import session_service

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", status_code=201, response_model=Session)
async def create_session(req: CreateSessionRequest):
    session = await session_service.create_session(req.user_id, req.metadata)
    return session


@router.get("/{session_id}", response_model=Session)
async def get_session(session_id: str):
    session = await session_service.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session
