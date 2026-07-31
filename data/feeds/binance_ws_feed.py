"""
data/feeds/binance_ws_feed.py
==============================
Binance public WebSocket ingestion client — real-time tick stream to
replace REST polling for "current price" freshness.

Uses Binance's combined ``@ticker`` stream (24hr rolling ticker, pushed
~once/second per symbol) rather than the raw ``@trade`` stream: it is
still tick-by-tick real-time data (not REST polling), and it already
carries ``price change`` / ``percent change`` fields that
frontend/hooks/useWebSocket.ts's MarketDataMessage shape expects
(``change`` / ``change_pct``) — using ``@trade`` would mean recomputing
those deltas ourselves from a rolling window for no real benefit.

Public market-data streams do not require API keys (confirmed against
Binance's WebSocket Market Streams docs: only User Data Streams, which
carry account/order events, require authentication). This client
therefore takes no credentials — it is unauthenticated by design, unlike
BinanceFeed (REST) which optionally takes keys for future authenticated
use.

This module's wire-protocol handling (message shape, stream naming,
reconnect-on-close) is written against Binance's documented WS API and is
logic-reviewed, not exercised against the live socket in this sandbox
(no outbound network access here).
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Iterable, Optional

import websockets
from websockets.exceptions import ConnectionClosed

from data.tick_cache import TickCache

logger = logging.getLogger(__name__)

_STREAM_BASE = "wss://stream.binance.com:9443/stream"

_CONNECTION_STATUS_KEY = "market:ws:connection"
_MAX_BACKOFF_SECONDS = 30.0


def _to_stream_symbol(symbol: str) -> str:
    """"BTC/USDT" -> "btcusdt" (Binance's lower-case, slash-free stream naming)."""
    return symbol.replace("/", "").lower()


class BinanceWSFeed:
    """
    Persistent public WebSocket client streaming 24hr ticker updates for a
    fixed symbol list into Redis (via TickCache) and the ``market:ticks``
    pub/sub channel.

    Run as a long-lived background task (see api/main.py's lifespan) —
    ``start()`` never returns under normal operation; it reconnects with
    exponential backoff on any connection error.

    Usage::

        feed = BinanceWSFeed(symbols=["BTC/USDT", "ETH/USDT"], redis_client=redis)
        task = asyncio.create_task(feed.start())
        ...
        await feed.stop()
    """

    def __init__(
        self,
        symbols: Iterable[str],
        redis_client,
        tick_cache: Optional[TickCache] = None,
    ) -> None:
        self.symbols = list(symbols)
        self._redis = redis_client
        self._tick_cache = tick_cache or TickCache(redis_client=redis_client)
        self._stop = asyncio.Event()

    @property
    def stream_url(self) -> str:
        streams = "/".join(f"{_to_stream_symbol(s)}@ticker" for s in self.symbols)
        return f"{_STREAM_BASE}?streams={streams}"

    # ------------------------------------------------------------------
    # Connection-status bookkeeping (feeds GET /system/connection-status)
    # ------------------------------------------------------------------

    async def _set_status(
        self,
        status: str,
        latency_ms: Optional[float] = None,
        reason: Optional[str] = None,
    ) -> None:
        payload = {
            "status": status,  # "connected" | "disconnected" | "reconnecting"
            "latency_ms": latency_ms,
            "reason": reason,
            "updated_at": time.time(),
        }
        try:
            await self._redis.set(_CONNECTION_STATUS_KEY, json.dumps(payload))
        except Exception:
            logger.exception("Failed to persist WS connection status")

    async def stop(self) -> None:
        self._stop.set()

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    async def start(self) -> None:
        await self._tick_cache.connect()
        backoff = 1.0

        while not self._stop.is_set():
            await self._set_status("reconnecting")
            try:
                async with websockets.connect(self.stream_url, ping_interval=20, ping_timeout=20) as ws:
                    logger.info("BinanceWSFeed connected: %d symbols", len(self.symbols))
                    await self._set_status("connected", latency_ms=0.0)
                    backoff = 1.0

                    async for raw_message in ws:
                        if self._stop.is_set():
                            break
                        recv_time = time.time()
                        await self._handle_message(raw_message, recv_time)

            except asyncio.CancelledError:
                logger.info("BinanceWSFeed cancelled — stopping.")
                await self._set_status("disconnected", reason="task_cancelled")
                return
            except (ConnectionClosed, OSError) as exc:
                logger.warning("BinanceWSFeed connection lost: %s — retrying in %.1fs", exc, backoff)
                await self._set_status("disconnected", reason=str(exc))
            except Exception as exc:
                logger.error("BinanceWSFeed unexpected error: %s", exc, exc_info=True)
                await self._set_status("disconnected", reason=str(exc))

            if self._stop.is_set():
                break
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, _MAX_BACKOFF_SECONDS)

        await self._set_status("disconnected", reason="stopped")

    async def _handle_message(self, raw_message: str | bytes, recv_time: float) -> None:
        try:
            envelope = json.loads(raw_message)
            data = envelope.get("data", envelope)  # combined-stream wraps in {"stream":..,"data":..}

            symbol_raw: str = data.get("s", "")
            price = float(data.get("c", 0.0))       # last price
            change = float(data.get("p", 0.0))      # absolute 24h price change
            change_pct = float(data.get("P", 0.0))  # 24h percent change
            volume = float(data.get("v", 0.0))      # base-asset 24h volume

            event_time_ms = data.get("E")
            latency_ms = None
            if event_time_ms:
                latency_ms = max(0.0, recv_time * 1000 - float(event_time_ms))

            symbol = _match_canonical_symbol(symbol_raw, self.symbols)
            if symbol is None:
                return

            await self._tick_cache.set_tick(
                symbol, price=price, volume=volume, change=change, change_pct=change_pct,
            )
            if latency_ms is not None:
                await self._set_status("connected", latency_ms=latency_ms)

        except (ValueError, KeyError, TypeError):
            logger.warning("Malformed Binance WS message, skipping: %.200s", raw_message)
        except Exception:
            logger.exception("Error handling Binance WS tick")


def _match_canonical_symbol(binance_symbol: str, canonical_symbols: list[str]) -> Optional[str]:
    """Map Binance's "BTCUSDT" back to our canonical "BTC/USDT" form."""
    target = binance_symbol.upper()
    for s in canonical_symbols:
        if s.replace("/", "").upper() == target:
            return s
    return None
