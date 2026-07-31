"""
Redis-backed market data cache.

TTL per timeframe keeps hot candles available without stale reads.
All serialisation is JSON so values are human-readable in redis-cli.
"""
from __future__ import annotations

import json
import logging
from typing import Optional

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

# Seconds each timeframe's data is considered fresh
_TTL_MAP: dict[str, int] = {
    "1m":  30,
    "3m":  90,
    "5m":  150,
    "15m": 450,
    "30m": 900,
    "1h":  300,
    "4h":  1200,
    "1d":  3600,
}
_DEFAULT_TTL = 300  # fallback for unknown timeframes


def _key(symbol: str, timeframe: str) -> str:
    """Canonical Redis key for a symbol/timeframe pair."""
    # Normalise symbol: replace / with _ for safe key usage
    safe_symbol = symbol.replace("/", "_").upper()
    return f"market:{safe_symbol}:{timeframe}:latest"


class RedisCacheManager:
    """
    Async Redis cache for unified market data dicts.

    Usage::

        cache = RedisCacheManager(redis_url="redis://localhost:6379/0")
        await cache.connect()

        await cache.set("BTC/USDT", "1h", market_data)
        data = await cache.get("BTC/USDT", "1h")   # dict | None

        await cache.close()
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        redis_client: Optional[aioredis.Redis] = None,
    ) -> None:
        """
        Args:
            redis_url:     Connection URL used when no client is provided.
            redis_client:  Pre-existing async Redis client (takes priority).
        """
        self._url    = redis_url
        self._client = redis_client
        self._owned  = redis_client is None  # True → we created it, so we close it

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Open a connection pool if one was not injected at construction."""
        if self._client is None:
            self._client = await aioredis.from_url(
                self._url,
                encoding="utf-8",
                decode_responses=True,
            )
            logger.info("RedisCacheManager connected to %s", self._url)

    async def close(self) -> None:
        """Release the connection pool if we own it."""
        if self._owned and self._client is not None:
            await self._client.aclose()
            self._client = None
            logger.info("RedisCacheManager disconnected")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get(self, symbol: str, timeframe: str) -> Optional[dict]:
        """
        Retrieve cached market data.

        Returns:
            Unified market_data dict, or ``None`` if absent / expired.
        """
        if self._client is None:
            raise RuntimeError("Call await cache.connect() first")

        key = _key(symbol, timeframe)
        try:
            raw = await self._client.get(key)
        except Exception:
            logger.exception("Redis GET failed for key %s", key)
            return None

        if raw is None:
            return None

        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Corrupt cache entry for %s — evicting", key)
            await self._client.delete(key)
            return None

    async def set(self, symbol: str, timeframe: str, data: dict) -> None:
        """
        Store market data with the appropriate TTL.

        Args:
            symbol:    e.g. "BTC/USDT"
            timeframe: e.g. "1h"
            data:      Unified market_data dict
        """
        if self._client is None:
            raise RuntimeError("Call await cache.connect() first")

        key = _key(symbol, timeframe)
        ttl = _TTL_MAP.get(timeframe, _DEFAULT_TTL)

        try:
            payload = json.dumps(data, default=_json_default)
            await self._client.setex(key, ttl, payload)
        except Exception:
            logger.exception("Redis SET failed for key %s", key)

    async def delete(self, symbol: str, timeframe: str) -> None:
        """Manually invalidate a cached entry."""
        if self._client is None:
            raise RuntimeError("Call await cache.connect() first")
        await self._client.delete(_key(symbol, timeframe))

    async def ttl(self, symbol: str, timeframe: str) -> int:
        """Return remaining TTL in seconds (-2 = not found, -1 = no expiry)."""
        if self._client is None:
            raise RuntimeError("Call await cache.connect() first")
        return await self._client.ttl(_key(symbol, timeframe))

    # ------------------------------------------------------------------
    # Context-manager support
    # ------------------------------------------------------------------

    async def __aenter__(self) -> "RedisCacheManager":
        await self.connect()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _json_default(obj: object) -> object:
    """Fallback JSON serialiser for numpy types and similar."""
    import numpy as np  # local import to avoid hard dep at module level
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")
