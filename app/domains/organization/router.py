"""Organization API router - organization management endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError
from app.db.postgres import get_db
from app.dependencies.auth import AdminOnly, CurrentAgent
from app.domains.organization.repository import OrganizationRepository
from app.domains.organization.schemas import (
    EnvironmentResponse,
    OrganizationCreate,
    OrganizationResponse,
    OrganizationUpdate,
    OrganizationWithKeysResponse,
    EnvironmentCreateResponse,
)
from app.domains.organization.service import OrganizationService

router = APIRouter()


def get_organization_service(db: AsyncSession = Depends(get_db)) -> OrganizationService:
    """Dependency injection for OrganizationService."""
    repository = OrganizationRepository(db)
    return OrganizationService(repository)


@router.post("", response_model=OrganizationWithKeysResponse, status_code=201)
async def create_organization(
    data: OrganizationCreate,
    service: OrganizationService = Depends(get_organization_service),
):
    """
    Create a new organization.

    Creates the organization with a default development environment.
    Returns the organization with API keys (api_secret shown only once).

    Note: This endpoint is typically called during initial setup
    and may require additional protection in production.
    """
    org, api_secret = await service.create_organization(data)

    # Build response with environment including secret
    env_responses = []
    for env in org.environments:
        env_data = EnvironmentCreateResponse(
            id=env.id,
            name=env.name,
            env_type=env.env_type.value,
            plugin_key=env.plugin_key,
            api_key=env.api_key,
            api_secret=api_secret,  # Only returned on creation
            allowed_domains=env.allowed_domains,
            is_active=env.is_active,
            created_at=env.created_at,
        )
        env_responses.append(env_data)

    return OrganizationWithKeysResponse(
        id=org.id,
        name=org.name,
        slug=org.slug,
        status=org.status,
        plan=org.plan,
        max_agents=org.max_agents,
        settings=org.settings,
        created_at=org.created_at,
        updated_at=org.updated_at,
        environments=env_responses,
    )


@router.get("/me", response_model=OrganizationResponse)
async def get_my_organization(
    current_agent: CurrentAgent,
    service: OrganizationService = Depends(get_organization_service),
):
    """
    Get current agent's organization.

    Returns organization details without sensitive API keys.
    """
    org = await service.get_organization(UUID(current_agent["org_id"]))
    return org


@router.get("/{org_id}", response_model=OrganizationWithKeysResponse)
async def get_organization(
    org_id: UUID,
    current_agent: AdminOnly,
    service: OrganizationService = Depends(get_organization_service),
):
    """
    Get organization by ID.

    Requires admin role. Returns organization with environments
    (but not API secrets).
    """
    # Verify agent belongs to this organization
    if str(org_id) != current_agent["org_id"]:
        raise ForbiddenError("Access denied to this organization")

    org = await service.get_organization(org_id)

    env_responses = [
        EnvironmentResponse(
            id=env.id,
            name=env.name,
            env_type=env.env_type.value,
            plugin_key=env.plugin_key,
            api_key=env.api_key,
            allowed_domains=env.allowed_domains,
            is_active=env.is_active,
            created_at=env.created_at,
        )
        for env in org.environments
    ]

    return OrganizationWithKeysResponse(
        id=org.id,
        name=org.name,
        slug=org.slug,
        status=org.status,
        plan=org.plan,
        max_agents=org.max_agents,
        settings=org.settings,
        created_at=org.created_at,
        updated_at=org.updated_at,
        environments=env_responses,
    )


@router.put("/{org_id}", response_model=OrganizationResponse)
async def update_organization(
    org_id: UUID,
    data: OrganizationUpdate,
    current_agent: AdminOnly,
    service: OrganizationService = Depends(get_organization_service),
):
    """
    Update organization.

    Requires admin role. Only updates provided fields.
    """
    if str(org_id) != current_agent["org_id"]:
        raise ForbiddenError("Access denied to this organization")

    org = await service.update_organization(org_id, data)
    return org


@router.get("/{org_id}/environments", response_model=list[EnvironmentResponse])
async def get_environments(
    org_id: UUID,
    current_agent: AdminOnly,
    service: OrganizationService = Depends(get_organization_service),
):
    """
    Get all environments for an organization.

    Requires admin role. Returns environments without API secrets.
    """
    if str(org_id) != current_agent["org_id"]:
        raise ForbiddenError("Access denied to this organization")

    environments = await service.get_environments(org_id)

    return [
        EnvironmentResponse(
            id=env.id,
            name=env.name,
            env_type=env.env_type.value,
            plugin_key=env.plugin_key,
            api_key=env.api_key,
            allowed_domains=env.allowed_domains,
            is_active=env.is_active,
            created_at=env.created_at,
        )
        for env in environments
    ]
