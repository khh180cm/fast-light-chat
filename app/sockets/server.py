"""Socket.IO server configuration and utilities."""

import socketio

from app.core.config import settings
from app.core.security import verify_access_token


# Create Socket.IO async server
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=settings.cors_origins if settings.is_production else "*",
    logger=settings.is_development,
    engineio_logger=settings.is_development,
    ping_timeout=60,
    ping_interval=25,
)


# Session storage for connected clients
# Maps sid -> user/agent info
connected_users: dict[str, dict] = {}
connected_agents: dict[str, dict] = {}


# Room naming helpers
def get_chat_room(chat_id: str) -> str:
    """Get room name for a chat."""
    return f"chat:{chat_id}"


def get_org_room(org_id: str) -> str:
    """Get room name for organization (agent notifications)."""
    return f"org:{org_id}"


def get_agent_room(agent_id: str) -> str:
    """Get room name for specific agent."""
    return f"agent:{agent_id}"


class SocketAuth:
    """Socket authentication utilities."""

    @staticmethod
    async def authenticate_agent(auth_data: dict) -> dict | None:
        """
        Authenticate agent from JWT token.

        Args:
            auth_data: dict with 'token' key

        Returns:
            Agent info dict or None if invalid
        """
        token = auth_data.get("token")
        if not token:
            return None

        try:
            payload = verify_access_token(token)
            return {
                "user_id": payload.get("sub"),
                "org_id": payload.get("org_id"),
                "role": payload.get("role"),
                "email": payload.get("email"),
                "name": payload.get("name"),
                "type": "agent",
            }
        except Exception:
            return None

    @staticmethod
    async def authenticate_user(auth_data: dict) -> dict | None:
        """
        Authenticate user from plugin key and session/user info.

        Args:
            auth_data: dict with 'plugin_key', 'user_id' or 'session_id'

        Returns:
            User info dict or None if invalid
        """
        from sqlalchemy import select

        from app.db.postgres import AsyncSessionLocal
        from app.domains.environment.models import Environment

        plugin_key = auth_data.get("plugin_key")
        if not plugin_key:
            return None

        user_id = auth_data.get("user_id") or auth_data.get("session_id")
        member_id = auth_data.get("member_id")
        if not user_id:
            return None

        try:
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(Environment).where(
                        Environment.plugin_key == plugin_key,
                        Environment.is_active == True,
                    )
                )
                env = result.scalar_one_or_none()

                if not env:
                    return None

                return {
                    "user_id": user_id,
                    "member_id": member_id or user_id,
                    "org_id": str(env.organization_id),
                    "env_type": env.env_type.value,
                    "type": "user",
                }
        except Exception:
            return None


# Import and register namespaces
from app.sockets.namespaces.chat import ChatNamespace
from app.sockets.namespaces.agent import AgentNamespace

sio.register_namespace(ChatNamespace("/chat"))
sio.register_namespace(AgentNamespace("/agent"))
