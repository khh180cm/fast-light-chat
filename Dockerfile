# syntax=docker/dockerfile:1.4
# Fast Light Chat - Optimized Dockerfile
# Build with: DOCKER_BUILDKIT=1 docker build -t fast-light-chat .

# ============================================
# Stage 1: Base image with dependencies
# ============================================
FROM python:3.13-slim AS base

# Prevent Python from writing bytecode and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    # Reduce pip/uv overhead
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# ============================================
# Stage 2: Builder - install dependencies
# ============================================
FROM base AS builder

# Install uv (faster than pip)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy only dependency files first (better layer caching)
COPY pyproject.toml ./

# Create virtual environment and install dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    uv venv /opt/venv && \
    . /opt/venv/bin/activate && \
    uv pip install \
        fastapi \
        "uvicorn[standard]" \
        python-socketio \
        "sqlalchemy[asyncio]" \
        asyncpg \
        alembic \
        motor \
        redis \
        pyjwt \
        bcrypt \
        python-multipart \
        pydantic \
        pydantic-settings \
        email-validator \
        python-dateutil \
        httpx \
        google-genai

# ============================================
# Stage 3: Development
# ============================================
FROM base AS development

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    ENVIRONMENT=development

COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.asgi:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ============================================
# Stage 4: Production
# ============================================
FROM base AS production

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    ENVIRONMENT=production

# Install gunicorn in production
RUN /opt/venv/bin/pip install --no-cache-dir gunicorn

# Create non-root user for security
RUN adduser --disabled-password --gecos '' --uid 1000 appuser

# Copy application code
COPY --chown=appuser:appuser app/ ./app/
COPY --chown=appuser:appuser alembic/ ./alembic/
COPY --chown=appuser:appuser alembic.ini ./
COPY --chown=appuser:appuser frontend/ ./frontend/

USER appuser

EXPOSE 8000

# Optimized gunicorn settings for low latency
# - workers: 2 * CPU cores + 1 (adjust based on your needs)
# - keepalive: keep connections alive for WebSocket
CMD ["gunicorn", "app.asgi:app", \
     "-w", "2", \
     "-k", "uvicorn.workers.UvicornWorker", \
     "-b", "0.0.0.0:8000", \
     "--keepalive", "65", \
     "--timeout", "30", \
     "--graceful-timeout", "10", \
     "--max-requests", "10000", \
     "--max-requests-jitter", "1000"]
