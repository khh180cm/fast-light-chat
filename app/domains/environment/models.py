"""Environment SQLAlchemy models."""

import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.db.postgres import Base


class EnvironmentType(str, PyEnum):
    """Environment type enum."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class Environment(Base):
    """Environment model - represents dev/staging/prod environments with API keys."""

    __tablename__ = "environments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(String(100), nullable=False)
    env_type = Column(
        Enum(EnvironmentType, values_callable=lambda e: [x.value for x in e]),
        nullable=False,
    )

    # SDK용 Plugin Key (public)
    plugin_key = Column(String(64), unique=True, nullable=False, index=True)

    # 백엔드 연동용 API Key/Secret (private)
    api_key = Column(String(64), unique=True, nullable=False, index=True)
    api_secret_hash = Column(String(128), nullable=False)

    # Key management
    key_rotated_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    # Allowed domains for CORS
    allowed_domains = Column(JSONB, default=list, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    organization = relationship("Organization", back_populates="environments")

    def __repr__(self) -> str:
        return f"<Environment {self.name} ({self.env_type.value})>"
