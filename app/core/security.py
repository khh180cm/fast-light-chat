"""Security utilities - JWT, password hashing, key generation."""

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt

from app.core.config import settings
from app.core.exceptions import InvalidTokenError, TokenExpiredError


def _prepare_password(password: str) -> bytes:
    """Prepare password for bcrypt (handle >72 bytes)."""
    password_bytes = password.encode("utf-8")
    if len(password_bytes) > 72:
        # Hash long passwords with SHA256 first
        return hashlib.sha256(password_bytes).hexdigest().encode("utf-8")
    return password_bytes


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(_prepare_password(password), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash."""
    return bcrypt.checkpw(
        _prepare_password(plain_password),
        hashed_password.encode("utf-8"),
    )


def generate_api_key(length: int | None = None) -> str:
    """Generate a secure API key."""
    if length is None:
        length = settings.api_key_length
    return secrets.token_urlsafe(length)


def generate_api_secret(length: int | None = None) -> str:
    """Generate a secure API secret."""
    if length is None:
        length = settings.api_secret_length
    return secrets.token_urlsafe(length)


def generate_plugin_key() -> str:
    """Generate a plugin key for SDK."""
    return f"pk_{secrets.token_urlsafe(24)}"


def create_access_token(
    data: dict[str, Any],
    expires_delta: timedelta | None = None,
) -> str:
    """
    Create a JWT access token.

    Args:
        data: Payload data (user_id, org_id, role, etc.)
        expires_delta: Custom expiration time

    Returns:
        Encoded JWT token string
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.jwt_access_token_expire_minutes
        )

    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "jti": str(uuid.uuid4()),  # JWT ID for blacklisting
        "type": "access",
    })

    return jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def create_refresh_token(
    data: dict[str, Any],
    expires_delta: timedelta | None = None,
) -> str:
    """
    Create a JWT refresh token.

    Args:
        data: Payload data (user_id only for refresh tokens)
        expires_delta: Custom expiration time

    Returns:
        Encoded JWT token string
    """
    to_encode = {"sub": data.get("sub")}  # Only include user ID

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            days=settings.jwt_refresh_token_expire_days
        )

    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "jti": str(uuid.uuid4()),
        "type": "refresh",
    })

    return jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_token(token: str) -> dict[str, Any]:
    """
    Decode and verify a JWT token.

    Args:
        token: JWT token string

    Returns:
        Decoded payload

    Raises:
        TokenExpiredError: If token has expired
        InvalidTokenError: If token is invalid
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise TokenExpiredError()
    except jwt.InvalidTokenError as e:
        raise InvalidTokenError(message=str(e))


def verify_access_token(token: str) -> dict[str, Any]:
    """
    Verify an access token and return payload.

    Args:
        token: JWT access token

    Returns:
        Token payload containing user_id, org_id, role, etc.

    Raises:
        InvalidTokenError: If token type is not 'access'
    """
    payload = decode_token(token)

    if payload.get("type") != "access":
        raise InvalidTokenError(message="Invalid token type")

    return payload


def verify_refresh_token(token: str) -> dict[str, Any]:
    """
    Verify a refresh token and return payload.

    Args:
        token: JWT refresh token

    Returns:
        Token payload containing user_id

    Raises:
        InvalidTokenError: If token type is not 'refresh'
    """
    payload = decode_token(token)

    if payload.get("type") != "refresh":
        raise InvalidTokenError(message="Invalid token type")

    return payload


def get_token_jti(token: str) -> str | None:
    """
    Get the JTI (JWT ID) from a token without full verification.
    Used for blacklisting tokens.
    """
    try:
        # Decode without verification to get JTI
        payload = jwt.decode(
            token,
            options={"verify_signature": False},
        )
        return payload.get("jti")
    except jwt.InvalidTokenError:
        return None
