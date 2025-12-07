"""Tone Profile repository for PostgreSQL."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domains.tone_profile.models import ToneProfile, ToneProfileVersion


class ToneProfileRepository:
    """Repository for tone profile operations."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_org_id(self, org_id: UUID) -> ToneProfile | None:
        """Get tone profile by organization ID."""
        stmt = select(ToneProfile).where(ToneProfile.organization_id == org_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id(self, profile_id: UUID) -> ToneProfile | None:
        """Get tone profile by ID."""
        stmt = select(ToneProfile).where(ToneProfile.id == profile_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, profile: ToneProfile) -> ToneProfile:
        """Create a new tone profile."""
        self._session.add(profile)
        await self._session.flush()
        await self._session.refresh(profile)
        return profile

    async def update(self, profile: ToneProfile) -> ToneProfile:
        """Update a tone profile."""
        await self._session.flush()
        await self._session.refresh(profile)
        return profile

    async def delete(self, profile: ToneProfile) -> None:
        """Delete a tone profile."""
        await self._session.delete(profile)
        await self._session.flush()

    # Version management
    async def create_version(self, version: ToneProfileVersion) -> ToneProfileVersion:
        """Create a version snapshot."""
        self._session.add(version)
        await self._session.flush()
        await self._session.refresh(version)
        return version

    async def get_versions(
        self,
        profile_id: UUID,
        limit: int = 10,
        offset: int = 0,
    ) -> tuple[list[ToneProfileVersion], int]:
        """Get version history for a profile."""
        # Count total
        count_stmt = (
            select(ToneProfileVersion)
            .where(ToneProfileVersion.profile_id == profile_id)
        )
        count_result = await self._session.execute(count_stmt)
        total = len(count_result.scalars().all())

        # Get paginated versions
        stmt = (
            select(ToneProfileVersion)
            .where(ToneProfileVersion.profile_id == profile_id)
            .order_by(ToneProfileVersion.version.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        versions = list(result.scalars().all())

        return versions, total

    async def get_version_by_number(
        self,
        profile_id: UUID,
        version: int,
    ) -> ToneProfileVersion | None:
        """Get a specific version by number."""
        stmt = (
            select(ToneProfileVersion)
            .where(
                ToneProfileVersion.profile_id == profile_id,
                ToneProfileVersion.version == version,
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
