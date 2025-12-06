"""Custom exceptions for the application."""

from typing import Any


class AppException(Exception):
    """Base exception for all application exceptions."""

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        error_code: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code or "INTERNAL_ERROR"
        self.details = details or {}
        super().__init__(self.message)


# Authentication Exceptions
class AuthenticationError(AppException):
    """Raised when authentication fails."""

    def __init__(self, message: str = "Authentication failed", details: dict | None = None):
        super().__init__(
            message=message,
            status_code=401,
            error_code="AUTHENTICATION_ERROR",
            details=details,
        )


class InvalidCredentialsError(AuthenticationError):
    """Raised when credentials are invalid."""

    def __init__(self, message: str = "Invalid email or password"):
        super().__init__(message=message)
        self.error_code = "INVALID_CREDENTIALS"


class TokenExpiredError(AuthenticationError):
    """Raised when token has expired."""

    def __init__(self, message: str = "Token has expired"):
        super().__init__(message=message)
        self.error_code = "TOKEN_EXPIRED"


class InvalidTokenError(AuthenticationError):
    """Raised when token is invalid."""

    def __init__(self, message: str = "Invalid token"):
        super().__init__(message=message)
        self.error_code = "INVALID_TOKEN"


class InvalidAPIKeyError(AuthenticationError):
    """Raised when API key is invalid."""

    def __init__(self, message: str = "Invalid API key"):
        super().__init__(message=message)
        self.error_code = "INVALID_API_KEY"


class InvalidPluginKeyError(AuthenticationError):
    """Raised when Plugin key is invalid."""

    def __init__(self, message: str = "Invalid plugin key"):
        super().__init__(message=message)
        self.error_code = "INVALID_PLUGIN_KEY"


# Authorization Exceptions
class AuthorizationError(AppException):
    """Raised when authorization fails."""

    def __init__(self, message: str = "Access denied", details: dict | None = None):
        super().__init__(
            message=message,
            status_code=403,
            error_code="AUTHORIZATION_ERROR",
            details=details,
        )


class ForbiddenError(AuthorizationError):
    """Raised when access is forbidden."""

    def __init__(self, message: str = "Access forbidden"):
        super().__init__(message=message)
        self.error_code = "FORBIDDEN"


class InsufficientPermissionsError(AuthorizationError):
    """Raised when user doesn't have required permissions."""

    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(message=message)
        self.error_code = "INSUFFICIENT_PERMISSIONS"


class OrganizationAccessDeniedError(AuthorizationError):
    """Raised when user doesn't have access to organization."""

    def __init__(self, message: str = "Access denied to this organization"):
        super().__init__(message=message)
        self.error_code = "ORGANIZATION_ACCESS_DENIED"


# Resource Exceptions
class NotFoundError(AppException):
    """Raised when resource is not found."""

    def __init__(
        self, resource: str = "Resource", identifier: str | None = None
    ):
        message = f"{resource} not found"
        if identifier:
            message = f"{resource} with id '{identifier}' not found"
        super().__init__(
            message=message,
            status_code=404,
            error_code="NOT_FOUND",
            details={"resource": resource, "identifier": identifier},
        )


class ConflictError(AppException):
    """Raised when resource conflicts."""

    def __init__(self, message: str = "Resource already exists", details: dict | None = None):
        super().__init__(
            message=message,
            status_code=409,
            error_code="CONFLICT",
            details=details,
        )


class DuplicateError(ConflictError):
    """Raised when duplicate resource is detected."""

    def __init__(self, field: str, value: str):
        super().__init__(
            message=f"Resource with {field}='{value}' already exists",
            details={"field": field, "value": value},
        )
        self.error_code = "DUPLICATE_ERROR"


# Validation Exceptions
class ValidationError(AppException):
    """Raised when validation fails."""

    def __init__(self, message: str = "Validation failed", details: dict | None = None):
        super().__init__(
            message=message,
            status_code=422,
            error_code="VALIDATION_ERROR",
            details=details,
        )


class MessageTooLongError(ValidationError):
    """Raised when message exceeds max length."""

    def __init__(self, max_length: int, actual_length: int):
        super().__init__(
            message=f"Message exceeds maximum length of {max_length} characters",
            details={"max_length": max_length, "actual_length": actual_length},
        )
        self.error_code = "MESSAGE_TOO_LONG"


class FileTooLargeError(ValidationError):
    """Raised when file exceeds max size."""

    def __init__(self, max_size_mb: int, actual_size_mb: float):
        super().__init__(
            message=f"File exceeds maximum size of {max_size_mb}MB",
            details={"max_size_mb": max_size_mb, "actual_size_mb": actual_size_mb},
        )
        self.error_code = "FILE_TOO_LARGE"


# Rate Limiting
class RateLimitExceededError(AppException):
    """Raised when rate limit is exceeded."""

    def __init__(self, retry_after: int = 60):
        super().__init__(
            message="Rate limit exceeded. Please try again later.",
            status_code=429,
            error_code="RATE_LIMIT_EXCEEDED",
            details={"retry_after": retry_after},
        )


# Database Exceptions
class DatabaseError(AppException):
    """Raised when database operation fails."""

    def __init__(self, message: str = "Database operation failed"):
        super().__init__(
            message=message,
            status_code=500,
            error_code="DATABASE_ERROR",
        )
