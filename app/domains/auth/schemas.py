"""Auth domain schemas - request/response models."""

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    """Login request schema."""

    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class LoginResponse(BaseModel):
    """Login response schema."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., description="Access token expiration in seconds")


class RefreshRequest(BaseModel):
    """Token refresh request schema."""

    refresh_token: str


class RefreshResponse(BaseModel):
    """Token refresh response schema."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenPayload(BaseModel):
    """JWT token payload schema."""

    sub: str = Field(..., description="Subject (user ID)")
    org_id: str = Field(..., description="Organization ID")
    role: str = Field(..., description="Agent role")
    email: str
    name: str
    type: str = Field(..., description="Token type (access/refresh)")
    exp: int = Field(..., description="Expiration timestamp")
    iat: int = Field(..., description="Issued at timestamp")
    jti: str = Field(..., description="JWT ID for blacklisting")
