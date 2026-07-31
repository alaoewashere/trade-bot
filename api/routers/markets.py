"""
api/routers/markets.py
=======================
Live Market Monitor endpoints — real-time price/volume snapshots, order
book depth, futures funding/open-interest, and market-sentiment indicators.

Endpoints
---------
GET /markets/live                    — price/volume/24h high-low per symbol
GET /markets/{symbol}/candles        — historical OHLCV candles (Phase 5: chart foundation)
GET /markets/{symbol}/orderbook      — top-N bids/asks via ccxt order book
GET /markets/{symbol}/funding        — futures funding rate + open interest
                                        (null/"not applicable" for spot-only symbols)
GET /markets/fear-greed              — Fear & Greed Index (alternative.me, free/no-key)
GET /markets/whale-activity          — whale transaction alerts (provider-gated)
GET /markets/exchange-flows          — exchange in/out flow (provider-gated)

Notes
-----
Whale-activity and exchange-flows require a paid data provider (Whale Alert,
Glassnode, CryptoQuant, ...) that this deployment does not have credentials
for. Rather than fabricate numbers, both endpoints honestly report
``provider_configured: false`` and an empty ``data`` list until
WHALE_ALERT_API_KEY / EXCHANGE_FLOW_API_KEY are set (see config/settings.py).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import ccxt.async_support as ccxt
import httpx
from fastapi import APIRouter, HTTPException, Path, Query, status
from pydantic import BaseModel

from config.settings import get_settings
from data.cache import RedisCacheManager

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()

_DEFAULT_LIVE_SYMBOLS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT",
    "XRP/USDT", "ADA/USDT", "DOGE/USDT", "AVAX/USDT",
]

# Module-level cache manager reused across requests (own connection, does
# not depend on api.dependencies' request-scoped Redis client so this
# router works even if that pool isn't wired into every deployment path).
_cache = RedisCacheManager(redis_url=settings.redis_url)
_cache_connected = False


async def _get_cache() -> RedisCacheManager:
    global _cache_connected
    if not _cache_connected:
        await _cache.connect()
        _cache_connected = True
    return _cache


async def _short_ttl_get(cache: RedisCacheManager, key: str) -> dict | None:
    """Read-through helper for caches needing a shorter TTL than
    RedisCacheManager's timeframe map provides (e.g. live ticker data)."""
    import json
    if cache._client is None:  # noqa: SLF001 — same-module cooperating helper
        return None
    raw = await cache._client.get(key)
    return json.loads(raw) if raw else None


async def _short_ttl_set(cache: RedisCacheManager, key: str, data: dict, ttl_seconds: int) -> None:
    import json
    if cache._client is None:  # noqa: SLF001
        return
    await cache._client.setex(key, ttl_seconds, json.dumps(data, default=str))


def _make_exchange(futures: bool = False) -> "ccxt.binance":
    return ccxt.binance({
        "apiKey": settings.binance_api_key or None,
        "secret": settings.binance_secret_key or None,
        "enableRateLimit": True,
        "options": {"defaultType": "future" if futures else "spot"},
    })


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class LiveTicker(BaseModel):
    symbol: str
    price: float
    change_24h_pct: float
    high_24h: float
    low_24h: float
    volume_24h_quote: float
    updated_at: str


class OrderBookLevel(BaseModel):
    price: float
    quantity: float


class OrderBookResponse(BaseModel):
    symbol: str
    bids: list[OrderBookLevel]
    asks: list[OrderBookLevel]
    best_bid: float
    best_ask: float
    spread_bps: float
    fetched_at: str


class FundingResponse(BaseModel):
    symbol: str
    applicable: bool
    funding_rate_pct: float | None
    next_funding_time: str | None
    open_interest: float | None
    note: str | None = None


class FearGreedResponse(BaseModel):
    value: int
    classification: str
    updated_at: str
    source: str = "alternative.me"


class ProviderGatedResponse(BaseModel):
    provider_configured: bool
    data: list[dict[str, Any]]
    message: str


