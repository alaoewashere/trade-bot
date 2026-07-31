"""
api/main.py
============
Hedge Fund AI — FastAPI application entry point.

Mounts all routers, configures middleware, exposes a Prometheus /metrics
endpoint, and manages the asyncpg + Redis lifecycle.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import make_asgi_app

from api.dependencies import (
    close_db_pool,
    close_redis_pool,
    init_db_pool,
    init_redis_pool,
)
from api.routers import (
    agents,
    alerts,
    approvals,
    backtest,
    forecasts,
    journal,
    markets,
    portfolio,
    risk,
    system,
    trades,
)
from api.websockets import market_stream
from config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application startup and shutdown.

    Startup:
      1. Connect asyncpg pool.
      2. Connect Redis client.
      3. Start background circuit-breaker event subscriber.
      4. Start background Binance WS tick ingestion (Phase 6).

    Shutdown:
      1. Cancel background tasks.
      2. Close Redis.
      3. Close asyncpg pool.
    """
    import asyncio
    from risk.circuit_breakers import CircuitBreakerSubscriber
    import redis.asyncio as aioredis

    logger.info("Hedge Fund AI starting — environment=%s", settings.environment)

    # ---- Database pool ----
    try:
        await init_db_pool()
    except Exception as exc:
        logger.warning("DB pool failed to initialise (non-fatal for startup): %s", exc)

    # ---- Redis client ----
    try:
        await init_redis_pool()
    except Exception as exc:
        logger.warning("Redis failed to initialise (non-fatal for startup): %s", exc)

    # ---- Background circuit-breaker subscriber ----
    cb_subscriber_task = None
    try:
        _sub_redis = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
        subscriber = CircuitBreakerSubscriber(_sub_redis)
        cb_subscriber_task = asyncio.create_task(subscriber.start())
        logger.info("CircuitBreakerSubscriber started.")
    except Exception as exc:
        logger.warning("CircuitBreakerSubscriber could not start: %s", exc)

    # ---- Background Binance WS tick ingestion (Phase 6) ----
    # Runs as an asyncio task in the API process rather than a separate
    # Docker service: it's a single lightweight persistent socket writing
    # into Redis, following the exact same pattern as CircuitBreakerSubscriber
    # above. A dedicated service would only pay off once ingestion needs
    # independent scaling/restart from the API — not the case yet.
    ws_feed_task = None
    try:
        from api.routers.markets import _DEFAULT_LIVE_SYMBOLS
        from data.feeds.binance_ws_feed import BinanceWSFeed

        _feed_redis = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
        ws_feed = BinanceWSFeed(symbols=_DEFAULT_LIVE_SYMBOLS, redis_client=_feed_redis)
        ws_feed_task = asyncio.create_task(ws_feed.start())
        logger.info("BinanceWSFeed started for %d symbols.", len(_DEFAULT_LIVE_SYMBOLS))
    except Exception as exc:
        logger.warning("BinanceWSFeed could not start: %s", exc)

    yield

    # ---- Shutdown ----
    if cb_subscriber_task is not None:
        cb_subscriber_task.cancel()
        try:
            await cb_subscriber_task
        except asyncio.CancelledError:
            pass

    if ws_feed_task is not None:
        ws_feed_task.cancel()
        try:
            await ws_feed_task
        except asyncio.CancelledError:
            pass

    await close_redis_pool()
    await close_db_pool()
    logger.info("Hedge Fund AI shutdown complete.")


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------


app = FastAPI(
    title="Hedge Fund AI",
    description=(
        "Institutional-grade multi-agent AI trading system. "
        "40 specialised agents collaborate via LangGraph to analyse markets, "
        "debate signals, and execute trades with full human oversight."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Prometheus metrics endpoint
# ---------------------------------------------------------------------------

metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(agents.router, prefix="/agents", tags=["Agents"])
app.include_router(trades.router, prefix="/trades", tags=["Trades"])
app.include_router(journal.router, prefix="/journal", tags=["Journal"])
app.include_router(backtest.router, prefix="/backtest", tags=["Backtest"])
app.include_router(forecasts.router, prefix="/forecasts", tags=["Forecasts"])
app.include_router(portfolio.router, prefix="/portfolio", tags=["Portfolio"])
app.include_router(risk.router, prefix="/risk", tags=["Risk"])
app.include_router(approvals.router, prefix="/approvals", tags=["Approvals"])
app.include_router(system.router, prefix="/system", tags=["System"])
app.include_router(markets.router, prefix="/markets", tags=["Markets"])
app.include_router(alerts.router, prefix="/alerts", tags=["Alerts"])
app.include_router(market_stream.router, prefix="/ws", tags=["WebSocket"])


# ---------------------------------------------------------------------------
# Core endpoints
# ---------------------------------------------------------------------------


@app.get("/health", tags=["Health"])
async def health(request: Request) -> dict:
    """
    Liveness probe.

    Returns the application status, environment, and connectivity of all
    critical backend services (database, Redis).
    """
    from api.dependencies import _db_pool, _redis_client

    db_ok = False
    redis_ok = False

    if _db_pool is not None:
        try:
            async with _db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            db_ok = True
        except Exception:
            pass

    if _redis_client is not None:
        try:
            await _redis_client.ping()
            redis_ok = True
        except Exception:
            pass

    overall = "ok" if (db_ok and redis_ok) else "degraded"

    return {
        "status": overall,
        "environment": settings.environment,
        "services": {
            "database": "ok" if db_ok else "unavailable",
            "redis": "ok" if redis_ok else "unavailable",
        },
        "version": "1.0.0",
    }


@app.get("/", tags=["Health"])
async def root() -> dict:
    return {
        "name": "Hedge Fund AI",
        "version": "1.0.0",
        "environment": settings.environment,
        "docs": "/docs",
        "health": "/health",
        "metrics": "/metrics",
    }


# ---------------------------------------------------------------------------
# Global exception handler
# ---------------------------------------------------------------------------


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "Unhandled exception: %s %s — %s",
        request.method,
        request.url.path,
        exc,
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={
            "detail": "An internal server error occurred.",
            "path": request.url.path,
        },
    )
