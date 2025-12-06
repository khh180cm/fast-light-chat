"""Agent domain schemas - request/response models."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.domains.agent.models import AgentRole, AgentStatus


class AgentCreate(BaseModel):
    """Schema for creating a new agent."""

    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    name: str = Field(..., min_length=1, max_length=100)
    nickname: str | None = Field(None, max_length=50)
    role: AgentRole = AgentRole.AGENT
    max_concurrent_chats: int = Field(default=5, ge=1, le=50)


class AgentUpdate(BaseModel):
    """Schema for updating an agent."""

    name: str | None = Field(None, max_length=100)
    nickname: str | None = Field(None, max_length=50)
    avatar_url: str | None = Field(None, max_length=500)
    max_concurrent_chats: int | None = Field(None, ge=1, le=50)


class AgentStatusUpdate(BaseModel):
    """Schema for updating agent status."""

    status: AgentStatus


class AgentResponse(BaseModel):
    """Schema for agent response."""

    id: UUID
    organization_id: UUID
    email: str
    name: str
    nickname: str | None
    avatar_url: str | None
    role: AgentRole
    status: AgentStatus
    max_concurrent_chats: int
    current_chat_count: int
    is_active: bool
    last_login_at: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True


class AgentListResponse(BaseModel):
    """Schema for agent list response."""

    items: list[AgentResponse]
    total: int
