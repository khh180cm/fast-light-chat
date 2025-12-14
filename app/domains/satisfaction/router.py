"""Satisfaction survey API routes."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.db.mongodb import get_mongodb
from app.dependencies.auth import (
    AdminOnly,
    CurrentAgent,
    PluginKeyAuth,
)
from app.domains.satisfaction.repository import MongoSatisfactionRepository
from app.domains.satisfaction.schemas import (
    SatisfactionCreate,
    SatisfactionResponse,
    SatisfactionStatistics,
)
from app.domains.satisfaction.service import SatisfactionService

router = APIRouter(prefix="/satisfaction")


def get_satisfaction_service(
    env: PluginKeyAuth,
) -> SatisfactionService:
    """Get satisfaction service with plugin key auth."""
    db = get_mongodb()
    repo = MongoSatisfactionRepository(
        db=db,
        org_id=env["org_id"],
        env_type=env["env_type"],
    )
    return SatisfactionService(
        repository=repo,
        org_id=env["org_id"],
        env_type=env["env_type"],
    )


def get_satisfaction_service_jwt(
    agent: CurrentAgent,
) -> SatisfactionService:
    """Get satisfaction service with JWT auth."""
    db = get_mongodb()
    # Use production env type for dashboard
    env_type = "production"
    repo = MongoSatisfactionRepository(
        db=db,
        org_id=str(agent["org_id"]),
        env_type=env_type,
    )
    return SatisfactionService(
        repository=repo,
        org_id=str(agent["org_id"]),
        env_type=env_type,
    )


# ============================================================
# Plugin Key Auth Endpoints (for chat widget)
# ============================================================


@router.get(
    "/chat/{chat_id}",
    response_model=SatisfactionResponse | None,
    summary="Get survey for chat",
    description="Get satisfaction survey for a specific chat (for chat widget).",
)
async def get_survey_by_chat(
    chat_id: str,
    service: Annotated[SatisfactionService, Depends(get_satisfaction_service)],
):
    """Get satisfaction survey by chat ID."""
    survey = await service.get_survey_by_chat(chat_id)
    if not survey:
        return None
    return SatisfactionResponse(
        id=survey.id,
        chat_id=survey.chat_id,
        status=survey.status,
        rating=survey.rating,
        feedback=survey.feedback,
        triggered_by=survey.triggered_by,
        created_at=survey.created_at,
        responded_at=survey.responded_at,
    )


@router.post(
    "/{survey_id}/submit",
    response_model=SatisfactionResponse,
    summary="Submit survey response",
    description="Submit satisfaction survey response (rating and optional feedback).",
)
async def submit_survey(
    survey_id: str,
    data: SatisfactionCreate,
    service: Annotated[SatisfactionService, Depends(get_satisfaction_service)],
):
    """Submit satisfaction survey response."""
    survey = await service.submit_response(survey_id, data)
    return SatisfactionResponse(
        id=survey.id,
        chat_id=survey.chat_id,
        status=survey.status,
        rating=survey.rating,
        feedback=survey.feedback,
        triggered_by=survey.triggered_by,
        created_at=survey.created_at,
        responded_at=survey.responded_at,
    )


@router.post(
    "/{survey_id}/skip",
    response_model=SatisfactionResponse,
    summary="Skip survey",
    description="Mark survey as skipped.",
)
async def skip_survey(
    survey_id: str,
    service: Annotated[SatisfactionService, Depends(get_satisfaction_service)],
):
    """Skip satisfaction survey."""
    survey = await service.skip_survey(survey_id)
    return SatisfactionResponse(
        id=survey.id,
        chat_id=survey.chat_id,
        status=survey.status,
        rating=survey.rating,
        feedback=survey.feedback,
        triggered_by=survey.triggered_by,
        created_at=survey.created_at,
        responded_at=survey.responded_at,
    )


# ============================================================
# JWT Auth Endpoints (for agent dashboard)
# ============================================================


@router.get(
    "/statistics",
    response_model=SatisfactionStatistics,
    summary="Get satisfaction statistics",
    description="Get satisfaction survey statistics for the organization.",
)
async def get_statistics(
    agent: AdminOnly,
    service: Annotated[SatisfactionService, Depends(get_satisfaction_service_jwt)],
):
    """Get satisfaction survey statistics."""
    return await service.get_statistics()
