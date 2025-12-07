"""Tone Profile SQLAlchemy models.

Tone Profile is organization-wide settings for AI message style transformation.
Stored in PostgreSQL as it's structured configuration data.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.postgres import Base


class ToneProfile(Base):
    """Tone Profile model - organization's AI message style settings.

    This defines how AI should transform agent messages to match
    the organization's communication style.
    """

    __tablename__ = "tone_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,  # One profile per organization
        index=True,
    )

    # Profile name (e.g., "친근한 상담원", "공식 비즈니스")
    name = Column(String(100), nullable=False, default="기본 말투")

    # The actual prompt/instructions for AI
    # This is the core content that tells AI how to transform messages
    prompt = Column(
        Text,
        nullable=False,
        default="""다음 규칙에 따라 메시지를 변환해주세요:
- 항상 존댓말을 사용합니다
- "고객님"이라는 호칭을 사용합니다
- 친절하고 공손한 어조를 유지합니다
- 부정적인 표현을 긍정적으로 바꿉니다
- 마무리에 "추가 문의사항이 있으시면 말씀해주세요"를 추가합니다""",
    )

    # Whether this profile is active
    is_active = Column(Boolean, default=True, nullable=False)

    # Current version number (for tracking)
    current_version = Column(Integer, default=1, nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    versions = relationship(
        "ToneProfileVersion",
        back_populates="profile",
        cascade="all, delete-orphan",
        order_by="desc(ToneProfileVersion.version)",
    )

    def __repr__(self) -> str:
        return f"<ToneProfile {self.name} v{self.current_version}>"


class ToneProfileVersion(Base):
    """Tone Profile version history.

    Keeps track of all previous versions for rollback capability.
    """

    __tablename__ = "tone_profile_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tone_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Version info
    version = Column(Integer, nullable=False)
    name = Column(String(100), nullable=False)
    prompt = Column(Text, nullable=False)

    # Who made this change
    changed_by = Column(
        UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Change description (optional)
    change_note = Column(String(500), nullable=True)

    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationship
    profile = relationship("ToneProfile", back_populates="versions")

    def __repr__(self) -> str:
        return f"<ToneProfileVersion v{self.version}>"
