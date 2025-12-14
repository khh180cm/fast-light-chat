"""Environment domain service - environment and API key management."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.security import (
    generate_api_key,
    generate_api_secret,
    generate_plugin_key,
    hash_password,
)
from app.domains.environment.models import Environment, EnvironmentType


class EnvironmentService:
    """Environment management service."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_environment(self, env_id: UUID) -> Environment:
        """
        Get environment by ID.

        Args:
            env_id: Environment ID

        Returns:
            Environment

        Raises:
            NotFoundError: If environment not found
        """
        result = await self.db.execute(
            select(Environment).where(Environment.id == env_id)
        )
        env = result.scalar_one_or_none()

        if not env:
            raise NotFoundError("Environment", str(env_id))

        return env

    async def get_environment_by_plugin_key(
        self, plugin_key: str
    ) -> Environment | None:
        """
        Get environment by plugin key.

        Args:
            plugin_key: Plugin key for SDK authentication

        Returns:
            Environment or None
        """
        result = await self.db.execute(
            select(Environment).where(
                Environment.plugin_key == plugin_key,
                Environment.is_active == True,
            )
        )
        return result.scalar_one_or_none()

    async def get_environment_by_api_key(
        self, api_key: str
    ) -> Environment | None:
        """
        Get environment by API key.

        Args:
            api_key: API key for backend authentication

        Returns:
            Environment or None
        """
        result = await self.db.execute(
            select(Environment).where(
                Environment.api_key == api_key,
                Environment.is_active == True,
            )
        )
        return result.scalar_one_or_none()

    async def create_environment(
        self,
        org_id: UUID,
        name: str,
        env_type: EnvironmentType,
        allowed_domains: list[str] = None,
    ) -> tuple[Environment, str]:
        """
        Create a new environment.

        Args:
            org_id: Organization ID
            name: Environment name
            env_type: Environment type (development/staging/production)
            allowed_domains: List of allowed CORS domains

        Returns:
            Tuple of (environment, api_secret)
        """
        api_secret = generate_api_secret()

        env = Environment(
            organization_id=org_id,
            name=name,
            env_type=env_type,
            plugin_key=generate_plugin_key(),
            api_key=generate_api_key(),
            api_secret_hash=hash_password(api_secret),
            allowed_domains=allowed_domains or [],
        )

        self.db.add(env)
        await self.db.commit()
        await self.db.refresh(env)

        return env, api_secret

    async def rotate_keys(self, env_id: UUID) -> tuple[Environment, str, str, str]:
        """
        Rotate all keys for an environment.

        Args:
            env_id: Environment ID

        Returns:
            Tuple of (environment, new_plugin_key, new_api_key, new_api_secret)
        """
        env = await self.get_environment(env_id)

        # Generate new keys
        new_plugin_key = generate_plugin_key()
        new_api_key = generate_api_key()
        new_api_secret = generate_api_secret()

        # Update environment
        env.plugin_key = new_plugin_key
        env.api_key = new_api_key
        env.api_secret_hash = hash_password(new_api_secret)
        env.key_rotated_at = datetime.now(timezone.utc)

        await self.db.commit()
        await self.db.refresh(env)

        return env, new_plugin_key, new_api_key, new_api_secret

    async def update_allowed_domains(
        self, env_id: UUID, domains: list[str]
    ) -> Environment:
        """
        Update allowed domains for an environment.

        Args:
            env_id: Environment ID
            domains: List of allowed CORS domains

        Returns:
            Updated environment
        """
        env = await self.get_environment(env_id)
        env.allowed_domains = domains

        await self.db.commit()
        await self.db.refresh(env)

        return env

    async def deactivate_environment(self, env_id: UUID) -> Environment:
        """
        Deactivate an environment.

        Args:
            env_id: Environment ID

        Returns:
            Deactivated environment
        """
        env = await self.get_environment(env_id)
        env.is_active = False

        await self.db.commit()
        await self.db.refresh(env)

        return env

    async def activate_environment(self, env_id: UUID) -> Environment:
        """
        Activate an environment.

        Args:
            env_id: Environment ID

        Returns:
            Activated environment
        """
        env = await self.get_environment(env_id)
        env.is_active = True

        await self.db.commit()
        await self.db.refresh(env)

        return env
