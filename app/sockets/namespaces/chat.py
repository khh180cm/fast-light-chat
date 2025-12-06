"""Chat namespace - handles user chat socket events."""

import socketio

from app.db.mongodb import get_mongodb
from app.domains.chat.models import MessageType, SenderType
from app.domains.chat.repository import MongoChatRepository, MongoMessageRepository
from app.domains.chat.schemas import MessageCreate
from app.domains.chat.service import ChatService
from app.sockets.server import (
    SocketAuth,
    connected_users,
    get_chat_room,
    get_org_room,
)


class ChatNamespace(socketio.AsyncNamespace):
    """
    Chat namespace for user-side events.

    Handles:
    - User authentication via plugin key
    - Joining/leaving chat rooms
    - Sending messages
    - Typing indicators
    - Read receipts
    """

    async def on_connect(self, sid, environ, auth):
        """Handle user connection."""
        if not auth:
            return False

        user_info = await SocketAuth.authenticate_user(auth)
        if not user_info:
            return False

        # Store session info
        connected_users[sid] = user_info

        # Join organization room for notifications
        await self.enter_room(sid, get_org_room(user_info["org_id"]))

        print(f"[Chat] User connected: {sid} - {user_info.get('member_id')}")
        return True

    async def on_disconnect(self, sid):
        """Handle user disconnection."""
        user_info = connected_users.pop(sid, None)
        if user_info:
            print(f"[Chat] User disconnected: {sid} - {user_info.get('member_id')}")

    async def on_join_chat(self, sid, data):
        """
        Join a chat room.

        Data: { chat_id: string }
        """
        user_info = connected_users.get(sid)
        if not user_info:
            return {"error": "Not authenticated"}

        chat_id = data.get("chat_id")
        if not chat_id:
            return {"error": "chat_id required"}

        room = get_chat_room(chat_id)
        await self.enter_room(sid, room)

        print(f"[Chat] User {sid} joined chat room: {chat_id}")
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

        print(f"[Chat] User {sid} left chat room: {chat_id}")
        return {"success": True}

    async def on_send_message(self, sid, data):
        """
        Send a message to chat.

        Data: {
            chat_id: string,
            content: string,
            message_type?: "text" | "image" | "file"
        }
        """
        user_info = connected_users.get(sid)
        if not user_info:
            return {"error": "Not authenticated"}

        chat_id = data.get("chat_id")
        content = data.get("content")

        if not chat_id or not content:
            return {"error": "chat_id and content required"}

        try:
            # Get service
            db = get_mongodb()
            chat_repo = MongoChatRepository(
                db=db,
                org_id=user_info["org_id"],
                env_type=user_info["env_type"],
            )
            message_repo = MongoMessageRepository(
                db=db,
                org_id=user_info["org_id"],
                env_type=user_info["env_type"],
            )
            service = ChatService(
                chat_repository=chat_repo,
                message_repository=message_repo,
                org_id=user_info["org_id"],
                env_type=user_info["env_type"],
            )

            # Create message
            message_type = MessageType(data.get("message_type", "text"))
            message = await service.send_message(
                chat_id=chat_id,
                sender_type=SenderType.USER,
                sender_id=user_info["user_id"],
                data=MessageCreate(content=content, message_type=message_type),
            )

            # Broadcast to chat room (including sender)
            message_data = {
                "id": str(message.id),
                "chat_id": message.chat_id,
                "sender_type": message.sender_type.value if hasattr(message.sender_type, 'value') else message.sender_type,
                "sender_id": message.sender_id,
                "message_type": message.message_type.value if hasattr(message.message_type, 'value') else message.message_type,
                "content": message.content,
                "created_at": message.created_at.isoformat(),
            }

            room = get_chat_room(chat_id)
            await self.emit("new_message", message_data, room=room)

            return {"success": True, "message": message_data}

        except Exception as e:
            print(f"[Chat] Error sending message: {e}")
            return {"error": str(e)}

    async def on_typing_start(self, sid, data):
        """
        Notify that user started typing.

        Data: { chat_id: string }
        """
        user_info = connected_users.get(sid)
        if not user_info:
            return

        chat_id = data.get("chat_id")
        if not chat_id:
            return

        room = get_chat_room(chat_id)
        await self.emit(
            "typing",
            {
                "chat_id": chat_id,
                "user_id": user_info["user_id"],
                "user_type": "user",
                "is_typing": True,
            },
            room=room,
            skip_sid=sid,
        )

    async def on_typing_stop(self, sid, data):
        """
        Notify that user stopped typing.

        Data: { chat_id: string }
        """
        user_info = connected_users.get(sid)
        if not user_info:
            return

        chat_id = data.get("chat_id")
        if not chat_id:
            return

        room = get_chat_room(chat_id)
        await self.emit(
            "typing",
            {
                "chat_id": chat_id,
                "user_id": user_info["user_id"],
                "user_type": "user",
                "is_typing": False,
            },
            room=room,
            skip_sid=sid,
        )

    async def on_mark_read(self, sid, data):
        """
        Mark messages as read.

        Data: {
            chat_id: string,
            last_message_id?: string
        }
        """
        user_info = connected_users.get(sid)
        if not user_info:
            return {"error": "Not authenticated"}

        chat_id = data.get("chat_id")
        if not chat_id:
            return {"error": "chat_id required"}

        try:
            db = get_mongodb()
            chat_repo = MongoChatRepository(
                db=db,
                org_id=user_info["org_id"],
                env_type=user_info["env_type"],
            )
            message_repo = MongoMessageRepository(
                db=db,
                org_id=user_info["org_id"],
                env_type=user_info["env_type"],
            )
            service = ChatService(
                chat_repository=chat_repo,
                message_repository=message_repo,
                org_id=user_info["org_id"],
                env_type=user_info["env_type"],
            )

            count = await service.mark_messages_read(
                chat_id=chat_id,
                reader_type=SenderType.USER,
                up_to_message_id=data.get("last_message_id"),
            )

            # Notify others in room
            room = get_chat_room(chat_id)
            await self.emit(
                "message_read",
                {
                    "chat_id": chat_id,
                    "reader_type": "user",
                    "reader_id": user_info["user_id"],
                    "read_count": count,
                },
                room=room,
                skip_sid=sid,
            )

            return {"success": True, "read_count": count}

        except Exception as e:
            print(f"[Chat] Error marking read: {e}")
            return {"error": str(e)}
