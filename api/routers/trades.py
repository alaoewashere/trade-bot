"""
api/routers/trades.py
======================
Trade history, open positions, and execution record endpoints.

Endpoints
---------
GET  /trades                        — paginated trade history
GET  /trades/open                   — current open positions
GET  /trades/{trade_id}             — specific trade detail
GET  /trades/{trade_id}/timeline    — full execution timeline for a trade
GET  /trades/stats                  — aggregate performance statistics
GET  /trades/equity-curve           — cumulative equity/drawdown time series
GET  /trades/calendar               — daily PnL bucketed by date
POST /trades/{trade_id}/close       — manually close a position (paper only)
POST /trades/paper/execute          — execute a signal against the paper broker
"""
from __future__ import annotations

import logging
import statistics
from datetime import datetime, timedelta, timezone
from typing import Any

import asyncpg
import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from api.dependencies import get_db, get_redis

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class TradeResponse(BaseModel):
    trade_id: str
    symbol: str
    direction: str
    entry_type: str
    entry_price: float | None
    filled_price: float | None
    quantity: float
    stop_loss: float
    take_profit_levels: list[float]
    broker: str
    broker_order_id: str | None
    status: str  # open | closed | cancelled | partially_filled
    pnl_usd: float | None
    pnl_pct: float | None
    commission: float
    slippage: float
    consensus_direction: str | None
    consensus_confidence_pct: float | None
    approval_id: str | None
    opened_at: str
    closed_at: str | None
    notes: str


class OpenPositionResponse(BaseModel):
    trade_id: str
    symbol: str
    direction: str
    quantity: float
    entry_price: float
    current_price: float | None
    unrealised_pnl_usd: float | None
    unrealised_pnl_pct: float | None
    stop_loss: float
    take_profit_levels: list[float]
    broker_order_id: str | None
    opened_at: str
    duration_minutes: float


class DayPnl(BaseModel):
    date: str
    pnl_usd: float


class TradeStats(BaseModel):
    total_trades: int
    open_trades: int
    closed_trades: int
    win_rate_pct: float
    total_pnl_usd: float
    avg_win_usd: float
    avg_loss_usd: float
    profit_factor: float
    avg_risk_reward: float
    largest_win_usd: float
    largest_loss_usd: float
    avg_duration_minutes: float
    measured_at: str

    # --- Phase 2 additions (additive only — existing fields above unchanged) ---
    expectancy_usd: float
    sharpe_ratio: float | None
    sortino_ratio: float | None
    calmar_ratio: float | None
    max_drawdown_pct: float
    avg_trade_duration_minutes: float
    best_day: DayPnl | None
    worst_day: DayPnl | None
    equity_usd: float
    realized_pnl_usd: float
    unrealized_pnl_usd: float
    daily_return_pct: float
    weekly_return_pct: float
    monthly_return_pct: float


class EquityCurvePoint(BaseModel):
    timestamp: str
    cumulative_pnl_usd: float
    drawdown_pct: float


class CalendarDay(BaseModel):
    date: str
    pnl_usd: float
    trade_count: int


class TradeCloseRequest(BaseModel):
    reason: str = "Manual close via API"


class TimelineEvent(BaseModel):
    event_type: str
    description: str
    occurred_at: str
    metadata: dict[str, Any]


class PaperExecuteRequest(BaseModel):
    """
    Everything needed to place a paper order for an already-computed AI
    signal — the frontend passes through whatever it already fetched for
    ConsensusPanel/TradeSignalPanel (RiskAssessmentResponse / TradeSignal)
    rather than this endpoint re-deriving entry/SL/TP itself.
    """

    symbol: str
    direction: str  # LONG | SHORT
    quantity: float
    entry_price: float | None = None  # informational only; fill price comes from the broker
    stop_loss: float
    take_profit: float
    consensus_direction: str | None = None
    consensus_confidence_pct: float | None = None
    proposal_id: str | None = None
    notes: str = ""


