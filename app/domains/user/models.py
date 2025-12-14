"""User domain models for MongoDB.

Users are stored in MongoDB with organization-specific collections.
Collection naming: users_{org_id}_{env_type}
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class UserStatus(str, Enum):
    """User status enum."""

    ACTIVE = "active"
    BLOCKED = "blocked"
    DELETED = "deleted"


class UserProfile(BaseModel):
    """User profile information."""

    name: str | None = None
    email: str | None = None
    phone: str | None = None
    avatar_url: str | None = None


class User(BaseModel):
    """User document model for MongoDB.

    This represents an end-user (customer) who uses the chat widget.
    """

    id: str | None = Field(None, alias="_id")
    member_id: str = Field(..., description="External user ID from client's system")
    org_id: str = Field(..., description="Organization ID")
    env_type: str = Field(..., description="Environment type (development/staging/production)")

    # Profile
    profile: UserProfile = Field(default_factory=UserProfile)

    # Custom fields (flexible key-value store)
    custom_fields: dict[str, Any] = Field(default_factory=dict)

    # Tags for filtering/grouping
    tags: list[str] = Field(default_factory=list)

    # Statistics
    total_chats: int = Field(default=0)
    total_messages: int = Field(default=0)

    # Status
    status: UserStatus = Field(default=UserStatus.ACTIVE)

    # Timestamps
    first_seen_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_seen_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Config:
        populate_by_name = True
        use_enum_values = True


class TempUser(BaseModel):
    """Temporary user stored in Redis.

    For anonymous users who haven't logged in yet.
    TTL: 24 hours
    """

    session_id: str = Field(..., description="Unique session ID")
    org_id: str
    env_type: str

    # Temporary profile
    profile: UserProfile = Field(default_factory=UserProfile)

    # Conversation history (stored temporarily)
    chat_ids: list[str] = Field(default_factory=list)

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_activity_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
