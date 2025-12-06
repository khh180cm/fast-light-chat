"""User domain service - user management business logic.

This service handles both permanent users (MongoDB) and
temporary users (Redis) for the chat system.
"""

from datetime import datetime
from uuid import uuid4

from app.core.exceptions import ConflictError, NotFoundError
from app.domains.user.models import TempUser, User, UserProfile, UserStatus
from app.domains.user.repository import (
    TempUserRepositoryInterface,
    UserRepositoryInterface,
)
from app.domains.user.schemas import UserCreate, UserUpdate


class UserService:
    """User management service (Application/Use Case layer).

    Handles permanent user operations with MongoDB.
    """

    def __init__(
        self,
        repository: UserRepositoryInterface,
        org_id: str,
        env_type: str,
    ):
        self._repository = repository
        self._org_id = org_id
        self._env_type = env_type

    async def create_user(self, data: UserCreate) -> User:
        """
        Create a new user.

        Business rules:
        - member_id must be unique within org/env

        Args:
            data: User creation data

        Returns:
            Created user

        Raises:
            ConflictError: If member_id already exists
        """
        # Check if member_id already exists
        existing = await self._repository.get_by_member_id(data.member_id)
        if existing:
            raise ConflictError(f"User with member_id '{data.member_id}' already exists")

        user = User(
            member_id=data.member_id,
            org_id=self._org_id,
            env_type=self._env_type,
            profile=data.profile or UserProfile(),
            custom_fields=data.custom_fields or {},
            tags=data.tags or [],
        )

        return await self._repository.create(user)

    async def get_user(self, user_id: str) -> User:
        """
        Get user by ID.

        Args:
            user_id: User ID

        Returns:
            User

        Raises:
            NotFoundError: If user not found
        """
        user = await self._repository.get_by_id(user_id)
        if not user:
            raise NotFoundError("User", user_id)
        return user

    async def get_user_by_member_id(self, member_id: str) -> User | None:
        """
        Get user by member ID.

        Args:
            member_id: External member ID

        Returns:
            User or None
        """
        return await self._repository.get_by_member_id(member_id)

    async def get_or_create_user(self, data: UserCreate) -> tuple[User, bool]:
        """
        Get existing user or create new one.

        Args:
            data: User creation data

        Returns:
            Tuple of (user, created) where created is True if new user
        """
        existing = await self._repository.get_by_member_id(data.member_id)
        if existing:
            # Update last_seen_at
            existing.last_seen_at = datetime.utcnow()
            await self._repository.update(existing)
            return existing, False

        user = await self.create_user(data)
        return user, True

    async def list_users(
        self,
        skip: int = 0,
        limit: int = 20,
        status: UserStatus | None = None,
        tags: list[str] | None = None,
    ) -> tuple[list[User], int]:
        """
        List users with pagination and filters.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records
            status: Filter by status
            tags: Filter by tags (all must match)

        Returns:
            Tuple of (users list, total count)
        """
        return await self._repository.list_users(
            skip=skip,
            limit=limit,
            status=status,
            tags=tags,
        )

    async def update_user(self, member_id: str, data: UserUpdate) -> User:
        """
        Update user by member ID.

        Args:
            member_id: External member ID
            data: Update data

        Returns:
            Updated user
        """
        user = await self._repository.get_by_member_id(member_id)
        if not user:
            raise NotFoundError("User", member_id)

        if data.profile:
            # Merge profile updates
            current_profile = user.profile.model_dump()
            update_profile = data.profile.model_dump(exclude_unset=True)
            current_profile.update(update_profile)
            user.profile = UserProfile(**current_profile)

        if data.custom_fields is not None:
            # Merge custom fields
            user.custom_fields.update(data.custom_fields)

        if data.tags is not None:
            user.tags = data.tags

        user.last_seen_at = datetime.utcnow()
        return await self._repository.update(user)

    async def delete_user(self, member_id: str) -> bool:
        """
        Soft delete user by member ID.

        Args:
            member_id: External member ID

        Returns:
            True if deleted
        """
        user = await self._repository.get_by_member_id(member_id)
        if not user:
            raise NotFoundError("User", member_id)

        return await self._repository.delete(user.id)


class TempUserService:
    """Temporary user management service.

    Handles anonymous users stored in Redis with TTL.
    """

    def __init__(
        self,
        repository: TempUserRepositoryInterface,
        org_id: str,
        env_type: str,
    ):
        self._repository = repository
        self._org_id = org_id
        self._env_type = env_type

    async def create_temp_user(
        self,
        session_id: str | None = None,
        profile: UserProfile | None = None,
    ) -> TempUser:
        """
        Create a temporary user.

        Args:
            session_id: Optional session ID (generated if not provided)
            profile: Optional profile data

        Returns:
            Created temporary user
        """
        if not session_id:
            session_id = str(uuid4())

        temp_user = TempUser(
            session_id=session_id,
            org_id=self._org_id,
            env_type=self._env_type,
            profile=profile or UserProfile(),
        )

        return await self._repository.create(temp_user, ttl_hours=24)

    async def get_temp_user(self, session_id: str) -> TempUser | None:
        """
        Get temporary user by session ID.

        Args:
            session_id: Session ID

        Returns:
            Temporary user or None if not found/expired
        """
        return await self._repository.get(session_id)

    async def get_or_create_temp_user(
        self,
        session_id: str,
        profile: UserProfile | None = None,
    ) -> tuple[TempUser, bool]:
        """
        Get existing temp user or create new one.

        Args:
            session_id: Session ID
            profile: Optional profile data

        Returns:
            Tuple of (temp_user, created)
        """
        existing = await self._repository.get(session_id)
        if existing:
            return existing, False

        temp_user = await self.create_temp_user(session_id, profile)
        return temp_user, True

    async def add_chat_to_temp_user(self, session_id: str, chat_id: str) -> None:
        """
        Add chat ID to temporary user.

        Args:
            session_id: Session ID
            chat_id: Chat ID to add
        """
        await self._repository.add_chat_id(session_id, chat_id)

    async def convert_to_permanent(
        self,
        session_id: str,
        member_id: str,
        user_repository: UserRepositoryInterface,
    ) -> User:
        """
        Convert temporary user to permanent user.

        Business rules:
        - Transfers profile and chat history
        - Deletes temporary user after conversion

        Args:
            session_id: Temporary user session ID
            member_id: New permanent member ID
            user_repository: Repository for permanent users

        Returns:
            Created permanent user

        Raises:
            NotFoundError: If temp user not found
            ConflictError: If member_id already exists
        """
        temp_user = await self._repository.get(session_id)
        if not temp_user:
            raise NotFoundError("TempUser", session_id)

        # Check if member_id already exists
        existing = await user_repository.get_by_member_id(member_id)
        if existing:
            raise ConflictError(f"User with member_id '{member_id}' already exists")

        # Create permanent user
        user = User(
            member_id=member_id,
            org_id=self._org_id,
            env_type=self._env_type,
            profile=temp_user.profile,
            first_seen_at=temp_user.created_at,
        )
        user = await user_repository.create(user)

        # Delete temporary user
        await self._repository.delete(session_id)

        return user
