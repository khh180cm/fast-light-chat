"""Tone Profile schemas for API requests/responses."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ToneProfileCreate(BaseModel):
    """Schema for creating a tone profile."""

    name: str = Field(..., min_length=1, max_length=100)
    prompt: str = Field(..., min_length=10, max_length=5000)


class ToneProfileUpdate(BaseModel):
    """Schema for updating a tone profile."""

    name: str | None = Field(None, min_length=1, max_length=100)
    prompt: str | None = Field(None, min_length=10, max_length=5000)
    change_note: str | None = Field(None, max_length=500)


class ToneProfileResponse(BaseModel):
    """Tone profile response."""

    id: UUID
    organization_id: UUID
    name: str
    prompt: str
    is_active: bool
    current_version: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ToneProfileVersionResponse(BaseModel):
    """Tone profile version response."""

    id: UUID
    profile_id: UUID
    version: int
    name: str
    prompt: str
    changed_by: UUID | None
    change_note: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class ToneProfileVersionListResponse(BaseModel):
    """List of tone profile versions."""

    items: list[ToneProfileVersionResponse]
    total: int


# ============================================================
# AI Transformation Schemas
# ============================================================


class MessageTransformRequest(BaseModel):
    """Request to transform a message using AI."""

    original_message: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Original message to transform",
    )


class MessageTransformResponse(BaseModel):
    """Response with transformed message."""

    original_message: str
    transformed_message: str
    tone_profile_name: str
    tone_profile_version: int


class MessageDraftCreate(BaseModel):
    """Create a message draft for review before sending."""

    chat_id: str
    original_message: str = Field(..., min_length=1, max_length=2000)
    use_ai_transform: bool = True


class MessageDraftResponse(BaseModel):
    """Message draft response."""

    id: str
    chat_id: str
    original_message: str
    transformed_message: str | None = None
    final_message: str  # What will actually be sent (original or edited transformed)
    status: str  # "pending" | "sent" | "discarded"
    created_at: datetime


class MessageDraftUpdate(BaseModel):
    """Update a message draft."""

    final_message: str = Field(..., min_length=1, max_length=2000)


class MessageDraftSend(BaseModel):
    """Send a message draft."""

    use_original: bool = False  # If True, send original instead of transformed
