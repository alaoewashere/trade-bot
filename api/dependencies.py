"""
api/dependencies.py
====================
FastAPI dependency providers for database connections and Redis clients.

Usage (in a router)
-------------------
    from api.dependencies import get_db, get_redis

    @router.get("/example")
    async def example(
        db: asyncpg.Connection = Depends(get_db),
        redis: aioredis.Redis = Depends(get_redis),
    ):
        row = await db.fetchrow("SELECT 1")
        val = await redis.get("key")

Application lifecycle
---------------------
Call ``init_db_pool()`` and ``init_redis_pool()`` from the FastAPI lifespan
context manager in ``api/main.py``.  Both pools are module-level singletons
so they are shared across all workers in the same process.
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import asyncpg  # type: ignore[import]
import redis.asyncio as aioredis
from fastapi import HTTPException, status

from config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# ---------------------------------------------------------------------------
# Module-level pool singletons
# ---------------------------------------------------------------------------

_db_pool: asyncpg.Pool | None = None
_redis_client: aioredis.Redis | None = None


# ---------------------------------------------------------------------------
# Initialisation (called from lifespan)
# ---------------------------------------------------------------------------


async def init_db_pool() -> None:
    """
    Create the asyncpg connection pool.

    Configures the pool to use the JSON codec so that Python dicts and
    lists are automatically serialised / deserialised.
    """
    global _db_pool

    async def _init_connection(conn: asyncpg.Connection) -> None:
        """Register JSON codecs on every new connection."""
        import json
        await conn.set_type_codec(
            "jsonb",
            encoder=json.dumps,
            decoder=json.loads,
            schema="pg_catalog",
        )
        await conn.set_type_codec(
            "json",
            encoder=json.dumps,
            decoder=json.loads,
            schema="pg_catalog",
        )

    try:
        _db_pool = await asyncpg.create_pool(
            dsn=settings.database_url,
            min_size=2,
            max_size=20,
            max_inactive_connection_lifetime=300,
            init=_init_connection,
            command_timeout=30,
        )
        logger.info("asyncpg pool created: min=2 max=20 dsn=%s", _redact_dsn(settings.database_url))
    except Exception as exc:
        logger.error("Failed to create asyncpg pool: %s", exc, exc_info=True)
        raise


async def init_redis_pool() -> None:
    """
    Create the redis.asyncio connection pool with health check.
    """
    global _redis_client

    try:
        _redis_client = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            max_connections=50,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True,
        )
        # Verify connectivity
        await _redis_client.ping()
        logger.info("Redis client ready: %s", _redact_dsn(settings.redis_url))
    except Exception as exc:
        logger.error("Failed to connect to Redis: %s", exc, exc_info=True)
        raise


async def close_db_pool() -> None:
    """Gracefully close the asyncpg pool during application shutdown."""
    global _db_pool
    if _db_pool is not None:
        await _db_pool.close()
        _db_pool = None
        logger.info("asyncpg pool closed.")


async def close_redis_pool() -> None:
    """Close the Redis client during application shutdown."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None
        logger.info("Redis client closed.")


# ---------------------------------------------------------------------------
# FastAPI dependency functions
# ---------------------------------------------------------------------------


async def get_db() -> AsyncGenerator[asyncpg.Connection, None]:
    """
    Yield an asyncpg connection from the pool.

    Acquires a connection, yields it for the duration of the request, then
    releases it back to the pool.  Raises HTTP 503 if the pool is not ready.

    Usage
    -----
        @router.get("/")
        async def endpoint(db: asyncpg.Connection = Depends(get_db)):
            ...
    """
    if _db_pool is None:
        logger.error("get_db called before pool initialisation")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection pool is not initialised.",
        )

    async with _db_pool.acquire() as conn:
        yield conn


async def get_redis() -> AsyncGenerator[aioredis.Redis, None]:
    """
    Yield the shared Redis client.

    The same client instance is yielded for every request (Redis clients are
    thread-safe / coroutine-safe).  Raises HTTP 503 if the client is not ready.

    Usage
    -----
        @router.get("/")
        async def endpoint(redis: aioredis.Redis = Depends(get_redis)):
            ...
    """
    if _redis_client is None:
        logger.error("get_redis called before client initialisation")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis client is not initialised.",
        )
    yield _redis_client


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------


def _redact_dsn(dsn: str) -> str:
    """
    Redact the password from a connection DSN for safe logging.

    Handles both ``postgresql://user:pass@host/db`` and
    ``redis://:pass@host:port`` formats.
    """
    try:
        from urllib.parse import urlparse, urlunparse
        parsed = urlparse(dsn)
        if parsed.password:
            netloc = parsed.netloc.replace(f":{parsed.password}@", ":***@")
            return urlunparse(parsed._replace(netloc=netloc))
    except Exception:
        pass
    return dsn
