"""CalibrationTracker — reads model accuracy from PostgreSQL with in-memory TTL cache."""
from __future__ import annotations

import asyncio
import time
from typing import Any

import asyncpg
import structlog

logger = structlog.get_logger(__name__)

# Cache entry TTL in seconds (10 minutes)
_CACHE_TTL_SECONDS = 600

_SELECT_ACCURACY_SQL = """
    SELECT accuracy_pct
    FROM calibration_stats
    WHERE symbol = $1
      AND timeframe = $2
      AND model_name = $3
      AND window_size = $4
    ORDER BY computed_at DESC
    LIMIT 1
"""

_SELECT_ALL_ACCURACIES_SQL = """
    SELECT DISTINCT ON (model_name)
        model_name,
        accuracy_pct
    FROM calibration_stats
    WHERE symbol = $1
      AND timeframe = $2
    ORDER BY model_name, computed_at DESC
"""


class _CacheEntry:
    __slots__ = ("value", "expires_at")

    def __init__(self, value: Any, ttl: float) -> None:
        self.value = value
        self.expires_at = time.monotonic() + ttl


class CalibrationTracker:
    """
    Reads model calibration accuracy from the calibration_stats PostgreSQL table.

    Usage:
        tracker = await CalibrationTracker.create(database_url)
        acc = await tracker.get_accuracy("BTC/USDT", "1h", "technical")

    Gracefully returns None if the database is unavailable or the table doesn't exist.
    Results are cached for 10 minutes to avoid hammering the DB on every forecast cycle.
    """

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool
        # Cache key: (symbol, timeframe, model_name, window_size) → _CacheEntry(float | None)
        self._cache: dict[tuple, _CacheEntry] = {}
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Class-level factory
    # ------------------------------------------------------------------

    @classmethod
    async def create(cls, database_url: str) -> "CalibrationTracker":
        """
        Async factory — creates a connection pool and returns a CalibrationTracker.
        Returns a non-functional (pool=None) tracker on connection failure.
        """
        try:
            pool = await asyncpg.create_pool(
                database_url,
                min_size=1,
                max_size=3,
                command_timeout=10,
            )
            logger.info("calibration_tracker_connected")
            return cls(pool)
        except Exception as exc:
            logger.warning(
                "calibration_tracker_db_unavailable",
                error=str(exc),
                detail="Prediction engine will run without calibration data.",
            )
            return cls.__new_without_pool()

    @classmethod
    def __new_without_pool(cls) -> "CalibrationTracker":
        """Return a no-op tracker that always returns None accuracies."""
        instance = object.__new__(cls)
        instance._pool = None
        instance._cache = {}
        instance._lock = asyncio.Lock()
        return instance

    # ------------------------------------------------------------------
    # Public async API
    # ------------------------------------------------------------------

    async def get_accuracy(
        self,
        symbol: str,
        timeframe: str,
        model_name: str,
        window: int = 100,
    ) -> float | None:
        """
        Return accuracy_pct for the given model/symbol/timeframe, or None if unavailable.

        Caches the result for _CACHE_TTL_SECONDS.
        """
        if self._pool is None:
            return None

        cache_key = (symbol, timeframe, model_name, window)

        # Fast path — check cache without lock
        entry = self._cache.get(cache_key)
        if entry is not None and time.monotonic() < entry.expires_at:
            return entry.value

        # Slow path — query DB under lock to prevent thundering herd
        async with self._lock:
            # Double-check after acquiring lock
            entry = self._cache.get(cache_key)
            if entry is not None and time.monotonic() < entry.expires_at:
                return entry.value

            value = await self._query_accuracy(symbol, timeframe, model_name, window)
            self._cache[cache_key] = _CacheEntry(value, _CACHE_TTL_SECONDS)
            return value

    async def get_all_accuracies(
        self,
        symbol: str,
        timeframe: str,
    ) -> dict[str, float]:
        """
        Return a mapping of {model_name: accuracy_pct} for the most recent records.
        Returns an empty dict if the DB is unavailable.
        """
        if self._pool is None:
            return {}

        cache_key = ("__all__", symbol, timeframe)
        entry = self._cache.get(cache_key)
        if entry is not None and time.monotonic() < entry.expires_at:
            return entry.value or {}

        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(_SELECT_ALL_ACCURACIES_SQL, symbol, timeframe)
            result = {row["model_name"]: float(row["accuracy_pct"]) for row in rows}
            self._cache[cache_key] = _CacheEntry(result, _CACHE_TTL_SECONDS)
            logger.debug(
                "calibration_all_accuracies_fetched",
                symbol=symbol,
                timeframe=timeframe,
                models=list(result.keys()),
            )
            return result
        except Exception as exc:
            logger.warning(
                "calibration_all_accuracies_error",
                symbol=symbol,
                timeframe=timeframe,
                error=str(exc),
            )
            return {}

    def get_accuracy_sync(
        self,
        symbol: str,
        timeframe: str,
        model_name: str,
        window: int = 100,
    ) -> float | None:
        """
        Synchronous cache-only lookup (no DB query).
        Used by EnsembleVoter when an async call is not possible.
        Returns None if not in cache.
        """
        cache_key = (symbol, timeframe, model_name, window)
        entry = self._cache.get(cache_key)
        if entry is not None and time.monotonic() < entry.expires_at:
            return entry.value
        return None

    async def warm_cache(self, symbol: str, timeframe: str) -> None:
        """
        Pre-warm the cache for all models for a given symbol/timeframe.
        Call this during engine startup to ensure synchronous lookups work on first vote.
        """
        if self._pool is None:
            return
        accuracies = await self.get_all_accuracies(symbol, timeframe)
        for model_name, accuracy_pct in accuracies.items():
            cache_key = (symbol, timeframe, model_name, 100)
            self._cache[cache_key] = _CacheEntry(accuracy_pct, _CACHE_TTL_SECONDS)
        logger.debug(
            "calibration_cache_warmed",
            symbol=symbol,
            timeframe=timeframe,
            count=len(accuracies),
        )

    def invalidate(self, symbol: str | None = None, timeframe: str | None = None) -> None:
        """
        Invalidate cache entries. Removes all entries if symbol is None,
        or only entries matching symbol (and optionally timeframe).
        """
        if symbol is None:
            self._cache.clear()
            logger.debug("calibration_cache_cleared_all")
            return

        keys_to_delete = [
            k for k in self._cache
            if k[0] == symbol and (timeframe is None or k[1] == timeframe)
        ]
        for k in keys_to_delete:
            del self._cache[k]
        logger.debug(
            "calibration_cache_invalidated",
            symbol=symbol,
            timeframe=timeframe,
            removed=len(keys_to_delete),
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _query_accuracy(
        self,
        symbol: str,
        timeframe: str,
        model_name: str,
        window: int,
    ) -> float | None:
        """Execute the DB query and return accuracy_pct or None."""
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    _SELECT_ACCURACY_SQL,
                    symbol,
                    timeframe,
                    model_name,
                    window,
                )
            if row is not None:
                accuracy = float(row["accuracy_pct"])
                logger.debug(
                    "calibration_accuracy_fetched",
                    symbol=symbol,
                    timeframe=timeframe,
                    model=model_name,
                    window=window,
                    accuracy_pct=accuracy,
                )
                return accuracy
            logger.debug(
                "calibration_accuracy_no_data",
                symbol=symbol,
                timeframe=timeframe,
                model=model_name,
                window=window,
            )
            return None
        except asyncpg.exceptions.UndefinedTableError:
            logger.warning(
                "calibration_table_missing",
                detail="calibration_stats table does not exist. "
                       "Run migrations to create it.",
            )
            return None
        except Exception as exc:
            logger.warning(
                "calibration_query_error",
                symbol=symbol,
                timeframe=timeframe,
                model=model_name,
                error=str(exc),
            )
            return None
