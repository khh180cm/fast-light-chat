"""Authentication dependencies for FastAPI."""

from typing import Annotated

from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AuthenticationError,
    InvalidAPIKeyError,
    InvalidPluginKeyError,
    InvalidTokenError,
    InsufficientPermissionsError,
    OrganizationAccessDeniedError,
)
from app.core.security import verify_access_token, verify_password
from app.db.postgres import get_db
from app.db.redis import api_key_cache, plugin_key_cache, jwt_blacklist
from app.domains.agent.models import Agent, AgentRole
from app.domains.environment.models import Environment


# JWT Bearer scheme
bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_agent(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Verify JWT token and return current agent info.

    Used for dashboard authentication (agents/admins).

    Returns:
        dict with user_id, org_id, role, email, name
    """
    from app.core.config import settings

    # 개발 환경에서 토큰 없으면 더미 에이전트 반환
    if settings.debug and not credentials:
        # 첫 번째 조직의 첫 번째 에이전트 사용
        result = await db.execute(select(Agent).where(Agent.is_active == True).limit(1))
        agent = result.scalar_one_or_none()
        if agent:
            return {
                "user_id": str(agent.id),
                "org_id": str(agent.organization_id),
                "role": agent.role.value,
                "email": agent.email,
                "name": agent.name,
            }

    if not credentials:
        raise AuthenticationError("Authorization header required")

    token = credentials.credentials

    # Check if token is blacklisted
    if await jwt_blacklist.exists(token):
        raise InvalidTokenError("Token has been revoked")

    # Verify token
    try:
        payload = verify_access_token(token)
    except Exception as e:
        raise InvalidTokenError(str(e))

    # Extract user info from token
    user_id = payload.get("sub")
    if not user_id:
        raise InvalidTokenError("Invalid token payload")

    # Check Redis cache first for better performance
    from app.db.redis import RedisCache
    agent_cache = RedisCache(prefix="agent_session")

    cached_agent = await agent_cache.get_json(user_id)
    if cached_agent:
        return cached_agent

    # Cache miss - query database
    result = await db.execute(
        select(Agent).where(Agent.id == user_id, Agent.is_active == True)
    )
    agent = result.scalar_one_or_none()

    if not agent:
        raise AuthenticationError("Agent not found or inactive")

    agent_data = {
        "user_id": str(agent.id),
        "org_id": str(agent.organization_id),
        "role": agent.role.value,
        "email": agent.email,
        "name": agent.name,
    }

    # Cache for 5 minutes
    await agent_cache.set_json(user_id, agent_data, ttl=300)

    return agent_data


async def get_current_agent_optional(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: AsyncSession = Depends(get_db),
) -> dict | None:
    """
    Get current agent if token provided, otherwise return None.
    Useful for endpoints that work with or without authentication.
    """
    if not credentials:
        return None

    try:
        return await get_current_agent(credentials, db)
    except Exception:
        return None


async def verify_api_key(
    x_api_key: Annotated[str, Header()],
    x_api_secret: Annotated[str, Header()],
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Verify API Key + Secret for backend integration.

    Returns:
        dict with org_id, env_type, env_id
    """
    # Check cache first
    cached = await api_key_cache.get_json(x_api_key)
    if cached:
        # Still need to verify secret
        if not verify_password(x_api_secret, cached["secret_hash"]):
            raise InvalidAPIKeyError("Invalid API secret")
        return {
            "org_id": cached["org_id"],
            "env_type": cached["env_type"],
            "env_id": cached["env_id"],
        }

    # Query database
    result = await db.execute(
        select(Environment).where(
            Environment.api_key == x_api_key,
            Environment.is_active == True,
        )
    )
    env = result.scalar_one_or_none()

    if not env:
        raise InvalidAPIKeyError()

    # Verify secret
    if not verify_password(x_api_secret, env.api_secret_hash):
        raise InvalidAPIKeyError("Invalid API secret")

    # Cache for 5 minutes
    await api_key_cache.set_json(
        x_api_key,
        {
            "org_id": str(env.organization_id),
            "env_type": env.env_type.value,
            "env_id": str(env.id),
            "secret_hash": env.api_secret_hash,
        },
        ttl=300,
    )

    return {
        "org_id": str(env.organization_id),
        "env_type": env.env_type.value,
        "env_id": str(env.id),
    }


async def verify_plugin_key(
    x_plugin_key: Annotated[str, Header()],
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Verify Plugin Key for SDK/frontend.

    Returns:
        dict with org_id, env_type, env_id, allowed_domains
    """
    # Check cache first
    cached = await plugin_key_cache.get_json(x_plugin_key)
    if cached:
        return cached

    # Query database
    result = await db.execute(
        select(Environment).where(
            Environment.plugin_key == x_plugin_key,
            Environment.is_active == True,
        )
    )
    env = result.scalar_one_or_none()

    if not env:
        raise InvalidPluginKeyError()

    result_data = {
        "org_id": str(env.organization_id),
        "env_type": env.env_type.value,
        "env_id": str(env.id),
        "allowed_domains": env.allowed_domains or [],
    }

    # Cache for 5 minutes
    await plugin_key_cache.set_json(x_plugin_key, result_data, ttl=300)

    return result_data


def require_roles(*allowed_roles: AgentRole):
    """
    Dependency factory that checks if current agent has required role.

    Usage:
        @router.get("/admin-only")
        async def admin_endpoint(
            agent: dict = Depends(require_roles(AgentRole.ADMIN, AgentRole.SUPER_ADMIN))
        ):
            ...
    """
    async def role_checker(
        current_agent: dict = Depends(get_current_agent),
    ) -> dict:
        agent_role = current_agent.get("role")

        if agent_role not in [r.value for r in allowed_roles]:
            raise InsufficientPermissionsError(
                f"Required roles: {[r.value for r in allowed_roles]}"
            )

        return current_agent

    return role_checker


async def verify_org_access(
    org_id: str,
    current_agent: dict = Depends(get_current_agent),
) -> dict:
    """
    Verify that current agent has access to the specified organization.

    Super admins can access any organization.
    Other agents can only access their own organization.
    """
    if current_agent["role"] == AgentRole.SUPER_ADMIN.value:
        return current_agent

    if current_agent["org_id"] != org_id:
        raise OrganizationAccessDeniedError()

    return current_agent


# Type aliases for cleaner dependency injection
CurrentAgent = Annotated[dict, Depends(get_current_agent)]
OptionalAgent = Annotated[dict | None, Depends(get_current_agent_optional)]
APIKeyAuth = Annotated[dict, Depends(verify_api_key)]
PluginKeyAuth = Annotated[dict, Depends(verify_plugin_key)]
AdminOnly = Annotated[dict, Depends(require_roles(AgentRole.ADMIN, AgentRole.SUPER_ADMIN))]
