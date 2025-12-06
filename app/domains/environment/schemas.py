"""Environment domain schemas - request/response models."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.domains.environment.models import EnvironmentType


class EnvironmentCreate(BaseModel):
    """Schema for creating a new environment."""

    name: str = Field(..., min_length=1, max_length=100)
    env_type: EnvironmentType
    allowed_domains: list[str] = Field(default_factory=list)


class EnvironmentUpdate(BaseModel):
    """Schema for updating an environment."""

    name: str | None = Field(None, max_length=100)
    allowed_domains: list[str] | None = None


class EnvironmentResponse(BaseModel):
    """Schema for environment response."""

    id: UUID
    name: str
    env_type: str
    plugin_key: str
    api_key: str
    allowed_domains: list[str]
    is_active: bool
    key_rotated_at: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True


class EnvironmentWithSecretResponse(EnvironmentResponse):
    """Schema for environment response with API secret (shown only once)."""

    api_secret: str = Field(..., description="API Secret (shown only once)")


class RotateKeysResponse(BaseModel):
    """Schema for key rotation response."""

    id: UUID
    name: str
    env_type: str
    plugin_key: str
    api_key: str
    api_secret: str = Field(..., description="API Secret (shown only once)")
    key_rotated_at: datetime

    class Config:
        from_attributes = True
