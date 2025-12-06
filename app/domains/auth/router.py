"""Auth API router - login, token refresh, logout."""

from fastapi import APIRouter, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import get_token_jti
from app.db.postgres import get_db
from app.dependencies.auth import CurrentAgent
from app.domains.auth.schemas import (
    LoginRequest,
    LoginResponse,
    RefreshRequest,
    RefreshResponse,
)
from app.domains.auth.service import AuthService

router = APIRouter()


@router.post("/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Login with email and password.

    Returns access token and refresh token.
    """
    service = AuthService(db)
    access_token, refresh_token = await service.login(
        email=request.email,
        password=request.password,
    )

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


@router.post("/refresh", response_model=RefreshResponse)
async def refresh(
    request: RefreshRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Refresh access token using refresh token.

    Returns new access token.
    """
    service = AuthService(db)
    access_token = await service.refresh_tokens(refresh_token=request.refresh_token)

    return RefreshResponse(
        access_token=access_token,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


@router.post("/logout")
async def logout(
    current_agent: CurrentAgent,
    authorization: str = Header(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Logout current session.

    Blacklists the current access token.
    """
    # Extract token from header
    token = authorization.replace("Bearer ", "")
    jti = get_token_jti(token)

    if jti:
        service = AuthService(db)
        await service.logout(access_token=token, jti=jti)

    return {"message": "Logged out successfully"}


@router.post("/logout-all")
async def logout_all(
    current_agent: CurrentAgent,
    db: AsyncSession = Depends(get_db),
):
    """
    Logout from all devices.

    Revokes all refresh tokens for the current agent.
    """
    service = AuthService(db)
    count = await service.revoke_all_refresh_tokens(agent_id=current_agent["user_id"])

    return {"message": f"Revoked {count} sessions"}
