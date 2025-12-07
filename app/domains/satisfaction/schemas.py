"""Satisfaction survey schemas for API requests/responses."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.domains.satisfaction.models import SurveyStatus


class SatisfactionCreate(BaseModel):
    """Schema for submitting satisfaction survey response."""

    rating: int = Field(..., ge=1, le=5, description="Rating from 1-5 stars")
    feedback: str | None = Field(None, max_length=1000, description="Optional feedback")


class SatisfactionResponse(BaseModel):
    """Satisfaction survey response."""

    id: str
    chat_id: str
    status: SurveyStatus
    rating: int | None = None
    feedback: str | None = None
    triggered_by: str
    created_at: datetime
    responded_at: datetime | None = None


class SatisfactionStatistics(BaseModel):
    """Satisfaction survey statistics."""

    total_surveys: int = 0
    completed_surveys: int = 0
    skipped_surveys: int = 0
    expired_surveys: int = 0

    # Rating stats
    average_rating: float | None = None
    rating_distribution: dict[int, int] = Field(
        default_factory=lambda: {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    )

    # Response rate
    response_rate: float = 0.0  # completed / (completed + skipped + expired)


class SatisfactionListResponse(BaseModel):
    """Paginated satisfaction survey list response."""

    items: list[SatisfactionResponse]
    total: int
    has_more: bool
    next_cursor: str | None = None
