"""Environment API router - environment and API key management endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError
from app.db.postgres import get_db
from app.dependencies.auth import AdminOnly
from app.domains.environment.schemas import (
    EnvironmentCreate,
    EnvironmentResponse,
    EnvironmentUpdate,
    EnvironmentWithSecretResponse,
    RotateKeysResponse,
)
from app.domains.environment.service import EnvironmentService
from app.domains.organization.service import OrganizationService

router = APIRouter()


@router.post("", response_model=EnvironmentWithSecretResponse, status_code=201)
async def create_environment(
    data: EnvironmentCreate,
    current_agent: AdminOnly,
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new environment.

    Requires admin role. Returns the new environment with API secret
    (shown only once).
    """
    org_id = UUID(current_agent["org_id"])

    service = EnvironmentService(db)
    env, api_secret = await service.create_environment(
        org_id=org_id,
        name=data.name,
        env_type=data.env_type,
        allowed_domains=data.allowed_domains,
    )

    return EnvironmentWithSecretResponse(
        id=env.id,
        name=env.name,
        env_type=env.env_type.value,
        plugin_key=env.plugin_key,
        api_key=env.api_key,
        api_secret=api_secret,
        allowed_domains=env.allowed_domains,
        is_active=env.is_active,
        key_rotated_at=env.key_rotated_at,
        created_at=env.created_at,
    )


@router.get("/{env_id}", response_model=EnvironmentResponse)
async def get_environment(
    env_id: UUID,
    current_agent: AdminOnly,
    db: AsyncSession = Depends(get_db),
):
    """
    Get environment by ID.

    Requires admin role. Verifies the environment belongs to the agent's organization.
    """
    service = EnvironmentService(db)
    env = await service.get_environment(env_id)

    # Verify environment belongs to agent's organization
    if str(env.organization_id) != current_agent["org_id"]:
        raise ForbiddenError("Access denied to this environment")

    return EnvironmentResponse(
        id=env.id,
        name=env.name,
        env_type=env.env_type.value,
        plugin_key=env.plugin_key,
        api_key=env.api_key,
        allowed_domains=env.allowed_domains,
        is_active=env.is_active,
        key_rotated_at=env.key_rotated_at,
        created_at=env.created_at,
    )


@router.put("/{env_id}", response_model=EnvironmentResponse)
async def update_environment(
    env_id: UUID,
    data: EnvironmentUpdate,
    current_agent: AdminOnly,
    db: AsyncSession = Depends(get_db),
):
    """
    Update environment settings.

    Requires admin role.
    """
    service = EnvironmentService(db)
    env = await service.get_environment(env_id)

    # Verify environment belongs to agent's organization
    if str(env.organization_id) != current_agent["org_id"]:
        raise ForbiddenError("Access denied to this environment")

    # Update allowed domains if provided
    if data.allowed_domains is not None:
        env = await service.update_allowed_domains(env_id, data.allowed_domains)

    return EnvironmentResponse(
        id=env.id,
        name=env.name,
        env_type=env.env_type.value,
        plugin_key=env.plugin_key,
        api_key=env.api_key,
        allowed_domains=env.allowed_domains,
        is_active=env.is_active,
        key_rotated_at=env.key_rotated_at,
        created_at=env.created_at,
    )


@router.post("/{env_id}/rotate-keys", response_model=RotateKeysResponse)
async def rotate_keys(
    env_id: UUID,
    current_agent: AdminOnly,
    db: AsyncSession = Depends(get_db),
):
    """
    Rotate all API keys for an environment.

    Requires admin role. This will invalidate all existing keys.
    New keys will be generated:
    - Plugin Key (for SDK)
    - API Key (for backend)
    - API Secret (for backend - shown only once)

    IMPORTANT: Store the new API Secret securely. It will not be shown again.
    """
    service = EnvironmentService(db)
    env = await service.get_environment(env_id)

    # Verify environment belongs to agent's organization
    if str(env.organization_id) != current_agent["org_id"]:
        raise ForbiddenError("Access denied to this environment")

    env, plugin_key, api_key, api_secret = await service.rotate_keys(env_id)

    return RotateKeysResponse(
        id=env.id,
        name=env.name,
        env_type=env.env_type.value,
        plugin_key=plugin_key,
        api_key=api_key,
        api_secret=api_secret,
        key_rotated_at=env.key_rotated_at,
    )


@router.post("/{env_id}/deactivate", response_model=EnvironmentResponse)
async def deactivate_environment(
    env_id: UUID,
    current_agent: AdminOnly,
    db: AsyncSession = Depends(get_db),
):
    """
    Deactivate an environment.

    Requires admin role. Deactivated environments cannot be used for authentication.
    """
    service = EnvironmentService(db)
    env = await service.get_environment(env_id)

    # Verify environment belongs to agent's organization
    if str(env.organization_id) != current_agent["org_id"]:
        raise ForbiddenError("Access denied to this environment")

    env = await service.deactivate_environment(env_id)

    return EnvironmentResponse(
        id=env.id,
        name=env.name,
        env_type=env.env_type.value,
        plugin_key=env.plugin_key,
        api_key=env.api_key,
        allowed_domains=env.allowed_domains,
        is_active=env.is_active,
        key_rotated_at=env.key_rotated_at,
        created_at=env.created_at,
    )


@router.post("/{env_id}/activate", response_model=EnvironmentResponse)
async def activate_environment(
    env_id: UUID,
    current_agent: AdminOnly,
    db: AsyncSession = Depends(get_db),
):
    """
    Activate an environment.

    Requires admin role.
    """
    service = EnvironmentService(db)
    env = await service.get_environment(env_id)

    # Verify environment belongs to agent's organization
    if str(env.organization_id) != current_agent["org_id"]:
        raise ForbiddenError("Access denied to this environment")

    env = await service.activate_environment(env_id)

    return EnvironmentResponse(
        id=env.id,
        name=env.name,
        env_type=env.env_type.value,
        plugin_key=env.plugin_key,
        api_key=env.api_key,
        allowed_domains=env.allowed_domains,
        is_active=env.is_active,
        key_rotated_at=env.key_rotated_at,
        created_at=env.created_at,
    )
