"""User repository - data access layer for MongoDB."""

from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from redis.asyncio import Redis

from app.domains.user.models import TempUser, User, UserStatus


class UserRepositoryInterface(ABC):
    """User repository interface (Port)."""

    @abstractmethod
    async def create(self, user: User) -> User:
        """Create a new user."""
        pass

    @abstractmethod
    async def get_by_id(self, user_id: str) -> User | None:
        """Get user by ID."""
        pass

    @abstractmethod
    async def get_by_member_id(self, member_id: str) -> User | None:
        """Get user by member ID."""
        pass

    @abstractmethod
    async def list_users(
        self,
        skip: int = 0,
        limit: int = 20,
        status: UserStatus | None = None,
        tags: list[str] | None = None,
    ) -> tuple[list[User], int]:
        """List users with pagination and filters."""
        pass

    @abstractmethod
    async def update(self, user: User) -> User:
        """Update a user."""
        pass

    @abstractmethod
    async def delete(self, user_id: str) -> bool:
        """Soft delete a user."""
        pass


class MongoUserRepository(UserRepositoryInterface):
    """MongoDB implementation of user repository (Adapter)."""

    def __init__(self, db: AsyncIOMotorDatabase, org_id: str, env_type: str):
        self._db = db
        self._org_id = org_id
        self._env_type = env_type
        self._collection = db[f"users_{org_id}_{env_type}"]

    async def create(self, user: User) -> User:
        """Create a new user."""
        user_dict = user.model_dump(exclude={"id"}, by_alias=True)
        user_dict["created_at"] = datetime.utcnow()
        user_dict["updated_at"] = datetime.utcnow()

        result = await self._collection.insert_one(user_dict)
        user.id = str(result.inserted_id)
        return user

    async def get_by_id(self, user_id: str) -> User | None:
        """Get user by ID."""
        try:
            doc = await self._collection.find_one({"_id": ObjectId(user_id)})
        except Exception:
            return None

        if not doc:
            return None

        doc["_id"] = str(doc["_id"])
        return User(**doc)

    async def get_by_member_id(self, member_id: str) -> User | None:
        """Get user by member ID."""
        doc = await self._collection.find_one({"member_id": member_id})
        if not doc:
            return None

        doc["_id"] = str(doc["_id"])
        return User(**doc)

    async def list_users(
        self,
        skip: int = 0,
        limit: int = 20,
        status: UserStatus | None = None,
        tags: list[str] | None = None,
    ) -> tuple[list[User], int]:
        """List users with pagination and filters."""
        query: dict[str, Any] = {}

        if status:
            query["status"] = status.value

        if tags:
            query["tags"] = {"$all": tags}

        # Get total count
        total = await self._collection.count_documents(query)

        # Get paginated results
        cursor = (
            self._collection.find(query)
            .sort("last_seen_at", -1)
            .skip(skip)
            .limit(limit)
        )

        users = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            users.append(User(**doc))

        return users, total

    async def update(self, user: User) -> User:
        """Update a user."""
        user.updated_at = datetime.utcnow()
        user_dict = user.model_dump(exclude={"id"}, by_alias=True)

        await self._collection.update_one(
            {"_id": ObjectId(user.id)},
            {"$set": user_dict},
        )
        return user

    async def delete(self, user_id: str) -> bool:
        """Soft delete a user."""
        result = await self._collection.update_one(
            {"_id": ObjectId(user_id)},
            {
                "$set": {
                    "status": UserStatus.DELETED.value,
                    "updated_at": datetime.utcnow(),
                }
            },
        )
        return result.modified_count > 0

    async def increment_stats(
        self,
        user_id: str,
        chats: int = 0,
        messages: int = 0,
    ) -> None:
        """Increment user statistics."""
        update: dict[str, Any] = {"$set": {"last_seen_at": datetime.utcnow()}}
        inc: dict[str, int] = {}

        if chats:
            inc["total_chats"] = chats
        if messages:
            inc["total_messages"] = messages

        if inc:
            update["$inc"] = inc

        await self._collection.update_one(
            {"_id": ObjectId(user_id)},
            update,
        )


class TempUserRepositoryInterface(ABC):
    """Temporary user repository interface (Port)."""

    @abstractmethod
    async def create(self, temp_user: TempUser, ttl_hours: int = 24) -> TempUser:
        """Create a temporary user."""
        pass

    @abstractmethod
    async def get(self, session_id: str) -> TempUser | None:
        """Get temporary user by session ID."""
        pass

    @abstractmethod
    async def update(self, temp_user: TempUser) -> TempUser:
        """Update temporary user."""
        pass

    @abstractmethod
    async def delete(self, session_id: str) -> bool:
        """Delete temporary user."""
        pass

    @abstractmethod
    async def add_chat_id(self, session_id: str, chat_id: str) -> None:
        """Add chat ID to temporary user."""
        pass


class RedisTempUserRepository(TempUserRepositoryInterface):
    """Redis implementation of temporary user repository (Adapter)."""

    def __init__(self, redis: Redis, org_id: str, env_type: str):
        self._redis = redis
        self._org_id = org_id
        self._env_type = env_type

    def _key(self, session_id: str) -> str:
        """Generate Redis key for temp user."""
        return f"temp_user:{self._org_id}:{self._env_type}:{session_id}"

    async def create(self, temp_user: TempUser, ttl_hours: int = 24) -> TempUser:
        """Create a temporary user with TTL."""
        key = self._key(temp_user.session_id)
        data = temp_user.model_dump_json()

        await self._redis.setex(
            key,
            timedelta(hours=ttl_hours),
            data,
        )
        return temp_user

    async def get(self, session_id: str) -> TempUser | None:
        """Get temporary user by session ID."""
        key = self._key(session_id)
        data = await self._redis.get(key)

        if not data:
            return None

        return TempUser.model_validate_json(data)

    async def update(self, temp_user: TempUser) -> TempUser:
        """Update temporary user (preserves TTL)."""
        key = self._key(temp_user.session_id)

        # Get remaining TTL
        ttl = await self._redis.ttl(key)
        if ttl < 0:
            ttl = 86400  # Default 24 hours if no TTL

        temp_user.last_activity_at = datetime.utcnow()
        data = temp_user.model_dump_json()

        await self._redis.setex(key, ttl, data)
        return temp_user

    async def delete(self, session_id: str) -> bool:
        """Delete temporary user."""
        key = self._key(session_id)
        result = await self._redis.delete(key)
        return result > 0

    async def add_chat_id(self, session_id: str, chat_id: str) -> None:
        """Add chat ID to temporary user."""
        temp_user = await self.get(session_id)
        if temp_user:
            if chat_id not in temp_user.chat_ids:
                temp_user.chat_ids.append(chat_id)
            await self.update(temp_user)
