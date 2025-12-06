"""Agent repository - data access layer."""

from abc import ABC, abstractmethod
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.agent.models import Agent, AgentStatus


class AgentRepositoryInterface(ABC):
    """Agent repository interface (Port)."""

    @abstractmethod
    async def create(self, agent: Agent) -> Agent:
        """Create a new agent."""
        pass

    @abstractmethod
    async def get_by_id(self, agent_id: UUID) -> Agent | None:
        """Get agent by ID."""
        pass

    @abstractmethod
    async def get_by_email(self, email: str) -> Agent | None:
        """Get agent by email."""
        pass

    @abstractmethod
    async def list_by_org(
        self,
        org_id: UUID,
        skip: int = 0,
        limit: int = 20,
        include_inactive: bool = False,
    ) -> tuple[list[Agent], int]:
        """List agents by organization."""
        pass

    @abstractmethod
    async def update(self, agent: Agent) -> Agent:
        """Update an agent."""
        pass

    @abstractmethod
    async def get_online_agents(self, org_id: UUID) -> list[Agent]:
        """Get all online agents in organization."""
        pass

    @abstractmethod
    async def get_available_agent(self, org_id: UUID) -> Agent | None:
        """Get available agent for chat assignment."""
        pass


class AgentRepository(AgentRepositoryInterface):
    """SQLAlchemy implementation of agent repository (Adapter)."""

    def __init__(self, db: AsyncSession):
        self._db = db

    async def create(self, agent: Agent) -> Agent:
        """Create a new agent."""
        self._db.add(agent)
        await self._db.commit()
        await self._db.refresh(agent)
        return agent

    async def get_by_id(self, agent_id: UUID) -> Agent | None:
        """Get agent by ID."""
        result = await self._db.execute(
            select(Agent).where(Agent.id == agent_id)
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Agent | None:
        """Get agent by email."""
        result = await self._db.execute(
            select(Agent).where(Agent.email == email)
        )
        return result.scalar_one_or_none()

    async def list_by_org(
        self,
        org_id: UUID,
        skip: int = 0,
        limit: int = 20,
        include_inactive: bool = False,
    ) -> tuple[list[Agent], int]:
        """List agents by organization."""
        query = select(Agent).where(Agent.organization_id == org_id)

        if not include_inactive:
            query = query.where(Agent.is_active == True)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total = await self._db.scalar(count_query)

        # Get paginated results
        query = query.offset(skip).limit(limit).order_by(Agent.created_at.desc())
        result = await self._db.execute(query)
        agents = result.scalars().all()

        return list(agents), total or 0

    async def update(self, agent: Agent) -> Agent:
        """Update an agent."""
        await self._db.commit()
        await self._db.refresh(agent)
        return agent

    async def get_online_agents(self, org_id: UUID) -> list[Agent]:
        """Get all online agents in organization."""
        result = await self._db.execute(
            select(Agent).where(
                Agent.organization_id == org_id,
                Agent.is_active == True,
                Agent.status == AgentStatus.ONLINE,
            )
        )
        return list(result.scalars().all())

    async def get_available_agent(self, org_id: UUID) -> Agent | None:
        """Get available agent for chat assignment."""
        result = await self._db.execute(
            select(Agent)
            .where(
                Agent.organization_id == org_id,
                Agent.is_active == True,
                Agent.status == AgentStatus.ONLINE,
                Agent.current_chat_count < Agent.max_concurrent_chats,
            )
            .order_by(Agent.current_chat_count.asc())
            .limit(1)
        )
        return result.scalar_one_or_none()
