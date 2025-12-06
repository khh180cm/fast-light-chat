"""User API router - user management endpoints."""

from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from redis.asyncio import Redis

from app.core.exceptions import NotFoundError
from app.db.mongodb import get_mongodb
from app.db.redis import get_redis
from app.dependencies.auth import APIKeyAuth, PluginKeyAuth
from app.domains.user.models import UserStatus
from app.domains.user.repository import (
    MongoUserRepository,
    RedisTempUserRepository,
)
from app.domains.user.schemas import (
    ConvertTempUserRequest,
    TempUserCreate,
    TempUserResponse,
    UserCreate,
    UserListResponse,
    UserResponse,
    UserUpdate,
)
from app.domains.user.service import TempUserService, UserService

router = APIRouter()


def get_user_service(
    auth: APIKeyAuth,
    db: AsyncIOMotorDatabase = Depends(get_mongodb),
) -> UserService:
    """Dependency injection for UserService."""
    repository = MongoUserRepository(
        db=db,
        org_id=auth["org_id"],
        env_type=auth["env_type"],
    )
    return UserService(
        repository=repository,
        org_id=auth["org_id"],
        env_type=auth["env_type"],
    )


def get_temp_user_service(
    auth: PluginKeyAuth,
    redis: Redis = Depends(get_redis),
) -> TempUserService:
    """Dependency injection for TempUserService."""
    repository = RedisTempUserRepository(
        redis=redis,
        org_id=auth["org_id"],
        env_type=auth["env_type"],
    )
    return TempUserService(
        repository=repository,
        org_id=auth["org_id"],
        env_type=auth["env_type"],
    )


# ============================================================
# API Key authenticated endpoints (Backend integration)
# ============================================================


