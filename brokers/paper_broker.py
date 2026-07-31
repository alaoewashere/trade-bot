"""
Paper broker — simulates order execution with realistic slippage and commissions.

All state (cash balance, positions, trade history) is persisted in Redis so the
simulated portfolio survives process restarts and can be inspected from any
service in the stack.

Redis key layout
----------------
portfolio:cash                  STRING  float (current cash balance)
portfolio:positions             HASH    symbol → JSON position dict
portfolio:trades                LIST    JSON trade dicts (newest at head)
portfolio:total_trades          STRING  int counter
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Literal, Optional

import redis.asyncio as aioredis

from brokers.base_broker import BaseBroker, OrderResult

logger = logging.getLogger(__name__)

SLIPPAGE_BPS   = 5    # 0.05 % — realistic for liquid markets
COMMISSION_BPS = 10   # 0.10 % — typical retail commission

_CASH_KEY      = "portfolio:cash"
_POSITIONS_KEY = "portfolio:positions"
_TRADES_KEY    = "portfolio:trades"
_COUNTER_KEY   = "portfolio:total_trades"
_TRADE_HISTORY_MAX = 500  # keep last N trades in Redis list


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class PaperBroker(BaseBroker):
    """
    Paper (simulated) broker suitable for strategy development and live shadowing.

    Slippage model
    ~~~~~~~~~~~~~~
    * Buy  orders execute at ``price × (1 + SLIPPAGE_BPS / 10_000)``
    * Sell orders execute at ``price × (1 - SLIPPAGE_BPS / 10_000)``

    Commission model
    ~~~~~~~~~~~~~~~~
    ``filled_value × COMMISSION_BPS / 10_000`` deducted from cash on every fill.

    Example::

        broker = PaperBroker(redis_client=redis, initial_balance=100_000.0)
        await broker.initialise()   # seed balance if first run

        result = await broker.place_order("BTC/USDT", "buy", quantity=0.1)
        positions = await broker.get_positions()
        balance   = await broker.get_balance()
    """

    def __init__(
        self,
        redis_client: aioredis.Redis,
        initial_balance: float = 10_000.0,
        slippage_bps: int = SLIPPAGE_BPS,
        commission_bps: int = COMMISSION_BPS,
    ) -> None:
        self.redis          = redis_client
        self.initial_balance = initial_balance
        self._slippage_bps  = slippage_bps
        self._commission_bps = commission_bps

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialise(self) -> None:
        """
        Seed the Redis state if this is the first run.

        Safe to call on every startup — it does not overwrite an existing balance.
        """
        exists = await self.redis.exists(_CASH_KEY)
        if not exists:
            await self.redis.set(_CASH_KEY, str(self.initial_balance))
            logger.info(
                "PaperBroker initialised with %.2f cash", self.initial_balance
            )

    # ------------------------------------------------------------------
    # BaseBroker implementation
    # ------------------------------------------------------------------

    async def place_order(
        self,
        symbol:     str,
        side:       Literal["buy", "sell"],
        quantity:   float,
        order_type: str = "market",
        price:      float | None = None,
    ) -> OrderResult:
        """
        Simulate a market or limit order fill.

        For limit orders we check whether the limit price is satisfied by the
        current market price; if not, the order is "accepted" but not filled
        (fills are synchronous in paper mode — this is a simplification).

        Returns:
            OrderResult with fill details.
        """
        if quantity <= 0:
            return OrderResult(
                success=False, order_id=None, filled_price=None,
                filled_quantity=None, commission=0.0, slippage=0.0,
                error="Quantity must be positive",
            )

        market_price = await self._get_price(symbol)
        if market_price <= 0:
            return OrderResult(
                success=False, order_id=None, filled_price=None,
                filled_quantity=None, commission=0.0, slippage=0.0,
                error=f"Cannot determine market price for {symbol}",
            )

        # Determine execution price
        if order_type == "market":
            exec_price = market_price
        elif order_type in ("limit", "stop_limit"):
            if price is None:
                return OrderResult(
                    success=False, order_id=None, filled_price=None,
                    filled_quantity=None, commission=0.0, slippage=0.0,
                    error="price is required for limit orders",
                )
            # Instant fill simulation: buy executes if limit >= market; sell if limit <= market
            if side == "buy"  and price < market_price:
                # Not immediately fillable — return accepted but unfilled
                oid = str(uuid.uuid4())
                logger.info("Limit buy order %s accepted (not yet fillable)", oid)
                return OrderResult(
                    success=True, order_id=oid, filled_price=None,
                    filled_quantity=None, commission=0.0, slippage=0.0,
                    error="order_open",
                )
            if side == "sell" and price > market_price:
                oid = str(uuid.uuid4())
                logger.info("Limit sell order %s accepted (not yet fillable)", oid)
                return OrderResult(
                    success=True, order_id=oid, filled_price=None,
                    filled_quantity=None, commission=0.0, slippage=0.0,
                    error="order_open",
                )
            exec_price = price
        elif order_type == "stop":
            exec_price = price if price is not None else market_price
        else:
            exec_price = market_price

        # Apply slippage
        slip_factor = self._slippage_bps / 10_000
        if side == "buy":
            filled_price = exec_price * (1 + slip_factor)
        else:
            filled_price = exec_price * (1 - slip_factor)

        filled_value = filled_price * quantity
        commission   = filled_value * self._commission_bps / 10_000
        slippage_cost = abs(filled_price - exec_price) * quantity

        # Verify / deduct cash (buy) or add cash (sell)
        cash = await self._get_cash()
        if side == "buy":
            total_cost = filled_value + commission
            if cash < total_cost:
                return OrderResult(
                    success=False, order_id=None, filled_price=None,
                    filled_quantity=None, commission=0.0, slippage=0.0,
                    error=f"Insufficient cash: need {total_cost:.2f}, have {cash:.2f}",
                )
            new_cash = cash - total_cost
        else:
            # Selling — must have the position
            pos = await self._get_position(symbol)
            if pos is None or pos["quantity"] < quantity:
                held = pos["quantity"] if pos else 0.0
                return OrderResult(
                    success=False, order_id=None, filled_price=None,
                    filled_quantity=None, commission=0.0, slippage=0.0,
                    error=f"Insufficient position: need {quantity}, have {held}",
                )
            proceeds  = filled_value - commission
            new_cash  = cash + proceeds

        order_id = str(uuid.uuid4())

        # Persist: update cash
        await self.redis.set(_CASH_KEY, str(new_cash))

        # Persist: update position
        await self._update_position(symbol, side, quantity, filled_price)

        # Persist: append trade record
        trade: dict = {
            "trade_id":       order_id,
            "symbol":         symbol,
            "side":           side,
            "quantity":       quantity,
            "filled_price":   filled_price,
            "filled_value":   filled_value,
            "commission":     commission,
            "slippage":       slippage_cost,
            "market_price":   market_price,
            "order_type":     order_type,
            "timestamp":      _now_iso(),
        }
        await self.redis.lpush(_TRADES_KEY, json.dumps(trade))
        await self.redis.ltrim(_TRADES_KEY, 0, _TRADE_HISTORY_MAX - 1)
        await self.redis.incr(_COUNTER_KEY)

        logger.info(
            "PaperBroker %s %s qty=%.6f @ %.6f (slip=%.4f comm=%.4f)",
            side.upper(), symbol, quantity, filled_price, slippage_cost, commission,
        )

        return OrderResult(
            success=True,
            order_id=order_id,
            filled_price=filled_price,
            filled_quantity=quantity,
            commission=commission,
            slippage=slippage_cost,
        )

    async def cancel_order(self, order_id: str) -> bool:
        """Paper orders are always immediately cancellable."""
        logger.debug("PaperBroker: cancel_order %s (no-op)", order_id)
        return True

    async def get_positions(self) -> dict:
        """
        Return all open positions with mark-to-market values.

        Returns:
            Dict mapping symbol → position dict.
        """
        raw = await self.redis.hgetall(_POSITIONS_KEY)
        positions: dict = {}
        for sym, val in raw.items():
            try:
                pos = json.loads(val)
            except json.JSONDecodeError:
                continue
            if pos.get("quantity", 0) == 0:
                continue

            # Enrich with current price for unrealised PnL
            current_price = await self._get_price(sym)
            pos["current_price"]   = current_price
            pos["market_value"]    = pos["quantity"] * current_price
            pos["unrealized_pnl"]  = (
                (current_price - pos["avg_cost"]) * pos["quantity"]
                if pos.get("side") == "long"
                else (pos["avg_cost"] - current_price) * pos["quantity"]
            )
            positions[sym] = pos

        return positions

    async def get_balance(self) -> dict:
        """
        Return cash balance and total equity (cash + mark-to-market positions).

        Returns:
            Dict with cash, total_equity, unrealized_pnl, used_margin.
        """
        cash      = await self._get_cash()
        positions = await self.get_positions()

        unrealized_pnl = sum(p.get("unrealized_pnl", 0.0) for p in positions.values())
        market_value   = sum(p.get("market_value",   0.0) for p in positions.values())
        total_equity   = cash + market_value

        return {
            "cash":          cash,
            "total_equity":  total_equity,
            "unrealized_pnl": unrealized_pnl,
            "used_margin":   market_value,
            "num_positions": len(positions),
        }

    async def close_position(self, symbol: str) -> OrderResult:
        """
        Flatten the entire position for *symbol*.

        Returns:
            OrderResult. If no position exists, returns a success with zero quantity.
        """
        pos = await self._get_position(symbol)
        if pos is None or pos.get("quantity", 0) <= 0:
            return OrderResult(
                success=True, order_id=None, filled_price=None,
                filled_quantity=0.0, commission=0.0, slippage=0.0,
                error="no_position",
            )

        side: Literal["buy", "sell"] = (
            "sell" if pos.get("side") == "long" else "buy"
        )
        return await self.place_order(symbol, side, pos["quantity"])

    async def close_all_positions(self) -> list[OrderResult]:
        """
        Emergency close of all open positions.

        Iterates positions and closes each one; continues even if individual
        closes fail so every position gets an attempt.

        Returns:
            List of OrderResult, one per symbol attempted.
        """
        positions = await self.get_positions()
        results: list[OrderResult] = []
        for symbol in list(positions.keys()):
            try:
                result = await self.close_position(symbol)
                results.append(result)
            except Exception as exc:
                logger.exception("close_all_positions error for %s: %s", symbol, exc)
                results.append(
                    OrderResult(
                        success=False, order_id=None, filled_price=None,
                        filled_quantity=None, commission=0.0, slippage=0.0,
                        error=str(exc),
                    )
                )
        logger.warning(
            "PaperBroker.close_all_positions: closed %d positions", len(results)
        )
        return results

    async def get_trade_history(
        self, symbol: Optional[str] = None, limit: int = 50
    ) -> list[dict]:
        """
        Return recent trades from Redis list.

        Args:
            symbol: Filter by symbol if provided.
            limit:  Maximum trades to return.

        Returns:
            List of trade dicts, newest first.
        """
        raw = await self.redis.lrange(_TRADES_KEY, 0, limit * 2 - 1)
        trades: list[dict] = []
        for item in raw:
            try:
                t = json.loads(item)
            except json.JSONDecodeError:
                continue
            if symbol is None or t.get("symbol") == symbol:
                trades.append(t)
            if len(trades) >= limit:
                break
        return trades

    async def reset(self) -> None:
        """
        Reset portfolio to initial state.

        WARNING: destroys all paper trade history and positions.
        """
        await self.redis.set(_CASH_KEY, str(self.initial_balance))
        await self.redis.delete(_POSITIONS_KEY)
        await self.redis.delete(_TRADES_KEY)
        await self.redis.set(_COUNTER_KEY, "0")
        logger.warning(
            "PaperBroker reset — balance restored to %.2f", self.initial_balance
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _get_cash(self) -> float:
        """Read cash balance from Redis."""
        raw = await self.redis.get(_CASH_KEY)
        if raw is None:
            # Auto-seed if missing (e.g. after Redis flush)
            await self.redis.set(_CASH_KEY, str(self.initial_balance))
            return self.initial_balance
        try:
            return float(raw)
        except (ValueError, TypeError):
            return self.initial_balance

    async def _get_position(self, symbol: str) -> dict | None:
        """Read a single position from the Redis hash."""
        raw = await self.redis.hget(_POSITIONS_KEY, symbol)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    async def _update_position(
        self,
        symbol: str,
        side: Literal["buy", "sell"],
        quantity: float,
        price: float,
    ) -> None:
        """
        Update the position hash in Redis using a weighted-average cost basis.
        Removes the key when the position reaches zero.
        """
        pos = await self._get_position(symbol) or {
            "symbol":   symbol,
            "quantity": 0.0,
            "avg_cost": 0.0,
            "side":     "long",
        }

        current_qty  = float(pos.get("quantity", 0.0))
        current_cost = float(pos.get("avg_cost",  0.0))

        if side == "buy":
            new_qty  = current_qty + quantity
            new_cost = (
                (current_cost * current_qty + price * quantity) / new_qty
                if new_qty > 0
                else price
            )
            pos["side"] = "long"
        else:  # sell
            new_qty  = current_qty - quantity
            new_cost = current_cost  # cost basis unchanged on partial close

        pos["quantity"] = round(new_qty, 10)
        pos["avg_cost"] = new_cost

        if pos["quantity"] <= 1e-10:
            # Position fully closed — remove from hash
            await self.redis.hdel(_POSITIONS_KEY, symbol)
            logger.debug("Position closed for %s", symbol)
        else:
            await self.redis.hset(_POSITIONS_KEY, symbol, json.dumps(pos))

    async def _get_price(self, symbol: str) -> float:
        """
        Resolve the current price from the Redis market data cache.

        Probes the most common timeframes in order; returns 0.0 if nothing
        is cached (caller should handle this as a pricing failure).
        """
        for tf in ("1m", "5m", "1h"):
            safe_symbol = symbol.replace("/", "_").upper()
            key = f"market:{safe_symbol}:{tf}:latest"
            try:
                raw = await self.redis.get(key)
                if raw:
                    data = json.loads(raw)
                    price = data.get("current_price", 0.0)
                    if price and float(price) > 0:
                        return float(price)
            except Exception:
                continue

        logger.warning(
            "PaperBroker: no cached price for %s — cannot simulate order", symbol
        )
        return 0.0
