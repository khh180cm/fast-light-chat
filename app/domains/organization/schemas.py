"""Organization domain schemas - request/response models."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.domains.organization.models import OrganizationPlan, OrganizationStatus


class OrganizationCreate(BaseModel):
    """Schema for creating a new organization."""

    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$")
    plan: OrganizationPlan = OrganizationPlan.FREE
    max_agents: int = Field(default=5, ge=1, le=1000)


class OrganizationUpdate(BaseModel):
    """Schema for updating an organization."""

    name: str | None = Field(None, max_length=255)
    plan: OrganizationPlan | None = None
    max_agents: int | None = Field(None, ge=1, le=1000)
    settings: dict | None = None


class OrganizationResponse(BaseModel):
    """Schema for organization response."""

    id: UUID
    name: str
    slug: str
    status: OrganizationStatus
    plan: OrganizationPlan
    max_agents: int
    settings: dict
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class OrganizationWithKeysResponse(OrganizationResponse):
    """Schema for organization with API keys."""

    environments: list["EnvironmentResponse"]


class EnvironmentResponse(BaseModel):
    """Schema for environment response."""

    id: UUID
    name: str
    env_type: str
    plugin_key: str
    api_key: str
    # Note: api_secret is not returned after creation
    allowed_domains: list[str]
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class EnvironmentCreateResponse(EnvironmentResponse):
    """Schema for environment creation response (includes secret)."""

    api_secret: str = Field(..., description="API Secret (shown only once)")
