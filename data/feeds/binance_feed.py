"""
Binance market-data feed via ccxt async.

Fetches OHLCV candles + 24-h ticker, normalises into the unified schema,
and caches results in Redis to avoid hammering the exchange on every cycle.
"""
from __future__ import annotations

import logging
from typing import Optional

import ccxt.async_support as ccxt

from data.normalizer import DataNormalizer
from data.cache import RedisCacheManager

logger = logging.getLogger(__name__)


class BinanceFeed:
    """
    Async Binance feed backed by ccxt.

    Example::

        feed = BinanceFeed(api_key="...", secret="...", cache=cache)
        data = await feed.fetch("BTC/USDT", "1h")
        price = await feed.get_current_price("BTC/USDT")
        await feed.close()
    """

    CCXT_TIMEFRAMES: dict[str, str] = {
        "1m":  "1m",
        "3m":  "3m",
        "5m":  "5m",
        "15m": "15m",
        "30m": "30m",
        "1h":  "1h",
        "4h":  "4h",
        "1d":  "1d",
    }
    CANDLE_LIMIT = 500  # candles per fetch

    def __init__(
        self,
        api_key: str = "",
        secret: str = "",
        cache: Optional[RedisCacheManager] = None,
        testnet: bool = False,
    ) -> None:
        """
        Args:
            api_key:  Binance API key (public data works without one).
            secret:   Binance API secret.
            cache:    Optional RedisCacheManager for caching market data.
            testnet:  Route to Binance testnet when True.
        """
        exchange_config: dict = {
            "apiKey":          api_key or None,
            "secret":          secret or None,
            "enableRateLimit": True,
            "options":         {"defaultType": "spot"},
        }
        if testnet:
            exchange_config["urls"] = {
                "api": {
                    "public":  "https://testnet.binance.vision/api",
                    "private": "https://testnet.binance.vision/api",
                }
            }

        self.exchange: ccxt.binance = ccxt.binance(exchange_config)
        self.cache = cache

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def fetch(self, symbol: str, timeframe: str) -> dict:
        """
        Fetch OHLCV candles + 24-h volume statistics for *symbol*.

        Flow:
            1. Check Redis cache — return immediately on hit.
            2. Fetch OHLCV from Binance (500 candles).
            3. Fetch 24-h ticker for USD volume.
            4. Normalise into unified schema.
            5. Store in Redis cache.
            6. Return normalised dict.

        Args:
            symbol:    ccxt symbol, e.g. "BTC/USDT".
            timeframe: One of the keys in CCXT_TIMEFRAMES.

        Returns:
            Unified market_data dict.
        """
        # 1. Cache look-up
        if self.cache is not None:
            cached = await self.cache.get(symbol, timeframe)
            if cached is not None:
                logger.debug("Cache hit for %s %s", symbol, timeframe)
                return cached

        tf = self.CCXT_TIMEFRAMES.get(timeframe, "1h")

        # 2. OHLCV
        try:
            raw_ohlcv: list = await self.exchange.fetch_ohlcv(
                symbol, tf, limit=self.CANDLE_LIMIT
            )
        except ccxt.BaseError as exc:
            logger.error("fetch_ohlcv failed for %s %s: %s", symbol, timeframe, exc)
            return DataNormalizer._empty(symbol, timeframe)

        if not raw_ohlcv:
            logger.warning("Empty OHLCV response for %s %s", symbol, timeframe)
            return DataNormalizer._empty(symbol, timeframe)

        # 3. 24-h ticker (best-effort — don't fail the whole fetch on ticker error)
        volume_24h: float = 0.0
        try:
            ticker = await self.exchange.fetch_ticker(symbol)
            # quoteVolume is in the quote currency (USDT for BTC/USDT)
            volume_24h = float(ticker.get("quoteVolume") or 0.0)
        except Exception as exc:
            logger.warning("fetch_ticker failed for %s: %s", symbol, exc)

        # 4. Normalise
        market_data = DataNormalizer.normalize_ccxt(
            raw_ohlcv, symbol, timeframe, volume_24h=volume_24h
        )

        # 5. Cache
        if self.cache is not None:
            await self.cache.set(symbol, timeframe, market_data)

        return market_data

    async def get_current_price(self, symbol: str) -> float:
        """
        Fast spot-price fetch suitable for forecast evaluation.

        Tries the Redis cache first (any timeframe), then falls back to
        a lightweight ticker call.

        Returns:
            Latest price as float, or 0.0 on failure.
        """
        # Quick cache probe — try "1m" and "1h" as the most common timeframes
        if self.cache is not None:
            for tf in ("1m", "1h"):
                cached = await self.cache.get(symbol, tf)
                if cached and cached.get("current_price"):
                    return float(cached["current_price"])

        # Live ticker fallback
        try:
            ticker = await self.exchange.fetch_ticker(symbol)
            return float(ticker.get("last") or ticker.get("close") or 0.0)
        except Exception as exc:
            logger.error("get_current_price failed for %s: %s", symbol, exc)
            return 0.0

    async def get_orderbook(self, symbol: str, limit: int = 20) -> dict:
        """
        Fetch level-2 order book for spread / liquidity analysis.

        Returns:
            Dict with keys ``bids``, ``asks``, ``spread_bps``.
        """
        try:
            ob = await self.exchange.fetch_order_book(symbol, limit=limit)
            best_bid = ob["bids"][0][0] if ob.get("bids") else 0.0
            best_ask = ob["asks"][0][0] if ob.get("asks") else 0.0
            spread_bps = (
                ((best_ask - best_bid) / best_bid * 10_000)
                if best_bid > 0
                else 0.0
            )
            return {
                "bids":       ob.get("bids", []),
                "asks":       ob.get("asks", []),
                "best_bid":   best_bid,
                "best_ask":   best_ask,
                "spread_bps": round(spread_bps, 2),
            }
        except Exception as exc:
            logger.error("get_orderbook failed for %s: %s", symbol, exc)
            return {"bids": [], "asks": [], "best_bid": 0.0, "best_ask": 0.0, "spread_bps": 0.0}

    async def close(self) -> None:
        """Release the underlying ccxt HTTP session."""
        await self.exchange.close()

    # ------------------------------------------------------------------
    # Context-manager support
    # ------------------------------------------------------------------

    async def __aenter__(self) -> "BinanceFeed":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()