class Candle(BaseModel):
    time: int  # unix seconds — lightweight-charts' native time unit
    open: float
    high: float
    low: float
    close: float
    volume: float


class CandlesResponse(BaseModel):
    symbol: str
    timeframe: str
    candles: list[Candle]


# ---------------------------------------------------------------------------
# GET /markets/live
# ---------------------------------------------------------------------------


@router.get("/live", response_model=list[LiveTicker], summary="Live price/volume snapshot per symbol")
async def get_live_markets(
    symbols: str | None = Query(
        default=None,
        description="Comma-separated ccxt symbols, e.g. BTC/USDT,ETH/USDT. Defaults to a built-in watchlist.",
    ),
) -> list[LiveTicker]:
    symbol_list = (
        [s.strip() for s in symbols.split(",") if s.strip()]
        if symbols
        else _DEFAULT_LIVE_SYMBOLS
    )

    cache = await _get_cache()
    exchange = _make_exchange()
    results: list[LiveTicker] = []

    try:
        for symbol in symbol_list:
            cache_key = f"market:live:{symbol.replace('/', '_').upper()}"
            cached = await _short_ttl_get(cache, cache_key)
            if cached is not None:
                results.append(LiveTicker(**cached))
                continue

            try:
                ticker = await exchange.fetch_ticker(symbol)
            except Exception as exc:
                logger.warning("fetch_ticker failed for %s: %s", symbol, exc)
                continue

            payload = {
                "symbol": symbol,
                "price": float(ticker.get("last") or ticker.get("close") or 0.0),
                "change_24h_pct": float(ticker.get("percentage") or 0.0),
                "high_24h": float(ticker.get("high") or 0.0),
                "low_24h": float(ticker.get("low") or 0.0),
                "volume_24h_quote": float(ticker.get("quoteVolume") or 0.0),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            await _short_ttl_set(cache, cache_key, payload, ttl_seconds=8)
            results.append(LiveTicker(**payload))
    finally:
        await exchange.close()

    return results


# ---------------------------------------------------------------------------
# GET /markets/{symbol}/candles — Phase 5 chart foundation
# ---------------------------------------------------------------------------

# Same timeframe set BinanceFeed.CCXT_TIMEFRAMES / RedisCacheManager._TTL_MAP
# already support — kept here rather than importing BinanceFeed so this
# endpoint uses the same lightweight direct-ccxt + module cache pattern as
# the rest of this router (get_live_markets, get_orderbook, get_funding).
_CANDLE_TIMEFRAMES = {"1m", "5m", "15m", "30m", "1h", "4h", "1d"}

# Mirrors data/cache.py's RedisCacheManager._TTL_MAP — duplicated as a small
# local constant rather than importing a private module attribute.
_TTL_MAP_FALLBACK = {
    "1m": 30, "5m": 150, "15m": 450, "30m": 900, "1h": 300, "4h": 1200, "1d": 3600,
}


@router.get(
    "/{symbol}/candles",
    response_model=CandlesResponse,
    summary="Historical OHLCV candles for the chart",
    description=(
        "Backs InstitutionalChart's candlestick series (Phase 5). Cached in Redis "
        "per symbol/timeframe/limit at the same TTL RedisCacheManager already uses "
        "for that timeframe, so the chart doesn't hammer Binance on every re-render."
    ),
)
async def get_candles(
    symbol: str = Path(..., description="ccxt symbol, URL-encode the slash e.g. BTC%2FUSDT"),
    timeframe: str = Query(default="1h", description="One of: 1m 5m 15m 30m 1h 4h 1d"),
    limit: int = Query(default=300, ge=10, le=1000),
) -> CandlesResponse:
    if timeframe not in _CANDLE_TIMEFRAMES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported timeframe '{timeframe}'. Supported: {sorted(_CANDLE_TIMEFRAMES)}",
        )

    ccxt_symbol = symbol.replace("-", "/")
    cache = await _get_cache()
    cache_key = f"market:candles:{ccxt_symbol.replace('/', '_').upper()}:{timeframe}:{limit}"
    ttl = _TTL_MAP_FALLBACK.get(timeframe, 300)

    cached = await _short_ttl_get(cache, cache_key)
    if cached is not None:
        return CandlesResponse(**cached)

    exchange = _make_exchange()
    try:
        try:
            raw = await exchange.fetch_ohlcv(ccxt_symbol, timeframe, limit=limit)
        except Exception as exc:
            logger.error("fetch_ohlcv failed for %s %s: %s", ccxt_symbol, timeframe, exc)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Could not fetch candles for '{ccxt_symbol}' {timeframe}: {exc}",
            ) from exc
    finally:
        await exchange.close()

    candles = [
        Candle(
            time=int(row[0] // 1000),
            open=float(row[1]),
            high=float(row[2]),
            low=float(row[3]),
            close=float(row[4]),
            volume=float(row[5] or 0.0),
        )
        for row in (raw or [])
    ]

    payload = {"symbol": ccxt_symbol, "timeframe": timeframe, "candles": [c.model_dump() for c in candles]}
    await _short_ttl_set(cache, cache_key, payload, ttl_seconds=ttl)
    return CandlesResponse(**payload)


# ---------------------------------------------------------------------------
# GET /markets/{symbol}/orderbook
# ---------------------------------------------------------------------------


@router.get(
    "/{symbol}/orderbook",
    response_model=OrderBookResponse,
    summary="Top-N order book levels for a symbol",
)
async def get_orderbook(
    symbol: str = Path(..., description="ccxt symbol, URL-encode the slash e.g. BTC%2FUSDT"),
    depth: int = Query(default=20, ge=1, le=100),
) -> OrderBookResponse:
    exchange = _make_exchange()
    try:
        ccxt_symbol = symbol.replace("-", "/")
        ob = await exchange.fetch_order_book(ccxt_symbol, limit=depth)
    except Exception as exc:
        logger.error("fetch_order_book failed for %s: %s", symbol, exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Could not fetch order book for '{symbol}': {exc}",
        ) from exc
    finally:
        await exchange.close()

    bids = [OrderBookLevel(price=p, quantity=q) for p, q in (ob.get("bids") or [])]
    asks = [OrderBookLevel(price=p, quantity=q) for p, q in (ob.get("asks") or [])]
    best_bid = bids[0].price if bids else 0.0
    best_ask = asks[0].price if asks else 0.0
    spread_bps = ((best_ask - best_bid) / best_bid * 10_000) if best_bid > 0 else 0.0

    return OrderBookResponse(
        symbol=ccxt_symbol,
        bids=bids,
        asks=asks,
        best_bid=best_bid,
        best_ask=best_ask,
        spread_bps=round(spread_bps, 2),
        fetched_at=datetime.now(timezone.utc).isoformat(),
    )


# ---------------------------------------------------------------------------
# GET /markets/{symbol}/funding
# ---------------------------------------------------------------------------


@router.get(
    "/{symbol}/funding",
    response_model=FundingResponse,
    summary="Futures funding rate + open interest (futures-only)",
)
async def get_funding(
    symbol: str = Path(..., description="ccxt symbol, e.g. BTC/USDT (spot notation; futures market is resolved automatically)"),
) -> FundingResponse:
    ccxt_symbol = symbol.replace("-", "/")
    exchange = _make_exchange(futures=True)

    try:
        try:
            await exchange.load_markets()
        except Exception as exc:
            logger.warning("load_markets failed: %s", exc)

        if ccxt_symbol not in getattr(exchange, "markets", {}):
            return FundingResponse(
                symbol=ccxt_symbol,
                applicable=False,
                funding_rate_pct=None,
                next_funding_time=None,
                open_interest=None,
                note="No perpetual futures market found for this symbol on Binance — funding is not applicable to spot-only instruments.",
            )

        funding_rate_pct: float | None = None
        next_funding_time: str | None = None
        open_interest: float | None = None

        try:
            fr = await exchange.fetch_funding_rate(ccxt_symbol)
            rate = fr.get("fundingRate")
            funding_rate_pct = round(float(rate) * 100, 5) if rate is not None else None
            ts = fr.get("fundingTimestamp") or fr.get("nextFundingTimestamp")
            if ts:
                next_funding_time = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).isoformat()
        except Exception as exc:
            logger.warning("fetch_funding_rate failed for %s: %s", ccxt_symbol, exc)

        try:
            oi = await exchange.fetch_open_interest(ccxt_symbol)
            open_interest = float(oi.get("openInterestAmount") or oi.get("openInterestValue") or 0.0) or None
        except Exception as exc:
            logger.warning("fetch_open_interest failed for %s: %s", ccxt_symbol, exc)

        return FundingResponse(
            symbol=ccxt_symbol,
            applicable=True,
            funding_rate_pct=funding_rate_pct,
            next_funding_time=next_funding_time,
            open_interest=open_interest,
        )
    finally:
        await exchange.close()


