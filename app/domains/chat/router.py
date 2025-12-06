"""Chat API router - chat and message endpoints."""

from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db.mongodb import get_mongodb
from app.dependencies.auth import CurrentAgent, PluginKeyAuth
from app.domains.chat.models import ChatStatus, SenderType
from app.domains.chat.repository import MongoChatRepository, MongoMessageRepository
from app.domains.chat.schemas import (
    ChatAssign,
    ChatCreate,
    ChatListResponse,
    ChatResponse,
    ChatStatistics,
    MarkReadRequest,
    MessageCreate,
    MessageListResponse,
    MessageResponse,
)
from app.domains.chat.service import ChatService

router = APIRouter()


def get_chat_service(
    auth: dict,
    db: AsyncIOMotorDatabase,
) -> ChatService:
    """Create ChatService with repositories."""
    org_id = auth["org_id"]
    env_type = auth["env_type"]

    chat_repo = MongoChatRepository(db=db, org_id=org_id, env_type=env_type)
    message_repo = MongoMessageRepository(db=db, org_id=org_id, env_type=env_type)

    return ChatService(
        chat_repository=chat_repo,
        message_repository=message_repo,
        org_id=org_id,
        env_type=env_type,
    )


def _chat_to_response(chat) -> ChatResponse:
    """Convert Chat model to ChatResponse."""
    return ChatResponse(
        id=str(chat.id),
        org_id=chat.org_id,
        env_type=chat.env_type,
        user_id=chat.user_id,
        member_id=chat.member_id,
        assigned_agent_id=chat.assigned_agent_id,
        status=chat.status,
        message_count=chat.message_count,
        unread_count_user=chat.unread_count_user,
        unread_count_agent=chat.unread_count_agent,
        last_message=chat.last_message,
        tags=chat.tags,
        metadata=chat.metadata,
        created_at=chat.created_at,
        first_response_at=chat.first_response_at,
        resolved_at=chat.resolved_at,
        closed_at=chat.closed_at,
        updated_at=chat.updated_at,
    )


def _message_to_response(message) -> MessageResponse:
    """Convert Message model to MessageResponse."""
    return MessageResponse(
        id=str(message.id),
        chat_id=message.chat_id,
        sender_type=message.sender_type,
        sender_id=message.sender_id,
        message_type=message.message_type,
        content=message.content,
        attachments=message.attachments,
        read_by_user=message.read_by_user,
        read_by_agent=message.read_by_agent,
        created_at=message.created_at,
        updated_at=message.updated_at,
    )


# ============================================================
# Plugin Key authenticated endpoints (SDK/Widget - User)
# ============================================================


@router.post("", response_model=ChatResponse, status_code=201)
async def create_chat(
    data: ChatCreate,
    auth: PluginKeyAuth,
    db: AsyncIOMotorDatabase = Depends(get_mongodb),
):
    """
    Create a new chat.

    Requires Plugin Key authentication.
    """
    service = get_chat_service(auth, db)

    # Use provided user_id or session_id as temporary user_id
    user_id = data.user_id or data.session_id or data.member_id

    chat = await service.create_chat(data=data, user_id=user_id)
    return _chat_to_response(chat)


@router.get("/{pk}", response_model=ChatResponse)
async def get_chat(
    pk: str,
    auth: PluginKeyAuth,
    db: AsyncIOMotorDatabase = Depends(get_mongodb),
):
    """
    Get chat by ID.

    Requires Plugin Key authentication.
    """
    service = get_chat_service(auth, db)
    chat = await service.get_chat(pk)
    return _chat_to_response(chat)


@router.get("/{pk}/messages", response_model=MessageListResponse)
async def get_messages(
    pk: str,
    auth: PluginKeyAuth,
    db: AsyncIOMotorDatabase = Depends(get_mongodb),
    limit: int = Query(50, ge=1, le=100),
    cursor: str | None = Query(None),
    before: bool = Query(True, description="Get messages before cursor (older)"),
):
    """
    Get messages for a chat with cursor pagination.

    Requires Plugin Key authentication.
    """
    service = get_chat_service(auth, db)
    messages, next_cursor, has_more = await service.list_messages(
        chat_id=pk,
        limit=limit,
        cursor=cursor,
        before=before,
    )

    return MessageListResponse(
        items=[_message_to_response(m) for m in messages],
        cursor=next_cursor,
        has_more=has_more,
    )


@router.post("/{pk}/messages", response_model=MessageResponse, status_code=201)
async def send_message(
    pk: str,
    data: MessageCreate,
    auth: PluginKeyAuth,
    db: AsyncIOMotorDatabase = Depends(get_mongodb),
    user_id: str = Query(..., description="User ID sending the message"),
):
    """
    Send a message to chat.

    Requires Plugin Key authentication.
    """
    service = get_chat_service(auth, db)
    message = await service.send_message(
        chat_id=pk,
        sender_type=SenderType.USER,
        sender_id=user_id,
        data=data,
    )
    return _message_to_response(message)


@router.put("/{pk}/read")
async def mark_read(
    pk: str,
    data: MarkReadRequest,
    auth: PluginKeyAuth,
    db: AsyncIOMotorDatabase = Depends(get_mongodb),
):
    """
    Mark messages as read by user.

    Requires Plugin Key authentication.
    """
    service = get_chat_service(auth, db)
    count = await service.mark_messages_read(
        chat_id=pk,
        reader_type=SenderType.USER,
        up_to_message_id=data.last_read_message_id,
    )
    return {"marked_count": count}


