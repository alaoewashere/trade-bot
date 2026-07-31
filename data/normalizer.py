"""
Unified market data normalizer.

Converts raw OHLCV data from any exchange / broker into a single
canonical dict schema that every downstream agent can rely on.
"""
from __future__ import annotations

import numpy as np
from typing import Any

# ---------------------------------------------------------------------------
# Canonical field names understood by all agents and risk modules
# ---------------------------------------------------------------------------
UNIFIED_SCHEMA_KEYS = [
    "symbol",
    "timeframe",
    "current_price",
    "closes",
    "opens",
    "highs",
    "lows",
    "volumes",
    "timestamps",
    "ohlcv",           # dict with last candle: open/high/low/close/volume
    "indicators",      # dict for calculated indicators (empty by default, filled by feeds)
    "volume_24h_usd",
    "daily_returns",
    "volume_trend",    # "increasing" | "decreasing" | "flat"
    # Optional enrichment fields populated by feeds / enrichment agents
    "macro_data",      # dict: dxy_value, yield_10y, yield_2y, vix, etc.
    "options_data",    # dict: put_call_ratio, gamma_exposure, iv_percentile
    "onchain_data",    # dict: exchange_inflow, mvrv_ratio, etc.
    "news_data",       # list[dict]: recent headlines with impact scores
    "performance_data",  # dict: recent trade performance metrics
    "recent_trades",     # list[dict]: last N trades for learning agent
]

# Set-based look-ups used by _empty()
_LIST_KEYS  = {"closes", "opens", "highs", "lows", "volumes",
               "timestamps", "daily_returns", "news_data", "recent_trades"}
_DICT_KEYS  = {"ohlcv", "indicators", "macro_data",
               "options_data", "onchain_data", "performance_data"}
_FLOAT_KEYS = {"current_price", "volume_24h_usd"}


