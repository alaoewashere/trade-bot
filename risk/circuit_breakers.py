"""
risk/circuit_breakers.py
========================
Kill-switch, circuit-breaker, and safety-gate primitives backed by Redis.

All state is persisted in Redis so that multiple processes / workers share
the same view.  Every state-change event is published to the Redis pub/sub
channel ``risk:circuit_breaker:events`` as a JSON payload.

Custom exceptions
-----------------
KillSwitchActiveError   — raised when the kill switch is armed.
CircuitBreakerTrippedError — raised when the circuit breaker is open.
StaleMarketDataError    — raised when live market data for a symbol is
                          disconnected or older than the freshness window.

Classes
-------
KillSwitch              — manual emergency stop.
CircuitBreaker          — automatic loss-based stop.
SafetyGate              — composite of both; single entry-point for nodes.
CircuitBreakerSubscriber — async listener for published events.
MarketDataStalenessGate — Phase 6 safety primitive: blocks trading on a
                          symbol when its live WS tick feed is dead or
                          stale. Nothing calls this yet in anger — Phase 7
                          (execution engine) wires it into the order path.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

import redis.asyncio as aioredis

from risk.limits import (
    CIRCUIT_BREAKER_COOLDOWN_MINUTES,
    MAX_CONSECUTIVE_LOSSES,
    MAX_DAILY_LOSS_USD,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Redis key constants
# ---------------------------------------------------------------------------

_KILL_SWITCH_KEY = "risk:kill_switch"
_CIRCUIT_BREAKER_KEY = "risk:circuit_breaker"
_DAILY_PNL_KEY = "risk:daily_pnl"
_CONSECUTIVE_LOSSES_KEY = "risk:consecutive_losses"
_PUBSUB_CHANNEL = "risk:circuit_breaker:events"

# Market-data staleness rule (Phase 6): a symbol's live feed is considered
# stale — and trading on it must be blocked — once its last tick is older
# than this many seconds, OR the WS connection itself is not "connected".
# This is a per-symbol check: one dead symbol does not halt unrelated
# symbols whose ticks are still fresh, but a fully disconnected socket
# means every watched symbol is stale simultaneously (there is only one
# shared connection, so "disconnected" fails every symbol's check).
MARKET_DATA_STALENESS_SECONDS = 2.0
_WS_CONNECTION_STATUS_KEY = "market:ws:connection"


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------


class KillSwitchActiveError(RuntimeError):
    """Raised when an operation is blocked because the kill switch is armed."""

    def __init__(self, reason: str = "Kill switch is active.") -> None:
        super().__init__(reason)
        self.reason = reason


class CircuitBreakerTrippedError(RuntimeError):
    """Raised when an operation is blocked because the circuit breaker is open."""

    def __init__(self, reason: str = "Circuit breaker is tripped.") -> None:
        super().__init__(reason)
        self.reason = reason


class StaleMarketDataError(RuntimeError):
    """
    Raised when an operation is blocked because live market data for a
    symbol is disconnected or older than MARKET_DATA_STALENESS_SECONDS.

    Mirrors KillSwitchActiveError's shape: a plain RuntimeError subclass
    carrying a human-readable ``reason`` plus the ``symbol`` and measured
    ``age_seconds`` (None when there is no tick at all / feed never connected).
    """

    def __init__(self, symbol: str, reason: str, age_seconds: float | None = None) -> None:
        super().__init__(reason)
        self.symbol = symbol
        self.reason = reason
        self.age_seconds = age_seconds


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_event(event_type: str, **payload: Any) -> str:
    return json.dumps({"event_type": event_type, "ts": _utcnow_iso(), **payload})


# ---------------------------------------------------------------------------
# KillSwitch
# ---------------------------------------------------------------------------


class KillSwitch:
    """
    Manual emergency stop lever.

    When activated all SafetyGate checks raise KillSwitchActiveError.
    The state is stored in Redis under the key ``risk:kill_switch`` as a
    JSON object so it survives process restarts.

    Usage
    -----
        ks = KillSwitch(redis_client)
        await ks.activate("flash crash detected", "ops-team")
        await ks.check_or_raise()   # raises KillSwitchActiveError
        await ks.deactivate("ops-team")
    """

    def __init__(self, redis: aioredis.Redis) -> None:
        self._redis = redis

    async def activate(self, reason: str, operator: str) -> None:
        """Arm the kill switch."""
        payload = {
            "active": True,
            "reason": reason,
            "operator": operator,
            "activated_at": _utcnow_iso(),
        }
        async with self._redis.pipeline(transaction=True) as pipe:
            pipe.set(_KILL_SWITCH_KEY, json.dumps(payload))
            pipe.publish(
                _PUBSUB_CHANNEL,
                _build_event("kill_switch_activated", reason=reason, operator=operator),
            )
            await pipe.execute()

        logger.critical("KILL SWITCH ACTIVATED — reason=%s operator=%s", reason, operator)

    async def deactivate(self, operator: str) -> None:
        """Disarm the kill switch."""
        payload = {
            "active": False,
            "reason": None,
            "operator": operator,
            "deactivated_at": _utcnow_iso(),
        }
        async with self._redis.pipeline(transaction=True) as pipe:
            pipe.set(_KILL_SWITCH_KEY, json.dumps(payload))
            pipe.publish(
                _PUBSUB_CHANNEL,
                _build_event("kill_switch_deactivated", operator=operator),
            )
            await pipe.execute()

        logger.warning("Kill switch deactivated by %s", operator)

    async def is_active(self) -> bool:
        """Return True if the kill switch is currently armed."""
        raw = await self._redis.get(_KILL_SWITCH_KEY)
        if raw is None:
            return False
        try:
            data = json.loads(raw)
            return bool(data.get("active", False))
        except (json.JSONDecodeError, TypeError):
            return False

    async def get_status(self) -> dict[str, Any]:
        """Return the full kill-switch state dict, or a safe default."""
        raw = await self._redis.get(_KILL_SWITCH_KEY)
        if raw is None:
            return {"active": False, "reason": None, "operator": None}
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {"active": False, "reason": None, "operator": None}

    async def check_or_raise(self) -> None:
        """
        Raise KillSwitchActiveError if the kill switch is armed.
        Call this at the start of any order-submission code path.
        """
        if await self.is_active():
            status = await self.get_status()
            raise KillSwitchActiveError(
                f"Kill switch is active. Reason: {status.get('reason', 'unknown')}. "
                f"Armed by: {status.get('operator', 'unknown')}."
            )


# ---------------------------------------------------------------------------
# CircuitBreaker
# ---------------------------------------------------------------------------


class CircuitBreaker:
    """
    Automatic drawdown-based circuit breaker.

    Tracks daily realised PnL and the count of consecutive losing trades.
    The breaker trips automatically when either:
      * The daily loss exceeds MAX_DAILY_LOSS_USD, or
      * The number of consecutive losses reaches MAX_CONSECUTIVE_LOSSES.

    After tripping the breaker enters a cooldown period
    (CIRCUIT_BREAKER_COOLDOWN_MINUTES).  It can only be reset manually by
    an authorised operator after the cooldown expires.

    Redis keys
    ----------
    risk:circuit_breaker      — breaker state JSON
    risk:daily_pnl            — running daily PnL (float string)
    risk:consecutive_losses   — integer counter
    """

    def __init__(self, redis: aioredis.Redis) -> None:
        self._redis = redis

    # ------------------------------------------------------------------
    # State queries
    # ------------------------------------------------------------------

    async def check(self) -> bool:
        """Return True if the breaker is currently tripped (open)."""
        raw = await self._redis.get(_CIRCUIT_BREAKER_KEY)
        if raw is None:
            return False
        try:
            data = json.loads(raw)
            return bool(data.get("tripped", False))
        except (json.JSONDecodeError, TypeError):
            return False

    async def get_state(self) -> dict[str, Any]:
        """Return the full circuit-breaker state dict."""
        raw = await self._redis.get(_CIRCUIT_BREAKER_KEY)
        if raw is None:
            return {"tripped": False, "reason": None, "tripped_at": None, "operator": None}
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {"tripped": False, "reason": None, "tripped_at": None, "operator": None}

    # ------------------------------------------------------------------
    # State mutations
    # ------------------------------------------------------------------

    async def trip(self, reason: str) -> None:
        """
        Open the circuit breaker.

        Published to the pub/sub channel so that all subscribers
        (e.g. position monitors) can react immediately.
        """
        payload = {
            "tripped": True,
            "reason": reason,
            "tripped_at": _utcnow_iso(),
            "cooldown_minutes": CIRCUIT_BREAKER_COOLDOWN_MINUTES,
        }
        async with self._redis.pipeline(transaction=True) as pipe:
            pipe.set(_CIRCUIT_BREAKER_KEY, json.dumps(payload))
            pipe.publish(
                _PUBSUB_CHANNEL,
                _build_event("circuit_breaker_tripped", reason=reason),
            )
            await pipe.execute()

        logger.critical("CIRCUIT BREAKER TRIPPED — %s", reason)

    async def reset(self, operator: str) -> None:
        """
        Close the circuit breaker (manual operator action only).

        Also resets the consecutive-loss counter and daily PnL counter.
        """
        payload = {
            "tripped": False,
            "reason": None,
            "tripped_at": None,
            "reset_at": _utcnow_iso(),
            "operator": operator,
        }
        async with self._redis.pipeline(transaction=True) as pipe:
            pipe.set(_CIRCUIT_BREAKER_KEY, json.dumps(payload))
            pipe.set(_CONSECUTIVE_LOSSES_KEY, "0")
            pipe.set(_DAILY_PNL_KEY, "0.0")
            pipe.publish(
                _PUBSUB_CHANNEL,
                _build_event("circuit_breaker_reset", operator=operator),
            )
            await pipe.execute()

        logger.warning("Circuit breaker reset by %s", operator)

    async def check_or_raise(self) -> None:
        """Raise CircuitBreakerTrippedError if the breaker is tripped."""
        if await self.check():
            state = await self.get_state()
            raise CircuitBreakerTrippedError(
                f"Circuit breaker is tripped. Reason: {state.get('reason', 'unknown')}. "
                f"Tripped at: {state.get('tripped_at', 'unknown')}."
            )

    # ------------------------------------------------------------------
    # PnL tracking
    # ------------------------------------------------------------------

    async def record_pnl(self, pnl_usd: float) -> None:
        """
        Record a single trade's realised PnL.

        Updates the running daily PnL total and the consecutive-loss
        counter.  Trips the breaker automatically if thresholds are
        breached.

        Parameters
        ----------
        pnl_usd:
            Positive for profit, negative for loss.
        """
        # Use a Lua script for atomic read-modify-write
        lua_script = """
        local pnl_key = KEYS[1]
        local losses_key = KEYS[2]
        local pnl_delta = tonumber(ARGV[1])

        -- Update daily PnL
        local current_pnl = tonumber(redis.call('GET', pnl_key) or '0')
        local new_pnl = current_pnl + pnl_delta
        redis.call('SET', pnl_key, tostring(new_pnl))

        -- Update consecutive losses
        local consec = tonumber(redis.call('GET', losses_key) or '0')
        if pnl_delta < 0 then
            consec = consec + 1
        else
            consec = 0
        end
        redis.call('SET', losses_key, tostring(consec))

        return {tostring(new_pnl), tostring(consec)}
        """
        result = await self._redis.eval(
            lua_script,
            2,  # number of KEYS
            _DAILY_PNL_KEY,
            _CONSECUTIVE_LOSSES_KEY,
            str(pnl_usd),
        )

        new_pnl = float(result[0])
        consecutive_losses = int(result[1])

        logger.info(
            "pnl_recorded",
            pnl_usd=pnl_usd,
            daily_pnl=new_pnl,
            consecutive_losses=consecutive_losses,
        )

        await self._redis.publish(
            _PUBSUB_CHANNEL,
            _build_event(
                "pnl_recorded",
                pnl_usd=pnl_usd,
                daily_pnl=new_pnl,
                consecutive_losses=consecutive_losses,
            ),
        )

        # Auto-trip checks
        if new_pnl <= -abs(MAX_DAILY_LOSS_USD):
            await self.trip(
                f"Daily loss limit reached: ${new_pnl:,.2f} (limit: -${MAX_DAILY_LOSS_USD:,.2f})"
            )
        elif consecutive_losses >= MAX_CONSECUTIVE_LOSSES:
            await self.trip(
                f"Consecutive losses limit reached: {consecutive_losses} trades "
                f"(limit: {MAX_CONSECUTIVE_LOSSES})"
            )

    async def get_daily_pnl(self) -> float:
        """Return the current running daily PnL in USD."""
        raw = await self._redis.get(_DAILY_PNL_KEY)
        if raw is None:
            return 0.0
        try:
            return float(raw)
        except (ValueError, TypeError):
            return 0.0

    async def reset_daily_pnl(self) -> None:
        """Reset daily PnL and consecutive-loss counters (call at midnight)."""
        async with self._redis.pipeline(transaction=True) as pipe:
            pipe.set(_DAILY_PNL_KEY, "0.0")
            pipe.set(_CONSECUTIVE_LOSSES_KEY, "0")
            pipe.publish(
                _PUBSUB_CHANNEL,
                _build_event("daily_pnl_reset"),
            )
            await pipe.execute()

        logger.info("Daily PnL counters reset.")

    async def get_consecutive_losses(self) -> int:
        """Return the current consecutive-loss streak."""
        raw = await self._redis.get(_CONSECUTIVE_LOSSES_KEY)
        if raw is None:
            return 0
        try:
            return int(raw)
        except (ValueError, TypeError):
            return 0


# ---------------------------------------------------------------------------
# SafetyGate
# ---------------------------------------------------------------------------


class SafetyGate:
    """
    Single entry-point that combines KillSwitch and CircuitBreaker checks.

    Call ``check_all_or_raise()`` at the top of every order-placement
    code path.  Either exception propagates upward and the order is
    never sent to the broker.
    """

    def __init__(self, redis: aioredis.Redis) -> None:
        self._redis = redis
        self.kill_switch = KillSwitch(redis)
        self.circuit_breaker = CircuitBreaker(redis)

    async def check_all_or_raise(self) -> None:
        """
        Raise the appropriate exception if either safety mechanism is active.

        KillSwitchActiveError takes precedence over
        CircuitBreakerTrippedError.
        """
        await self.kill_switch.check_or_raise()
        await self.circuit_breaker.check_or_raise()

    async def get_status(self) -> dict[str, Any]:
        """
        Return a composite status dict for dashboarding / health endpoints.

        Returns
        -------
        dict with keys:
          kill_switch     — KillSwitch.get_status() result
          circuit_breaker — CircuitBreaker.get_state() result
          daily_pnl       — current daily PnL
          consecutive_losses — current consecutive loss count
          all_clear       — True only when both mechanisms are inactive
        """
        ks_status = await self.kill_switch.get_status()
        cb_state = await self.circuit_breaker.get_state()
        daily_pnl = await self.circuit_breaker.get_daily_pnl()
        consec = await self.circuit_breaker.get_consecutive_losses()

        all_clear = not ks_status.get("active", False) and not cb_state.get("tripped", False)

        return {
            "kill_switch": ks_status,
            "circuit_breaker": cb_state,
            "daily_pnl": daily_pnl,
            "consecutive_losses": consec,
            "all_clear": all_clear,
            "checked_at": _utcnow_iso(),
        }


# ---------------------------------------------------------------------------
# MarketDataStalenessGate
# ---------------------------------------------------------------------------


class MarketDataStalenessGate:
    """
    Phase 6 safety primitive: the single shared function any future
    execution code must call before permitting a trade on a symbol whose
    price depends on the live WS tick stream.

    Contract
    --------
    ``trading_enabled(symbol) -> bool`` and ``assert_fresh_or_raise(symbol) -> None``
    both apply the *same* rule, evaluated per-symbol:

        stale  =  (WS connection status != "connected")
                  OR (no tick has ever been received for `symbol`)
                  OR (now - last_tick_timestamp) > MARKET_DATA_STALENESS_SECONDS (2.0s)

    When the shared WS connection itself is down, every watched symbol
    reads as stale simultaneously (there's one socket, not one per
    symbol) — this is intentional: a global outage should block all
    symbols, while one symbol's feed going quiet (e.g. a delisted pair)
    should only block that symbol.

    This class only reads state — it does not open connections or run
    the feed itself (see data/feeds/binance_ws_feed.py for that). It is
    Redis-backed like KillSwitch/CircuitBreaker so any process can call
    it without needing an in-process reference to the WS client.

    Usage (future — Phase 7 execution engine)::

        gate = MarketDataStalenessGate(redis_client)
        await gate.assert_fresh_or_raise("BTC/USDT")  # raises StaleMarketDataError if stale
        # ... proceed to submit the order ...
    """

    def __init__(self, redis: aioredis.Redis, tick_cache: Any = None) -> None:
        self._redis = redis
        if tick_cache is None:
            from data.tick_cache import TickCache  # local import: avoids a hard import-time cycle
            tick_cache = TickCache(redis_client=redis)
        self._tick_cache = tick_cache

    async def _connection_status(self) -> dict[str, Any]:
        raw = await self._redis.get(_WS_CONNECTION_STATUS_KEY)
        if raw is None:
            return {"status": "disconnected", "latency_ms": None, "reason": "no_ws_process_running"}
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {"status": "disconnected", "latency_ms": None, "reason": "corrupt_status"}

    async def get_symbol_status(self, symbol: str) -> dict[str, Any]:
        """
        Return a full diagnostic dict for one symbol:
        ``{symbol, ws_status, latency_ms, last_tick_at, age_seconds, trading_enabled, reason}``.

        Used both by ``assert_fresh_or_raise`` and by
        GET /system/connection-status so the API and the enforcement path
        can never disagree about what "fresh" means.
        """
        conn = await self._connection_status()
        ws_status = conn.get("status", "disconnected")
        age = await self._tick_cache.age_seconds(symbol)
        tick = await self._tick_cache.get_tick(symbol)
        last_tick_at = (
            datetime.fromtimestamp(tick["ts"], tz=timezone.utc).isoformat() if tick else None
        )

        if ws_status != "connected":
            return {
                "symbol": symbol,
                "ws_status": ws_status,
                "latency_ms": conn.get("latency_ms"),
                "last_tick_at": last_tick_at,
                "age_seconds": age,
                "trading_enabled": False,
                "reason": f"WS connection is '{ws_status}', not 'connected'.",
            }
        if age is None:
            return {
                "symbol": symbol,
                "ws_status": ws_status,
                "latency_ms": conn.get("latency_ms"),
                "last_tick_at": None,
                "age_seconds": None,
                "trading_enabled": False,
                "reason": "No tick has ever been received for this symbol.",
            }
        if age > MARKET_DATA_STALENESS_SECONDS:
            return {
                "symbol": symbol,
                "ws_status": ws_status,
                "latency_ms": conn.get("latency_ms"),
                "last_tick_at": last_tick_at,
                "age_seconds": age,
                "trading_enabled": False,
                "reason": (
                    f"Last tick is {age:.2f}s old, exceeding the "
                    f"{MARKET_DATA_STALENESS_SECONDS:.1f}s staleness limit."
                ),
            }
        return {
            "symbol": symbol,
            "ws_status": ws_status,
            "latency_ms": conn.get("latency_ms"),
            "last_tick_at": last_tick_at,
            "age_seconds": age,
            "trading_enabled": True,
            "reason": None,
        }

    async def trading_enabled(self, symbol: str) -> bool:
        """Return True iff *symbol*'s live data is fresh enough to trade on."""
        status = await self.get_symbol_status(symbol)
        return bool(status["trading_enabled"])

    async def assert_fresh_or_raise(self, symbol: str) -> None:
        """
        Raise StaleMarketDataError if *symbol*'s live data is stale or the
        feed is disconnected. Returns None (no-op) when data is fresh.

        Call this at the top of any order-submission code path that
        depends on live pricing for `symbol` — mirrors
        KillSwitch.check_or_raise() / CircuitBreaker.check_or_raise().
        """
        status = await self.get_symbol_status(symbol)
        if not status["trading_enabled"]:
            raise StaleMarketDataError(
                symbol=symbol,
                reason=status["reason"] or "Market data is stale.",
                age_seconds=status["age_seconds"],
            )