class PaperExecuteResponse(BaseModel):
    trade_id: str
    symbol: str
    direction: str
    quantity: float
    filled_price: float
    commission: float
    slippage: float
    stop_loss: float
    take_profit: float
    status: str
    opened_at: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _row_to_trade(row: asyncpg.Record) -> TradeResponse:
    return TradeResponse(
        trade_id=str(row["trade_id"]),
        symbol=row["symbol"],
        direction=row["direction"],
        entry_type=row.get("entry_type", "market"),
        entry_price=float(row["entry_price"]) if row["entry_price"] else None,
        filled_price=float(row["filled_price"]) if row["filled_price"] else None,
        quantity=float(row["quantity"]),
        stop_loss=float(row["stop_loss"]),
        take_profit_levels=row.get("take_profit_levels") or [],
        broker=row.get("broker", "unknown"),
        broker_order_id=row.get("broker_order_id"),
        status=row["status"],
        pnl_usd=float(row["pnl_usd"]) if row.get("pnl_usd") is not None else None,
        pnl_pct=float(row["pnl_pct"]) if row.get("pnl_pct") is not None else None,
        commission=float(row.get("commission", 0.0)),
        slippage=float(row.get("slippage", 0.0)),
        consensus_direction=row.get("consensus_direction"),
        consensus_confidence_pct=(
            float(row["consensus_confidence_pct"]) if row.get("consensus_confidence_pct") else None
        ),
        approval_id=row.get("approval_id"),
        opened_at=row["opened_at"].isoformat(),
        closed_at=row["closed_at"].isoformat() if row.get("closed_at") else None,
        notes=row.get("notes", ""),
    )


async def _auto_create_journal_entry(
    db: asyncpg.Connection,
    trade_row: asyncpg.Record,
    closed_at: datetime,
) -> None:
    """
    Populate a trade_journal row from the closed trade + its originating
    trade_proposal, reusing the consensus/agent_signals/risk_assessment
    JSONB already captured on the proposal rather than re-deriving them.

    Best-effort: any failure here must not break the close endpoint itself,
    since journaling is a convenience feature, not part of the execution
    path.
    """
    try:
        entry_price = float(trade_row["filled_price"]) if trade_row["filled_price"] else 0.0
        exit_price = entry_price  # no live price feed available at close time
        quantity = float(trade_row["quantity"])
        direction = trade_row["direction"]

        pnl_usd = (
            (exit_price - entry_price) * quantity
            if direction == "LONG"
            else (entry_price - exit_price) * quantity
        )
        outcome = "WIN" if pnl_usd > 0 else ("LOSS" if pnl_usd < 0 else "BE")

        proposal = None
        proposal_id = trade_row.get("proposal_id")
        if proposal_id:
            proposal = await db.fetchrow(
                """
                SELECT consensus_score, confidence_pct, agent_signals, risk_assessment
                FROM trade_proposals WHERE id = $1
                """,
                proposal_id,
            )

        agent_opinions = proposal["agent_signals"] if proposal and proposal["agent_signals"] else []
        risk_assessment = proposal["risk_assessment"] if proposal else None
        risk_score = None
        market_regime = None
        if risk_assessment:
            risk_score = risk_assessment.get("risk_score") if isinstance(risk_assessment, dict) else None
            market_regime = risk_assessment.get("market_regime") if isinstance(risk_assessment, dict) else None

        ai_confidence_pct = (
            float(proposal["confidence_pct"])
            if proposal and proposal["confidence_pct"] is not None
            else (
                float(trade_row["consensus_confidence_pct"])
                if trade_row.get("consensus_confidence_pct") is not None
                else None
            )
        )

        await db.execute(
            """
            INSERT INTO trade_journal (
                trade_id, symbol, direction, entry_price, exit_price,
                opened_at, closed_at, outcome, pnl_usd, ai_consensus_direction,
                ai_confidence_pct, agent_opinions, market_regime, risk_score
            )
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)
            """,
            trade_row["trade_id"],
            trade_row["symbol"],
            direction,
            entry_price,
            exit_price,
            trade_row.get("opened_at"),
            closed_at,
            outcome,
            round(pnl_usd, 8),
            trade_row.get("consensus_direction"),
            ai_confidence_pct,
            agent_opinions,
            market_regime,
            risk_score,
        )
    except Exception:
        logger.exception(
            "auto_journal_entry_failed trade_id=%s (non-fatal, close already committed)",
            trade_row.get("trade_id"),
        )


