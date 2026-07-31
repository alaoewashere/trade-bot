"""
Abstract base broker interface.

All broker implementations (paper, Alpaca live, Binance live, etc.) must
subclass BaseBroker and implement every abstract method so that the rest
of the system can treat them interchangeably.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Literal


@dataclass
class OrderResult:
    """
    Unified result object returned by every broker after an order attempt.

    Attributes:
        success:          Whether the order was accepted and filled.
        order_id:         Exchange / broker order ID (None on failure).
        filled_price:     Actual execution price including slippage (None on failure).
        filled_quantity:  Quantity actually filled (None on failure).
        commission:       Commission charged in quote currency.
        slippage:         Slippage cost in quote currency (positive = cost).
        error:            Human-readable error message (None on success).
    """

    success:          bool
    order_id:         str | None
    filled_price:     float | None
    filled_quantity:  float | None
    commission:       float
    slippage:         float
    error:            str | None = None

    # Computed convenience
    @property
    def total_cost(self) -> float:
        """Commission + slippage in quote currency."""
        return self.commission + self.slippage

    @property
    def net_filled_value(self) -> float:
        """Filled value after costs (filled_price × filled_quantity - total_cost)."""
        if self.filled_price is None or self.filled_quantity is None:
            return 0.0
        return self.filled_price * self.filled_quantity - self.total_cost


class BaseBroker(ABC):
    """
    Abstract interface that every broker adapter must implement.

    The hedge-fund graph and risk modules import only this class so they
    remain broker-agnostic.  Swapping paper → live trading requires only
    changing which concrete class is injected at startup.
    """

    # ------------------------------------------------------------------
    # Order management
    # ------------------------------------------------------------------

    @abstractmethod
    async def place_order(
        self,
        symbol:     str,
        side:       Literal["buy", "sell"],
        quantity:   float,
        order_type: str = "market",
        price:      float | None = None,
    ) -> OrderResult:
        """
        Place an order.

        Args:
            symbol:     Instrument identifier (e.g. "BTC/USDT" or "AAPL").
            side:       "buy" or "sell".
            quantity:   Number of units / contracts.
            order_type: "market" | "limit" | "stop" | "stop_limit".
            price:      Limit / stop price (required for non-market orders).

        Returns:
            OrderResult describing the fill.
        """
        ...

    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an open order by ID.

        Returns:
            True if the order was cancelled (or did not exist), False on error.
        """
        ...

    # ------------------------------------------------------------------
    # Position & account queries
    # ------------------------------------------------------------------

    @abstractmethod
    async def get_positions(self) -> dict:
        """
        Retrieve all open positions.

        Returns:
            Dict mapping symbol → position dict with at minimum:
            ``{"symbol": str, "quantity": float, "avg_cost": float,
               "current_price": float, "unrealized_pnl": float,
               "side": "long"|"short"}``.
        """
        ...

    @abstractmethod
    async def get_balance(self) -> dict:
        """
        Retrieve account balances.

        Returns:
            Dict with at minimum:
            ``{"cash": float, "total_equity": float,
               "unrealized_pnl": float, "used_margin": float}``.
        """
        ...

    # ------------------------------------------------------------------
    # Position closing
    # ------------------------------------------------------------------

    @abstractmethod
    async def close_position(self, symbol: str) -> OrderResult:
        """
        Flatten the entire position for *symbol*.

        Args:
            symbol: Instrument to close.

        Returns:
            OrderResult for the closing trade.
        """
        ...

    @abstractmethod
    async def close_all_positions(self) -> list[OrderResult]:
        """
        Emergency flatten of every open position.

        Called by the emergency-stop module when circuit-breakers trip.

        Returns:
            List of OrderResult, one per position closed.
        """
        ...

    # ------------------------------------------------------------------
    # Optional helpers (concrete implementations may override)
    # ------------------------------------------------------------------

    async def get_order_status(self, order_id: str) -> dict:
        """
        Poll the status of a specific order.

        Default implementation returns an empty dict; brokers that support
        GTC / limit orders should override this.
        """
        return {}

    async def get_trade_history(self, symbol: str | None = None, limit: int = 50) -> list[dict]:
        """
        Fetch recent fills / executions.

        Default implementation returns an empty list.
        """
        return []