# ---------------------------------------------------------------------------
# CircuitBreakerSubscriber
# ---------------------------------------------------------------------------


class CircuitBreakerSubscriber:
    """
    Async pub/sub listener for circuit-breaker and kill-switch events.

    Start this as a background task at application startup.  It logs
    all events and dispatches them to registered callback coroutines.

    Usage
    -----
        subscriber = CircuitBreakerSubscriber(redis_client)
        asyncio.create_task(subscriber.start())
    """

    def __init__(self, redis: aioredis.Redis) -> None:
        self._redis = redis
        self._callbacks: list[Any] = []

    def register_callback(self, coro_func: Any) -> None:
        """
        Register an async callback that will be called with each event dict.

        The callback signature must be: ``async def my_cb(event: dict) -> None``.
        """
        self._callbacks.append(coro_func)

    async def start(self) -> None:
        """
        Subscribe to the events channel and dispatch incoming messages.

        This coroutine runs indefinitely.  Reconnects automatically on
        connection errors with exponential back-off (max 30 s).
        """
        backoff = 1.0
        while True:
            try:
                async with self._redis.pubsub() as pubsub:
                    await pubsub.subscribe(_PUBSUB_CHANNEL)
                    logger.info("CircuitBreakerSubscriber listening on %s", _PUBSUB_CHANNEL)
                    backoff = 1.0  # reset on successful connect

                    async for raw_message in pubsub.listen():
                        if raw_message["type"] != "message":
                            continue
                        await self._handle_message(raw_message["data"])

            except asyncio.CancelledError:
                logger.info("CircuitBreakerSubscriber cancelled — stopping.")
                return
            except Exception as exc:
                logger.error(
                    "CircuitBreakerSubscriber connection error: %s — retrying in %.1f s",
                    exc,
                    backoff,
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30.0)

    async def _handle_message(self, data: bytes | str) -> None:
        """Parse a raw pub/sub message and dispatch to callbacks."""
        try:
            event: dict = json.loads(data)
        except (json.JSONDecodeError, TypeError) as exc:
            logger.warning("Malformed event on %s: %s", _PUBSUB_CHANNEL, exc)
            return

        event_type: str = event.get("event_type", "unknown")

        # Structured logging per event type
        if event_type == "kill_switch_activated":
            logger.critical(
                "EVENT kill_switch_activated reason=%s operator=%s",
                event.get("reason"),
                event.get("operator"),
            )
        elif event_type == "kill_switch_deactivated":
            logger.warning(
                "EVENT kill_switch_deactivated operator=%s", event.get("operator")
            )
        elif event_type == "circuit_breaker_tripped":
            logger.critical(
                "EVENT circuit_breaker_tripped reason=%s", event.get("reason")
            )
        elif event_type == "circuit_breaker_reset":
            logger.warning(
                "EVENT circuit_breaker_reset operator=%s", event.get("operator")
            )
        elif event_type == "pnl_recorded":
            logger.info(
                "EVENT pnl_recorded pnl=%.2f daily_pnl=%.2f consecutive_losses=%s",
                event.get("pnl_usd", 0),
                event.get("daily_pnl", 0),
                event.get("consecutive_losses", 0),
            )
        elif event_type == "daily_pnl_reset":
            logger.info("EVENT daily_pnl_reset")
        else:
            logger.debug("EVENT %s: %s", event_type, event)

        # Fan out to registered callbacks
        for cb in self._callbacks:
            try:
                await cb(event)
            except Exception as exc:
                logger.error("Callback %s raised: %s", cb, exc, exc_info=True)
