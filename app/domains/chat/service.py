"""Chat domain service - chat management business logic."""

from datetime import datetime

from app.core.exceptions import NotFoundError, ValidationError
from app.domains.chat.models import (
    Chat,
    ChatStatus,
    LastMessage,
    Message,
    MessageType,
    SenderType,
)
from app.domains.chat.repository import (
    ChatRepositoryInterface,
    MessageRepositoryInterface,
    MongoChatRepository,
    MongoMessageRepository,
)
from app.domains.chat.schemas import ChatCreate, ChatStatistics, MessageCreate


class ChatService:
    """Chat management service."""

    def __init__(
        self,
        chat_repository: ChatRepositoryInterface,
        message_repository: MessageRepositoryInterface,
        org_id: str,
        env_type: str,
    ):
        self._chat_repo = chat_repository
        self._message_repo = message_repository
        self._org_id = org_id
        self._env_type = env_type

    async def create_chat(
        self,
        data: ChatCreate,
        user_id: str,
    ) -> Chat:
        """
        Create a new chat.

        Args:
            data: Chat creation data
            user_id: MongoDB User ID

        Returns:
            Created chat
        """
        chat = Chat(
            org_id=self._org_id,
            env_type=self._env_type,
            user_id=user_id,
            member_id=data.member_id,
            metadata=data.metadata or {},
        )

        chat = await self._chat_repo.create(chat)

        # If initial message provided, create it
        if data.initial_message:
            await self.send_message(
                chat_id=chat.id,
                sender_type=SenderType.USER,
                sender_id=user_id,
                data=MessageCreate(content=data.initial_message),
            )
            # Refresh chat to get updated message count
            chat = await self._chat_repo.get_by_id(chat.id)

        return chat

    async def get_chat(self, chat_id: str) -> Chat:
        """
        Get chat by ID.

        Args:
            chat_id: Chat ID

        Returns:
            Chat

        Raises:
            NotFoundError: If chat not found
        """
        chat = await self._chat_repo.get_by_id(chat_id)
        if not chat:
            raise NotFoundError("Chat", chat_id)
        return chat

    async def list_chats(
        self,
        status: ChatStatus | None = None,
        agent_id: str | None = None,
        user_id: str | None = None,
        limit: int = 20,
        cursor: str | None = None,
    ) -> tuple[list[Chat], str | None, bool]:
        """
        List chats with pagination.

        Args:
            status: Filter by status
            agent_id: Filter by assigned agent
            user_id: Filter by user
            limit: Maximum number of results
            cursor: Cursor for pagination

        Returns:
            Tuple of (chats, next_cursor, has_more)
        """
        return await self._chat_repo.list_chats(
            status=status,
            agent_id=agent_id,
            user_id=user_id,
            limit=limit,
            cursor=cursor,
        )

    async def assign_agent(
        self,
        chat_id: str,
        agent_id: str,
        assigner_id: str,
    ) -> Chat:
        """
        Assign agent to chat.

        Args:
            chat_id: Chat ID
            agent_id: Agent ID to assign
            assigner_id: ID of the agent performing assignment

        Returns:
            Updated chat
        """
        chat = await self.get_chat(chat_id)

        if chat.status == ChatStatus.CLOSED:
            raise ValidationError("Cannot assign agent to closed chat")

        success = await self._chat_repo.assign_agent(chat_id, agent_id)
        if not success:
            raise NotFoundError("Chat", chat_id)

        # Record first response time if this is the first agent assignment
        if chat.first_response_at is None:
            chat = await self._chat_repo.get_by_id(chat_id)
            if isinstance(self._chat_repo, MongoChatRepository):
                chat.first_response_at = datetime.utcnow()
                await self._chat_repo.update(chat)

        return await self.get_chat(chat_id)

    async def close_chat(
        self,
        chat_id: str,
        closer_type: SenderType,
    ) -> Chat:
        """
        Close a chat.

        Args:
            chat_id: Chat ID
            closer_type: Who is closing (user or agent)

        Returns:
            Updated chat
        """
        chat = await self.get_chat(chat_id)

        if chat.status == ChatStatus.CLOSED:
            return chat  # Already closed

        await self._chat_repo.update_status(chat_id, ChatStatus.CLOSED)

        # Send system message
        await self.send_message(
            chat_id=chat_id,
            sender_type=SenderType.SYSTEM,
            sender_id="system",
            data=MessageCreate(
                content=f"Chat closed by {'user' if closer_type == SenderType.USER else 'agent'}",
                message_type=MessageType.SYSTEM,
            ),
        )

        return await self.get_chat(chat_id)

    async def resolve_chat(self, chat_id: str) -> Chat:
        """
        Mark chat as resolved.

        Args:
            chat_id: Chat ID

        Returns:
            Updated chat
        """
        chat = await self.get_chat(chat_id)

        if chat.status == ChatStatus.CLOSED:
            raise ValidationError("Cannot resolve closed chat")

        await self._chat_repo.update_status(chat_id, ChatStatus.RESOLVED)
        return await self.get_chat(chat_id)

    async def get_statistics(self) -> ChatStatistics:
        """Get chat statistics."""
        stats = await self._chat_repo.get_statistics()
        return ChatStatistics(**stats)

    async def send_message(
        self,
        chat_id: str,
        sender_type: SenderType,
        sender_id: str,
        data: MessageCreate,
    ) -> Message:
        """
        Send a message to chat.

        Args:
            chat_id: Chat ID
            sender_type: Who is sending
            sender_id: Sender's ID (user_id or agent_id)
            data: Message data

        Returns:
            Created message
        """
        # Verify chat exists and is not closed
        chat = await self.get_chat(chat_id)

        if chat.status == ChatStatus.CLOSED:
            raise ValidationError("Cannot send message to closed chat")

        # Create message
        message = Message(
            chat_id=chat_id,
            org_id=self._org_id,
            sender_type=sender_type,
            sender_id=sender_id,
            message_type=data.message_type,
            content=data.content,
            attachments=data.attachments or [],
        )

        # Auto-mark as read by sender
        if sender_type == SenderType.USER:
            message.read_by_user = True
        else:
            message.read_by_agent = True

        message = await self._message_repo.create(message)

        # Update chat's last message and message count
        last_message = LastMessage(
            sender_type=sender_type,
            content=data.content[:100],  # Truncate for preview
            message_type=data.message_type,
            created_at=message.created_at,
        )

        if isinstance(self._chat_repo, MongoChatRepository):
            await self._chat_repo.increment_message_count(
                chat_id=chat_id,
                sender_type=sender_type,
                last_message=last_message,
            )

        # Track first response time for agent messages
        if sender_type == SenderType.AGENT and chat.first_response_at is None:
            chat.first_response_at = datetime.utcnow()
            await self._chat_repo.update(chat)

        return message

    async def list_messages(
        self,
        chat_id: str,
        limit: int = 50,
        cursor: str | None = None,
        before: bool = True,
    ) -> tuple[list[Message], str | None, bool]:
        """
        List messages with cursor pagination.

        Args:
            chat_id: Chat ID
            limit: Maximum number of messages
            cursor: Cursor for pagination
            before: If True, get older messages

        Returns:
            Tuple of (messages, next_cursor, has_more)
        """
        # Verify chat exists
        await self.get_chat(chat_id)

        return await self._message_repo.list_messages(
            chat_id=chat_id,
            limit=limit,
            cursor=cursor,
            before=before,
        )

    async def mark_messages_read(
        self,
        chat_id: str,
        reader_type: SenderType,
        up_to_message_id: str | None = None,
    ) -> int:
        """
        Mark messages as read.

        Args:
            chat_id: Chat ID
            reader_type: Who is reading
            up_to_message_id: Mark all messages up to this ID

        Returns:
            Number of messages marked as read
        """
        # Verify chat exists
        await self.get_chat(chat_id)

        count = await self._message_repo.mark_read(
            chat_id=chat_id,
            reader_type=reader_type,
            up_to_message_id=up_to_message_id,
        )

        # Reset unread count in chat
        if isinstance(self._chat_repo, MongoChatRepository):
            await self._chat_repo.reset_unread_count(chat_id, reader_type)

        return count