# ---------------------------------------------------------------------------
# GET /markets/fear-greed
# ---------------------------------------------------------------------------


@router.get("/fear-greed", response_model=FearGreedResponse, summary="Crypto Fear & Greed Index")
async def get_fear_greed() -> FearGreedResponse:
    cache = await _get_cache()
    cache_symbol, cache_tf = "FEAR_GREED", "index"
    cached = await cache.get(cache_symbol, cache_tf)
    if cached is not None:
        return FearGreedResponse(**cached)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get("https://api.alternative.me/fng/?limit=1")
            resp.raise_for_status()
            body = resp.json()
        entry = (body.get("data") or [{}])[0]
        value = int(entry.get("value", 50))
        classification = entry.get("value_classification", "Neutral")
        payload = {
            "value": value,
            "classification": classification,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "source": "alternative.me",
        }
    except Exception as exc:
        logger.error("Fear & Greed fetch failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Fear & Greed Index provider (alternative.me) is unreachable.",
        ) from exc

    # Cache manually at the 1h TTL this endpoint warrants — RedisCacheManager's
    # timeframe TTL map tops out at 1h for "1d", which matches our needs here.
    await cache.set(cache_symbol, "1d", payload)
    return FearGreedResponse(**payload)


# ---------------------------------------------------------------------------
# GET /markets/whale-activity
# ---------------------------------------------------------------------------


