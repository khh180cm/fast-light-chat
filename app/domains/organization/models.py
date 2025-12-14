"""Organization SQLAlchemy models."""

import uuid
from datetime import datetime, timezone
from enum import Enum as PyEnum

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.db.postgres import Base


class OrganizationStatus(str, PyEnum):
    """Organization status enum."""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETED = "deleted"


class OrganizationPlan(str, PyEnum):
    """Organization plan enum."""

    FREE = "free"
    STARTER = "starter"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class Organization(Base):
    """Organization model - represents a customer company."""

    __tablename__ = "organizations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    status = Column(
        Enum(OrganizationStatus, values_callable=lambda e: [x.value for x in e]),
        default=OrganizationStatus.ACTIVE,
        nullable=False,
    )
    plan = Column(
        Enum(OrganizationPlan, values_callable=lambda e: [x.value for x in e]),
        default=OrganizationPlan.FREE,
        nullable=False,
    )
    max_agents = Column(Integer, default=5, nullable=False)

    # Chat widget settings, auto-response configs, etc.
    settings = Column(JSONB, default=dict, nullable=False)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    environments = relationship(
        "Environment",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    agents = relationship(
        "Agent",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    settings_history = relationship(
        "OrganizationSettingsHistory",
        back_populates="organization",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Organization {self.slug}>"


class OrganizationSettingsHistory(Base):
    """Organization settings change history."""

    __tablename__ = "organization_settings_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    changed_by = Column(
        UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="SET NULL"),
        nullable=True,
    )
    field_name = Column(String(100), nullable=False)
    old_value = Column(JSONB, nullable=True)
    new_value = Column(JSONB, nullable=True)
    changed_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    organization = relationship("Organization", back_populates="settings_history")

    def __repr__(self) -> str:
        return f"<SettingsHistory {self.field_name} @ {self.changed_at}>"
