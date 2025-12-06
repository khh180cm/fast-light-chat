"""Organization domain service - organization management business logic.

This service contains pure business logic and depends on repository interfaces,
not on specific database implementations.
"""

from uuid import UUID

from app.core.exceptions import ConflictError, NotFoundError
from app.core.security import generate_api_key, generate_api_secret, generate_plugin_key, hash_password
from app.domains.environment.models import Environment, EnvironmentType
from app.domains.organization.models import Organization
from app.domains.organization.repository import OrganizationRepositoryInterface
from app.domains.organization.schemas import OrganizationCreate, OrganizationUpdate


class OrganizationService:
    """Organization management service (Application/Use Case layer).

    This service orchestrates business logic using repository interfaces.
    It doesn't know about SQLAlchemy or any specific database implementation.
    """

    def __init__(self, repository: OrganizationRepositoryInterface):
        self._repository = repository

    async def create_organization(self, data: OrganizationCreate) -> tuple[Organization, str]:
        """
        Create a new organization with default environments.

        Business rules:
        - Slug must be unique
        - Default development environment is created automatically

        Args:
            data: Organization creation data

        Returns:
            Tuple of (organization, api_secret for development env)

        Raises:
            ConflictError: If slug already exists
        """
        # Business rule: slug must be unique
        existing = await self._repository.get_by_slug(data.slug)
        if existing:
            raise ConflictError(f"Organization with slug '{data.slug}' already exists")

        # Create organization
        org = Organization(
            name=data.name,
            slug=data.slug,
            plan=data.plan,
            max_agents=data.max_agents,
        )
        org = await self._repository.create(org)

        # Create default development environment
        api_secret = generate_api_secret()
        dev_env = Environment(
            organization_id=org.id,
            name="Development",
            env_type=EnvironmentType.DEVELOPMENT,
            plugin_key=generate_plugin_key(),
            api_key=generate_api_key(),
            api_secret_hash=hash_password(api_secret),
            allowed_domains=["http://localhost:3000", "http://localhost:8000"],
        )
        await self._repository.add_environment(dev_env)

        # Refresh to get environments
        org = await self._repository.get_by_id_with_environments(org.id)

        return org, api_secret

    async def get_organization(self, org_id: UUID) -> Organization:
        """
        Get organization by ID.

        Args:
            org_id: Organization ID

        Returns:
            Organization

        Raises:
            NotFoundError: If organization not found
        """
        org = await self._repository.get_by_id_with_environments(org_id)
        if not org:
            raise NotFoundError("Organization", str(org_id))
        return org

    async def get_organization_by_slug(self, slug: str) -> Organization | None:
        """
        Get organization by slug.

        Args:
            slug: Organization slug

        Returns:
            Organization or None
        """
        return await self._repository.get_by_slug(slug)

    async def update_organization(
        self,
        org_id: UUID,
        data: OrganizationUpdate,
    ) -> Organization:
        """
        Update organization.

        Args:
            org_id: Organization ID
            data: Update data

        Returns:
            Updated organization
        """
        org = await self.get_organization(org_id)

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(org, field, value)

        return await self._repository.update(org)

    async def get_environments(self, org_id: UUID) -> list[Environment]:
        """
        Get all environments for an organization.

        Args:
            org_id: Organization ID

        Returns:
            List of environments
        """
        return await self._repository.get_environments(org_id)
