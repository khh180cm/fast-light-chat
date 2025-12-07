"""FastAPI application factory."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.exceptions import AppException
from app.db.mongodb import connect_mongodb, close_mongodb
from app.db.redis import connect_redis, close_redis
from app.middlewares.security import SecurityHeadersMiddleware, RateLimitMiddleware
from app.domains.auth.router import router as auth_router
from app.domains.organization.router import router as organization_router
from app.domains.environment.router import router as environment_router
from app.domains.agent.router import router as agent_router
from app.domains.user.router import router as user_router
from app.domains.chat.router import router as chat_router
from app.domains.satisfaction.router import router as satisfaction_router
from app.domains.tone_profile.router import router as tone_profile_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Application lifespan events."""
    # Startup
    print(f"Starting Fast Light Chat in {settings.environment} mode...")

    await connect_mongodb()
    await connect_redis()

    yield

    # Shutdown
    print("Shutting down Fast Light Chat...")
    await close_mongodb()
    await close_redis()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Fast Light Chat",
        description="Real-time chat support platform like Channel Talk",
        version="0.1.0",
        docs_url="/docs" if settings.is_development else None,
        redoc_url="/redoc" if settings.is_development else None,
        lifespan=lifespan,
    )

    # Security middlewares (order matters: first added = last executed)
    app.add_middleware(SecurityHeadersMiddleware)

    # Rate limiting (only in production or if explicitly enabled)
    if settings.is_production:
        app.add_middleware(RateLimitMiddleware)

    # CORS middleware - be specific about allowed origins in production
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "X-Plugin-Key",
            "X-API-Key",
            "X-API-Secret",
        ],
        expose_headers=["X-RateLimit-Limit", "X-RateLimit-Remaining"],
    )

    # Exception handlers
    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.error_code,
                    "message": exc.message,
                    "details": exc.details,
                }
            },
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        if settings.is_development:
            return JSONResponse(
                status_code=500,
                content={
                    "error": {
                        "code": "INTERNAL_ERROR",
                        "message": str(exc),
                        "details": {"type": type(exc).__name__},
                    }
                },
            )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred",
                }
            },
        )

    # Health check endpoint
    @app.get("/health")
    async def health_check():
        return {"status": "healthy", "environment": settings.environment}

    # API info endpoint
    @app.get("/")
    async def root():
        return {
            "name": "Fast Light Chat API",
            "version": "0.1.0",
            "docs": "/docs" if settings.is_development else None,
        }

    # Register routers
    _register_routers(app)

    # Mount static files for frontend (development)
    if settings.is_development:
        try:
            app.mount("/widget", StaticFiles(directory="frontend/widget", html=True), name="widget")
            app.mount(
                "/dashboard", StaticFiles(directory="frontend/dashboard", html=True), name="dashboard"
            )
        except Exception:
            # Frontend directories may not exist yet
            pass

    return app


def _register_routers(app: FastAPI) -> None:
    """Register all API routers."""
    api_prefix = settings.api_prefix

    app.include_router(auth_router, prefix=f"{api_prefix}/auth", tags=["Auth"])
    app.include_router(
        organization_router, prefix=f"{api_prefix}/organizations", tags=["Organizations"]
    )
    app.include_router(
        environment_router, prefix=f"{api_prefix}/environments", tags=["Environments"]
    )
    app.include_router(agent_router, prefix=f"{api_prefix}/agents", tags=["Agents"])
    app.include_router(user_router, prefix=f"{api_prefix}/users", tags=["Users"])
    app.include_router(chat_router, prefix=f"{api_prefix}/chats", tags=["Chats"])
    app.include_router(satisfaction_router, prefix=api_prefix, tags=["Satisfaction"])
    app.include_router(tone_profile_router, prefix=api_prefix, tags=["Tone Profile"])
