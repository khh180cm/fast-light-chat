"""Tone Profile and Message Draft API routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres import get_db
from app.db.redis import get_redis
from app.dependencies.auth import AdminOnly, CurrentAgent
from app.domains.tone_profile.draft_service import MessageDraft, MessageDraftService
from app.domains.tone_profile.schemas import (
    MessageDraftCreate,
    MessageDraftUpdate,
    MessageTransformRequest,
    MessageTransformResponse,
    ToneProfileResponse,
    ToneProfileUpdate,
    ToneProfileVersionListResponse,
    ToneProfileVersionResponse,
)
from app.domains.tone_profile.service import ToneProfileService
from app.integrations.llm.base import LLMProviderType
from app.integrations.llm.transformer import MessageTransformer

router = APIRouter(prefix="/tone-profile")


# ============================================================
# Tone Profile Endpoints
# ============================================================


# ============================================================
# Tone Profile Endpoints
# ============================================================


@router.get(
    "",
    response_model=ToneProfileResponse,
    summary="Get tone profile",
    description="Get organization's tone profile. Creates default if not exists.",
)
async def get_profile(
    agent: CurrentAgent,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get the organization's tone profile."""
    service = ToneProfileService(db, agent["org_id"])
    profile = await service.get_or_create_profile()
    return ToneProfileResponse.model_validate(profile)


