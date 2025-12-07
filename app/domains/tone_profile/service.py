"""Tone Profile service - business logic."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.domains.tone_profile.models import ToneProfile, ToneProfileVersion
from app.domains.tone_profile.repository import ToneProfileRepository
from app.domains.tone_profile.schemas import ToneProfileCreate, ToneProfileUpdate


class ToneProfileService:
    """Tone Profile management service."""

    def __init__(self, session: AsyncSession, org_id: UUID):
        self._session = session
        self._repo = ToneProfileRepository(session)
        self._org_id = org_id

    async def get_or_create_profile(self) -> ToneProfile:
        """Get existing profile or create default one."""
        profile = await self._repo.get_by_org_id(self._org_id)
        if profile:
            return profile

        # Create default profile
        profile = ToneProfile(
            organization_id=self._org_id,
            name="기본 말투",
            prompt="""다음 규칙에 따라 메시지를 변환해주세요:
- 항상 존댓말을 사용합니다
- "고객님"이라는 호칭을 사용합니다
- 친절하고 공손한 어조를 유지합니다
- 부정적인 표현을 긍정적으로 바꿉니다
- 마무리에 "추가 문의사항이 있으시면 말씀해주세요"를 추가합니다""",
        )
        profile = await self._repo.create(profile)

        # Create initial version
        await self._create_version_snapshot(profile, None, "초기 생성")
        await self._session.commit()

        return profile

    async def get_profile(self) -> ToneProfile:
        """Get the organization's tone profile."""
        profile = await self._repo.get_by_org_id(self._org_id)
        if not profile:
            raise NotFoundError("ToneProfile", str(self._org_id))
        return profile

    async def update_profile(
        self,
        data: ToneProfileUpdate,
        changed_by: UUID,
    ) -> ToneProfile:
        """
        Update tone profile and create version snapshot.

        Args:
            data: Update data
            changed_by: Agent ID who made the change

        Returns:
            Updated profile
        """
        profile = await self.get_profile()

        # Check if anything changed
        changed = False
        if data.name is not None and data.name != profile.name:
            profile.name = data.name
            changed = True
        if data.prompt is not None and data.prompt != profile.prompt:
            profile.prompt = data.prompt
            changed = True

        if not changed:
            return profile

        # Increment version
        profile.current_version += 1

        # Create version snapshot
        await self._create_version_snapshot(
            profile,
            changed_by,
            data.change_note,
        )

        await self._repo.update(profile)
        await self._session.commit()

        return profile

    async def _create_version_snapshot(
        self,
        profile: ToneProfile,
        changed_by: UUID | None,
        change_note: str | None,
    ) -> ToneProfileVersion:
        """Create a version snapshot of current profile state."""
        version = ToneProfileVersion(
            profile_id=profile.id,
            version=profile.current_version,
            name=profile.name,
            prompt=profile.prompt,
            changed_by=changed_by,
            change_note=change_note,
        )
        return await self._repo.create_version(version)

    async def get_version_history(
        self,
        limit: int = 10,
        offset: int = 0,
    ) -> tuple[list[ToneProfileVersion], int]:
        """Get version history."""
        profile = await self.get_profile()
        return await self._repo.get_versions(profile.id, limit, offset)

    async def restore_version(
        self,
        version_number: int,
        restored_by: UUID,
    ) -> ToneProfile:
        """
        Restore profile to a previous version.

        Args:
            version_number: Version to restore
            restored_by: Agent ID who is restoring

        Returns:
            Updated profile
        """
        profile = await self.get_profile()

        # Get the version to restore
        version = await self._repo.get_version_by_number(profile.id, version_number)
        if not version:
            raise NotFoundError("ToneProfileVersion", str(version_number))

        # Apply version data
        profile.name = version.name
        profile.prompt = version.prompt
        profile.current_version += 1

        # Create new version snapshot
        await self._create_version_snapshot(
            profile,
            restored_by,
            f"v{version_number}에서 복구됨",
        )

        await self._repo.update(profile)
        await self._session.commit()

        return profile

    async def toggle_active(self, is_active: bool) -> ToneProfile:
        """Enable or disable the tone profile."""
        profile = await self.get_profile()
        profile.is_active = is_active
        await self._repo.update(profile)
        await self._session.commit()
        return profile
