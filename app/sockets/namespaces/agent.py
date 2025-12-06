"""Agent namespace - handles agent dashboard socket events."""

import socketio

from app.db.mongodb import get_mongodb
from app.domains.chat.models import MessageType, SenderType
from app.domains.chat.repository import MongoChatRepository, MongoMessageRepository
from app.domains.chat.schemas import MessageCreate
from app.domains.chat.service import ChatService
from app.sockets.server import (
    SocketAuth,
    connected_agents,
    get_agent_room,
    get_chat_room,
    get_org_room,
)


class AgentNamespace(socketio.AsyncNamespace):
    """
    Agent namespace for dashboard events.

    Handles:
    - Agent authentication via JWT
    - Status updates (online/away/offline)
    - New chat notifications
    - Sending messages as agent
    - Chat assignment
    """

    async def on_connect(self, sid, environ, auth):
        """Handle agent connection."""
        if not auth:
            return False

        agent_info = await SocketAuth.authenticate_agent(auth)
        if not agent_info:
            return False

        # Store session info
        connected_agents[sid] = agent_info

        # Join organization room for new chat notifications
        await self.enter_room(sid, get_org_room(agent_info["org_id"]))

        # Join personal agent room
        await self.enter_room(sid, get_agent_room(agent_info["user_id"]))

        # Update agent status to online in Redis
        await self._set_agent_status(agent_info["org_id"], agent_info["user_id"], "online")

        # Notify other agents of status change
        await self.emit(
            "agent_status_changed",
            {
                "agent_id": agent_info["user_id"],
                "status": "online",
                "name": agent_info.get("name"),
            },
            room=get_org_room(agent_info["org_id"]),
        )

        print(f"[Agent] Connected: {sid} - {agent_info.get('email')}")
        return True

    async def on_disconnect(self, sid):
        """Handle agent disconnection."""
        agent_info = connected_agents.pop(sid, None)
        if agent_info:
            # Update status to offline
            await self._set_agent_status(
                agent_info["org_id"], agent_info["user_id"], "offline"
            )

            # Notify other agents
            await self.emit(
                "agent_status_changed",
                {
                    "agent_id": agent_info["user_id"],
                    "status": "offline",
                    "name": agent_info.get("name"),
                },
                room=get_org_room(agent_info["org_id"]),
            )

            print(f"[Agent] Disconnected: {sid} - {agent_info.get('email')}")

    async def on_status_change(self, sid, data):
        """
        Update agent status.

        Data: { status: "online" | "away" | "busy" | "offline" }
        """
        agent_info = connected_agents.get(sid)
        if not agent_info:
            return {"error": "Not authenticated"}

        status = data.get("status")
        if status not in ["online", "away", "busy", "offline"]:
            return {"error": "Invalid status"}

        await self._set_agent_status(agent_info["org_id"], agent_info["user_id"], status)

        # Notify other agents
        await self.emit(
            "agent_status_changed",
            {
                "agent_id": agent_info["user_id"],
                "status": status,
                "name": agent_info.get("name"),
            },
            room=get_org_room(agent_info["org_id"]),
        )

        return {"success": True, "status": status}

    async def on_join_chat(self, sid, data):
        """
        Join a chat room.

        Data: { chat_id: string }
        """
        agent_info = connected_agents.get(sid)
        if not agent_info:
            return {"error": "Not authenticated"}

        chat_id = data.get("chat_id")
        if not chat_id:
            return {"error": "chat_id required"}

        room = get_chat_room(chat_id)
        await self.enter_room(sid, room)

        print(f"[Agent] {agent_info.get('email')} joined chat: {chat_id}")
        return {"success": True, "chat_id": chat_id}

    async def on_leave_chat(self, sid, data):
        """
        Leave a chat room.

        Data: { chat_id: string }
        """
        chat_id = data.get("chat_id")
        if not chat_id:
            return {"error": "chat_id required"}

        room = get_chat_room(chat_id)
        await self.leave_room(sid, room)
        return {"success": True}

    async def on_send_message(self, sid, data):
        """
        Send a message as agent.

        Data: {
            chat_id: string,
            content: string,
            message_type?: "text" | "image" | "file"
        }
        """
        agent_info = connected_agents.get(sid)
        if not agent_info:
            return {"error": "Not authenticated"}

        chat_id = data.get("chat_id")
        content = data.get("content")

        if not chat_id or not content:
            return {"error": "chat_id and content required"}

        try:
            db = get_mongodb()
            # Use production env for agent dashboard
            env_type = "production"

            chat_repo = MongoChatRepository(
                db=db,
                org_id=agent_info["org_id"],
                env_type=env_type,
            )
            message_repo = MongoMessageRepository(
                db=db,
                org_id=agent_info["org_id"],
                env_type=env_type,
            )
            service = ChatService(
                chat_repository=chat_repo,
                message_repository=message_repo,
                org_id=agent_info["org_id"],
                env_type=env_type,
            )

            message_type = MessageType(data.get("message_type", "text"))
            message = await service.send_message(
                chat_id=chat_id,
                sender_type=SenderType.AGENT,
                sender_id=agent_info["user_id"],
                data=MessageCreate(content=content, message_type=message_type),
            )

            message_data = {
                "id": str(message.id),
                "chat_id": message.chat_id,
                "sender_type": message.sender_type.value if hasattr(message.sender_type, 'value') else message.sender_type,
                "sender_id": message.sender_id,
                "sender_name": agent_info.get("name"),
                "message_type": message.message_type.value if hasattr(message.message_type, 'value') else message.message_type,
                "content": message.content,
                "created_at": message.created_at.isoformat(),
            }

            # Broadcast to chat room
            room = get_chat_room(chat_id)
            await self.emit("new_message", message_data, room=room)

            # Also emit to /chat namespace for user clients
            from app.sockets.server import sio
            await sio.emit("new_message", message_data, room=room, namespace="/chat")

            return {"success": True, "message": message_data}

        except Exception as e:
            print(f"[Agent] Error sending message: {e}")
            return {"error": str(e)}

    async def on_typing_start(self, sid, data):
        """Notify that agent started typing."""
        agent_info = connected_agents.get(sid)
        if not agent_info:
            return

        chat_id = data.get("chat_id")
        if not chat_id:
            return

        room = get_chat_room(chat_id)

        typing_data = {
            "chat_id": chat_id,
            "user_id": agent_info["user_id"],
            "user_name": agent_info.get("name"),
            "user_type": "agent",
            "is_typing": True,
        }

        # Emit to both namespaces
        await self.emit("typing", typing_data, room=room, skip_sid=sid)

        from app.sockets.server import sio
        await sio.emit("typing", typing_data, room=room, namespace="/chat")

    async def on_typing_stop(self, sid, data):
        """Notify that agent stopped typing."""
        agent_info = connected_agents.get(sid)
        if not agent_info:
            return

        chat_id = data.get("chat_id")
        if not chat_id:
            return

        room = get_chat_room(chat_id)

        typing_data = {
            "chat_id": chat_id,
            "user_id": agent_info["user_id"],
            "user_name": agent_info.get("name"),
            "user_type": "agent",
            "is_typing": False,
        }

        await self.emit("typing", typing_data, room=room, skip_sid=sid)

        from app.sockets.server import sio
        await sio.emit("typing", typing_data, room=room, namespace="/chat")

    async def on_assign_chat(self, sid, data):
        """
        Assign chat to an agent.

        Data: {
            chat_id: string,
            agent_id: string
        }
        """
        agent_info = connected_agents.get(sid)
        if not agent_info:
            return {"error": "Not authenticated"}

        chat_id = data.get("chat_id")
        target_agent_id = data.get("agent_id")

        if not chat_id or not target_agent_id:
            return {"error": "chat_id and agent_id required"}

        try:
            db = get_mongodb()
            env_type = "production"

            chat_repo = MongoChatRepository(
                db=db,
                org_id=agent_info["org_id"],
                env_type=env_type,
            )
            message_repo = MongoMessageRepository(
                db=db,
                org_id=agent_info["org_id"],
                env_type=env_type,
            )
            service = ChatService(
                chat_repository=chat_repo,
                message_repository=message_repo,
                org_id=agent_info["org_id"],
                env_type=env_type,
            )

            chat = await service.assign_agent(
                chat_id=chat_id,
                agent_id=target_agent_id,
                assigner_id=agent_info["user_id"],
            )

            # Notify the assigned agent
            await self.emit(
                "chat_assigned",
                {
                    "chat_id": chat_id,
                    "assigned_by": agent_info.get("name"),
                },
                room=get_agent_room(target_agent_id),
            )

            # Notify user in chat room
            room = get_chat_room(chat_id)
            from app.sockets.server import sio
            await sio.emit(
                "agent_assigned",
                {
                    "chat_id": chat_id,
                    "agent_id": target_agent_id,
                },
                room=room,
                namespace="/chat",
            )

            return {"success": True, "chat_id": chat_id}

        except Exception as e:
            print(f"[Agent] Error assigning chat: {e}")
            return {"error": str(e)}

    async def on_mark_read(self, sid, data):
        """Mark messages as read by agent."""
        agent_info = connected_agents.get(sid)
        if not agent_info:
            return {"error": "Not authenticated"}

        chat_id = data.get("chat_id")
        if not chat_id:
            return {"error": "chat_id required"}

        try:
            db = get_mongodb()
            env_type = "production"

            chat_repo = MongoChatRepository(
                db=db,
                org_id=agent_info["org_id"],
                env_type=env_type,
            )
            message_repo = MongoMessageRepository(
                db=db,
                org_id=agent_info["org_id"],
                env_type=env_type,
            )
            service = ChatService(
                chat_repository=chat_repo,
                message_repository=message_repo,
                org_id=agent_info["org_id"],
                env_type=env_type,
            )

            count = await service.mark_messages_read(
                chat_id=chat_id,
                reader_type=SenderType.AGENT,
                up_to_message_id=data.get("last_message_id"),
            )

            # Notify user
            room = get_chat_room(chat_id)
            from app.sockets.server import sio
            await sio.emit(
                "message_read",
                {
                    "chat_id": chat_id,
                    "reader_type": "agent",
                    "reader_id": agent_info["user_id"],
                    "read_count": count,
                },
                room=room,
                namespace="/chat",
            )

            return {"success": True, "read_count": count}

        except Exception as e:
            print(f"[Agent] Error marking read: {e}")
            return {"error": str(e)}

    async def _set_agent_status(self, org_id: str, agent_id: str, status: str) -> None:
        """Update agent status in Redis."""
        try:
            # Store as hash: agent_status:{org_id} -> {agent_id: status}
            from app.db.redis import get_redis
            redis = get_redis()
            await redis.hset(f"agent_status:{org_id}", agent_id, status)
        except Exception as e:
            print(f"[Agent] Error setting status: {e}")


# Utility function to notify agents of new chat
async def notify_new_chat(org_id: str, chat_data: dict) -> None:
    """
    Notify all agents in organization of a new waiting chat.

    Called when a new chat is created.
    """
    from app.sockets.server import sio

    await sio.emit(
        "new_chat",
        chat_data,
        room=get_org_room(org_id),
        namespace="/agent",
    )
