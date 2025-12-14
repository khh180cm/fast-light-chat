"""Chat domain models for MongoDB.

Chats and messages are stored in MongoDB with organization-specific collections.
Collection naming: chats_{org_id}_{env_type}, messages_{org_id}_{env_type}
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ChatStatus(str, Enum):
    """Chat status enum."""

    WAITING = "waiting"  # Waiting for agent assignment
    ACTIVE = "active"  # Active conversation
    RESOLVED = "resolved"  # Issue resolved
    CLOSED = "closed"  # Chat closed


class SenderType(str, Enum):
    """Message sender type enum."""

    USER = "user"
    AGENT = "agent"
    BOT = "bot"
    SYSTEM = "system"


class MessageType(str, Enum):
    """Message type enum."""

    TEXT = "text"
    IMAGE = "image"
    FILE = "file"
    SYSTEM = "system"


class Attachment(BaseModel):
    """File/image attachment model."""

    file_name: str
    file_url: str
    file_type: str
    file_size: int  # bytes


class LastMessage(BaseModel):
    """Last message summary for chat list display."""

    sender_type: SenderType
    content: str
    message_type: MessageType = MessageType.TEXT
    created_at: datetime


class Chat(BaseModel):
    """Chat document model for MongoDB."""

    id: str | None = Field(None, alias="_id")
    org_id: str
    env_type: str

    # Participants
    user_id: str = Field(..., description="MongoDB User ID")
    member_id: str = Field(..., description="External member ID for display")
    assigned_agent_id: str | None = None

    # Status
    status: ChatStatus = ChatStatus.WAITING

    # Message stats
    message_count: int = 0
    unread_count_user: int = 0  # Unread by user
    unread_count_agent: int = 0  # Unread by agent

    # Last message preview
    last_message: LastMessage | None = None

    # Metadata
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    first_response_at: datetime | None = None  # When agent first responded
    resolved_at: datetime | None = None
    closed_at: datetime | None = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Config:
        populate_by_name = True
        use_enum_values = True


class Message(BaseModel):
    """Message document model for MongoDB."""

    id: str | None = Field(None, alias="_id")
    chat_id: str
    org_id: str

    # Sender info
    sender_type: SenderType
    sender_id: str  # User ID or Agent ID

    # Content
    message_type: MessageType = MessageType.TEXT
    content: str = Field(..., max_length=5000)

    # Attachments
    attachments: list[Attachment] = Field(default_factory=list)

    # Read status
    read_by_user: bool = False
    read_by_agent: bool = False

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Config:
        populate_by_name = True
        use_enum_values = True
