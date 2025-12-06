"""Agent API router - agent management endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres import get_db
from app.dependencies.auth import AdminOnly, CurrentAgent
from app.domains.agent.repository import AgentRepository
from app.domains.agent.schemas import (
    AgentCreate,
    AgentListResponse,
    AgentResponse,
    AgentStatusUpdate,
    AgentUpdate,
)
from app.domains.agent.service import AgentService

router = APIRouter()


def get_agent_service(db: AsyncSession = Depends(get_db)) -> AgentService:
    """Dependency injection for AgentService."""
    repository = AgentRepository(db)
    return AgentService(repository)


@router.get("/me", response_model=AgentResponse)
async def get_me(
    current_agent: CurrentAgent,
    service: AgentService = Depends(get_agent_service),
):
    """
    Get current agent's information.
    """
    agent = await service.get_agent(UUID(current_agent["user_id"]))
    return agent


@router.put("/me", response_model=AgentResponse)
async def update_me(
    data: AgentUpdate,
    current_agent: CurrentAgent,
    service: AgentService = Depends(get_agent_service),
):
    """
    Update current agent's information.
    """
    agent = await service.update_agent(UUID(current_agent["user_id"]), data)
    return agent


@router.put("/me/status", response_model=AgentResponse)
async def update_my_status(
    data: AgentStatusUpdate,
    current_agent: CurrentAgent,
    service: AgentService = Depends(get_agent_service),
):
    """
    Update current agent's online status.

    Status options: online, away, busy, offline
    """
    agent = await service.update_status(UUID(current_agent["user_id"]), data)
    return agent


@router.get("", response_model=AgentListResponse)
async def list_agents(
    current_agent: AdminOnly,
    service: AgentService = Depends(get_agent_service),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    include_inactive: bool = Query(False),
):
    """
    List all agents in the organization.

    Requires admin role.
    """
    agents, total = await service.list_agents(
        org_id=UUID(current_agent["org_id"]),
        skip=skip,
        limit=limit,
        include_inactive=include_inactive,
    )
    return AgentListResponse(items=agents, total=total)


@router.post("", response_model=AgentResponse, status_code=201)
async def create_agent(
    data: AgentCreate,
    current_agent: AdminOnly,
    service: AgentService = Depends(get_agent_service),
):
    """
    Create a new agent in the organization.

    Requires admin role.
    """
    agent = await service.create_agent(
        org_id=UUID(current_agent["org_id"]),
        data=data,
    )
    return agent


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: UUID,
    current_agent: AdminOnly,
    service: AgentService = Depends(get_agent_service),
):
    """
    Get agent by ID.

    Requires admin role.
    """
    agent = await service.get_agent(agent_id)
    return agent


@router.put("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: UUID,
    data: AgentUpdate,
    current_agent: AdminOnly,
    service: AgentService = Depends(get_agent_service),
):
    """
    Update agent by ID.

    Requires admin role.
    """
    agent = await service.update_agent(agent_id, data)
    return agent


@router.delete("/{agent_id}")
async def deactivate_agent(
    agent_id: UUID,
    current_agent: AdminOnly,
    service: AgentService = Depends(get_agent_service),
):
    """
    Deactivate agent (soft delete).

    Requires admin role.
    """
    await service.deactivate_agent(agent_id)
    return {"message": "Agent deactivated"}
