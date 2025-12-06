"""Initial schema - organizations, environments, agents.

Revision ID: 001
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Organizations table
    op.create_table(
        'organizations',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=100), nullable=False),
        sa.Column(
            'status',
            sa.Enum('active', 'suspended', 'deleted', name='organizationstatus'),
            nullable=False,
            server_default='active',
        ),
        sa.Column(
            'plan',
            sa.Enum('free', 'starter', 'pro', 'enterprise', name='organizationplan'),
            nullable=False,
            server_default='free',
        ),
        sa.Column('max_agents', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('settings', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_organizations_slug', 'organizations', ['slug'], unique=True)

    # Environments table
    op.create_table(
        'environments',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column(
            'env_type',
            sa.Enum('development', 'staging', 'production', name='environmenttype'),
            nullable=False,
        ),
        sa.Column('plugin_key', sa.String(length=64), nullable=False),
        sa.Column('api_key', sa.String(length=64), nullable=False),
        sa.Column('api_secret_hash', sa.String(length=128), nullable=False),
        sa.Column('key_rotated_at', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('allowed_domains', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_environments_organization_id', 'environments', ['organization_id'])
    op.create_index('ix_environments_plugin_key', 'environments', ['plugin_key'], unique=True)
    op.create_index('ix_environments_api_key', 'environments', ['api_key'], unique=True)

    # Agents table
    op.create_table(
        'agents',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=128), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('nickname', sa.String(length=50), nullable=True),
        sa.Column('avatar_url', sa.String(length=500), nullable=True),
        sa.Column(
            'role',
            sa.Enum('super_admin', 'admin', 'manager', 'agent', name='agentrole'),
            nullable=False,
            server_default='agent',
        ),
        sa.Column(
            'status',
            sa.Enum('online', 'away', 'busy', 'offline', name='agentstatus'),
            nullable=False,
            server_default='offline',
        ),
        sa.Column('max_concurrent_chats', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('current_chat_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('last_login_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_agents_organization_id', 'agents', ['organization_id'])
    op.create_index('ix_agents_email', 'agents', ['email'], unique=True)

    # Refresh tokens table
    op.create_table(
        'refresh_tokens',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('agent_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('token_hash', sa.String(length=128), nullable=False),
        sa.Column('device_info', sa.String(length=255), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('revoked_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_refresh_tokens_agent_id', 'refresh_tokens', ['agent_id'])
    op.create_index('ix_refresh_tokens_token_hash', 'refresh_tokens', ['token_hash'], unique=True)

    # Organization settings history table
    op.create_table(
        'organization_settings_history',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('changed_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('field_name', sa.String(length=100), nullable=False),
        sa.Column('old_value', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('new_value', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('changed_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['changed_by'], ['agents.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_organization_settings_history_organization_id', 'organization_settings_history', ['organization_id'])


def downgrade() -> None:
    op.drop_index('ix_organization_settings_history_organization_id', table_name='organization_settings_history')
    op.drop_table('organization_settings_history')

    op.drop_index('ix_refresh_tokens_token_hash', table_name='refresh_tokens')
    op.drop_index('ix_refresh_tokens_agent_id', table_name='refresh_tokens')
    op.drop_table('refresh_tokens')

    op.drop_index('ix_agents_email', table_name='agents')
    op.drop_index('ix_agents_organization_id', table_name='agents')
    op.drop_table('agents')

    op.drop_index('ix_environments_api_key', table_name='environments')
    op.drop_index('ix_environments_plugin_key', table_name='environments')
    op.drop_index('ix_environments_organization_id', table_name='environments')
    op.drop_table('environments')

    op.drop_index('ix_organizations_slug', table_name='organizations')
    op.drop_table('organizations')

    # Drop enums
    op.execute('DROP TYPE IF EXISTS organizationstatus')
    op.execute('DROP TYPE IF EXISTS organizationplan')
    op.execute('DROP TYPE IF EXISTS environmenttype')
    op.execute('DROP TYPE IF EXISTS agentrole')
    op.execute('DROP TYPE IF EXISTS agentstatus')
