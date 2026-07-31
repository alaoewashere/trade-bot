"""
Forex / commodity feed.

Primary source : ccxt currencycom (supports forex & gold with free public data).
Fallback       : yfinance for symbols not available on currencycom (e.g. GC=F for Gold futures).

Supported pairs (examples):
    EUR/USD, GBP/USD, USD/JPY, AUD/USD, USD/CHF   — forex
    XAU/USD (currencycom) / GC=F (yfinance)        — gold
    XAG/USD                                         — silver
"""
from __future__ import annotations

import asyncio
import logging
from functools import partial
from typing import Optional

from data.normalizer import DataNormalizer
from data.cache import RedisCacheManager

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Symbol mapping: internal symbol → {ccxt_symbol, yf_symbol}
# ---------------------------------------------------------------------------
_SYMBOL_MAP: dict[str, dict[str, str]] = {
    "EUR/USD": {"ccxt": "EUR/USD",  "yf": "EURUSD=X"},
    "GBP/USD": {"ccxt": "GBP/USD",  "yf": "GBPUSD=X"},
    "USD/JPY": {"ccxt": "USD/JPY",  "yf": "JPY=X"},
    "AUD/USD": {"ccxt": "AUD/USD",  "yf": "AUDUSD=X"},
    "USD/CHF": {"ccxt": "USD/CHF",  "yf": "USDCHF=X"},
    "USD/CAD": {"ccxt": "USD/CAD",  "yf": "CAD=X"},
    "NZD/USD": {"ccxt": "NZD/USD",  "yf": "NZDUSD=X"},
    "XAU/USD": {"ccxt": "XAU/USD",  "yf": "GC=F"},    # Gold
    "XAG/USD": {"ccxt": "XAG/USD",  "yf": "SI=F"},    # Silver
}

_YF_TIMEFRAME_MAP: dict[str, str] = {
    "1m":  "1m",
    "5m":  "5m",
    "15m": "15m",
    "30m": "30m",
    "1h":  "60m",
    "4h":  "1h",   # yfinance has no 4h — use 1h and let callers aggregate
    "1d":  "1d",
}

_CCXT_TIMEFRAME_MAP: dict[str, str] = {
    "1m":  "1m",
    "5m":  "5m",
    "15m": "15m",
    "30m": "30m",
    "1h":  "1h",
    "4h":  "4h",
    "1d":  "1d",
}

_YF_PERIOD_FOR_TIMEFRAME: dict[str, str] = {
    "1m":  "1d",
    "5m":  "5d",
    "15m": "5d",
    "30m": "1mo",
    "1h":  "1mo",
    "4h":  "3mo",
    "1d":  "1y",
}