# ---------------------------------------------------------------------------
# GET /trades
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=list[TradeResponse],
    summary="Paginated trade history",
)
async def list_trades(
    symbol: str | None = Query(default=None),
    direction: str | None = Query(default=None, description="LONG | SHORT"),
    trade_status: str | None = Query(default=None, alias="status", description="open|closed|cancelled"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: asyncpg.Connection = Depends(get_db),
) -> list[TradeResponse]:
    conditions = []
    params: list[Any] = []
    idx = 1

    if symbol:
        conditions.append(f"symbol = ${idx}")
        params.append(symbol)
        idx += 1

    if direction:
        conditions.append(f"direction = ${idx}")
        params.append(direction.upper())
        idx += 1

    if trade_status:
        conditions.append(f"status = ${idx}")
        params.append(trade_status.lower())
        idx += 1

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    params += [limit, offset]
    rows = await db.fetch(
        f"""
        SELECT trade_id, symbol, direction, entry_type, entry_price, filled_price,
               quantity, stop_loss, take_profit_levels, broker, broker_order_id,
               status, pnl_usd, pnl_pct, commission, slippage,
               consensus_direction, consensus_confidence_pct, approval_id,
               opened_at, closed_at, notes
        FROM trades
        {where_clause}
        ORDER BY opened_at DESC
        LIMIT ${idx} OFFSET ${idx+1}
        """,
        *params,
    )

    return [_row_to_trade(r) for r in rows]


# ---------------------------------------------------------------------------
# GET /trades/open
# ---------------------------------------------------------------------------


@router.get(
    "/open",
    response_model=list[OpenPositionResponse],
    summary="All currently open positions",
)
async def get_open_positions(
    db: asyncpg.Connection = Depends(get_db),
) -> list[OpenPositionResponse]:
    rows = await db.fetch(
        """
        SELECT
            t.trade_id,
            t.symbol,
            t.direction,
            t.quantity,
            t.filled_price       AS entry_price,
            p.last_price         AS current_price,
            CASE
                WHEN t.direction = 'LONG'
                    THEN (p.last_price - t.filled_price) * t.quantity
                ELSE (t.filled_price - p.last_price) * t.quantity
            END                  AS unrealised_pnl_usd,
            CASE
                WHEN t.direction = 'LONG' AND t.filled_price > 0
                    THEN (p.last_price - t.filled_price) / t.filled_price * 100
                WHEN t.direction = 'SHORT' AND t.filled_price > 0
                    THEN (t.filled_price - p.last_price) / t.filled_price * 100
                ELSE NULL
            END                  AS unrealised_pnl_pct,
            t.stop_loss,
            t.take_profit_levels,
            t.broker_order_id,
            t.opened_at,
            EXTRACT(EPOCH FROM (NOW() - t.opened_at)) / 60 AS duration_minutes
        FROM trades t
        LEFT JOIN market_prices p ON p.symbol = t.symbol
        WHERE t.status = 'open'
        ORDER BY t.opened_at DESC
        """,
    )

    return [
        OpenPositionResponse(
            trade_id=str(r["trade_id"]),
            symbol=r["symbol"],
            direction=r["direction"],
            quantity=float(r["quantity"]),
            entry_price=float(r["entry_price"]) if r["entry_price"] else 0.0,
            current_price=float(r["current_price"]) if r["current_price"] else None,
            unrealised_pnl_usd=(
                float(r["unrealised_pnl_usd"]) if r["unrealised_pnl_usd"] is not None else None
            ),
            unrealised_pnl_pct=(
                float(r["unrealised_pnl_pct"]) if r["unrealised_pnl_pct"] is not None else None
            ),
            stop_loss=float(r["stop_loss"]),
            take_profit_levels=r["take_profit_levels"] or [],
            broker_order_id=r.get("broker_order_id"),
            opened_at=r["opened_at"].isoformat(),
            duration_minutes=float(r["duration_minutes"] or 0.0),
        )
        for r in rows
    ]


async def _fetch_daily_pnl_series(
    db: asyncpg.Connection,
    where: str,
    params: list[Any],
) -> list[tuple[Any, float]]:
    """
    Closed-trade PnL bucketed by the UTC date the trade closed on, ascending.
    Used as the return series feeding Sharpe/Sortino/Calmar/drawdown/best-worst
    day — this project has no continuously-marked equity history for closed
    trades, so daily realized PnL is the best available proxy for a return
    series.
    """
    rows = await db.fetch(
        f"""
        SELECT date_trunc('day', closed_at) AS day, SUM(pnl_usd) AS pnl
        FROM trades
        {where}
        GROUP BY day
        ORDER BY day ASC
        """,
        *params,
    )
    return [(r["day"], float(r["pnl"] or 0.0)) for r in rows]


async def _fetch_equity_usd(db: asyncpg.Connection) -> float | None:
    """
    Latest recorded equity, reused from the same `portfolio_equity` table
    api/routers/portfolio.py reads from (avoids a second source of truth).
    Returns None if the table doesn't exist / has no rows yet.
    """
    try:
        row = await db.fetchrow(
            "SELECT equity_usd FROM portfolio_equity ORDER BY recorded_at DESC LIMIT 1"
        )
        return float(row["equity_usd"]) if row and row["equity_usd"] is not None else None
    except Exception:
        return None


# Trading days per year assumed for annualizing Sharpe/Sortino/Calmar.
# Crypto markets trade continuously (no weekends/holidays), unlike equities'
# conventional 252 — see module docstring / phase notes.
_ANNUALIZATION_DAYS = 365


def _compute_risk_adjusted_metrics(
    daily_pnls: list[float],
    equity_base: float,
) -> dict[str, float | None]:
    """
    Sharpe/Sortino/Calmar computed off daily-bucketed realized PnL expressed
    as a fraction of `equity_base` (current equity, or the closed-trade PnL
    range as a fallback when no equity snapshot exists). Risk-free rate is
    assumed to be 0 — this is a research/analytics figure, not a regulatory
    one. Annualized using sqrt(365) for Sharpe/Sortino (crypto trades every
    calendar day).
    """
    if not daily_pnls or equity_base <= 0:
        return {
            "sharpe_ratio": None,
            "sortino_ratio": None,
            "calmar_ratio": None,
            "max_drawdown_pct": 0.0,
        }

    daily_returns = [p / equity_base for p in daily_pnls]

    mean_return = statistics.mean(daily_returns)
    stdev_return = statistics.pstdev(daily_returns) if len(daily_returns) > 1 else 0.0
    sharpe = (
        (mean_return / stdev_return) * (_ANNUALIZATION_DAYS ** 0.5)
        if stdev_return > 0
        else None
    )

    downside = [r for r in daily_returns if r < 0]
    downside_dev = statistics.pstdev(downside) if len(downside) > 1 else (abs(downside[0]) if downside else 0.0)
    sortino = (
        (mean_return / downside_dev) * (_ANNUALIZATION_DAYS ** 0.5)
        if downside_dev > 0
        else None
    )

    # Max drawdown off the cumulative equity curve (equity_base + running sum).
    cumulative = equity_base
    peak = equity_base
    max_dd_pct = 0.0
    for pnl in daily_pnls:
        cumulative += pnl
        peak = max(peak, cumulative)
        if peak > 0:
            dd_pct = (peak - cumulative) / peak * 100.0
            max_dd_pct = max(max_dd_pct, dd_pct)

    annualized_return = mean_return * _ANNUALIZATION_DAYS
    calmar = (annualized_return * 100.0) / max_dd_pct if max_dd_pct > 0 else None

    return {
        "sharpe_ratio": round(sharpe, 3) if sharpe is not None else None,
        "sortino_ratio": round(sortino, 3) if sortino is not None else None,
        "calmar_ratio": round(calmar, 3) if calmar is not None else None,
        "max_drawdown_pct": round(max_dd_pct, 3),
    }


# ---------------------------------------------------------------------------
# GET /trades/stats
# ---------------------------------------------------------------------------


@router.get(
    "/stats",
    response_model=TradeStats,
    summary="Aggregate trading performance statistics",
)
async def get_trade_stats(
    symbol: str | None = Query(default=None),
    since: str | None = Query(default=None, description="ISO datetime filter (e.g. 2024-01-01T00:00:00Z)"),
    db: asyncpg.Connection = Depends(get_db),
) -> TradeStats:
    params: list[Any] = []
    conditions = ["status = 'closed'"]
    idx = 1

    if symbol:
        conditions.append(f"symbol = ${idx}")
        params.append(symbol)
        idx += 1

    if since:
        conditions.append(f"opened_at >= ${idx}")
        params.append(since)
        idx += 1

    where = f"WHERE {' AND '.join(conditions)}"

    row = await db.fetchrow(
        f"""
        SELECT
            COUNT(*)                                               AS total_closed,
            COUNT(*) FILTER (WHERE pnl_usd > 0)                   AS wins,
            SUM(pnl_usd)                                          AS total_pnl,
            AVG(pnl_usd) FILTER (WHERE pnl_usd > 0)              AS avg_win,
            AVG(pnl_usd) FILTER (WHERE pnl_usd <= 0)             AS avg_loss,
            MAX(pnl_usd)                                          AS largest_win,
            MIN(pnl_usd)                                          AS largest_loss,
            AVG(EXTRACT(EPOCH FROM (closed_at - opened_at)) / 60) AS avg_duration_min,
            SUM(pnl_usd) FILTER (WHERE pnl_usd > 0)              AS gross_profit,
            ABS(SUM(pnl_usd) FILTER (WHERE pnl_usd <= 0))        AS gross_loss,
            AVG(consensus_confidence_pct)                          AS avg_rr
        FROM trades
        {where}
        """,
        *params,
    )

    open_count_row = await db.fetchrow(
        "SELECT COUNT(*) AS cnt FROM trades WHERE status = 'open'"
    )
    open_count = int(open_count_row["cnt"]) if open_count_row else 0

    total = int(row["total_closed"]) if row else 0
    wins = int(row["wins"]) if row and row["wins"] else 0
    gross_profit = float(row["gross_profit"] or 0.0)
    gross_loss = float(row["gross_loss"] or 0.0)

    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    win_rate = wins / total if total > 0 else 0.0
    avg_win = float(row["avg_win"] or 0.0) if row else 0.0
    avg_loss = float(row["avg_loss"] or 0.0) if row else 0.0
    # Expectancy: expected $ per trade given the observed win rate and avg win/loss.
    expectancy_usd = (win_rate * avg_win) + ((1 - win_rate) * avg_loss)

    daily_series = await _fetch_daily_pnl_series(db, where, params)
    daily_pnls = [pnl for _, pnl in daily_series]

    equity_usd = await _fetch_equity_usd(db)
    total_pnl_usd = float(row["total_pnl"] or 0.0) if row else 0.0
    # Fall back to a synthetic equity base (starting capital implied by
    # closed PnL) when no portfolio_equity snapshot exists yet, so Sharpe/
    # Sortino/Calmar remain computable rather than always None.
    equity_base = equity_usd if equity_usd is not None else max(abs(total_pnl_usd) * 10, 10_000.0)

    risk_metrics = _compute_risk_adjusted_metrics(daily_pnls, equity_base)

    best_day = None
    worst_day = None
    if daily_series:
        best = max(daily_series, key=lambda d: d[1])
        worst = min(daily_series, key=lambda d: d[1])
        best_day = DayPnl(date=best[0].date().isoformat(), pnl_usd=round(best[1], 2))
        worst_day = DayPnl(date=worst[0].date().isoformat(), pnl_usd=round(worst[1], 2))

    # Unrealized PnL from currently open positions (mirrors /trades/open's calc).
    unrealized_row = await db.fetchrow(
        """
        SELECT SUM(
            CASE
                WHEN t.direction = 'LONG'  THEN (COALESCE(p.last_price, t.filled_price) - t.filled_price) * t.quantity
                WHEN t.direction = 'SHORT' THEN (t.filled_price - COALESCE(p.last_price, t.filled_price)) * t.quantity
                ELSE 0
            END
        ) AS unrealized_pnl
        FROM trades t
        LEFT JOIN market_prices p ON p.symbol = t.symbol
        WHERE t.status = 'open'
        """
    )
    unrealized_pnl_usd = float(unrealized_row["unrealized_pnl"] or 0.0) if unrealized_row else 0.0

    def _windowed_pnl(days: int) -> float:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        cutoff_pnls = [
            pnl for day, pnl in daily_series
            if (day if day.tzinfo else day.replace(tzinfo=timezone.utc)) >= cutoff
        ]
        return sum(cutoff_pnls)

    daily_pnl = daily_series[-1][1] if daily_series else 0.0
    weekly_pnl = _windowed_pnl(7)
    monthly_pnl = _windowed_pnl(30)

    return TradeStats(
        total_trades=total + open_count,
        open_trades=open_count,
        closed_trades=total,
        win_rate_pct=round(win_rate * 100.0, 2),
        total_pnl_usd=total_pnl_usd,
        avg_win_usd=avg_win,
        avg_loss_usd=avg_loss,
        profit_factor=round(profit_factor, 3),
        avg_risk_reward=float(row["avg_rr"] or 0.0) if row else 0.0,
        largest_win_usd=float(row["largest_win"] or 0.0) if row else 0.0,
        largest_loss_usd=float(row["largest_loss"] or 0.0) if row else 0.0,
        avg_duration_minutes=float(row["avg_duration_min"] or 0.0) if row else 0.0,
        measured_at=datetime.now(timezone.utc).isoformat(),
        expectancy_usd=round(expectancy_usd, 2),
        sharpe_ratio=risk_metrics["sharpe_ratio"],
        sortino_ratio=risk_metrics["sortino_ratio"],
        calmar_ratio=risk_metrics["calmar_ratio"],
        max_drawdown_pct=risk_metrics["max_drawdown_pct"],
        avg_trade_duration_minutes=float(row["avg_duration_min"] or 0.0) if row else 0.0,
        best_day=best_day,
        worst_day=worst_day,
        equity_usd=round(equity_base, 2),
        realized_pnl_usd=total_pnl_usd,
        unrealized_pnl_usd=round(unrealized_pnl_usd, 2),
        daily_return_pct=round(daily_pnl / equity_base * 100.0, 4) if equity_base > 0 else 0.0,
        weekly_return_pct=round(weekly_pnl / equity_base * 100.0, 4) if equity_base > 0 else 0.0,
        monthly_return_pct=round(monthly_pnl / equity_base * 100.0, 4) if equity_base > 0 else 0.0,
    )


# ---------------------------------------------------------------------------
# GET /trades/equity-curve
# ---------------------------------------------------------------------------


@router.get(
    "/equity-curve",
    response_model=list[EquityCurvePoint],
    summary="Cumulative equity / drawdown time series from closed-trade PnL",
)
async def get_equity_curve(
    symbol: str | None = Query(default=None),
    since: str | None = Query(default=None, description="ISO datetime filter (e.g. 2024-01-01T00:00:00Z)"),
    db: asyncpg.Connection = Depends(get_db),
) -> list[EquityCurvePoint]:
    params: list[Any] = []
    conditions = ["status = 'closed'", "closed_at IS NOT NULL"]
    idx = 1

    if symbol:
        conditions.append(f"symbol = ${idx}")
        params.append(symbol)
        idx += 1

    if since:
        conditions.append(f"opened_at >= ${idx}")
        params.append(since)
        idx += 1

    where = f"WHERE {' AND '.join(conditions)}"
    daily_series = await _fetch_daily_pnl_series(db, where, params)

    equity_usd = await _fetch_equity_usd(db)
    total_pnl = sum(pnl for _, pnl in daily_series)
    equity_base = equity_usd if equity_usd is not None else max(abs(total_pnl) * 10, 10_000.0)

    points: list[EquityCurvePoint] = []
    cumulative = 0.0
    peak = equity_base
    for day, pnl in daily_series:
        cumulative += pnl
        current_equity = equity_base + cumulative
        peak = max(peak, current_equity)
        drawdown_pct = (peak - current_equity) / peak * 100.0 if peak > 0 else 0.0
        points.append(
            EquityCurvePoint(
                timestamp=day.isoformat(),
                cumulative_pnl_usd=round(cumulative, 2),
                drawdown_pct=round(drawdown_pct, 3),
            )
        )

    return points


# ---------------------------------------------------------------------------
# GET /trades/calendar
# ---------------------------------------------------------------------------


@router.get(
    "/calendar",
    response_model=list[CalendarDay],
    summary="Daily PnL bucketed by date, for a monthly-heatmap-style calendar",
)
async def get_trade_calendar(
    symbol: str | None = Query(default=None),
    since: str | None = Query(default=None, description="ISO datetime filter (e.g. 2024-01-01T00:00:00Z)"),
    until: str | None = Query(default=None, description="ISO datetime filter (e.g. 2024-12-31T23:59:59Z)"),
    db: asyncpg.Connection = Depends(get_db),
) -> list[CalendarDay]:
    params: list[Any] = []
    conditions = ["status = 'closed'", "closed_at IS NOT NULL"]
    idx = 1

    if symbol:
        conditions.append(f"symbol = ${idx}")
        params.append(symbol)
        idx += 1

    if since:
        conditions.append(f"closed_at >= ${idx}")
        params.append(since)
        idx += 1

    if until:
        conditions.append(f"closed_at <= ${idx}")
        params.append(until)
        idx += 1

    where = f"WHERE {' AND '.join(conditions)}"

    rows = await db.fetch(
        f"""
        SELECT date_trunc('day', closed_at) AS day, SUM(pnl_usd) AS pnl, COUNT(*) AS cnt
        FROM trades
        {where}
        GROUP BY day
        ORDER BY day ASC
        """,
        *params,
    )

    return [
        CalendarDay(
            date=r["day"].date().isoformat(),
            pnl_usd=round(float(r["pnl"] or 0.0), 2),
            trade_count=int(r["cnt"]),
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# GET /trades/{trade_id}
# ---------------------------------------------------------------------------


@router.get(
    "/{trade_id}",
    response_model=TradeResponse,
    summary="Get a specific trade by ID",
)
async def get_trade(
    trade_id: str,
    db: asyncpg.Connection = Depends(get_db),
) -> TradeResponse:
    row = await db.fetchrow(
        """
        SELECT trade_id, symbol, direction, entry_type, entry_price, filled_price,
               quantity, stop_loss, take_profit_levels, broker, broker_order_id,
               status, pnl_usd, pnl_pct, commission, slippage,
               consensus_direction, consensus_confidence_pct, approval_id,
               opened_at, closed_at, notes
        FROM trades
        WHERE trade_id = $1
        """,
        trade_id,
    )

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trade '{trade_id}' not found.",
        )

    return _row_to_trade(row)


# ---------------------------------------------------------------------------
# GET /trades/{trade_id}/timeline
# ---------------------------------------------------------------------------


@router.get(
    "/{trade_id}/timeline",
    response_model=list[TimelineEvent],
    summary="Full execution timeline for a trade",
)
async def get_trade_timeline(
    trade_id: str,
    db: asyncpg.Connection = Depends(get_db),
) -> list[TimelineEvent]:
    # Verify the trade exists
    exists = await db.fetchval(
        "SELECT COUNT(*) FROM trades WHERE trade_id = $1", trade_id
    )
    if not exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trade '{trade_id}' not found.",
        )

    rows = await db.fetch(
        """
        SELECT event_type, description, occurred_at, metadata
        FROM trade_events
        WHERE trade_id = $1
        ORDER BY occurred_at ASC
        """,
        trade_id,
    )

    return [
        TimelineEvent(
            event_type=r["event_type"],
            description=r["description"],
            occurred_at=r["occurred_at"].isoformat(),
            metadata=r["metadata"] or {},
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# POST /trades/{trade_id}/close
# ---------------------------------------------------------------------------


@router.post(
    "/{trade_id}/close",
    summary="Manually close an open position (paper mode only)",
)
async def close_position(
    trade_id: str,
    body: TradeCloseRequest,
    db: asyncpg.Connection = Depends(get_db),
) -> dict[str, Any]:
    from config.settings import get_settings

    settings = get_settings()
    if settings.is_live:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Manual position close is not permitted in live mode.",
        )

    row = await db.fetchrow(
        """
        SELECT trade_id, symbol, status, filled_price, quantity, direction,
               stop_loss, take_profit_levels, opened_at, proposal_id,
               consensus_direction, consensus_confidence_pct
        FROM trades WHERE trade_id = $1
        """,
        trade_id,
    )

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trade '{trade_id}' not found.",
        )

    if row["status"] != "open":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Trade '{trade_id}' is not open (status: {row['status']}).",
        )

    closed_at = datetime.now(timezone.utc)

    await db.execute(
        """
        UPDATE trades
        SET status = 'closed',
            closed_at = $1,
            notes = CONCAT(COALESCE(notes, ''), ' | Manual close: ', $2)
        WHERE trade_id = $3
        """,
        closed_at,
        body.reason,
        trade_id,
    )

    await db.execute(
        """
        INSERT INTO trade_events (trade_id, event_type, description, occurred_at, metadata)
        VALUES ($1, 'manual_close', $2, $3, $4)
        """,
        trade_id,
        f"Position manually closed via API: {body.reason}",
        closed_at,
        {"reason": body.reason, "operator": "api_user"},
    )

    logger.info("Trade %s manually closed: %s", trade_id, body.reason)

    await _auto_create_journal_entry(db, row, closed_at)

    # Phase 3: alert-center hook, mirroring the _auto_create_journal_entry
    # precedent above — best-effort, never raises into this endpoint.
    try:
        from alerts.generator import generate_trade_close_alert

        direction = row["direction"]
        # Mirrors _auto_create_journal_entry's own note: no live price feed
        # is available at manual-close time, so PnL here is an estimate.
        pnl_usd = 0.0
        await generate_trade_close_alert(
            db,
            symbol=row["symbol"],
            direction=direction,
            pnl_usd=pnl_usd,
            reason=body.reason,
            trade_id=trade_id,
        )
    except Exception:
        logger.exception("Alert generation failed for trade close %s", trade_id)

    return {
        "trade_id": trade_id,
        "status": "closed",
        "closed_at": closed_at.isoformat(),
        "reason": body.reason,
        "message": "Position closed successfully.",
    }