@router.put("/{pk}/close")
async def close_chat(
    pk: str,
    auth: PluginKeyAuth,
    db: AsyncIOMotorDatabase = Depends(get_mongodb),
):
    """
    Close a chat (by user).

    Requires Plugin Key authentication.
    """
    service = get_chat_service(auth, db)
    chat = await service.close_chat(pk, closer_type=SenderType.USER)
    return _chat_to_response(chat)


# ============================================================
# JWT authenticated endpoints (Dashboard - Agent)
# ============================================================


@router.get("", response_model=ChatListResponse)
async def list_chats(
    current_agent: CurrentAgent,
    db: AsyncIOMotorDatabase = Depends(get_mongodb),
    status: ChatStatus | None = Query(None),
    agent_id: str | None = Query(None, description="Filter by assigned agent"),
    user_id: str | None = Query(None, description="Filter by user"),
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = Query(None),
):
    """
    List chats with filters and pagination.

    Requires JWT authentication (agent dashboard).
    """
    # Build auth dict from JWT payload
    auth = {
        "org_id": current_agent["org_id"],
        "env_type": "production",  # Dashboard uses production by default
    }

    service = get_chat_service(auth, db)
    chats, next_cursor, has_more = await service.list_chats(
        status=status,
        agent_id=agent_id,
        user_id=user_id,
        limit=limit,
        cursor=cursor,
    )

    return ChatListResponse(
        items=[_chat_to_response(c) for c in chats],
        total=len(chats),  # Note: for cursor pagination, we don't have total
        cursor=next_cursor,
        has_more=has_more,
    )


@router.get("/statistics", response_model=ChatStatistics)
async def get_statistics(
    current_agent: CurrentAgent,
    db: AsyncIOMotorDatabase = Depends(get_mongodb),
):
    """
    Get chat statistics.

    Requires JWT authentication (agent dashboard).
    """
    auth = {
        "org_id": current_agent["org_id"],
        "env_type": "production",
    }

    service = get_chat_service(auth, db)
    return await service.get_statistics()


@router.put("/{pk}/assign", response_model=ChatResponse)
async def assign_chat(
    pk: str,
    data: ChatAssign,
    current_agent: CurrentAgent,
    db: AsyncIOMotorDatabase = Depends(get_mongodb),
):
    """
    Assign chat to an agent.

    Requires JWT authentication (agent dashboard).
    """
    auth = {
        "org_id": current_agent["org_id"],
        "env_type": "production",
    }

    service = get_chat_service(auth, db)
    chat = await service.assign_agent(
        chat_id=pk,
        agent_id=data.agent_id,
        assigner_id=current_agent["user_id"],
    )
    return _chat_to_response(chat)


@router.post("/{pk}/messages/agent", response_model=MessageResponse, status_code=201)
async def send_agent_message(
    pk: str,
    data: MessageCreate,
    current_agent: CurrentAgent,
    db: AsyncIOMotorDatabase = Depends(get_mongodb),
):
    """
    Send a message as agent.

    Requires JWT authentication (agent dashboard).
    """
    auth = {
        "org_id": current_agent["org_id"],
        "env_type": "production",
    }

    service = get_chat_service(auth, db)
    message = await service.send_message(
        chat_id=pk,
        sender_type=SenderType.AGENT,
        sender_id=current_agent["user_id"],
        data=data,
    )
    return _message_to_response(message)


@router.put("/{pk}/read/agent")
async def mark_read_agent(
    pk: str,
    data: MarkReadRequest,
    current_agent: CurrentAgent,
    db: AsyncIOMotorDatabase = Depends(get_mongodb),
):
    """
    Mark messages as read by agent.

    Requires JWT authentication (agent dashboard).
    """
    auth = {
        "org_id": current_agent["org_id"],
        "env_type": "production",
    }

    service = get_chat_service(auth, db)
    count = await service.mark_messages_read(
        chat_id=pk,
        reader_type=SenderType.AGENT,
        up_to_message_id=data.last_read_message_id,
    )
    return {"marked_count": count}


@router.put("/{pk}/resolve", response_model=ChatResponse)
async def resolve_chat(
    pk: str,
    current_agent: CurrentAgent,
    db: AsyncIOMotorDatabase = Depends(get_mongodb),
):
    """
    Mark chat as resolved.

    Requires JWT authentication (agent dashboard).
    """
    auth = {
        "org_id": current_agent["org_id"],
        "env_type": "production",
    }

    service = get_chat_service(auth, db)
    chat = await service.resolve_chat(pk)
    return _chat_to_response(chat)


@router.put("/{pk}/close/agent", response_model=ChatResponse)
async def close_chat_agent(
    pk: str,
    current_agent: CurrentAgent,
    db: AsyncIOMotorDatabase = Depends(get_mongodb),
):
    """
    Close a chat (by agent).

    Requires JWT authentication (agent dashboard).
    """
    auth = {
        "org_id": current_agent["org_id"],
        "env_type": "production",
    }

    service = get_chat_service(auth, db)
    chat = await service.close_chat(pk, closer_type=SenderType.AGENT)
    return _chat_to_response(chat)