class ForexFeed:
    """
    Async feed for forex pairs and precious metals.

    Tries ccxt currencycom first (rate-limited free tier);
    falls back to yfinance via a thread-pool executor to keep the
    async event loop unblocked.

    Example::

        feed = ForexFeed(cache=cache)
        data = await feed.fetch("EUR/USD", "1h")
        data = await feed.fetch("XAU/USD", "1d")   # Gold
        await feed.close()
    """

    CANDLE_LIMIT = 500

    def __init__(
        self,
        cache: Optional[RedisCacheManager] = None,
        prefer_yfinance: bool = False,
    ) -> None:
        """
        Args:
            cache:          Optional Redis cache manager.
            prefer_yfinance: Skip ccxt and go straight to yfinance.
                             Useful if currencycom rate-limits you.
        """
        self.cache           = cache
        self._prefer_yf      = prefer_yfinance
        self._exchange: object | None = None  # lazy init

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def fetch(self, symbol: str, timeframe: str) -> dict:
        """
        Fetch OHLCV data for a forex pair or commodity.

        Args:
            symbol:    e.g. "EUR/USD", "XAU/USD"
            timeframe: e.g. "1h"

        Returns:
            Unified market_data dict.
        """
        # Cache probe
        if self.cache is not None:
            cached = await self.cache.get(symbol, timeframe)
            if cached is not None:
                logger.debug("ForexFeed cache hit %s %s", symbol, timeframe)
                return cached

        market_data: dict | None = None

        if not self._prefer_yf:
            market_data = await self._fetch_ccxt(symbol, timeframe)

        if market_data is None or not market_data.get("closes"):
            market_data = await self._fetch_yfinance(symbol, timeframe)

        if market_data is None:
            return DataNormalizer._empty(symbol, timeframe)

        if self.cache is not None:
            await self.cache.set(symbol, timeframe, market_data)

        return market_data

    async def get_current_price(self, symbol: str) -> float:
        """
        Return the latest mid-price for a forex pair.

        Returns:
            Price as float, or 0.0 on failure.
        """
        data = await self.fetch(symbol, "1m")
        return float(data.get("current_price", 0.0))

    async def close(self) -> None:
        """Release the ccxt HTTP session if one was opened."""
        if self._exchange is not None:
            try:
                await self._exchange.close()  # type: ignore[union-attr]
            except Exception:
                pass
            self._exchange = None

    # ------------------------------------------------------------------
    # Private: ccxt currencycom
    # ------------------------------------------------------------------

    async def _get_exchange(self):
        """Lazily initialise the currencycom ccxt exchange."""
        if self._exchange is None:
            try:
                import ccxt.async_support as ccxt  # type: ignore
                self._exchange = ccxt.currencycom({"enableRateLimit": True})
            except Exception as exc:
                logger.warning("currencycom init failed: %s", exc)
        return self._exchange

    async def _fetch_ccxt(self, symbol: str, timeframe: str) -> dict | None:
        """
        Attempt to fetch OHLCV from currencycom via ccxt.

        Returns None on any failure so the caller can fall back to yfinance.
        """
        exchange = await self._get_exchange()
        if exchange is None:
            return None

        # currencycom uses slightly different symbol formatting for some pairs
        ccxt_sym = _SYMBOL_MAP.get(symbol, {}).get("ccxt", symbol)
        tf       = _CCXT_TIMEFRAME_MAP.get(timeframe, "1h")

        try:
            raw: list = await exchange.fetch_ohlcv(  # type: ignore[union-attr]
                ccxt_sym, tf, limit=self.CANDLE_LIMIT
            )
            if not raw:
                return None
            return DataNormalizer.normalize_ccxt(raw, symbol, timeframe)
        except Exception as exc:
            logger.info(
                "ccxt currencycom failed for %s %s (%s) — falling back to yfinance",
                symbol, timeframe, exc,
            )
            return None

    # ------------------------------------------------------------------
    # Private: yfinance (runs in thread pool to avoid blocking the loop)
    # ------------------------------------------------------------------

    async def _fetch_yfinance(self, symbol: str, timeframe: str) -> dict | None:
        """
        Fetch OHLCV via yfinance in a thread-pool executor.

        Returns None if yfinance is not installed or raises an exception.
        """
        yf_sym    = _SYMBOL_MAP.get(symbol, {}).get("yf", symbol)
        yf_tf     = _YF_TIMEFRAME_MAP.get(timeframe, "1h")
        yf_period = _YF_PERIOD_FOR_TIMEFRAME.get(timeframe, "1mo")

        loop = asyncio.get_event_loop()
        try:
            raw_ohlcv = await loop.run_in_executor(
                None,
                partial(self._yf_fetch_sync, yf_sym, yf_tf, yf_period),
            )
        except Exception as exc:
            logger.error("yfinance fetch failed for %s: %s", symbol, exc)
            return None

        if not raw_ohlcv:
            return None

        return DataNormalizer.normalize_ccxt(raw_ohlcv, symbol, timeframe)

    @staticmethod
    def _yf_fetch_sync(
        yf_symbol: str, interval: str, period: str
    ) -> list[list]:
        """
        Synchronous yfinance call — executed in a thread pool.

        Returns list of [timestamp_ms, open, high, low, close, volume]
        matching ccxt format so we can reuse normalize_ccxt.
        """
        try:
            import yfinance as yf  # type: ignore
        except ImportError:
            logger.error("yfinance is not installed. Run: pip install yfinance")
            return []

        try:
            ticker = yf.Ticker(yf_symbol)
            df     = ticker.history(period=period, interval=interval, auto_adjust=True)
        except Exception as exc:
            logger.error("yfinance Ticker.history failed for %s: %s", yf_symbol, exc)
            return []

        if df is None or df.empty:
            return []

        result: list[list] = []
        for ts, row in df.iterrows():
            try:
                ts_ms  = int(ts.timestamp() * 1000)
                result.append([
                    ts_ms,
                    float(row["Open"]),
                    float(row["High"]),
                    float(row["Low"]),
                    float(row["Close"]),
                    float(row["Volume"]),
                ])
            except Exception:
                continue  # skip malformed rows

        return result

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    async def __aenter__(self) -> "ForexFeed":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()