# ---------------------------------------------------------------------------
# POST /trades/paper/execute
# ---------------------------------------------------------------------------


@router.post(
    "/paper/execute",
    response_model=PaperExecuteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Execute an AI signal against the paper broker",
)
async def execute_paper_trade(
    body: PaperExecuteRequest,
    db: asyncpg.Connection = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
) -> PaperExecuteResponse:
    """
    Paper-only execution path: the "Execute on Paper" button in the Trading
    Execution hub calls this. Order of operations is deliberate —
    1) staleness gate (never trade on stale/disconnected live data),
    2) PaperBroker.place_order (real Redis-persisted simulated fill),
    3) persist a row in `trades` the same shape the rest of the platform
       (journal auto-create, /trades/stats, /trades/open) already reads.
    Never permitted outside paper/dev environments.
    """
    from brokers.paper_broker import PaperBroker
    from config.settings import get_settings
    from risk.circuit_breakers import MarketDataStalenessGate, StaleMarketDataError

    settings = get_settings()
    if settings.is_live:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Paper execution is not available in live mode — no live broker is wired up.",
        )

    direction = body.direction.upper()
    if direction not in ("LONG", "SHORT"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="direction must be 'LONG' or 'SHORT'.",
        )
    if body.quantity <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="quantity must be positive.",
        )

    gate = MarketDataStalenessGate(redis)
    try:
        await gate.assert_fresh_or_raise(body.symbol)
    except StaleMarketDataError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Refusing to execute — market data for {body.symbol} is stale: {exc}",
        ) from exc

    broker = PaperBroker(redis_client=redis)
    await broker.initialise()

    side = "buy" if direction == "LONG" else "sell"
    result = await broker.place_order(body.symbol, side, body.quantity, order_type="market")

    if not result.success or result.filled_price is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.error or "Paper order was not filled.",
        )

    opened_at = datetime.now(timezone.utc)
    row = await db.fetchrow(
        """
        INSERT INTO trades (
            proposal_id, symbol, direction, entry_type, quantity,
            entry_price, filled_price, stop_loss, take_profit,
            take_profit_levels, broker, broker_order_id, status,
            commission, slippage, consensus_direction,
            consensus_confidence_pct, opened_at, notes
        )
        VALUES (
            $1, $2, $3, 'market', $4,
            $5, $5, $6, $7,
            ARRAY[$7]::DECIMAL(24,8)[], 'paper', $8, 'open',
            $9, $10, $11,
            $12, $13, $14
        )
        RETURNING trade_id, opened_at
        """,
        body.proposal_id,
        body.symbol,
        direction,
        body.quantity,
        result.filled_price,
        body.stop_loss,
        body.take_profit,
        result.order_id,
        result.commission,
        result.slippage,
        body.consensus_direction,
        body.consensus_confidence_pct,
        opened_at,
        body.notes,
    )

    trade_id = str(row["trade_id"])

    await db.execute(
        """
        INSERT INTO trade_events (trade_id, event_type, description, occurred_at, metadata)
        VALUES ($1, 'paper_execution', $2, $3, $4)
        """,
        row["trade_id"],
        f"Paper {side} {body.quantity} {body.symbol} @ {result.filled_price:.6f}",
        opened_at,
        {
            "broker": "paper",
            "order_id": result.order_id,
            "commission": result.commission,
            "slippage": result.slippage,
        },
    )

    logger.info(
        "Paper trade executed: trade_id=%s symbol=%s direction=%s qty=%.6f fill=%.6f",
        trade_id, body.symbol, direction, body.quantity, result.filled_price,
    )

    return PaperExecuteResponse(
        trade_id=trade_id,
        symbol=body.symbol,
        direction=direction,
        quantity=body.quantity,
        filled_price=result.filled_price,
        commission=result.commission,
        slippage=result.slippage,
        stop_loss=body.stop_loss,
        take_profit=body.take_profit,
        status="open",
        opened_at=row["opened_at"].isoformat(),
    )
