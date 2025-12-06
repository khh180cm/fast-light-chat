"""Security middleware - headers, rate limiting, input sanitization."""

from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Add security headers to all responses.

    Headers:
    - X-Content-Type-Options: Prevents MIME type sniffing
    - X-Frame-Options: Prevents clickjacking
    - X-XSS-Protection: XSS filter (legacy browsers)
    - Referrer-Policy: Controls referrer information
    - Content-Security-Policy: Controls resource loading (if needed)
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Remove server header (information disclosure)
        if "server" in response.headers:
            del response.headers["server"]

        # In production, add stricter CSP
        if settings.is_production:
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https:; "
                "font-src 'self'; "
                "connect-src 'self' wss: ws:;"
            )

        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Simple rate limiting middleware using Redis.

    Limits requests per IP address within a time window.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip rate limiting for health checks
        if request.url.path in ["/health", "/", "/docs", "/redoc", "/openapi.json"]:
            return await call_next(request)

        # Get client IP
        client_ip = self._get_client_ip(request)

        # Check rate limit
        try:
            from app.db.redis import get_redis

            redis = get_redis()
            key = f"rate_limit:{client_ip}:{request.url.path}"

            # Get current count
            current = await redis.get(key)

            if current and int(current) >= settings.rate_limit_requests:
                from fastapi.responses import JSONResponse

                return JSONResponse(
                    status_code=429,
                    content={
                        "error": {
                            "code": "RATE_LIMIT_EXCEEDED",
                            "message": "Too many requests. Please try again later.",
                            "details": {
                                "retry_after": settings.rate_limit_window_seconds
                            },
                        }
                    },
                    headers={
                        "Retry-After": str(settings.rate_limit_window_seconds),
                        "X-RateLimit-Limit": str(settings.rate_limit_requests),
                        "X-RateLimit-Remaining": "0",
                    },
                )

            # Increment counter
            pipe = redis.pipeline()
            pipe.incr(key)
            pipe.expire(key, settings.rate_limit_window_seconds)
            await pipe.execute()

        except Exception:
            # If Redis is unavailable, allow request (fail open)
            pass

        response = await call_next(request)

        # Add rate limit headers
        try:
            remaining = settings.rate_limit_requests - int(current or 0) - 1
            response.headers["X-RateLimit-Limit"] = str(settings.rate_limit_requests)
            response.headers["X-RateLimit-Remaining"] = str(max(0, remaining))
        except Exception:
            pass

        return response

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request, handling proxies."""
        # Check X-Forwarded-For header (from reverse proxy)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            # Take the first IP (original client)
            return forwarded.split(",")[0].strip()

        # Check X-Real-IP header
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # Fallback to direct connection
        if request.client:
            return request.client.host

        return "unknown"
