"""Organization repository - data access layer."""

from abc import ABC, abstractmethod
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domains.organization.models import Organization
from app.domains.environment.models import Environment


class OrganizationRepositoryInterface(ABC):
    """Organization repository interface (Port)."""

    @abstractmethod
    async def create(self, org: Organization) -> Organization:
        """Create a new organization."""
        pass

    @abstractmethod
    async def get_by_id(self, org_id: UUID) -> Organization | None:
        """Get organization by ID."""
        pass

    @abstractmethod
    async def get_by_id_with_environments(self, org_id: UUID) -> Organization | None:
        """Get organization by ID with environments loaded."""
        pass

    @abstractmethod
    async def get_by_slug(self, slug: str) -> Organization | None:
        """Get organization by slug."""
        pass

    @abstractmethod
    async def update(self, org: Organization) -> Organization:
        """Update an organization."""
        pass

    @abstractmethod
    async def get_environments(self, org_id: UUID) -> list[Environment]:
        """Get all environments for an organization."""
        pass

    @abstractmethod
    async def add_environment(self, env: Environment) -> Environment:
        """Add an environment to organization."""
        pass


class OrganizationRepository(OrganizationRepositoryInterface):
    """SQLAlchemy implementation of organization repository (Adapter)."""

    def __init__(self, db: AsyncSession):
        self._db = db

    async def create(self, org: Organization) -> Organization:
        """Create a new organization."""
        self._db.add(org)
        await self._db.commit()
        await self._db.refresh(org)
        return org

    async def get_by_id(self, org_id: UUID) -> Organization | None:
        """Get organization by ID."""
        result = await self._db.execute(
            select(Organization).where(Organization.id == org_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id_with_environments(self, org_id: UUID) -> Organization | None:
        """Get organization by ID with environments loaded."""
        result = await self._db.execute(
            select(Organization)
            .options(selectinload(Organization.environments))
            .where(Organization.id == org_id)
        )
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Organization | None:
        """Get organization by slug."""
        result = await self._db.execute(
            select(Organization).where(Organization.slug == slug)
        )
        return result.scalar_one_or_none()

    async def update(self, org: Organization) -> Organization:
        """Update an organization."""
        await self._db.commit()
        await self._db.refresh(org)
        return org

    async def get_environments(self, org_id: UUID) -> list[Environment]:
        """Get all environments for an organization."""
        result = await self._db.execute(
            select(Environment).where(Environment.organization_id == org_id)
        )
        return list(result.scalars().all())

    async def add_environment(self, env: Environment) -> Environment:
        """Add an environment to organization."""
        self._db.add(env)
        await self._db.flush()
        return env
