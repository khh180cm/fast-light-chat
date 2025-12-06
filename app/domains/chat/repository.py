"""Chat repository - data access layer for MongoDB."""

import base64
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.domains.chat.models import (
    Chat,
    ChatStatus,
    LastMessage,
    Message,
    SenderType,
)


class ChatRepositoryInterface(ABC):
    """Chat repository interface (Port)."""

    @abstractmethod
    async def create(self, chat: Chat) -> Chat:
        """Create a new chat."""
        pass

    @abstractmethod
    async def get_by_id(self, chat_id: str) -> Chat | None:
        """Get chat by ID."""
        pass

    @abstractmethod
    async def list_chats(
        self,
        status: ChatStatus | None = None,
        agent_id: str | None = None,
        user_id: str | None = None,
        limit: int = 20,
        cursor: str | None = None,
    ) -> tuple[list[Chat], str | None, bool]:
        """List chats with cursor pagination."""
        pass

    @abstractmethod
    async def update(self, chat: Chat) -> Chat:
        """Update a chat."""
        pass

    @abstractmethod
    async def update_status(self, chat_id: str, status: ChatStatus) -> bool:
        """Update chat status."""
        pass

    @abstractmethod
    async def assign_agent(self, chat_id: str, agent_id: str) -> bool:
        """Assign agent to chat."""
        pass

    @abstractmethod
    async def get_statistics(self) -> dict[str, Any]:
        """Get chat statistics."""
        pass


class MessageRepositoryInterface(ABC):
    """Message repository interface (Port)."""

    @abstractmethod
    async def create(self, message: Message) -> Message:
        """Create a new message."""
        pass

    @abstractmethod
    async def get_by_id(self, message_id: str) -> Message | None:
        """Get message by ID."""
        pass

    @abstractmethod
    async def list_messages(
        self,
        chat_id: str,
        limit: int = 50,
        cursor: str | None = None,
        before: bool = True,
    ) -> tuple[list[Message], str | None, bool]:
        """List messages with cursor pagination."""
        pass

    @abstractmethod
    async def mark_read(
        self,
        chat_id: str,
        reader_type: SenderType,
        up_to_message_id: str | None = None,
    ) -> int:
        """Mark messages as read."""
        pass


