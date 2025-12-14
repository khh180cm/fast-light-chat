"""Message Draft service - temporary message storage with AI transformation.

Drafts are stored in Redis for quick access and auto-expiration.
"""

import json
import uuid
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field
from redis.asyncio import Redis

from app.integrations.llm.transformer import MessageTransformer


class DraftStatus(str, Enum):
    """Draft status enum."""

    PENDING = "pending"  # Waiting for agent to review/send
    SENT = "sent"  # Message was sent
    DISCARDED = "discarded"  # Agent discarded the draft


class MessageDraft(BaseModel):
    """Message draft model stored in Redis."""

    id: str
    chat_id: str
    agent_id: str
    org_id: str

    # Message content
    original_message: str
    transformed_message: str | None = None
    final_message: str  # What will actually be sent

    # AI info
    ai_transformed: bool = False
    tone_profile_name: str | None = None
    tone_profile_version: int | None = None

    # Status
    status: DraftStatus = DraftStatus.PENDING

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MessageDraftService:
    """
    Service for managing message drafts with AI transformation.

    Flow:
    1. Agent types message
    2. Agent clicks "AI 교정" button
    3. System creates draft with original + transformed message
    4. Agent can:
       - Edit the transformed message
       - Send the transformed message
       - Send the original message
       - Discard the draft
    5. When sent, the actual message is created in chat
    """

    DRAFT_TTL = 3600  # 1 hour

    def __init__(
        self,
        redis: Redis,
        transformer: MessageTransformer,
        org_id: str,
        agent_id: str,
    ):
        self._redis = redis
        self._transformer = transformer
        self._org_id = org_id
        self._agent_id = agent_id

    def _draft_key(self, draft_id: str) -> str:
        """Get Redis key for a draft."""
        return f"draft:{self._org_id}:{draft_id}"

    def _agent_drafts_key(self) -> str:
        """Get Redis key for agent's draft list."""
        return f"agent_drafts:{self._org_id}:{self._agent_id}"

    async def create_draft(
        self,
        chat_id: str,
        original_message: str,
        use_ai_transform: bool = True,
    ) -> MessageDraft:
        """
        Create a new message draft.

        Args:
            chat_id: Chat ID to send message to
            original_message: Original message from agent
            use_ai_transform: Whether to apply AI transformation

        Returns:
            Created MessageDraft
        """
        draft_id = str(uuid.uuid4())

        transformed_message = None
        tone_profile_name = None
        tone_profile_version = None

        if use_ai_transform:
            # Transform using AI
            result = await self._transformer.transform(original_message)
            transformed_message = result["transformed_message"]
            tone_profile_name = result["tone_profile_name"]
            tone_profile_version = result["tone_profile_version"]

        draft = MessageDraft(
            id=draft_id,
            chat_id=chat_id,
            agent_id=self._agent_id,
            org_id=self._org_id,
            original_message=original_message,
            transformed_message=transformed_message,
            final_message=transformed_message or original_message,
            ai_transformed=use_ai_transform and transformed_message is not None,
            tone_profile_name=tone_profile_name,
            tone_profile_version=tone_profile_version,
        )

        # Store in Redis
        await self._redis.setex(
            self._draft_key(draft_id),
            self.DRAFT_TTL,
            draft.model_dump_json(),
        )

        # Add to agent's draft list
        await self._redis.sadd(self._agent_drafts_key(), draft_id)

        return draft

    async def get_draft(self, draft_id: str) -> MessageDraft | None:
        """Get a draft by ID."""
        data = await self._redis.get(self._draft_key(draft_id))
        if not data:
            return None
        return MessageDraft.model_validate_json(data)

    async def update_draft(
        self,
        draft_id: str,
        final_message: str,
    ) -> MessageDraft | None:
        """
        Update the final message in a draft.

        Args:
            draft_id: Draft ID
            final_message: Edited final message

        Returns:
            Updated draft or None if not found
        """
        draft = await self.get_draft(draft_id)
        if not draft or draft.status != DraftStatus.PENDING:
            return None

        draft.final_message = final_message
        draft.updated_at = datetime.now(timezone.utc)

        # Save back
        await self._redis.setex(
            self._draft_key(draft_id),
            self.DRAFT_TTL,
            draft.model_dump_json(),
        )

        return draft

    async def mark_sent(self, draft_id: str) -> MessageDraft | None:
        """Mark a draft as sent."""
        draft = await self.get_draft(draft_id)
        if not draft or draft.status != DraftStatus.PENDING:
            return None

        draft.status = DraftStatus.SENT
        draft.updated_at = datetime.now(timezone.utc)

        # Save with short TTL (keep for reference)
        await self._redis.setex(
            self._draft_key(draft_id),
            300,  # 5 minutes
            draft.model_dump_json(),
        )

        # Remove from agent's draft list
        await self._redis.srem(self._agent_drafts_key(), draft_id)

        return draft

    async def discard_draft(self, draft_id: str) -> bool:
        """Discard a draft."""
        draft = await self.get_draft(draft_id)
        if not draft or draft.status != DraftStatus.PENDING:
            return False

        # Delete from Redis
        await self._redis.delete(self._draft_key(draft_id))
        await self._redis.srem(self._agent_drafts_key(), draft_id)

        return True

    async def get_agent_drafts(self) -> list[MessageDraft]:
        """Get all pending drafts for the current agent."""
        draft_ids = await self._redis.smembers(self._agent_drafts_key())
        drafts = []

        for draft_id in draft_ids:
            if isinstance(draft_id, bytes):
                draft_id = draft_id.decode()
            draft = await self.get_draft(draft_id)
            if draft and draft.status == DraftStatus.PENDING:
                drafts.append(draft)
            elif not draft:
                # Clean up stale reference
                await self._redis.srem(self._agent_drafts_key(), draft_id)

        return drafts

    async def use_original(self, draft_id: str) -> MessageDraft | None:
        """Set draft to use original message instead of transformed."""
        draft = await self.get_draft(draft_id)
        if not draft or draft.status != DraftStatus.PENDING:
            return None

        draft.final_message = draft.original_message
        draft.updated_at = datetime.now(timezone.utc)

        await self._redis.setex(
            self._draft_key(draft_id),
            self.DRAFT_TTL,
            draft.model_dump_json(),
        )

        return draft