@router.get(
    "/whale-activity",
    response_model=ProviderGatedResponse,
    summary="Whale transaction alerts (requires a configured provider)",
)
async def get_whale_activity() -> ProviderGatedResponse:
    if not settings.whale_alert_api_key:
        return ProviderGatedResponse(
            provider_configured=False,
            data=[],
            message=(
                "No whale-transaction provider configured. Set WHALE_ALERT_API_KEY "
                "to connect Whale Alert (or an equivalent provider) — this endpoint "
                "will not fabricate transaction data."
            ),
        )

    # Provider key is present but the actual Whale Alert client integration
    # is out of scope for this phase (no network access to verify against
    # a live provider) — report the shape honestly rather than guessing at
    # response fields we can't validate.
    return ProviderGatedResponse(
        provider_configured=True,
        data=[],
        message="Whale Alert API key detected but the live client call is not yet wired up.",
    )


# ---------------------------------------------------------------------------
# GET /markets/exchange-flows
# ---------------------------------------------------------------------------


@router.get(
    "/exchange-flows",
    response_model=ProviderGatedResponse,
    summary="Exchange inflow/outflow (requires a configured provider)",
)
async def get_exchange_flows() -> ProviderGatedResponse:
    if not settings.exchange_flow_api_key:
        return ProviderGatedResponse(
            provider_configured=False,
            data=[],
            message=(
                "No exchange-flow provider configured. Set EXCHANGE_FLOW_API_KEY "
                "to connect Glassnode/CryptoQuant (or an equivalent provider) — "
                "this endpoint will not fabricate flow data."
            ),
        )

    return ProviderGatedResponse(
        provider_configured=True,
        data=[],
        message="Exchange-flow API key detected but the live client call is not yet wired up.",
    )
