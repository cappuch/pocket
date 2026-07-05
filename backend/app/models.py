from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# --- Session ---

class CreateSessionRequest(BaseModel):
    user_id: str
    metadata: dict | None = None


class Session(BaseModel):
    session_id: str
    user_id: str
    active_generation_id: Optional[str] = None
    last_message_at: Optional[datetime] = None


# --- Messages ---

class IncomingMessage(BaseModel):
    role: str = "user"
    content: str
    client_message_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class SendMessageRequest(BaseModel):
    session_id: str
    message: IncomingMessage
    interrupt_previous: bool = True


class MessageAccepted(BaseModel):
    session_id: str
    message_id: str
    generation_id: str
    status: str  # "queued" | "replacing_previous"


class CancelRequest(BaseModel):
    session_id: str
    reason: Optional[str] = None


class BatchRequest(BaseModel):
    session_id: str
    messages: list[IncomingMessage]


# --- SSE events ---

class StreamToken(BaseModel):
    """A single chunk emitted over SSE."""
    generation_id: str
    token: str
    done: bool = False


class MessageChunk(BaseModel):
    """A complete message bubble in the texting format."""
    generation_id: str
    message_index: int
    content: str
    delay_seconds: float
    done: bool = False
