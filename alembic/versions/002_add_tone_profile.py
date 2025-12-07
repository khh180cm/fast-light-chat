"""Add tone profile tables.

Revision ID: 002_add_tone_profile
Revises: 001_initial_schema
Create Date: 2024-12-06

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create tone_profiles and tone_profile_versions tables."""
    # Create tone_profiles table
    op.create_table(
        "tone_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
            index=True,
        ),
        sa.Column("name", sa.String(100), nullable=False, default="기본 말투"),
        sa.Column(
            "prompt",
            sa.Text,
            nullable=False,
            default="""다음 규칙에 따라 메시지를 변환해주세요:
- 항상 존댓말을 사용합니다
- "고객님"이라는 호칭을 사용합니다
- 친절하고 공손한 어조를 유지합니다
- 부정적인 표현을 긍정적으로 바꿉니다
- 마무리에 "추가 문의사항이 있으시면 말씀해주세요"를 추가합니다""",
        ),
        sa.Column("is_active", sa.Boolean, nullable=False, default=True),
        sa.Column("current_version", sa.Integer, nullable=False, default=1),
        sa.Column(
            "created_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )

    # Create tone_profile_versions table
    op.create_table(
        "tone_profile_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "profile_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tone_profiles.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("prompt", sa.Text, nullable=False),
        sa.Column(
            "changed_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("change_note", sa.String(500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    """Drop tone profile tables."""
    op.drop_table("tone_profile_versions")
    op.drop_table("tone_profiles")
