"""Chat domain schemas - request/response models."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.domains.chat.models import (
    Attachment,
    ChatStatus,
    LastMessage,
    MessageType,
    SenderType,
)


# ============================================================
# Chat Schemas
# ============================================================


class ChatCreate(BaseModel):
    """Schema for creating a new chat."""

    member_id: str = Field(..., description="External member ID")
    user_id: str | None = Field(None, description="MongoDB User ID (optional for temp users)")
    session_id: str | None = Field(None, description="Session ID for temp users")
    initial_message: str | None = Field(None, max_length=5000, description="Initial message")
    metadata: dict[str, Any] | None = None


class ChatUpdate(BaseModel):
    """Schema for updating a chat."""

    tags: list[str] | None = None
    metadata: dict[str, Any] | None = None


class ChatAssign(BaseModel):
    """Schema for assigning chat to an agent."""

    agent_id: str = Field(..., description="Agent ID to assign")


class ChatResponse(BaseModel):
    """Schema for chat response."""

    id: str
    org_id: str
    env_type: str
    user_id: str
    member_id: str
    assigned_agent_id: str | None
    status: ChatStatus
    message_count: int
    unread_count_user: int
    unread_count_agent: int
    last_message: LastMessage | None
    tags: list[str]
    metadata: dict[str, Any]
    created_at: datetime
    first_response_at: datetime | None
    resolved_at: datetime | None
    closed_at: datetime | None
    updated_at: datetime


class ChatListResponse(BaseModel):
    """Schema for chat list response."""

    items: list[ChatResponse]
    total: int
    cursor: str | None = None  # Next cursor for pagination
    has_more: bool = False


class ChatStatistics(BaseModel):
    """Schema for chat statistics."""

    total_chats: int
    waiting_chats: int
    active_chats: int
    resolved_chats: int
    closed_chats: int
    avg_response_time_seconds: float | None
    avg_resolution_time_seconds: float | None


# ============================================================
# Message Schemas
# ============================================================


class MessageCreate(BaseModel):
    """Schema for creating a new message."""

    content: str = Field(..., min_length=1, max_length=5000)
    message_type: MessageType = MessageType.TEXT
    attachments: list[Attachment] | None = None


class MessageResponse(BaseModel):
    """Schema for message response."""

    id: str
    chat_id: str
    sender_type: SenderType
    sender_id: str
    message_type: MessageType
    content: str
    attachments: list[Attachment]
    read_by_user: bool
    read_by_agent: bool
    created_at: datetime
    updated_at: datetime


class MessageListResponse(BaseModel):
    """Schema for message list response (cursor pagination)."""

    items: list[MessageResponse]
    cursor: str | None = None  # Cursor for next page (base64 encoded timestamp + id)
    has_more: bool = False


class MarkReadRequest(BaseModel):
    """Schema for marking messages as read."""

    last_read_message_id: str | None = None  # Mark all messages up to this ID as read
