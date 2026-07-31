"""
PostgreSQL-backed trade journal using asyncpg.

Tables
------
trade_proposals   — every signal that passed through the approval pipeline
trades            — executed positions with lifecycle tracking
portfolio_snapshots — periodic equity curve snapshots

The schema is created via ``TradeJournal.create_tables()`` on first run.
Production deployments should use the SQL migrations in /migrations instead.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

import asyncpg  # type: ignore

# Supabase Postgres DSN (read from environment, with sensible default)
import os as _os
_DEFAULT_DSN: str = _os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:"
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    ".eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imh1Z3BzcHNzc2NrYmVweW9mY250Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4NTQyOTk5MywiZXhwIjoyMTAxMDA1OTkzfQ"
    ".Yx0Mg2JgRjM98GKhuVJGSM9HB4rHdi50aWXIYuGM-j4"
    "@db.hugpspsssckbepyofcnt.supabase.co:5432/postgres",
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# DDL (idempotent — uses IF NOT EXISTS throughout)
# ---------------------------------------------------------------------------
_DDL = """
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS trade_proposals (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol          TEXT        NOT NULL,
    side            TEXT        NOT NULL,           -- 'buy' | 'sell'
    quantity        NUMERIC     NOT NULL,
    signal_strength NUMERIC,
    confidence      NUMERIC,
    reasoning       TEXT,
    agents_agreed   JSONB       DEFAULT '[]',
    risk_metrics    JSONB       DEFAULT '{}',
    status          TEXT        NOT NULL DEFAULT 'pending',
                                                   -- pending | approved | rejected | executed | cancelled
    human_decision  TEXT,                          -- 'approved' | 'rejected' | null
    human_reason    TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    decided_at      TIMESTAMPTZ,
    raw_payload     JSONB       DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_proposals_symbol     ON trade_proposals (symbol);
CREATE INDEX IF NOT EXISTS idx_proposals_status     ON trade_proposals (status);
CREATE INDEX IF NOT EXISTS idx_proposals_created_at ON trade_proposals (created_at DESC);

CREATE TABLE IF NOT EXISTS trades (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    proposal_id     UUID REFERENCES trade_proposals(id) ON DELETE SET NULL,
    symbol          TEXT        NOT NULL,
    side            TEXT        NOT NULL,           -- 'buy' | 'sell'
    quantity        NUMERIC     NOT NULL,
    entry_price     NUMERIC     NOT NULL,
    exit_price      NUMERIC,
    commission      NUMERIC     NOT NULL DEFAULT 0,
    slippage        NUMERIC     NOT NULL DEFAULT 0,
    status          TEXT        NOT NULL DEFAULT 'open',
                                                   -- open | closed | cancelled
    realized_pnl    NUMERIC,
    exit_reason     TEXT,                          -- 'take_profit' | 'stop_loss' | 'signal' | 'emergency'
    entry_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    exit_at         TIMESTAMPTZ,
    hold_duration   INTERVAL GENERATED ALWAYS AS (exit_at - entry_at) STORED,
    tags            JSONB       DEFAULT '[]',
    extra           JSONB       DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_trades_symbol   ON trades (symbol);
CREATE INDEX IF NOT EXISTS idx_trades_status   ON trades (status);
CREATE INDEX IF NOT EXISTS idx_trades_entry_at ON trades (entry_at DESC);

CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id              BIGSERIAL   PRIMARY KEY,
    snapshot_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    cash            NUMERIC     NOT NULL,
    total_equity    NUMERIC     NOT NULL,
    unrealized_pnl  NUMERIC     NOT NULL DEFAULT 0,
    num_positions   INT         NOT NULL DEFAULT 0,
    positions       JSONB       DEFAULT '{}',
    extra           JSONB       DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_snapshots_at ON portfolio_snapshots (snapshot_at DESC);
"""


class TradeJournal:
    """
    Async PostgreSQL trade journal.

    Manages the full lifecycle of trade proposals → executed trades →
    portfolio snapshots, and computes performance metrics for strategy
    evaluation.

    Example::

        journal = TradeJournal(dsn="postgresql://user:pass@localhost/hedgefund")
        await journal.connect()
        await journal.create_tables()

        proposal_id = await journal.save_proposal({
            "symbol": "BTC/USDT", "side": "buy", "quantity": 0.1,
            "confidence": 0.78, "reasoning": "momentum signal",
        })
        await journal.update_proposal_status(proposal_id, "approved")

        trade_id = await journal.save_trade({
            "symbol": "BTC/USDT", "side": "buy", "quantity": 0.1,
            "entry_price": 65_000.0, "commission": 6.5, "slippage": 3.25,
            "proposal_id": proposal_id,
        })
        await journal.close_trade(trade_id, exit_price=67_000.0,
                                  realized_pnl=193.25, exit_reason="take_profit")

        metrics = await journal.get_performance_metrics(days=30)
    """

    def __init__(
        self,
        dsn: str = _DEFAULT_DSN,
        pool: Optional[asyncpg.Pool] = None,
    ) -> None:
        self._dsn   = dsn
        self._pool  = pool
        self._owned = pool is None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self, min_size: int = 2, max_size: int = 10) -> None:
        """Create the connection pool (skipped when pool is injected)."""
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                self._dsn, min_size=min_size, max_size=max_size
            )
            logger.info("TradeJournal connected to PostgreSQL")

    async def close(self) -> None:
        """Release the pool if we own it."""
        if self._owned and self._pool is not None:
            await self._pool.close()
            self._pool = None

    async def create_tables(self) -> None:
        """Apply DDL (idempotent — safe to run on every startup)."""
        if self._pool is None:
            raise RuntimeError("Call await journal.connect() first")
        async with self._pool.acquire() as conn:
            await conn.execute(_DDL)
        logger.info("TradeJournal tables verified / created")

    # ------------------------------------------------------------------
    # Trade proposals
    # ------------------------------------------------------------------

    async def save_proposal(self, proposal: dict) -> str:
        """
        Persist a trade proposal.

        Args:
            proposal: Dict with at minimum ``symbol``, ``side``, ``quantity``.
                      Recognised optional fields: ``signal_strength``,
                      ``confidence``, ``reasoning``, ``agents_agreed``,
                      ``risk_metrics``, ``raw_payload``.

        Returns:
            UUID string of the inserted row.
        """
        _assert_pool(self._pool)
        proposal_id = str(uuid.uuid4())

        sql = """
            INSERT INTO trade_proposals
                (id, symbol, side, quantity, signal_strength, confidence,
                 reasoning, agents_agreed, risk_metrics, raw_payload)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
            RETURNING id::TEXT
        """
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                sql,
                proposal_id,
                str(proposal.get("symbol", "")),
                str(proposal.get("side", "")),
                float(proposal.get("quantity", 0)),
                _opt_float(proposal.get("signal_strength")),
                _opt_float(proposal.get("confidence")),
                proposal.get("reasoning"),
                json.dumps(proposal.get("agents_agreed", [])),
                json.dumps(proposal.get("risk_metrics", {}), default=str),
                json.dumps(
                    {k: v for k, v in proposal.items()
                     if k not in ("symbol","side","quantity","signal_strength",
                                  "confidence","reasoning","agents_agreed","risk_metrics")},
                    default=str,
                ),
            )
        result_id = row["id"] if row else proposal_id
        logger.info("Proposal saved: %s %s %s @ qty=%.4f",
                    result_id, proposal.get("side"), proposal.get("symbol"),
                    proposal.get("quantity", 0))
        return result_id

    async def update_proposal_status(
        self,
        proposal_id: str,
        status: str,
        human_decision: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> None:
        """
        Update proposal lifecycle status.

        Args:
            proposal_id:    UUID of the proposal.
            status:         New status string.
            human_decision: "approved" | "rejected" | None.
            reason:         Optional free-text reason.
        """
        _assert_pool(self._pool)
        decided_at = datetime.now(timezone.utc) if human_decision else None

        sql = """
            UPDATE trade_proposals
               SET status = $2,
                   human_decision = COALESCE($3, human_decision),
                   human_reason   = COALESCE($4, human_reason),
                   decided_at     = COALESCE($5, decided_at)
             WHERE id = $1::UUID
        """
        async with self._pool.acquire() as conn:
            await conn.execute(sql, proposal_id, status, human_decision, reason, decided_at)

    # ------------------------------------------------------------------
    # Trades (executed positions)
    # ------------------------------------------------------------------

    async def save_trade(self, trade: dict) -> str:
        """
        Record an executed trade (open position).

        Args:
            trade: Dict with at minimum ``symbol``, ``side``, ``quantity``,
                   ``entry_price``.  Optional: ``proposal_id``, ``commission``,
                   ``slippage``, ``tags``, ``extra``.

        Returns:
            UUID string of the inserted row.
        """
        _assert_pool(self._pool)
        trade_id = str(uuid.uuid4())

        sql = """
            INSERT INTO trades
                (id, proposal_id, symbol, side, quantity, entry_price,
                 commission, slippage, tags, extra)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
            RETURNING id::TEXT
        """
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                sql,
                trade_id,
                trade.get("proposal_id"),
                str(trade.get("symbol", "")),
                str(trade.get("side", "")),
                float(trade.get("quantity", 0)),
                float(trade.get("entry_price", 0)),
                float(trade.get("commission", 0)),
                float(trade.get("slippage", 0)),
                json.dumps(trade.get("tags", [])),
                json.dumps(
                    {k: v for k, v in trade.items()
                     if k not in ("proposal_id","symbol","side","quantity",
                                  "entry_price","commission","slippage","tags")},
                    default=str,
                ),
            )
        result_id = row["id"] if row else trade_id
        logger.info("Trade saved: %s %s %s qty=%.6f @ %.4f",
                    result_id, trade.get("side"), trade.get("symbol"),
                    trade.get("quantity", 0), trade.get("entry_price", 0))
        return result_id

    async def close_trade(
        self,
        trade_id: str,
        exit_price: float,
        realized_pnl: float,
        exit_reason: str = "signal",
    ) -> None:
        """
        Mark a trade as closed with its P&L.

        Args:
            trade_id:     UUID of the trade to close.
            exit_price:   Execution price of the closing order.
            realized_pnl: Net P&L in quote currency (after costs).
            exit_reason:  e.g. "take_profit", "stop_loss", "signal", "emergency".
        """
        _assert_pool(self._pool)
        sql = """
            UPDATE trades
               SET exit_price   = $2,
                   realized_pnl = $3,
                   exit_reason  = $4,
                   exit_at      = NOW(),
                   status       = 'closed'
             WHERE id = $1::UUID
        """
        async with self._pool.acquire() as conn:
            await conn.execute(sql, trade_id, exit_price, realized_pnl, exit_reason)
        logger.info("Trade closed: %s exit=%.4f pnl=%.4f reason=%s",
                    trade_id, exit_price, realized_pnl, exit_reason)

    async def get_open_trades(self) -> list[dict]:
        """
        Return all currently open positions.

        Returns:
            List of trade dicts sorted by entry_at ascending.
        """
        _assert_pool(self._pool)
        sql = """
            SELECT id::TEXT, proposal_id::TEXT, symbol, side,
                   quantity::FLOAT, entry_price::FLOAT, commission::FLOAT,
                   slippage::FLOAT, status, tags, extra,
                   entry_at AT TIME ZONE 'UTC' AS entry_at
              FROM trades
             WHERE status = 'open'
             ORDER BY entry_at ASC
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(sql)
        return [_row_to_dict(r) for r in rows]

    async def get_recent_trades(self, limit: int = 20) -> list[dict]:
        """
        Return the most recently closed trades.

        Args:
            limit: Maximum number of trades to return.

        Returns:
            List of trade dicts sorted by exit_at descending.
        """
        _assert_pool(self._pool)
        sql = """
            SELECT id::TEXT, proposal_id::TEXT, symbol, side,
                   quantity::FLOAT, entry_price::FLOAT, exit_price::FLOAT,
                   commission::FLOAT, slippage::FLOAT, realized_pnl::FLOAT,
                   exit_reason, status, tags, extra,
                   entry_at AT TIME ZONE 'UTC' AS entry_at,
                   exit_at  AT TIME ZONE 'UTC' AS exit_at
              FROM trades
             WHERE status = 'closed'
             ORDER BY exit_at DESC
             LIMIT $1
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(sql, limit)
        return [_row_to_dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Portfolio snapshots
    # ------------------------------------------------------------------

    async def save_portfolio_snapshot(self, snapshot: dict) -> None:
        """
        Persist a portfolio equity snapshot.

        Args:
            snapshot: Dict with at minimum ``cash`` and ``total_equity``.
                      Optional: ``unrealized_pnl``, ``num_positions``,
                      ``positions`` (dict), ``extra`` (dict).
        """
        _assert_pool(self._pool)
        sql = """
            INSERT INTO portfolio_snapshots
                (cash, total_equity, unrealized_pnl, num_positions,
                 positions, extra)
            VALUES ($1,$2,$3,$4,$5,$6)
        """
        async with self._pool.acquire() as conn:
            await conn.execute(
                sql,
                float(snapshot.get("cash", 0)),
                float(snapshot.get("total_equity", 0)),
                float(snapshot.get("unrealized_pnl", 0)),
                int(snapshot.get("num_positions", 0)),
                json.dumps(snapshot.get("positions", {}), default=str),
                json.dumps(
                    {k: v for k, v in snapshot.items()
                     if k not in ("cash","total_equity","unrealized_pnl",
                                  "num_positions","positions")},
                    default=str,
                ),
            )

    # ------------------------------------------------------------------
    # Performance metrics
    # ------------------------------------------------------------------

    async def get_performance_metrics(self, days: int = 30) -> dict:
        """
        Compute performance metrics over the last *days* calendar days.

        Metrics computed
        ~~~~~~~~~~~~~~~~
        - ``total_trades``   — number of closed trades in the window
        - ``winning_trades`` — trades with realized_pnl > 0
        - ``losing_trades``  — trades with realized_pnl <= 0
        - ``win_rate``       — winning / total (0.0–1.0)
        - ``total_pnl``      — sum of realized_pnl
        - ``avg_pnl``        — mean pnl per trade
        - ``avg_winner``     — mean pnl of winning trades
        - ``avg_loser``      — mean pnl of losing trades
        - ``profit_factor``  — |sum winners| / |sum losers|  (inf if no losers)
        - ``sharpe_ratio``   — annualised Sharpe of daily P&L series
        - ``max_drawdown``   — maximum peak-to-trough drawdown of cumulative pnl
        - ``period_days``    — days requested
        - ``computed_at``    — ISO timestamp of computation

        Returns:
            Dict of metric name → value.
        """
        _assert_pool(self._pool)

        since = datetime.now(timezone.utc) - timedelta(days=days)

        # ---- Retrieve closed trades in window ----
        sql_trades = """
            SELECT realized_pnl::FLOAT,
                   exit_at AT TIME ZONE 'UTC' AS exit_at
              FROM trades
             WHERE status     = 'closed'
               AND exit_at   >= $1
             ORDER BY exit_at ASC
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(sql_trades, since)

        pnls: list[float] = [float(r["realized_pnl"]) for r in rows if r["realized_pnl"] is not None]
        exit_dates:  list[datetime] = [r["exit_at"] for r in rows]

        total = len(pnls)
        if total == 0:
            return _empty_metrics(days)

        winners = [p for p in pnls if p > 0]
        losers  = [p for p in pnls if p <= 0]

        total_pnl    = sum(pnls)
        avg_pnl      = total_pnl / total
        avg_winner   = sum(winners) / len(winners) if winners else 0.0
        avg_loser    = sum(losers)  / len(losers)  if losers  else 0.0

        sum_winners  = sum(winners)
        sum_losers   = abs(sum(losers))
        profit_factor = (sum_winners / sum_losers) if sum_losers > 0 else float("inf")

        # ---- Sharpe ratio (annualised, daily P&L) ----
        sharpe = _compute_sharpe(pnls, exit_dates)

        # ---- Maximum drawdown on cumulative P&L curve ----
        max_dd = _compute_max_drawdown(pnls)

        return {
            "total_trades":   total,
            "winning_trades": len(winners),
            "losing_trades":  len(losers),
            "win_rate":       round(len(winners) / total, 4),
            "total_pnl":      round(total_pnl,    4),
            "avg_pnl":        round(avg_pnl,       4),
            "avg_winner":     round(avg_winner,    4),
            "avg_loser":      round(avg_loser,     4),
            "profit_factor":  round(profit_factor, 4) if profit_factor != float("inf") else None,
            "sharpe_ratio":   round(sharpe,        4),
            "max_drawdown":   round(max_dd,         4),
            "period_days":    days,
            "computed_at":    datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    async def __aenter__(self) -> "TradeJournal":
        await self.connect()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _assert_pool(pool: Optional[asyncpg.Pool]) -> None:
    if pool is None:
        raise RuntimeError("Call await journal.connect() first")


def _opt_float(v: Any) -> Optional[float]:
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _row_to_dict(row: asyncpg.Record) -> dict:
    """Convert an asyncpg Record to a plain dict, serialising datetimes."""
    d: dict = {}
    for key in row.keys():
        val = row[key]
        if isinstance(val, datetime):
            d[key] = val.isoformat()
        elif hasattr(val, "isoformat"):          # timedelta etc.
            d[key] = str(val)
        elif isinstance(val, str):
            # Attempt to parse JSONB strings back to Python objects
            try:
                parsed = json.loads(val)
                d[key] = parsed
            except (json.JSONDecodeError, TypeError):
                d[key] = val
        else:
            d[key] = val
    return d


def _empty_metrics(days: int) -> dict:
    return {
        "total_trades":   0,
        "winning_trades": 0,
        "losing_trades":  0,
        "win_rate":       0.0,
        "total_pnl":      0.0,
        "avg_pnl":        0.0,
        "avg_winner":     0.0,
        "avg_loser":      0.0,
        "profit_factor":  None,
        "sharpe_ratio":   0.0,
        "max_drawdown":   0.0,
        "period_days":    days,
        "computed_at":    datetime.now(timezone.utc).isoformat(),
    }


def _compute_sharpe(pnls: list[float], exit_dates: list[datetime]) -> float:
    """
    Annualised Sharpe ratio from a list of per-trade P&Ls.

    Groups P&Ls by calendar day, computes daily returns series,
    then annualises (√252).  Returns 0.0 when there is insufficient data.
    """
    if len(pnls) < 2:
        return 0.0

    # Aggregate by day
    from collections import defaultdict
    daily: dict[str, float] = defaultdict(float)
    for pnl, dt in zip(pnls, exit_dates):
        day = dt.strftime("%Y-%m-%d") if dt else "unknown"
        daily[day] += pnl

    series = list(daily.values())
    if len(series) < 2:
        return 0.0

    import statistics
    try:
        mean = statistics.mean(series)
        std  = statistics.stdev(series)
        if std == 0:
            return 0.0
        return (mean / std) * (252 ** 0.5)
    except Exception:
        return 0.0


def _compute_max_drawdown(pnls: list[float]) -> float:
    """
    Maximum peak-to-trough drawdown of the cumulative P&L curve.

    Returns the drawdown as a negative float (e.g. -500.25).
    Returns 0.0 if there is no drawdown.
    """
    if not pnls:
        return 0.0

    peak    = 0.0
    cumul   = 0.0
    max_dd  = 0.0

    for pnl in pnls:
        cumul += pnl
        if cumul > peak:
            peak = cumul
        dd = cumul - peak
        if dd < max_dd:
            max_dd = dd

    return max_dd
