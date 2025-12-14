"""Change datetime columns to timezone aware.

Revision ID: 003_datetime_timezone_aware
Revises: 002_add_tone_profile
Create Date: 2024-12-14

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Convert TIMESTAMP WITHOUT TIME ZONE to TIMESTAMP WITH TIME ZONE."""

    # Organizations table
    op.execute("ALTER TABLE organizations ALTER COLUMN created_at TYPE TIMESTAMP WITH TIME ZONE")
    op.execute("ALTER TABLE organizations ALTER COLUMN updated_at TYPE TIMESTAMP WITH TIME ZONE")

    # Organization settings history table
    op.execute("ALTER TABLE organization_settings_history ALTER COLUMN changed_at TYPE TIMESTAMP WITH TIME ZONE")

    # Environments table
    op.execute("ALTER TABLE environments ALTER COLUMN key_rotated_at TYPE TIMESTAMP WITH TIME ZONE")
    op.execute("ALTER TABLE environments ALTER COLUMN created_at TYPE TIMESTAMP WITH TIME ZONE")
    op.execute("ALTER TABLE environments ALTER COLUMN updated_at TYPE TIMESTAMP WITH TIME ZONE")

    # Agents table
    op.execute("ALTER TABLE agents ALTER COLUMN last_login_at TYPE TIMESTAMP WITH TIME ZONE")
    op.execute("ALTER TABLE agents ALTER COLUMN created_at TYPE TIMESTAMP WITH TIME ZONE")
    op.execute("ALTER TABLE agents ALTER COLUMN updated_at TYPE TIMESTAMP WITH TIME ZONE")

    # Refresh tokens table
    op.execute("ALTER TABLE refresh_tokens ALTER COLUMN expires_at TYPE TIMESTAMP WITH TIME ZONE")
    op.execute("ALTER TABLE refresh_tokens ALTER COLUMN created_at TYPE TIMESTAMP WITH TIME ZONE")
    op.execute("ALTER TABLE refresh_tokens ALTER COLUMN revoked_at TYPE TIMESTAMP WITH TIME ZONE")

    # Tone profiles table
    op.execute("ALTER TABLE tone_profiles ALTER COLUMN created_at TYPE TIMESTAMP WITH TIME ZONE")
    op.execute("ALTER TABLE tone_profiles ALTER COLUMN updated_at TYPE TIMESTAMP WITH TIME ZONE")

    # Tone profile versions table
    op.execute("ALTER TABLE tone_profile_versions ALTER COLUMN created_at TYPE TIMESTAMP WITH TIME ZONE")


def downgrade() -> None:
    """Convert TIMESTAMP WITH TIME ZONE back to TIMESTAMP WITHOUT TIME ZONE."""

    # Organizations table
    op.execute("ALTER TABLE organizations ALTER COLUMN created_at TYPE TIMESTAMP WITHOUT TIME ZONE")
    op.execute("ALTER TABLE organizations ALTER COLUMN updated_at TYPE TIMESTAMP WITHOUT TIME ZONE")

    # Organization settings history table
    op.execute("ALTER TABLE organization_settings_history ALTER COLUMN changed_at TYPE TIMESTAMP WITHOUT TIME ZONE")

    # Environments table
    op.execute("ALTER TABLE environments ALTER COLUMN key_rotated_at TYPE TIMESTAMP WITHOUT TIME ZONE")
    op.execute("ALTER TABLE environments ALTER COLUMN created_at TYPE TIMESTAMP WITHOUT TIME ZONE")
    op.execute("ALTER TABLE environments ALTER COLUMN updated_at TYPE TIMESTAMP WITHOUT TIME ZONE")

    # Agents table
    op.execute("ALTER TABLE agents ALTER COLUMN last_login_at TYPE TIMESTAMP WITHOUT TIME ZONE")
    op.execute("ALTER TABLE agents ALTER COLUMN created_at TYPE TIMESTAMP WITHOUT TIME ZONE")
    op.execute("ALTER TABLE agents ALTER COLUMN updated_at TYPE TIMESTAMP WITHOUT TIME ZONE")

    # Refresh tokens table
    op.execute("ALTER TABLE refresh_tokens ALTER COLUMN expires_at TYPE TIMESTAMP WITHOUT TIME ZONE")
    op.execute("ALTER TABLE refresh_tokens ALTER COLUMN created_at TYPE TIMESTAMP WITHOUT TIME ZONE")
    op.execute("ALTER TABLE refresh_tokens ALTER COLUMN revoked_at TYPE TIMESTAMP WITHOUT TIME ZONE")

    # Tone profiles table
    op.execute("ALTER TABLE tone_profiles ALTER COLUMN created_at TYPE TIMESTAMP WITHOUT TIME ZONE")
    op.execute("ALTER TABLE tone_profiles ALTER COLUMN updated_at TYPE TIMESTAMP WITHOUT TIME ZONE")

    # Tone profile versions table
    op.execute("ALTER TABLE tone_profile_versions ALTER COLUMN created_at TYPE TIMESTAMP WITHOUT TIME ZONE")
