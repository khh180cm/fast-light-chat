"""Agent domain service - agent management business logic.

This service contains pure business logic and depends on repository interfaces,
not on specific database implementations.
"""

from uuid import UUID

from app.core.exceptions import ConflictError, NotFoundError
from app.core.security import hash_password
from app.domains.agent.models import Agent, AgentStatus
from app.domains.agent.repository import AgentRepositoryInterface
from app.domains.agent.schemas import AgentCreate, AgentUpdate, AgentStatusUpdate


class AgentService:
    """Agent management service (Application/Use Case layer).

    This service orchestrates business logic using repository interfaces.
    It doesn't know about SQLAlchemy or any specific database implementation.
    """

    def __init__(self, repository: AgentRepositoryInterface):
        self._repository = repository

    async def create_agent(
        self,
        org_id: UUID,
        data: AgentCreate,
    ) -> Agent:
        """
        Create a new agent.

        Business rules:
        - Email must be unique across all organizations
        - Password is hashed before storage

        Args:
            org_id: Organization ID
            data: Agent creation data

        Returns:
            Created agent

        Raises:
            ConflictError: If email already exists
        """
        # Business rule: email must be unique
        existing = await self._repository.get_by_email(data.email)
        if existing:
            raise ConflictError(f"Agent with email '{data.email}' already exists")

        # Create agent entity
        agent = Agent(
            organization_id=org_id,
            email=data.email,
            password_hash=hash_password(data.password),
            name=data.name,
            nickname=data.nickname,
            role=data.role,
            max_concurrent_chats=data.max_concurrent_chats,
        )

        return await self._repository.create(agent)

    async def get_agent(self, agent_id: UUID) -> Agent:
        """
        Get agent by ID.

        Args:
            agent_id: Agent ID

        Returns:
            Agent

        Raises:
            NotFoundError: If agent not found
        """
        agent = await self._repository.get_by_id(agent_id)
        if not agent:
            raise NotFoundError("Agent", str(agent_id))
        return agent

    async def get_agent_by_email(self, email: str) -> Agent | None:
        """
        Get agent by email.

        Args:
            email: Agent email

        Returns:
            Agent or None
        """
        return await self._repository.get_by_email(email)

    async def list_agents(
        self,
        org_id: UUID,
        skip: int = 0,
        limit: int = 20,
        include_inactive: bool = False,
    ) -> tuple[list[Agent], int]:
        """
        List agents in an organization.

        Args:
            org_id: Organization ID
            skip: Number of records to skip
            limit: Maximum number of records to return
            include_inactive: Include inactive agents

        Returns:
            Tuple of (agents list, total count)
        """
        return await self._repository.list_by_org(
            org_id=org_id,
            skip=skip,
            limit=limit,
            include_inactive=include_inactive,
        )

    async def update_agent(
        self,
        agent_id: UUID,
        data: AgentUpdate,
    ) -> Agent:
        """
        Update agent info.

        Args:
            agent_id: Agent ID
            data: Update data

        Returns:
            Updated agent
        """
        agent = await self.get_agent(agent_id)

        # Update fields that are provided
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(agent, field, value)

        return await self._repository.update(agent)

    async def update_status(
        self,
        agent_id: UUID,
        data: AgentStatusUpdate,
    ) -> Agent:
        """
        Update agent online status.

        Args:
            agent_id: Agent ID
            data: Status update data

        Returns:
            Updated agent
        """
        agent = await self.get_agent(agent_id)
        agent.status = data.status
        return await self._repository.update(agent)

    async def deactivate_agent(self, agent_id: UUID) -> Agent:
        """
        Deactivate an agent (soft delete).

        Business rules:
        - Deactivated agents are set to offline status

        Args:
            agent_id: Agent ID

        Returns:
            Deactivated agent
        """
        agent = await self.get_agent(agent_id)
        agent.is_active = False
        agent.status = AgentStatus.OFFLINE
        return await self._repository.update(agent)

    async def get_online_agents(self, org_id: UUID) -> list[Agent]:
        """
        Get all online agents in an organization.

        Args:
            org_id: Organization ID

        Returns:
            List of online agents
        """
        return await self._repository.get_online_agents(org_id)

    async def get_available_agent(self, org_id: UUID) -> Agent | None:
        """
        Get an available agent for chat assignment.

        Business rules:
        - Agent must be online
        - Agent must be active
        - Agent must have capacity (current < max concurrent chats)
        - Prefer agent with least current chats (load balancing)

        Args:
            org_id: Organization ID

        Returns:
            Available agent or None
        """
        return await self._repository.get_available_agent(org_id)

    async def increment_chat_count(self, agent_id: UUID) -> None:
        """Increment agent's current chat count."""
        agent = await self.get_agent(agent_id)
        agent.current_chat_count += 1
        await self._repository.update(agent)

    async def decrement_chat_count(self, agent_id: UUID) -> None:
        """Decrement agent's current chat count."""
        agent = await self.get_agent(agent_id)
        if agent.current_chat_count > 0:
            agent.current_chat_count -= 1
        await self._repository.update(agent)