class DataNormalizer:
    """
    Static helper that converts raw exchange / broker data into the
    unified schema consumed by all downstream components.
    """

    # ------------------------------------------------------------------
    # Public normalizers
    # ------------------------------------------------------------------

    @staticmethod
    def normalize_ccxt(
        raw_ohlcv: list,
        symbol: str,
        timeframe: str,
        volume_24h: float = 0.0,
    ) -> dict:
        """
        Normalize ccxt-style OHLCV data.

        Args:
            raw_ohlcv:  list of [timestamp_ms, open, high, low, close, volume]
            symbol:     e.g. "BTC/USDT"
            timeframe:  e.g. "1h"
            volume_24h: 24-hour volume in USD from ticker endpoint

        Returns:
            Unified market_data dict.
        """
        if not raw_ohlcv:
            return DataNormalizer._empty(symbol, timeframe)

        timestamps = [int(c[0])   for c in raw_ohlcv]
        opens      = [float(c[1]) for c in raw_ohlcv]
        highs      = [float(c[2]) for c in raw_ohlcv]
        lows       = [float(c[3]) for c in raw_ohlcv]
        closes     = [float(c[4]) for c in raw_ohlcv]
        volumes    = [float(c[5]) for c in raw_ohlcv]

        last          = raw_ohlcv[-1]
        current_price = float(last[4])

        closes_arr   = np.array(closes, dtype=np.float64)
        daily_returns = list(np.diff(np.log(closes_arr + 1e-10)))

        return {
            "symbol":        symbol,
            "timeframe":     timeframe,
            "current_price": current_price,
            "closes":        closes,
            "opens":         opens,
            "highs":         highs,
            "lows":          lows,
            "volumes":       volumes,
            "timestamps":    timestamps,
            "ohlcv": {
                "open":   float(last[1]),
                "high":   float(last[2]),
                "low":    float(last[3]),
                "close":  float(last[4]),
                "volume": float(last[5]),
            },
            "indicators":      {},
            "volume_24h_usd":  float(volume_24h),
            "daily_returns":   daily_returns,
            "volume_trend":    DataNormalizer._volume_trend(volumes),
            "macro_data":      {},
            "options_data":    {},
            "onchain_data":    {},
            "news_data":       [],
            "performance_data": {},
            "recent_trades":   [],
        }

    @staticmethod
    def normalize_alpaca(
        bars: list[dict],
        symbol: str,
        timeframe: str,
    ) -> dict:
        """
        Normalize Alpaca bar dicts.

        Each bar dict has the fields: t (ISO timestamp), o, h, l, c, v.

        Args:
            bars:      list of Alpaca bar dicts
            symbol:    e.g. "AAPL"
            timeframe: e.g. "1h"

        Returns:
            Unified market_data dict.
        """
        if not bars:
            return DataNormalizer._empty(symbol, timeframe)

        # Alpaca timestamps are ISO-8601 strings; convert to epoch ms for
        # compatibility with the ccxt-based schema.
        import datetime as _dt

        def _ts_to_ms(t: str) -> int:
            try:
                dt = _dt.datetime.fromisoformat(t.replace("Z", "+00:00"))
                return int(dt.timestamp() * 1000)
            except Exception:
                return 0

        timestamps = [_ts_to_ms(b["t"]) for b in bars]
        opens      = [float(b["o"])     for b in bars]
        highs      = [float(b["h"])     for b in bars]
        lows       = [float(b["l"])     for b in bars]
        closes     = [float(b["c"])     for b in bars]
        volumes    = [float(b["v"])     for b in bars]

        last          = bars[-1]
        current_price = float(last["c"])

        closes_arr    = np.array(closes, dtype=np.float64)
        daily_returns = list(np.diff(np.log(closes_arr + 1e-10)))

        # Approximate 24 h USD volume (last bar's close × last bar's volume)
        volume_24h_usd = current_price * volumes[-1] if volumes else 0.0

        return {
            "symbol":        symbol,
            "timeframe":     timeframe,
            "current_price": current_price,
            "closes":        closes,
            "opens":         opens,
            "highs":         highs,
            "lows":          lows,
            "volumes":       volumes,
            "timestamps":    timestamps,
            "ohlcv": {
                "open":   float(last["o"]),
                "high":   float(last["h"]),
                "low":    float(last["l"]),
                "close":  float(last["c"]),
                "volume": float(last["v"]),
            },
            "indicators":      {},
            "volume_24h_usd":  volume_24h_usd,
            "daily_returns":   daily_returns,
            "volume_trend":    DataNormalizer._volume_trend(volumes),
            "macro_data":      {},
            "options_data":    {},
            "onchain_data":    {},
            "news_data":       [],
            "performance_data": {},
            "recent_trades":   [],
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _volume_trend(volumes: list[float]) -> str:
        """
        Compare mean of last 5 candles versus previous 5.
        Returns "increasing", "decreasing", or "flat".
        """
        if len(volumes) < 10:
            return "flat"
        recent = float(np.mean(volumes[-5:]))
        prev   = float(np.mean(volumes[-10:-5]))
        if prev == 0:
            return "flat"
        ratio = recent / prev
        if ratio > 1.15:
            return "increasing"
        if ratio < 0.85:
            return "decreasing"
        return "flat"

    @staticmethod
    def _empty(symbol: str, timeframe: str) -> dict:
        """Return a zero-filled canonical dict when no data is available."""
        result: dict[str, Any] = {}
        for key in UNIFIED_SCHEMA_KEYS:
            if key in _LIST_KEYS:
                result[key] = []
            elif key in _DICT_KEYS:
                result[key] = {}
            elif key in _FLOAT_KEYS:
                result[key] = 0.0
            elif key == "volume_trend":
                result[key] = "flat"
            elif key == "symbol":
                result[key] = symbol
            elif key == "timeframe":
                result[key] = timeframe
            else:
                result[key] = None
        return result
