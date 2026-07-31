"""
data/tick_cache.py
===================
Redis-backed cache for individual WebSocket ticks (last price/volume per
symbol), distinct from RedisCacheManager's per-timeframe candle cache.

Ticks are written on every trade event from the exchange WS feed, so the
TTL here is deliberately very short (a few seconds) — a stale tick key is
exactly the signal the staleness circuit breaker (risk/circuit_breakers.py
MarketDataStalenessGate) needs to detect a dead feed.

Every write is also published to ``market:ticks`` so the backend WS
broadcaster (api/websockets/market_stream.py) can push it to browser
clients without polling Redis.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Optional

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

TICK_PUBSUB_CHANNEL = "market:ticks"
TICK_TTL_SECONDS = 10  # generous vs. the 2s staleness rule so reads don't race the writer


def _tick_key(symbol: str) -> str:
    safe_symbol = symbol.replace("/", "_").upper()
    return f"market:tick:{safe_symbol}:latest"


class TickCache:
    """
    Async Redis cache for the latest tick per symbol.

    Usage::

        cache = TickCache(redis_client=redis)
        await cache.set_tick("BTC/USDT", price=67123.4, volume=0.021, prev_close=66800.0)
        tick = await cache.get_tick("BTC/USDT")   # dict | None
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        redis_client: Optional[aioredis.Redis] = None,
    ) -> None:
        self._url = redis_url
        self._client = redis_client
        self._owned = redis_client is None

    async def connect(self) -> None:
        if self._client is None:
            self._client = await aioredis.from_url(
                self._url, encoding="utf-8", decode_responses=True,
            )
            logger.info("TickCache connected to %s", self._url)

    async def close(self) -> None:
        if self._owned and self._client is not None:
            await self._client.aclose()
            self._client = None

    async def set_tick(
        self,
        symbol: str,
        price: float,
        volume: float = 0.0,
        change: Optional[float] = None,
        change_pct: Optional[float] = None,
    ) -> dict:
        """
        Store the latest tick and publish it to ``market:ticks``.

        Returns the tick payload dict that was stored/published so callers
        (the WS ingestion client) don't have to reconstruct it.
        """
        if self._client is None:
            raise RuntimeError("Call await cache.connect() first")

        now = time.time()
        payload = {
            "symbol": symbol,
            "price": price,
            "volume": volume,
            "change": change,
            "change_pct": change_pct,
            "ts": now,  # epoch seconds — cheap staleness arithmetic, no datetime parsing on the hot path
        }
        raw = json.dumps(payload)
        try:
            async with self._client.pipeline(transaction=True) as pipe:
                pipe.setex(_tick_key(symbol), TICK_TTL_SECONDS, raw)
                pipe.publish(TICK_PUBSUB_CHANNEL, raw)
                await pipe.execute()
        except Exception:
            logger.exception("Failed to write tick for %s", symbol)
        return payload

    async def get_tick(self, symbol: str) -> Optional[dict]:
        """Return the latest tick dict for *symbol*, or None if absent/expired."""
        if self._client is None:
            raise RuntimeError("Call await cache.connect() first")
        raw = await self._client.get(_tick_key(symbol))
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    async def age_seconds(self, symbol: str) -> Optional[float]:
        """Seconds since the last tick for *symbol*, or None if there's no tick at all."""
        tick = await self.get_tick(symbol)
        if tick is None:
            return None
        return max(0.0, time.time() - tick["ts"])