class MongoChatRepository(ChatRepositoryInterface):
    """MongoDB implementation of chat repository (Adapter)."""

    def __init__(self, db: AsyncIOMotorDatabase, org_id: str, env_type: str):
        self._db = db
        self._org_id = org_id
        self._env_type = env_type
        self._collection = db[f"chats_{org_id}_{env_type}"]

    async def create(self, chat: Chat) -> Chat:
        """Create a new chat."""
        chat_dict = chat.model_dump(exclude={"id"}, by_alias=True)
        chat_dict["created_at"] = datetime.utcnow()
        chat_dict["updated_at"] = datetime.utcnow()

        result = await self._collection.insert_one(chat_dict)
        chat.id = str(result.inserted_id)
        return chat

    async def get_by_id(self, chat_id: str) -> Chat | None:
        """Get chat by ID."""
        try:
            doc = await self._collection.find_one({"_id": ObjectId(chat_id)})
        except Exception:
            return None

        if not doc:
            return None

        doc["_id"] = str(doc["_id"])
        return Chat(**doc)

    async def list_chats(
        self,
        status: ChatStatus | None = None,
        agent_id: str | None = None,
        user_id: str | None = None,
        limit: int = 20,
        cursor: str | None = None,
    ) -> tuple[list[Chat], str | None, bool]:
        """List chats with cursor pagination."""
        query: dict[str, Any] = {}

        if status:
            query["status"] = status.value if isinstance(status, ChatStatus) else status
        if agent_id:
            query["assigned_agent_id"] = agent_id
        if user_id:
            query["user_id"] = user_id

        # Handle cursor (based on updated_at + _id)
        if cursor:
            try:
                decoded = base64.b64decode(cursor).decode()
                timestamp_str, last_id = decoded.rsplit("_", 1)
                timestamp = datetime.fromisoformat(timestamp_str)
                query["$or"] = [
                    {"updated_at": {"$lt": timestamp}},
                    {
                        "updated_at": timestamp,
                        "_id": {"$lt": ObjectId(last_id)},
                    },
                ]
            except Exception:
                pass  # Invalid cursor, ignore

        # Query with limit + 1 to check if there are more results
        cursor_result = (
            self._collection.find(query)
            .sort([("updated_at", -1), ("_id", -1)])
            .limit(limit + 1)
        )

        chats = []
        async for doc in cursor_result:
            doc["_id"] = str(doc["_id"])
            chats.append(Chat(**doc))

        has_more = len(chats) > limit
        if has_more:
            chats = chats[:limit]

        # Generate next cursor
        next_cursor = None
        if has_more and chats:
            last_chat = chats[-1]
            cursor_data = f"{last_chat.updated_at.isoformat()}_{last_chat.id}"
            next_cursor = base64.b64encode(cursor_data.encode()).decode()

        return chats, next_cursor, has_more

    async def update(self, chat: Chat) -> Chat:
        """Update a chat."""
        chat.updated_at = datetime.utcnow()
        chat_dict = chat.model_dump(exclude={"id"}, by_alias=True)

        await self._collection.update_one(
            {"_id": ObjectId(chat.id)},
            {"$set": chat_dict},
        )
        return chat

    async def update_status(self, chat_id: str, status: ChatStatus) -> bool:
        """Update chat status."""
        update: dict[str, Any] = {
            "status": status.value if isinstance(status, ChatStatus) else status,
            "updated_at": datetime.utcnow(),
        }

        if status == ChatStatus.RESOLVED:
            update["resolved_at"] = datetime.utcnow()
        elif status == ChatStatus.CLOSED:
            update["closed_at"] = datetime.utcnow()

        result = await self._collection.update_one(
            {"_id": ObjectId(chat_id)},
            {"$set": update},
        )
        return result.modified_count > 0

    async def assign_agent(self, chat_id: str, agent_id: str) -> bool:
        """Assign agent to chat."""
        update: dict[str, Any] = {
            "assigned_agent_id": agent_id,
            "status": ChatStatus.ACTIVE.value,
            "updated_at": datetime.utcnow(),
        }

        result = await self._collection.update_one(
            {"_id": ObjectId(chat_id)},
            {"$set": update},
        )
        return result.modified_count > 0

    async def increment_message_count(
        self,
        chat_id: str,
        sender_type: SenderType,
        last_message: LastMessage,
    ) -> None:
        """Increment message count and update last message."""
        inc: dict[str, int] = {"message_count": 1}

        # Increment unread count for the other party
        if sender_type == SenderType.USER:
            inc["unread_count_agent"] = 1
        else:
            inc["unread_count_user"] = 1

        await self._collection.update_one(
            {"_id": ObjectId(chat_id)},
            {
                "$inc": inc,
                "$set": {
                    "last_message": last_message.model_dump(),
                    "updated_at": datetime.utcnow(),
                },
            },
        )

    async def reset_unread_count(
        self,
        chat_id: str,
        reader_type: SenderType,
    ) -> None:
        """Reset unread count for reader."""
        field = "unread_count_user" if reader_type == SenderType.USER else "unread_count_agent"
        await self._collection.update_one(
            {"_id": ObjectId(chat_id)},
            {"$set": {field: 0, "updated_at": datetime.utcnow()}},
        )

    async def get_statistics(self) -> dict[str, Any]:
        """Get chat statistics."""
        pipeline = [
            {
                "$group": {
                    "_id": "$status",
                    "count": {"$sum": 1},
                }
            }
        ]

        status_counts = {status.value: 0 for status in ChatStatus}
        async for doc in self._collection.aggregate(pipeline):
            status_counts[doc["_id"]] = doc["count"]

        total = sum(status_counts.values())

        # Calculate average response time (from created_at to first_response_at)
        response_pipeline = [
            {"$match": {"first_response_at": {"$ne": None}}},
            {
                "$project": {
                    "response_time": {
                        "$subtract": ["$first_response_at", "$created_at"]
                    }
                }
            },
            {"$group": {"_id": None, "avg": {"$avg": "$response_time"}}},
        ]

        avg_response = None
        async for doc in self._collection.aggregate(response_pipeline):
            avg_response = doc.get("avg", 0) / 1000  # Convert ms to seconds

        # Calculate average resolution time
        resolution_pipeline = [
            {"$match": {"resolved_at": {"$ne": None}}},
            {
                "$project": {
                    "resolution_time": {
                        "$subtract": ["$resolved_at", "$created_at"]
                    }
                }
            },
            {"$group": {"_id": None, "avg": {"$avg": "$resolution_time"}}},
        ]

        avg_resolution = None
        async for doc in self._collection.aggregate(resolution_pipeline):
            avg_resolution = doc.get("avg", 0) / 1000

        return {
            "total_chats": total,
            "waiting_chats": status_counts.get(ChatStatus.WAITING.value, 0),
            "active_chats": status_counts.get(ChatStatus.ACTIVE.value, 0),
            "resolved_chats": status_counts.get(ChatStatus.RESOLVED.value, 0),
            "closed_chats": status_counts.get(ChatStatus.CLOSED.value, 0),
            "avg_response_time_seconds": avg_response,
            "avg_resolution_time_seconds": avg_resolution,
        }


