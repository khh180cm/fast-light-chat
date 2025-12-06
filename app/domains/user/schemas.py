"""User domain schemas - request/response models."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.domains.user.models import UserProfile, UserStatus


class UserCreate(BaseModel):
    """Schema for creating/registering a user."""

    member_id: str = Field(..., min_length=1, max_length=255, description="External user ID")
    profile: UserProfile | None = None
    custom_fields: dict[str, Any] | None = None
    tags: list[str] | None = None


class UserUpdate(BaseModel):
    """Schema for updating user information."""

    profile: UserProfile | None = None
    custom_fields: dict[str, Any] | None = None
    tags: list[str] | None = None


class UserResponse(BaseModel):
    """Schema for user response."""

    id: str
    member_id: str
    org_id: str
    env_type: str
    profile: UserProfile
    custom_fields: dict[str, Any]
    tags: list[str]
    total_chats: int
    total_messages: int
    status: UserStatus
    first_seen_at: datetime
    last_seen_at: datetime
    created_at: datetime
    updated_at: datetime


class UserListResponse(BaseModel):
    """Schema for user list response."""

    items: list[UserResponse]
    total: int
    skip: int
    limit: int


class TempUserCreate(BaseModel):
    """Schema for creating a temporary user."""

    session_id: str = Field(..., min_length=1, max_length=128)
    profile: UserProfile | None = None


class TempUserResponse(BaseModel):
    """Schema for temporary user response."""

    session_id: str
    org_id: str
    env_type: str
    profile: UserProfile
    chat_ids: list[str]
    created_at: datetime
    last_activity_at: datetime


class ConvertTempUserRequest(BaseModel):
    """Schema for converting temp user to permanent user."""

    session_id: str = Field(..., description="Temporary user session ID")
    member_id: str = Field(..., description="New permanent member ID")
