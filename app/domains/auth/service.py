"""Auth domain service - authentication business logic."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import InvalidCredentialsError, InvalidTokenError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
    verify_refresh_token,
)
from app.db.redis import jwt_blacklist
from app.domains.agent.models import Agent, RefreshToken


class AuthService:
    """Authentication service."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def login(self, email: str, password: str) -> tuple[str, str]:
        """
        Authenticate agent and return tokens.

        Args:
            email: Agent email
            password: Plain text password

        Returns:
            Tuple of (access_token, refresh_token)

        Raises:
            InvalidCredentialsError: If email or password is wrong
        """
        # Find agent by email
        result = await self.db.execute(
            select(Agent).where(Agent.email == email, Agent.is_active == True)
        )
        agent = result.scalar_one_or_none()

        if not agent:
            raise InvalidCredentialsError()

        # Verify password
        if not verify_password(password, agent.password_hash):
            raise InvalidCredentialsError()

        # Update last login
        agent.last_login_at = datetime.utcnow()
        await self.db.commit()

        # Create tokens
        token_data = {
            "sub": str(agent.id),
            "org_id": str(agent.organization_id),
            "role": agent.role.value,
            "email": agent.email,
            "name": agent.name,
        }

        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)

        # Store refresh token hash in DB for revocation
        refresh_token_record = RefreshToken(
            agent_id=agent.id,
            token_hash=hash_password(refresh_token),
            expires_at=datetime.now(timezone.utc)
            + timedelta(days=settings.jwt_refresh_token_expire_days),
        )
        self.db.add(refresh_token_record)
        await self.db.commit()

        return access_token, refresh_token

    async def refresh_tokens(self, refresh_token: str) -> str:
        """
        Refresh access token using refresh token.

        Args:
            refresh_token: Valid refresh token

        Returns:
            New access token

        Raises:
            InvalidTokenError: If refresh token is invalid or expired
        """
        # Verify refresh token
        try:
            payload = verify_refresh_token(refresh_token)
        except Exception as e:
            raise InvalidTokenError(str(e))

        user_id = payload.get("sub")
        if not user_id:
            raise InvalidTokenError("Invalid token payload")

        # Find agent
        result = await self.db.execute(
            select(Agent).where(Agent.id == user_id, Agent.is_active == True)
        )
        agent = result.scalar_one_or_none()

        if not agent:
            raise InvalidTokenError("Agent not found or inactive")

        # Create new access token
        token_data = {
            "sub": str(agent.id),
            "org_id": str(agent.organization_id),
            "role": agent.role.value,
            "email": agent.email,
            "name": agent.name,
        }

        return create_access_token(token_data)

    async def logout(self, access_token: str, jti: str) -> None:
        """
        Logout by blacklisting the access token.

        Args:
            access_token: Current access token
            jti: JWT ID from token payload
        """
        # Add to blacklist with TTL equal to token expiration
        ttl = settings.jwt_access_token_expire_minutes * 60
        await jwt_blacklist.set(jti, "1", ttl=ttl)

    async def revoke_refresh_token(self, agent_id: str, token_hash: str) -> None:
        """
        Revoke a specific refresh token.

        Args:
            agent_id: Agent ID
            token_hash: Hash of the refresh token to revoke
        """
        result = await self.db.execute(
            select(RefreshToken).where(
                RefreshToken.agent_id == agent_id,
                RefreshToken.token_hash == token_hash,
                RefreshToken.revoked_at == None,
            )
        )
        token_record = result.scalar_one_or_none()

        if token_record:
            token_record.revoked_at = datetime.utcnow()
            await self.db.commit()

    async def revoke_all_refresh_tokens(self, agent_id: str) -> int:
        """
        Revoke all refresh tokens for an agent.
        Useful for "logout from all devices".

        Args:
            agent_id: Agent ID

        Returns:
            Number of tokens revoked
        """
        result = await self.db.execute(
            select(RefreshToken).where(
                RefreshToken.agent_id == agent_id,
                RefreshToken.revoked_at == None,
            )
        )
        tokens = result.scalars().all()

        count = 0
        for token in tokens:
            token.revoked_at = datetime.utcnow()
            count += 1

        await self.db.commit()
        return count
