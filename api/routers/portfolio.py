"""
api/routers/portfolio.py
=========================
Portfolio state and performance analytics endpoints.

Endpoints
---------
GET /portfolio                          — current portfolio snapshot
GET /portfolio/history                  — equity curve (time series)
GET /portfolio/performance              — detailed performance metrics
GET /portfolio/risk-exposure            — current risk exposure breakdown
GET /portfolio/drawdown                 — drawdown analysis
GET /portfolio/allocation               — allocation by symbol / direction / broker
                                           (includes a diversification_score,
                                           1 - Herfindahl index over symbol weights)
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from api.dependencies import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class PortfolioSnapshot(BaseModel):
    equity_usd: float
    cash_usd: float
    open_positions_value_usd: float
    unrealised_pnl_usd: float
    unrealised_pnl_pct: float
    total_pnl_usd: float
    total_pnl_pct: float
    portfolio_heat_pct: float
    open_positions_count: int
    win_rate_pct: float
    daily_pnl_usd: float
    weekly_pnl_usd: float
    monthly_pnl_usd: float
    max_drawdown_pct: float
    sharpe_ratio: float | None
    snapshot_at: str


class EquityCurvePoint(BaseModel):
    timestamp: str
    equity_usd: float
    daily_pnl_usd: float
    cumulative_pnl_usd: float
    drawdown_pct: float
    open_positions: int


class PerformanceMetrics(BaseModel):
    total_trades: int
    win_rate_pct: float
    profit_factor: float
    sharpe_ratio: float | None
    sortino_ratio: float | None
    max_drawdown_pct: float
    max_drawdown_duration_days: float | None
    avg_win_usd: float
    avg_loss_usd: float
    avg_trade_duration_minutes: float
    largest_win_usd: float
    largest_loss_usd: float
    expectancy_usd: float
    calmar_ratio: float | None
    total_commission_usd: float
    total_slippage_usd: float
    measured_at: str


class RiskExposureEntry(BaseModel):
    symbol: str
    direction: str
    position_size_usd: float
    risk_usd: float
    risk_pct_of_equity: float
    stop_loss: float
    entry_price: float


class RiskExposure(BaseModel):
    total_exposure_usd: float
    total_risk_usd: float
    portfolio_heat_pct: float
    positions: list[RiskExposureEntry]
    measured_at: str


class DrawdownAnalysis(BaseModel):
    current_drawdown_pct: float
    max_drawdown_pct: float
    max_drawdown_from_date: str | None
    max_drawdown_to_date: str | None
    max_drawdown_duration_days: float | None
    recovery_factor: float | None
    periods: list[dict[str, Any]]
    analysed_at: str


class AllocationBreakdown(BaseModel):
    by_symbol: dict[str, float]
    by_direction: dict[str, float]
    by_broker: dict[str, float]
    diversification_score: float
    calculated_at: str


# ---------------------------------------------------------------------------
# GET /portfolio
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=PortfolioSnapshot,
    summary="Current portfolio snapshot",
)
async def get_portfolio(
    db: asyncpg.Connection = Depends(get_db),
) -> PortfolioSnapshot:
    row = await db.fetchrow(
        """
        WITH open_pos AS (
            SELECT
                SUM(filled_price * quantity) AS open_value,
                SUM(
                    CASE direction
                        WHEN 'LONG'  THEN (COALESCE(mp.last_price, filled_price) - filled_price) * quantity
                        WHEN 'SHORT' THEN (filled_price - COALESCE(mp.last_price, filled_price)) * quantity
                    END
                ) AS unrealised_pnl,
                SUM(ABS(filled_price - stop_loss) * quantity) AS total_risk,
                COUNT(*) AS pos_count
            FROM trades t
            LEFT JOIN market_prices mp ON mp.symbol = t.symbol
            WHERE t.status = 'open'
        ),
        closed_pnl AS (
            SELECT
                SUM(pnl_usd) AS total_closed_pnl,
                SUM(pnl_usd) FILTER (WHERE opened_at >= NOW() - INTERVAL '1 day') AS daily_pnl,
                SUM(pnl_usd) FILTER (WHERE opened_at >= NOW() - INTERVAL '7 days') AS weekly_pnl,
                SUM(pnl_usd) FILTER (WHERE opened_at >= NOW() - INTERVAL '30 days') AS monthly_pnl,
                COUNT(*) FILTER (WHERE status = 'closed')   AS total_closed,
                COUNT(*) FILTER (WHERE status = 'closed' AND pnl_usd > 0) AS wins,
                MAX(pnl_usd) - MIN(pnl_usd) AS pnl_range
            FROM trades
            WHERE status = 'closed'
        ),
        equity_info AS (
            SELECT equity_usd, initial_equity_usd
            FROM portfolio_equity
            ORDER BY recorded_at DESC
            LIMIT 1
        ),
        dd AS (
            SELECT MAX(drawdown_pct) AS max_dd
            FROM portfolio_equity_history
        )
        SELECT
            ei.equity_usd,
            ei.equity_usd - op.open_value                           AS cash_usd,
            COALESCE(op.open_value, 0)                              AS open_positions_value,
            COALESCE(op.unrealised_pnl, 0)                          AS unrealised_pnl,
            CASE WHEN ei.equity_usd > 0
                 THEN COALESCE(op.unrealised_pnl, 0) / ei.equity_usd * 100
                 ELSE 0 END                                         AS unrealised_pnl_pct,
            COALESCE(cp.total_closed_pnl, 0) + COALESCE(op.unrealised_pnl, 0) AS total_pnl,
            CASE WHEN ei.initial_equity_usd > 0
                 THEN (COALESCE(cp.total_closed_pnl, 0) + COALESCE(op.unrealised_pnl, 0))
                      / ei.initial_equity_usd * 100
                 ELSE 0 END                                         AS total_pnl_pct,
            CASE WHEN ei.equity_usd > 0
                 THEN COALESCE(op.total_risk, 0) / ei.equity_usd * 100
                 ELSE 0 END                                         AS portfolio_heat_pct,
            COALESCE(op.pos_count, 0)                               AS open_pos_count,
            CASE WHEN COALESCE(cp.total_closed, 0) > 0
                 THEN COALESCE(cp.wins, 0)::float / cp.total_closed * 100
                 ELSE 0 END                                         AS win_rate_pct,
            COALESCE(cp.daily_pnl, 0)                               AS daily_pnl,
            COALESCE(cp.weekly_pnl, 0)                              AS weekly_pnl,
            COALESCE(cp.monthly_pnl, 0)                             AS monthly_pnl,
            COALESCE(dd.max_dd, 0)                                  AS max_drawdown_pct
        FROM equity_info ei
        CROSS JOIN open_pos op
        CROSS JOIN closed_pnl cp
        CROSS JOIN dd
        """,
    )

    now = datetime.now(timezone.utc).isoformat()
    if row is None:
        return PortfolioSnapshot(
            equity_usd=0.0, cash_usd=0.0, open_positions_value_usd=0.0,
            unrealised_pnl_usd=0.0, unrealised_pnl_pct=0.0,
            total_pnl_usd=0.0, total_pnl_pct=0.0, portfolio_heat_pct=0.0,
            open_positions_count=0, win_rate_pct=0.0,
            daily_pnl_usd=0.0, weekly_pnl_usd=0.0, monthly_pnl_usd=0.0,
            max_drawdown_pct=0.0, sharpe_ratio=None, snapshot_at=now,
        )

    return PortfolioSnapshot(
        equity_usd=float(row["equity_usd"] or 0.0),
        cash_usd=float(row["cash_usd"] or 0.0),
        open_positions_value_usd=float(row["open_positions_value"] or 0.0),
        unrealised_pnl_usd=float(row["unrealised_pnl"] or 0.0),
        unrealised_pnl_pct=float(row["unrealised_pnl_pct"] or 0.0),
        total_pnl_usd=float(row["total_pnl"] or 0.0),
        total_pnl_pct=float(row["total_pnl_pct"] or 0.0),
        portfolio_heat_pct=float(row["portfolio_heat_pct"] or 0.0),
        open_positions_count=int(row["open_pos_count"] or 0),
        win_rate_pct=float(row["win_rate_pct"] or 0.0),
        daily_pnl_usd=float(row["daily_pnl"] or 0.0),
        weekly_pnl_usd=float(row["weekly_pnl"] or 0.0),
        monthly_pnl_usd=float(row["monthly_pnl"] or 0.0),
        max_drawdown_pct=float(row["max_drawdown_pct"] or 0.0),
        sharpe_ratio=None,
        snapshot_at=now,
    )


# ---------------------------------------------------------------------------
# GET /portfolio/history
# ---------------------------------------------------------------------------


@router.get(
    "/history",
    response_model=list[EquityCurvePoint],
    summary="Equity curve time series",
)
async def get_equity_history(
    interval: str = Query(default="1d", description="Aggregation interval: 1h | 4h | 1d | 1w"),
    limit: int = Query(default=90, ge=1, le=3650),
    db: asyncpg.Connection = Depends(get_db),
) -> list[EquityCurvePoint]:
    interval_map = {"1h": "1 hour", "4h": "4 hours", "1d": "1 day", "1w": "1 week"}
    pg_interval = interval_map.get(interval, "1 day")

    rows = await db.fetch(
        """
        SELECT
            date_trunc($1, recorded_at)  AS bucket,
            AVG(equity_usd)              AS equity,
            SUM(daily_pnl_usd)           AS daily_pnl,
            SUM(daily_pnl_usd) OVER (ORDER BY date_trunc($1, recorded_at)) AS cum_pnl,
            AVG(drawdown_pct)            AS drawdown,
            AVG(open_positions_count)    AS open_positions
        FROM portfolio_equity_history
        GROUP BY date_trunc($1, recorded_at)
        ORDER BY bucket DESC
        LIMIT $2
        """,
        pg_interval,
        limit,
    )

    return [
        EquityCurvePoint(
            timestamp=r["bucket"].isoformat(),
            equity_usd=float(r["equity"] or 0.0),
            daily_pnl_usd=float(r["daily_pnl"] or 0.0),
            cumulative_pnl_usd=float(r["cum_pnl"] or 0.0),
            drawdown_pct=float(r["drawdown"] or 0.0),
            open_positions=int(r["open_positions"] or 0),
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# GET /portfolio/performance
# ---------------------------------------------------------------------------


@router.get(
    "/performance",
    response_model=PerformanceMetrics,
    summary="Detailed portfolio performance metrics",
)
async def get_performance(
    db: asyncpg.Connection = Depends(get_db),
) -> PerformanceMetrics:
    row = await db.fetchrow(
        """
        SELECT
            COUNT(*)                                            AS total_trades,
            COUNT(*) FILTER (WHERE pnl_usd > 0)                AS wins,
            SUM(pnl_usd) FILTER (WHERE pnl_usd > 0)           AS gross_profit,
            ABS(SUM(pnl_usd) FILTER (WHERE pnl_usd <= 0))     AS gross_loss,
            AVG(pnl_usd) FILTER (WHERE pnl_usd > 0)           AS avg_win,
            AVG(pnl_usd) FILTER (WHERE pnl_usd <= 0)          AS avg_loss,
            MAX(pnl_usd)                                       AS largest_win,
            MIN(pnl_usd)                                       AS largest_loss,
            AVG(EXTRACT(EPOCH FROM (closed_at - opened_at)) / 60) AS avg_duration,
            SUM(commission)                                    AS total_commission,
            SUM(slippage)                                      AS total_slippage
        FROM trades
        WHERE status = 'closed'
        """,
    )

    dd_row = await db.fetchrow(
        "SELECT MAX(drawdown_pct) AS max_dd FROM portfolio_equity_history"
    )

    now = datetime.now(timezone.utc).isoformat()
    total = int(row["total_trades"]) if row else 0
    wins = int(row["wins"]) if row and row["wins"] else 0
    gross_profit = float(row["gross_profit"] or 0.0) if row else 0.0
    gross_loss = float(row["gross_loss"] or 0.0) if row else 0.0
    avg_win = float(row["avg_win"] or 0.0) if row else 0.0
    avg_loss = float(row["avg_loss"] or 0.0) if row else 0.0

    win_rate = wins / total if total > 0 else 0.0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")
    expectancy = (win_rate * avg_win) + ((1 - win_rate) * avg_loss)

    return PerformanceMetrics(
        total_trades=total,
        win_rate_pct=round(win_rate * 100, 2),
        profit_factor=round(profit_factor, 3),
        sharpe_ratio=None,
        sortino_ratio=None,
        max_drawdown_pct=float(dd_row["max_dd"] or 0.0) if dd_row else 0.0,
        max_drawdown_duration_days=None,
        avg_win_usd=round(avg_win, 4),
        avg_loss_usd=round(avg_loss, 4),
        avg_trade_duration_minutes=float(row["avg_duration"] or 0.0) if row else 0.0,
        largest_win_usd=float(row["largest_win"] or 0.0) if row else 0.0,
        largest_loss_usd=float(row["largest_loss"] or 0.0) if row else 0.0,
        expectancy_usd=round(expectancy, 4),
        calmar_ratio=None,
        total_commission_usd=float(row["total_commission"] or 0.0) if row else 0.0,
        total_slippage_usd=float(row["total_slippage"] or 0.0) if row else 0.0,
        measured_at=now,
    )


# ---------------------------------------------------------------------------
# GET /portfolio/risk-exposure
# ---------------------------------------------------------------------------


@router.get(
    "/risk-exposure",
    response_model=RiskExposure,
    summary="Current risk exposure breakdown by position",
)
async def get_risk_exposure(
    db: asyncpg.Connection = Depends(get_db),
) -> RiskExposure:
    equity_row = await db.fetchrow(
        "SELECT equity_usd FROM portfolio_equity ORDER BY recorded_at DESC LIMIT 1"
    )
    equity = float(equity_row["equity_usd"]) if equity_row else 10_000.0

    rows = await db.fetch(
        """
        SELECT
            t.symbol,
            t.direction,
            t.filled_price * t.quantity               AS position_size_usd,
            ABS(t.filled_price - t.stop_loss) * t.quantity AS risk_usd,
            t.stop_loss,
            t.filled_price                             AS entry_price
        FROM trades t
        WHERE t.status = 'open'
        ORDER BY risk_usd DESC
        """,
    )

    positions: list[RiskExposureEntry] = [
        RiskExposureEntry(
            symbol=r["symbol"],
            direction=r["direction"],
            position_size_usd=float(r["position_size_usd"] or 0.0),
            risk_usd=float(r["risk_usd"] or 0.0),
            risk_pct_of_equity=float(r["risk_usd"] or 0.0) / equity * 100 if equity > 0 else 0.0,
            stop_loss=float(r["stop_loss"]),
            entry_price=float(r["entry_price"]),
        )
        for r in rows
    ]

    total_exposure = sum(p.position_size_usd for p in positions)
    total_risk = sum(p.risk_usd for p in positions)
    heat_pct = total_risk / equity * 100 if equity > 0 else 0.0

    return RiskExposure(
        total_exposure_usd=round(total_exposure, 4),
        total_risk_usd=round(total_risk, 4),
        portfolio_heat_pct=round(heat_pct, 2),
        positions=positions,
        measured_at=datetime.now(timezone.utc).isoformat(),
    )


# ---------------------------------------------------------------------------
# GET /portfolio/drawdown
# ---------------------------------------------------------------------------


@router.get(
    "/drawdown",
    response_model=DrawdownAnalysis,
    summary="Drawdown analysis with historical drawdown periods",
)
async def get_drawdown(
    db: asyncpg.Connection = Depends(get_db),
) -> DrawdownAnalysis:
    current_row = await db.fetchrow(
        "SELECT drawdown_pct FROM portfolio_equity_history ORDER BY recorded_at DESC LIMIT 1"
    )

    max_row = await db.fetchrow(
        """
        SELECT
            drawdown_pct,
            recorded_at AS peak_date
        FROM portfolio_equity_history
        ORDER BY drawdown_pct DESC
        LIMIT 1
        """
    )

    periods_rows = await db.fetch(
        """
        SELECT
            period_start,
            period_end,
            max_drawdown_pct,
            duration_days,
            recovery_days
        FROM drawdown_periods
        ORDER BY max_drawdown_pct DESC
        LIMIT 10
        """,
    )

    now = datetime.now(timezone.utc).isoformat()

    return DrawdownAnalysis(
        current_drawdown_pct=float(current_row["drawdown_pct"]) if current_row else 0.0,
        max_drawdown_pct=float(max_row["drawdown_pct"]) if max_row else 0.0,
        max_drawdown_from_date=max_row["peak_date"].isoformat() if max_row and max_row["peak_date"] else None,
        max_drawdown_to_date=None,
        max_drawdown_duration_days=None,
        recovery_factor=None,
        periods=[
            {
                "period_start": r["period_start"].isoformat() if r["period_start"] else None,
                "period_end": r["period_end"].isoformat() if r["period_end"] else None,
                "max_drawdown_pct": float(r["max_drawdown_pct"]),
                "duration_days": float(r["duration_days"] or 0),
                "recovery_days": float(r["recovery_days"] or 0) if r.get("recovery_days") else None,
            }
            for r in periods_rows
        ],
        analysed_at=now,
    )


# ---------------------------------------------------------------------------
# GET /portfolio/allocation
# ---------------------------------------------------------------------------


@router.get(
    "/allocation",
    response_model=AllocationBreakdown,
    summary="Portfolio allocation breakdown by symbol, direction, and broker",
)
async def get_allocation(
    db: asyncpg.Connection = Depends(get_db),
) -> AllocationBreakdown:
    rows = await db.fetch(
        """
        SELECT
            symbol,
            direction,
            broker,
            SUM(filled_price * quantity) AS allocation_usd
        FROM trades
        WHERE status = 'open'
        GROUP BY symbol, direction, broker
        """,
    )

    by_symbol: dict[str, float] = {}
    by_direction: dict[str, float] = {}
    by_broker: dict[str, float] = {}

    for r in rows:
        val = float(r["allocation_usd"] or 0.0)
        by_symbol[r["symbol"]] = by_symbol.get(r["symbol"], 0.0) + val
        by_direction[r["direction"]] = by_direction.get(r["direction"], 0.0) + val
        by_broker[r["broker"]] = by_broker.get(r["broker"], 0.0) + val

    # Diversification score = 1 - Herfindahl-Hirschman Index over by-symbol
    # allocation weights. HHI = sum(weight_i^2) for weight_i in [0, 1];
    # HHI == 1 means fully concentrated in one symbol (score 0), while an
    # even spread across N symbols yields HHI == 1/N (score approaches 1).
    total_alloc = sum(by_symbol.values())
    if total_alloc > 0:
        hhi = sum((v / total_alloc) ** 2 for v in by_symbol.values())
        diversification_score = round(max(0.0, 1.0 - hhi), 4)
    else:
        diversification_score = 0.0

    return AllocationBreakdown(
        by_symbol=by_symbol,
        by_direction=by_direction,
        by_broker=by_broker,
        diversification_score=diversification_score,
        calculated_at=datetime.now(timezone.utc).isoformat(),
    )
