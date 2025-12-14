"""Satisfaction survey models for MongoDB."""

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class SurveyStatus(str, Enum):
    """Survey status enum."""

    PENDING = "pending"  # Survey sent, awaiting response
    COMPLETED = "completed"  # User submitted response
    SKIPPED = "skipped"  # User skipped/closed without responding
    EXPIRED = "expired"  # Survey expired (auto-closed chats)


class SatisfactionSurvey(BaseModel):
    """Satisfaction survey document model for MongoDB.

    Collection: satisfaction_surveys_{org_id}_{env_type}
    """

    id: str | None = Field(None, alias="_id")
    org_id: str
    env_type: str

    # Reference
    chat_id: str
    user_id: str
    member_id: str
    agent_id: str | None = None  # Agent who handled the chat

    # Survey data
    status: SurveyStatus = SurveyStatus.PENDING
    rating: int | None = Field(None, ge=1, le=5)  # 1-5 stars
    feedback: str | None = Field(None, max_length=1000)

    # Trigger info
    triggered_by: str  # "agent_resolve" | "user_close" | "auto_close"

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    responded_at: datetime | None = None
    expires_at: datetime | None = None

    class Config:
        populate_by_name = True
        use_enum_values = True
