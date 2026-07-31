"""
Alpaca market-data feed (stocks & ETFs) via the Alpaca Data API v2.

Uses httpx for async HTTP. Falls back to an empty normalised dict when
API credentials are absent so the system degrades gracefully in paper/
backtesting mode without Alpaca access.
"""
from __future__ import annotations

import logging
from typing import Optional

import httpx

from data.normalizer import DataNormalizer
from data.cache import RedisCacheManager

logger = logging.getLogger(__name__)


class AlpacaFeed:
    """
    Async feed for US equities via Alpaca Data API v2.

    Example::

        feed = AlpacaFeed(api_key="PKXXX", secret_key="secretXXX", cache=cache)
        data = await feed.fetch("AAPL", "1h")
        price = await feed.get_current_price("AAPL")
    """

    BASE_URL = "https://data.alpaca.markets/v2"

    TIMEFRAME_MAP: dict[str, str] = {
        "1m":  "1Min",
        "5m":  "5Min",
        "15m": "15Min",
        "30m": "30Min",
        "1h":  "1Hour",
        "4h":  "4Hour",
        "1d":  "1Day",
    }

    def __init__(
        self,
        api_key: str = "",
        secret_key: str = "",
        cache: Optional[RedisCacheManager] = None,
        feed: str = "sip",           # "sip" (paid) or "iex" (free)
        timeout: float = 15.0,
    ) -> None:
        """
        Args:
            api_key:    Alpaca API key ID.
            secret_key: Alpaca API secret key.
            cache:      Optional Redis cache.
            feed:       Market data feed; "sip" requires data subscription.
            timeout:    HTTP request timeout in seconds.
        """
        self._available = bool(api_key and secret_key)
        self._feed      = feed
        self._timeout   = timeout
        self.cache      = cache

        self._headers: dict[str, str] = {}
        if self._available:
            self._headers = {
                "APCA-API-KEY-ID":     api_key,
                "APCA-API-SECRET-KEY": secret_key,
            }

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def fetch(self, symbol: str, timeframe: str) -> dict:
        """
        Fetch OHLCV bars for an equity symbol from Alpaca.

        Flow:
            1. Return empty dict if no credentials configured.
            2. Check Redis cache.
            3. Fetch bars from Alpaca (up to 500 bars).
            4. Normalise and cache.

        Args:
            symbol:    Equity ticker, e.g. "AAPL".
            timeframe: One of the keys in TIMEFRAME_MAP.

        Returns:
            Unified market_data dict.
        """
        if not self._available:
            logger.debug("AlpacaFeed: no credentials — returning empty for %s", symbol)
            return DataNormalizer._empty(symbol, timeframe)

        # Cache look-up
        if self.cache is not None:
            cached = await self.cache.get(symbol, timeframe)
            if cached is not None:
                logger.debug("AlpacaFeed cache hit for %s %s", symbol, timeframe)
                return cached

        tf  = self.TIMEFRAME_MAP.get(timeframe, "1Hour")
        url = f"{self.BASE_URL}/stocks/{symbol}/bars"
        params: dict[str, str | int] = {
            "timeframe":  tf,
            "limit":      500,
            "adjustment": "raw",
            "feed":       self._feed,
        }

        try:
            async with httpx.AsyncClient(
                headers=self._headers, timeout=self._timeout
            ) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "AlpacaFeed HTTP %s for %s %s: %s",
                exc.response.status_code, symbol, timeframe, exc,
            )
            return DataNormalizer._empty(symbol, timeframe)
        except Exception as exc:
            logger.error("AlpacaFeed fetch error for %s %s: %s", symbol, timeframe, exc)
            return DataNormalizer._empty(symbol, timeframe)

        bars: list[dict] = payload.get("bars", [])
        if not bars:
            logger.warning("AlpacaFeed: no bars returned for %s %s", symbol, timeframe)
            return DataNormalizer._empty(symbol, timeframe)

        market_data = DataNormalizer.normalize_alpaca(bars, symbol, timeframe)

        if self.cache is not None:
            await self.cache.set(symbol, timeframe, market_data)

        return market_data

    async def get_current_price(self, symbol: str) -> float:
        """
        Fetch the latest trade price for a symbol.

        Returns:
            Latest price as float, or 0.0 on failure / no credentials.
        """
        if not self._available:
            return 0.0

        url = f"{self.BASE_URL}/stocks/{symbol}/trades/latest"
        params = {"feed": self._feed}
        try:
            async with httpx.AsyncClient(
                headers=self._headers, timeout=self._timeout
            ) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                trade = response.json().get("trade", {})
                return float(trade.get("p", 0.0))
        except Exception as exc:
            logger.error("AlpacaFeed.get_current_price failed for %s: %s", symbol, exc)
            return 0.0

    async def get_snapshot(self, symbol: str) -> dict:
        """
        Fetch the full market snapshot (latest trade, quote, minute bar, day bar).

        Returns:
            Raw snapshot dict from Alpaca, or ``{}`` on failure.
        """
        if not self._available:
            return {}

        url = f"{self.BASE_URL}/stocks/{symbol}/snapshot"
        params = {"feed": self._feed}
        try:
            async with httpx.AsyncClient(
                headers=self._headers, timeout=self._timeout
            ) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                return response.json()
        except Exception as exc:
            logger.error("AlpacaFeed.get_snapshot failed for %s: %s", symbol, exc)
            return {}

    async def fetch_multiple(
        self, symbols: list[str], timeframe: str
    ) -> dict[str, dict]:
        """
        Fetch normalised market data for multiple symbols concurrently.

        Returns:
            Dict mapping symbol → unified market_data.
        """
        import asyncio

        tasks = {sym: asyncio.create_task(self.fetch(sym, timeframe)) for sym in symbols}
        results: dict[str, dict] = {}
        for sym, task in tasks.items():
            try:
                results[sym] = await task
            except Exception as exc:
                logger.error("fetch_multiple error for %s: %s", sym, exc)
                results[sym] = DataNormalizer._empty(sym, timeframe)
        return results
