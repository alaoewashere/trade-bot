"""
alerts/generator.py
====================
Alert-writing functions — one per alert_type in the `alerts` table
(migrations/versions/0004_alerts.sql).

This module is deliberately NOT a standalone daemon. Instead each function
is called directly from the natural point in the existing code where the
underlying event already happens, the same pattern Phase 1 established with
``api/routers/trades.py::_auto_create_journal_entry`` being called from
``close_position``. Every function is best-effort: a failure here must never
break the caller's primary flow, so all DB errors are caught and logged.

Hook-up status
---------------
WIRED:
  - stop_loss_hit / take_profit_hit  <- api/routers/trades.py::close_position
  - consensus_changed / confidence_dropped
        <- memory/trade_journal.py::TradeJournal.save_proposal
           (compares the new proposal's direction/confidence against the
           most recently saved proposal for the same symbol)

NOT WIRED (documented TODO, not forced):
  - market_regime_changed: no code path in this repository currently INSERTs
    into `market_regimes` (grep confirms only reads exist, e.g.
    api/routers/portfolio.py, graph/main_graph.py's routing). Wiring this
    would mean guessing at a writer that doesn't exist yet rather than
    hooking an existing one, which risks inventing behaviour Phase 1/2
    never had. TODO: once a `market_regimes` writer exists, call
    generate_market_regime_changed() from it the same way this module's
    other hooks are wired.
  - whale_alert: depends on the whale-transaction provider integration
    (see api/routers/markets.py::get_whale_activity) which is provider-gated
    and not connected to a live feed in this environment. TODO: call
    generate_whale_alert() from the provider's webhook/poll handler once
    WHALE_ALERT_API_KEY is wired to a real client.
  - volatility_spike / funding_rate_alert / large_liquidation /
    high_risk_position: these need a running market-data monitor loop
    (continuous polling of orderbook/funding/liquidation feeds) which is
    out of scope for this phase per the task brief ("not a new
    always-running daemon"). The functions are provided below so a future
    monitor loop can call them directly; TODO wire from that loop.
"""
from __future__ import annotations

import logging
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)

_VALID_SEVERITIES = {"info", "warning", "critical"}


