"""Redis connection for caching and session management."""

import json

import redis.asyncio as redis

from app.core.config import settings

# Global Redis client
redis_client: redis.Redis | None = None


async def connect_redis() -> None:
    """Connect to Redis."""
    global redis_client

    # Optimized connection settings for low latency
    redis_client = redis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
        max_connections=50,  # Connection pool size
        socket_timeout=5.0,  # Socket timeout
        socket_connect_timeout=5.0,  # Connection timeout
        retry_on_timeout=True,  # Retry on timeout
    )

    # Test connection
    try:
        await redis_client.ping()
        print(f"Connected to Redis: {settings.redis_url}")
    except Exception as e:
        print(f"Failed to connect to Redis: {e}")
        raise


async def close_redis() -> None:
    """Close Redis connection."""
    global redis_client

    if redis_client:
        await redis_client.close()
        print("Redis connection closed")


def get_redis() -> redis.Redis:
    """
    Get Redis client instance.

    Usage:
        @app.get("/")
        async def endpoint(redis: redis.Redis = Depends(get_redis)):
            await redis.get("key")
            ...
    """
    if redis_client is None:
        raise RuntimeError("Redis is not connected")
    return redis_client


class RedisCache:
    """Helper class for common Redis operations."""

    def __init__(self, prefix: str = ""):
        self.prefix = prefix

    def _key(self, key: str) -> str:
        """Build full key with prefix."""
        return f"{self.prefix}:{key}" if self.prefix else key

    async def get(self, key: str) -> str | None:
        """Get value by key."""
        client = get_redis()
        return await client.get(self._key(key))

    async def get_json(self, key: str) -> dict | None:
        """Get JSON value by key."""
        value = await self.get(key)
        if value:
            return json.loads(value)
        return None

    async def set(
        self,
        key: str,
        value: str,
        ttl: int | None = None,
    ) -> None:
        """Set value with optional TTL (seconds)."""
        client = get_redis()
        if ttl:
            await client.setex(self._key(key), ttl, value)
        else:
            await client.set(self._key(key), value)

    async def set_json(
        self,
        key: str,
        value: dict,
        ttl: int | None = None,
    ) -> None:
        """Set JSON value with optional TTL."""
        await self.set(key, json.dumps(value), ttl)

    async def delete(self, key: str) -> None:
        """Delete key."""
        client = get_redis()
        await client.delete(self._key(key))

    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        client = get_redis()
        return await client.exists(self._key(key)) > 0

    async def expire(self, key: str, ttl: int) -> None:
        """Set TTL on existing key."""
        client = get_redis()
        await client.expire(self._key(key), ttl)


# Pre-configured cache instances
api_key_cache = RedisCache(prefix="api_key")
plugin_key_cache = RedisCache(prefix="plugin_key")
temp_user_cache = RedisCache(prefix="temp_user")
agent_status_cache = RedisCache(prefix="agent_status")
jwt_blacklist = RedisCache(prefix="jwt_blacklist")