class MongoMessageRepository(MessageRepositoryInterface):
    """MongoDB implementation of message repository (Adapter)."""

    def __init__(self, db: AsyncIOMotorDatabase, org_id: str, env_type: str):
        self._db = db
        self._org_id = org_id
        self._env_type = env_type
        self._collection = db[f"messages_{org_id}_{env_type}"]

    async def create(self, message: Message) -> Message:
        """Create a new message."""
        message_dict = message.model_dump(exclude={"id"}, by_alias=True)
        message_dict["created_at"] = datetime.utcnow()
        message_dict["updated_at"] = datetime.utcnow()

        result = await self._collection.insert_one(message_dict)
        message.id = str(result.inserted_id)
        return message

    async def get_by_id(self, message_id: str) -> Message | None:
        """Get message by ID."""
        try:
            doc = await self._collection.find_one({"_id": ObjectId(message_id)})
        except Exception:
            return None

        if not doc:
            return None

        doc["_id"] = str(doc["_id"])
        return Message(**doc)

    async def list_messages(
        self,
        chat_id: str,
        limit: int = 50,
        cursor: str | None = None,
        before: bool = True,
    ) -> tuple[list[Message], str | None, bool]:
        """List messages with cursor pagination.

        Args:
            chat_id: Chat ID
            limit: Number of messages to return
            cursor: Cursor for pagination (base64 encoded timestamp + id)
            before: If True, get messages before cursor (older). If False, get after (newer).
        """
        query: dict[str, Any] = {"chat_id": chat_id}

        if cursor:
            try:
                decoded = base64.b64decode(cursor).decode()
                timestamp_str, last_id = decoded.rsplit("_", 1)
                timestamp = datetime.fromisoformat(timestamp_str)

                if before:
                    # Get older messages
                    query["$or"] = [
                        {"created_at": {"$lt": timestamp}},
                        {
                            "created_at": timestamp,
                            "_id": {"$lt": ObjectId(last_id)},
                        },
                    ]
                else:
                    # Get newer messages
                    query["$or"] = [
                        {"created_at": {"$gt": timestamp}},
                        {
                            "created_at": timestamp,
                            "_id": {"$gt": ObjectId(last_id)},
                        },
                    ]
            except Exception:
                pass

        # Sort: newest first when getting messages before cursor
        sort_order = -1 if before else 1

        cursor_result = (
            self._collection.find(query)
            .sort([("created_at", sort_order), ("_id", sort_order)])
            .limit(limit + 1)
        )

        messages = []
        async for doc in cursor_result:
            doc["_id"] = str(doc["_id"])
            messages.append(Message(**doc))

        has_more = len(messages) > limit
        if has_more:
            messages = messages[:limit]

        # When getting messages before cursor, reverse to show oldest first
        if before:
            messages.reverse()

        # Generate next cursor
        next_cursor = None
        if has_more and messages:
            # For "before" pagination, use the first (oldest) message
            # For "after" pagination, use the last (newest) message
            cursor_msg = messages[0] if before else messages[-1]
            cursor_data = f"{cursor_msg.created_at.isoformat()}_{cursor_msg.id}"
            next_cursor = base64.b64encode(cursor_data.encode()).decode()

        return messages, next_cursor, has_more

    async def mark_read(
        self,
        chat_id: str,
        reader_type: SenderType,
        up_to_message_id: str | None = None,
    ) -> int:
        """Mark messages as read by reader type."""
        field = "read_by_user" if reader_type == SenderType.USER else "read_by_agent"

        query: dict[str, Any] = {
            "chat_id": chat_id,
            field: False,
        }

        if up_to_message_id:
            try:
                query["_id"] = {"$lte": ObjectId(up_to_message_id)}
            except Exception:
                pass

        result = await self._collection.update_many(
            query,
            {"$set": {field: True, "updated_at": datetime.utcnow()}},
        )
        return result.modified_count