async def _write_alert(
    db: asyncpg.Connection,
    alert_type: str,
    severity: str,
    message: str,
    symbol: str | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    """Shared insert helper — best-effort, never raises to the caller."""
    if severity not in _VALID_SEVERITIES:
        severity = "info"
    try:
        await db.execute(
            """
            INSERT INTO alerts (alert_type, severity, symbol, message, payload)
            VALUES ($1, $2, $3, $4, $5)
            """,
            alert_type,
            severity,
            symbol,
            message,
            payload or {},
        )
    except Exception:
        logger.exception("Failed to write alert type=%s symbol=%s", alert_type, symbol)


# ---------------------------------------------------------------------------
# WIRED: trade close outcomes
# ---------------------------------------------------------------------------


async def generate_trade_close_alert(
    db: asyncpg.Connection,
    *,
    symbol: str,
    direction: str,
    pnl_usd: float,
    reason: str,
    trade_id: str,
) -> None:
    """
    Called from api/routers/trades.py::close_position after a position is
    closed. Classifies the close as stop_loss_hit / take_profit_hit based on
    the operator-supplied close reason (best-effort text match — there is no
    live price feed at manual-close time to verify against the exact SL/TP
    price, see _auto_create_journal_entry's own comment about this
    limitation), falling back to a generic informational alert otherwise.
    """
    reason_lower = reason.lower()
    payload = {"trade_id": trade_id, "pnl_usd": pnl_usd, "reason": reason}

    if "stop" in reason_lower:
        await _write_alert(
            db, "stop_loss_hit", "warning",
            f"{symbol} {direction} position closed near stop loss (PnL ${pnl_usd:.2f}).",
            symbol=symbol, payload=payload,
        )
    elif "target" in reason_lower or "take profit" in reason_lower or "take-profit" in reason_lower:
        await _write_alert(
            db, "take_profit_hit", "info",
            f"{symbol} {direction} position closed at take-profit (PnL ${pnl_usd:.2f}).",
            symbol=symbol, payload=payload,
        )
    else:
        severity = "warning" if pnl_usd < 0 else "info"
        await _write_alert(
            db, "stop_loss_hit" if pnl_usd < 0 else "take_profit_hit", severity,
            f"{symbol} {direction} position closed manually (PnL ${pnl_usd:.2f}): {reason}",
            symbol=symbol, payload=payload,
        )


# ---------------------------------------------------------------------------
# WIRED: consensus / confidence changes
# ---------------------------------------------------------------------------


async def generate_consensus_alerts(
    db: asyncpg.Connection,
    *,
    symbol: str,
    new_direction: str | None,
    new_confidence: float | None,
    previous_direction: str | None,
    previous_confidence: float | None,
    confidence_drop_threshold_pct: float = 15.0,
) -> None:
    """
    Called from memory/trade_journal.py::TradeJournal.save_proposal, which
    is the actual persistence point for a new trade_proposal (and therefore
    the closest existing hook to "when consensus results get stored" per
    the Phase 3 brief). Compares the incoming proposal to the most recent
    prior proposal for the same symbol.
    """
    if previous_direction is not None and new_direction is not None and new_direction != previous_direction:
        await _write_alert(
            db, "consensus_changed", "info",
            f"{symbol} consensus direction changed: {previous_direction} -> {new_direction}.",
            symbol=symbol,
            payload={"previous_direction": previous_direction, "new_direction": new_direction},
        )

    if previous_confidence is not None and new_confidence is not None:
        # confidence values are stored as 0-1 fractions or 0-100 percentages
        # depending on caller; normalise to percentage points for comparison.
        prev_pct = previous_confidence * 100 if previous_confidence <= 1 else previous_confidence
        new_pct = new_confidence * 100 if new_confidence <= 1 else new_confidence
        drop = prev_pct - new_pct
        if drop >= confidence_drop_threshold_pct:
            await _write_alert(
                db, "confidence_dropped", "warning",
                f"{symbol} consensus confidence dropped {drop:.1f}pp ({prev_pct:.1f}% -> {new_pct:.1f}%).",
                symbol=symbol,
                payload={"previous_confidence_pct": prev_pct, "new_confidence_pct": new_pct},
            )


# ---------------------------------------------------------------------------
# NOT WIRED — provided for a future monitor loop / market_regimes writer
# ---------------------------------------------------------------------------


async def generate_market_regime_changed(
    db: asyncpg.Connection, *, symbol: str, previous_regime: str | None, new_regime: str,
) -> None:
    """TODO: call from wherever `market_regimes` rows get INSERTed once that writer exists."""
    await _write_alert(
        db, "market_regime_changed", "info",
        f"{symbol} market regime changed: {previous_regime or 'unknown'} -> {new_regime}.",
        symbol=symbol,
        payload={"previous_regime": previous_regime, "new_regime": new_regime},
    )


async def generate_whale_alert(
    db: asyncpg.Connection, *, symbol: str, usd_value: float, direction: str,
) -> None:
    """TODO: call from the Whale Alert provider client once WHALE_ALERT_API_KEY is wired to a live feed."""
    await _write_alert(
        db, "whale_alert", "warning",
        f"Whale transaction detected on {symbol}: ${usd_value:,.0f} ({direction}).",
        symbol=symbol,
        payload={"usd_value": usd_value, "direction": direction},
    )


async def generate_high_risk_position(
    db: asyncpg.Connection, *, symbol: str, heat_pct: float, threshold_pct: float = 80.0,
) -> None:
    """TODO: call from a future risk-monitor loop reading api/routers/portfolio.py's risk-exposure query on an interval."""
    if heat_pct >= threshold_pct:
        await _write_alert(
            db, "high_risk_position", "critical",
            f"{symbol} portfolio heat at {heat_pct:.1f}% (threshold {threshold_pct:.0f}%).",
            symbol=symbol, payload={"heat_pct": heat_pct, "threshold_pct": threshold_pct},
        )


async def generate_volatility_spike(
    db: asyncpg.Connection, *, symbol: str, atr_pct_change: float, threshold_pct: float = 50.0,
) -> None:
    """TODO: call from a future market-data monitor loop polling ATR/volatility over an interval."""
    if atr_pct_change >= threshold_pct:
        await _write_alert(
            db, "volatility_spike", "warning",
            f"{symbol} volatility spiked {atr_pct_change:.1f}% above baseline.",
            symbol=symbol, payload={"atr_pct_change": atr_pct_change},
        )


async def generate_funding_rate_alert(
    db: asyncpg.Connection, *, symbol: str, funding_rate_pct: float, threshold_pct: float = 0.1,
) -> None:
    """TODO: call from a future monitor loop polling api/routers/markets.py::get_funding on an interval."""
    if abs(funding_rate_pct) >= threshold_pct:
        await _write_alert(
            db, "funding_rate_alert", "info",
            f"{symbol} funding rate at {funding_rate_pct:.4f}% (threshold {threshold_pct:.2f}%).",
            symbol=symbol, payload={"funding_rate_pct": funding_rate_pct},
        )


async def generate_large_liquidation(
    db: asyncpg.Connection, *, symbol: str, usd_value: float, direction: str,
) -> None:
    """TODO: call from a liquidation-feed subscriber once one exists (ccxt has no unified liquidation stream)."""
    await _write_alert(
        db, "large_liquidation", "warning",
        f"Large {direction} liquidation on {symbol}: ${usd_value:,.0f}.",
        symbol=symbol, payload={"usd_value": usd_value, "direction": direction},
    )
