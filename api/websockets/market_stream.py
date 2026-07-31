"""
api/websockets/market_stream.py
================================
Real backend WebSocket endpoint for live market ticks.

Mounted at /ws/market-data — the exact path frontend/hooks/useWebSocket.ts's
``useMarketDataWS`` already dials (it existed with nothing listening on the
other end until this phase). Subscribes to the ``market:ticks`` Redis
pub/sub channel (populated by data/feeds/binance_ws_feed.py) and rebroadcasts
each tick to every connected browser client in the exact MarketDataMessage
shape the hook expects: {type: 'price', symbol, price, change, change_pct, timestamp}.

Agent-activity WebSocket (/ws/agent-activity) is intentionally NOT built
here: DebateFeed.tsx/AgentBoard.tsx/AgentGrid.tsx currently render mock
data through that same useWebSocket hook with nothing backing it either,
but wiring that up is an agent-orchestration broadcasting concern (Phase 1's
domain), not market-data plumbing — out of scope for Phase 6.
"""
from __future__ import annotations

import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import redis.asyncio as aioredis

from config.settings import get_settings
from data.tick_cache import TICK_PUBSUB_CHANNEL

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()


def _to_market_data_message(tick: dict) -> dict:
    """Map a TickCache payload onto the frontend's MarketDataMessage shape."""
    from datetime import datetime, timezone

    ts = tick.get("ts")
    timestamp = (
        datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
        if ts is not None
        else datetime.now(timezone.utc).isoformat()
    )
    return {
        "type": "price",
        "symbol": tick.get("symbol"),
        "price": tick.get("price"),
        "change": tick.get("change"),
        "change_pct": tick.get("change_pct"),
        "timestamp": timestamp,
    }


@router.websocket("/market-data")
async def market_data_ws(websocket: WebSocket) -> None:
    """
    Stream live ticks to a connected frontend client.

    Each connection gets its own Redis pub/sub subscription (cheap — Redis
    pub/sub fan-out is O(subscribers), and market-data viewers are a small
    number of dashboard tabs, not thousands of consumers).
    """
    await websocket.accept()

    redis_client = aioredis.from_url(
        settings.redis_url, encoding="utf-8", decode_responses=True,
    )
    pubsub = redis_client.pubsub()

    try:
        await pubsub.subscribe(TICK_PUBSUB_CHANNEL)
        logger.info("market_data_ws client connected, subscribed to %s", TICK_PUBSUB_CHANNEL)

        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            try:
                tick = json.loads(message["data"])
            except (json.JSONDecodeError, TypeError):
                continue
            await websocket.send_json(_to_market_data_message(tick))

    except WebSocketDisconnect:
        logger.info("market_data_ws client disconnected")
    except Exception:
        logger.exception("market_data_ws error")
    finally:
        try:
            await pubsub.unsubscribe(TICK_PUBSUB_CHANNEL)
            await pubsub.aclose()
        except Exception:
            pass
        await redis_client.aclose()