@router.put(
    "",
    response_model=ToneProfileResponse,
    summary="Update tone profile",
    description="Update tone profile settings. Creates a new version.",
)
async def update_profile(
    data: ToneProfileUpdate,
    agent: AdminOnly,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Update the tone profile."""
    service = ToneProfileService(db, agent["org_id"])
    profile = await service.update_profile(data, agent["user_id"])
    return ToneProfileResponse.model_validate(profile)


@router.get(
    "/versions",
    response_model=ToneProfileVersionListResponse,
    summary="Get version history",
    description="Get tone profile version history for rollback.",
)
async def get_versions(
    agent: CurrentAgent,
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(10, ge=1, le=50),
    offset: int = Query(0, ge=0),
):
    """Get tone profile version history."""
    service = ToneProfileService(db, agent["org_id"])
    versions, total = await service.get_version_history(limit, offset)
    return ToneProfileVersionListResponse(
        items=[ToneProfileVersionResponse.model_validate(v) for v in versions],
        total=total,
    )


@router.post(
    "/versions/{version}/restore",
    response_model=ToneProfileResponse,
    summary="Restore version",
    description="Restore tone profile to a previous version.",
)
async def restore_version(
    version: int,
    agent: AdminOnly,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Restore to a previous version."""
    service = ToneProfileService(db, agent["org_id"])
    profile = await service.restore_version(version, agent["user_id"])
    return ToneProfileResponse.model_validate(profile)


class ToggleActiveRequest(BaseModel):
    is_active: bool


@router.post(
    "/toggle",
    response_model=ToneProfileResponse,
    summary="Toggle active status",
    description="Enable or disable AI tone transformation.",
)
async def toggle_active(
    data: ToggleActiveRequest,
    agent: AdminOnly,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Toggle tone profile active status."""
    service = ToneProfileService(db, agent["org_id"])
    profile = await service.toggle_active(data.is_active)
    return ToneProfileResponse.model_validate(profile)


# ============================================================
# Message Transform Endpoints
# ============================================================


@router.post(
    "/transform",
    response_model=MessageTransformResponse,
    summary="Transform message",
    description="Transform a message using AI with the current tone profile.",
)
async def transform_message(
    data: MessageTransformRequest,
    agent: CurrentAgent,
    db: Annotated[AsyncSession, Depends(get_db)],
    provider: LLMProviderType | None = Query(None, description="LLM provider to use"),
):
    """Transform a message using AI."""
    transformer = MessageTransformer(db, agent["org_id"])
    result = await transformer.transform(data.original_message, provider)
    return MessageTransformResponse(
        original_message=result["original_message"],
        transformed_message=result["transformed_message"],
        tone_profile_name=result["tone_profile_name"],
        tone_profile_version=result["tone_profile_version"],
    )


class PreviewTransformRequest(BaseModel):
    original_message: str
    custom_prompt: str | None = None


@router.post(
    "/transform/preview",
    response_model=MessageTransformResponse,
    summary="Preview transformation",
    description="Preview transformation with optional custom prompt (for testing).",
)
async def preview_transform(
    data: PreviewTransformRequest,
    agent: AdminOnly,
    db: Annotated[AsyncSession, Depends(get_db)],
    provider: LLMProviderType | None = Query(None),
):
    """Preview transformation with custom prompt."""
    transformer = MessageTransformer(db, agent["org_id"])
    result = await transformer.preview_transform(
        data.original_message,
        data.custom_prompt,
        provider,
    )
    return MessageTransformResponse(
        original_message=result["original_message"],
        transformed_message=result["transformed_message"],
        tone_profile_name=result["tone_profile_name"],
        tone_profile_version=result["tone_profile_version"],
    )


# ============================================================
# Message Draft Endpoints
# ============================================================


class DraftResponse(BaseModel):
    """Message draft response."""

    id: str
    chat_id: str
    original_message: str
    transformed_message: str | None
    final_message: str
    ai_transformed: bool
    tone_profile_name: str | None
    status: str
    created_at: str

    @classmethod
    def from_draft(cls, draft: MessageDraft) -> "DraftResponse":
        return cls(
            id=draft.id,
            chat_id=draft.chat_id,
            original_message=draft.original_message,
            transformed_message=draft.transformed_message,
            final_message=draft.final_message,
            ai_transformed=draft.ai_transformed,
            tone_profile_name=draft.tone_profile_name,
            status=draft.status.value,
            created_at=draft.created_at.isoformat(),
        )


@router.post(
    "/drafts",
    response_model=DraftResponse,
    summary="Create message draft",
    description="Create a message draft with optional AI transformation.",
)
async def create_draft(
    data: MessageDraftCreate,
    agent: CurrentAgent,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Create a new message draft."""
    redis = get_redis()
    transformer = MessageTransformer(db, agent["org_id"])
    service = MessageDraftService(
        redis=redis,
        transformer=transformer,
        org_id=str(agent["org_id"]),
        agent_id=str(agent["user_id"]),
    )
    draft = await service.create_draft(
        chat_id=data.chat_id,
        original_message=data.original_message,
        use_ai_transform=data.use_ai_transform,
    )
    return DraftResponse.from_draft(draft)


@router.get(
    "/drafts",
    response_model=list[DraftResponse],
    summary="Get my drafts",
    description="Get all pending drafts for the current agent.",
)
async def get_my_drafts(
    agent: CurrentAgent,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get all pending drafts for current agent."""
    redis = get_redis()
    transformer = MessageTransformer(db, agent["org_id"])
    service = MessageDraftService(
        redis=redis,
        transformer=transformer,
        org_id=str(agent["org_id"]),
        agent_id=str(agent["user_id"]),
    )
    drafts = await service.get_agent_drafts()
    return [DraftResponse.from_draft(d) for d in drafts]


@router.get(
    "/drafts/{draft_id}",
    response_model=DraftResponse,
    summary="Get draft",
    description="Get a specific message draft.",
)
async def get_draft(
    draft_id: str,
    agent: CurrentAgent,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get a specific draft."""
    redis = get_redis()
    transformer = MessageTransformer(db, agent["org_id"])
    service = MessageDraftService(
        redis=redis,
        transformer=transformer,
        org_id=str(agent["org_id"]),
        agent_id=str(agent["user_id"]),
    )
    draft = await service.get_draft(draft_id)
    if not draft:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("Draft", draft_id)
    return DraftResponse.from_draft(draft)


@router.put(
    "/drafts/{draft_id}",
    response_model=DraftResponse,
    summary="Update draft",
    description="Update the final message in a draft.",
)
async def update_draft(
    draft_id: str,
    data: MessageDraftUpdate,
    agent: CurrentAgent,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Update draft's final message."""
    redis = get_redis()
    transformer = MessageTransformer(db, agent["org_id"])
    service = MessageDraftService(
        redis=redis,
        transformer=transformer,
        org_id=str(agent["org_id"]),
        agent_id=str(agent["user_id"]),
    )
    draft = await service.update_draft(draft_id, data.final_message)
    if not draft:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("Draft", draft_id)
    return DraftResponse.from_draft(draft)


@router.post(
    "/drafts/{draft_id}/use-original",
    response_model=DraftResponse,
    summary="Use original message",
    description="Set draft to use original message instead of transformed.",
)
async def use_original(
    draft_id: str,
    agent: CurrentAgent,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Use original message instead of transformed."""
    redis = get_redis()
    transformer = MessageTransformer(db, agent["org_id"])
    service = MessageDraftService(
        redis=redis,
        transformer=transformer,
        org_id=str(agent["org_id"]),
        agent_id=str(agent["user_id"]),
    )
    draft = await service.use_original(draft_id)
    if not draft:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("Draft", draft_id)
    return DraftResponse.from_draft(draft)


@router.post(
    "/drafts/{draft_id}/send",
    response_model=DraftResponse,
    summary="Send draft",
    description="Mark draft as sent. The actual message sending should be done via chat API.",
)
async def send_draft(
    draft_id: str,
    agent: CurrentAgent,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Mark draft as sent."""
    redis = get_redis()
    transformer = MessageTransformer(db, agent["org_id"])
    service = MessageDraftService(
        redis=redis,
        transformer=transformer,
        org_id=str(agent["org_id"]),
        agent_id=str(agent["user_id"]),
    )
    draft = await service.mark_sent(draft_id)
    if not draft:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("Draft", draft_id)
    return DraftResponse.from_draft(draft)


@router.delete(
    "/drafts/{draft_id}",
    summary="Discard draft",
    description="Discard a message draft.",
)
async def discard_draft(
    draft_id: str,
    agent: CurrentAgent,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Discard a draft."""
    redis = get_redis()
    transformer = MessageTransformer(db, agent["org_id"])
    service = MessageDraftService(
        redis=redis,
        transformer=transformer,
        org_id=str(agent["org_id"]),
        agent_id=str(agent["user_id"]),
    )
    success = await service.discard_draft(draft_id)
    if not success:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("Draft", draft_id)
    return {"message": "Draft discarded"}