@router.get("", response_model=UserListResponse)
async def list_users(
    auth: APIKeyAuth,
    db: AsyncIOMotorDatabase = Depends(get_mongodb),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: UserStatus | None = Query(None),
    tags: str | None = Query(None, description="Comma-separated tags"),
):
    """
    List users with pagination and filters.

    Requires API Key authentication.
    """
    service = get_user_service(auth, db)

    tag_list = tags.split(",") if tags else None

    users, total = await service.list_users(
        skip=skip,
        limit=limit,
        status=status,
        tags=tag_list,
    )

    return UserListResponse(
        items=[
            UserResponse(
                id=str(u.id),
                member_id=u.member_id,
                org_id=u.org_id,
                env_type=u.env_type,
                profile=u.profile,
                custom_fields=u.custom_fields,
                tags=u.tags,
                total_chats=u.total_chats,
                total_messages=u.total_messages,
                status=u.status,
                first_seen_at=u.first_seen_at,
                last_seen_at=u.last_seen_at,
                created_at=u.created_at,
                updated_at=u.updated_at,
            )
            for u in users
        ],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post("", response_model=UserResponse, status_code=201)
async def create_user(
    data: UserCreate,
    auth: APIKeyAuth,
    db: AsyncIOMotorDatabase = Depends(get_mongodb),
):
    """
    Create a new user.

    Requires API Key authentication.
    """
    service = get_user_service(auth, db)
    user = await service.create_user(data)

    return UserResponse(
        id=str(user.id),
        member_id=user.member_id,
        org_id=user.org_id,
        env_type=user.env_type,
        profile=user.profile,
        custom_fields=user.custom_fields,
        tags=user.tags,
        total_chats=user.total_chats,
        total_messages=user.total_messages,
        status=user.status,
        first_seen_at=user.first_seen_at,
        last_seen_at=user.last_seen_at,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


@router.get("/{member_id}", response_model=UserResponse)
async def get_user(
    member_id: str,
    auth: APIKeyAuth,
    db: AsyncIOMotorDatabase = Depends(get_mongodb),
):
    """
    Get user by member ID.

    Requires API Key authentication.
    """
    service = get_user_service(auth, db)
    user = await service.get_user_by_member_id(member_id)

    if not user:
        raise NotFoundError("User", member_id)

    return UserResponse(
        id=str(user.id),
        member_id=user.member_id,
        org_id=user.org_id,
        env_type=user.env_type,
        profile=user.profile,
        custom_fields=user.custom_fields,
        tags=user.tags,
        total_chats=user.total_chats,
        total_messages=user.total_messages,
        status=user.status,
        first_seen_at=user.first_seen_at,
        last_seen_at=user.last_seen_at,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


@router.put("/{member_id}", response_model=UserResponse)
async def update_user(
    member_id: str,
    data: UserUpdate,
    auth: APIKeyAuth,
    db: AsyncIOMotorDatabase = Depends(get_mongodb),
):
    """
    Update user by member ID.

    Requires API Key authentication.
    """
    service = get_user_service(auth, db)
    user = await service.update_user(member_id, data)

    return UserResponse(
        id=str(user.id),
        member_id=user.member_id,
        org_id=user.org_id,
        env_type=user.env_type,
        profile=user.profile,
        custom_fields=user.custom_fields,
        tags=user.tags,
        total_chats=user.total_chats,
        total_messages=user.total_messages,
        status=user.status,
        first_seen_at=user.first_seen_at,
        last_seen_at=user.last_seen_at,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


@router.delete("/{member_id}")
async def delete_user(
    member_id: str,
    auth: APIKeyAuth,
    db: AsyncIOMotorDatabase = Depends(get_mongodb),
):
    """
    Delete user by member ID (soft delete).

    Requires API Key authentication.
    """
    service = get_user_service(auth, db)
    await service.delete_user(member_id)
    return {"message": "User deleted"}


# ============================================================
# Plugin Key authenticated endpoints (SDK/Widget)
# ============================================================


@router.post("/temp", response_model=TempUserResponse, status_code=201)
async def create_temp_user(
    data: TempUserCreate,
    auth: PluginKeyAuth,
    redis: Redis = Depends(get_redis),
):
    """
    Create a temporary user for anonymous chat.

    Requires Plugin Key authentication.
    Temporary users are stored in Redis with 24h TTL.
    """
    service = get_temp_user_service(auth, redis)
    temp_user, _ = await service.get_or_create_temp_user(
        session_id=data.session_id,
        profile=data.profile,
    )

    return TempUserResponse(
        session_id=temp_user.session_id,
        org_id=temp_user.org_id,
        env_type=temp_user.env_type,
        profile=temp_user.profile,
        chat_ids=temp_user.chat_ids,
        created_at=temp_user.created_at,
        last_activity_at=temp_user.last_activity_at,
    )


@router.get("/temp/{session_id}", response_model=TempUserResponse)
async def get_temp_user(
    session_id: str,
    auth: PluginKeyAuth,
    redis: Redis = Depends(get_redis),
):
    """
    Get temporary user by session ID.

    Requires Plugin Key authentication.
    """
    service = get_temp_user_service(auth, redis)
    temp_user = await service.get_temp_user(session_id)

    if not temp_user:
        raise NotFoundError("TempUser", session_id)

    return TempUserResponse(
        session_id=temp_user.session_id,
        org_id=temp_user.org_id,
        env_type=temp_user.env_type,
        profile=temp_user.profile,
        chat_ids=temp_user.chat_ids,
        created_at=temp_user.created_at,
        last_activity_at=temp_user.last_activity_at,
    )


@router.post("/temp/convert", response_model=UserResponse)
async def convert_temp_to_permanent(
    data: ConvertTempUserRequest,
    auth: APIKeyAuth,
    db: AsyncIOMotorDatabase = Depends(get_mongodb),
    redis: Redis = Depends(get_redis),
):
    """
    Convert temporary user to permanent user.

    Requires API Key authentication.
    Transfers profile and chat history to permanent user.
    """
    # Create services
    user_repo = MongoUserRepository(
        db=db,
        org_id=auth["org_id"],
        env_type=auth["env_type"],
    )
    temp_repo = RedisTempUserRepository(
        redis=redis,
        org_id=auth["org_id"],
        env_type=auth["env_type"],
    )
    temp_service = TempUserService(
        repository=temp_repo,
        org_id=auth["org_id"],
        env_type=auth["env_type"],
    )

    user = await temp_service.convert_to_permanent(
        session_id=data.session_id,
        member_id=data.member_id,
        user_repository=user_repo,
    )

    return UserResponse(
        id=str(user.id),
        member_id=user.member_id,
        org_id=user.org_id,
        env_type=user.env_type,
        profile=user.profile,
        custom_fields=user.custom_fields,
        tags=user.tags,
        total_chats=user.total_chats,
        total_messages=user.total_messages,
        status=user.status,
        first_seen_at=user.first_seen_at,
        last_seen_at=user.last_seen_at,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )
