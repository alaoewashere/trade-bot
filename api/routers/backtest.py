"""
api/routers/backtest.py
========================
Strategy backtesting execution endpoints.

This is a research tool, not a production job system: runs execute
synchronously against historical `forecasts` rows and are persisted to
`backtest_runs` for later retrieval. There is no dedicated backtest
execution engine elsewhere in the repo — `agents/quantitative/
backtesting_expert.py` is an LLM critique agent (judges whether a proposed
strategy has adequate backtest evidence) and is unrelated to this replay
engine.

Replay methodology
-------------------
Each historical forecast in [date_range_start, date_range_end] for the
requested symbol/timeframe is treated as a trade signal:
  - direction: 'bullish' -> LONG, 'bearish' -> SHORT, 'neutral' -> skipped
    (no position taken, matches how the rest of the platform treats neutral
    consensus).
  - entry price:  forecasts.price_at_creation
  - exit price:   forecasts.actual_price_at_expiry (already computed by the
    prediction_engine/evaluator.py daemon — we never re-fetch prices from an
    exchange).
  - Only forecasts with evaluated = TRUE and a non-null
    actual_price_at_expiry are usable; everything else is skipped (still
    counted, reported separately) rather than causing a failure.
  - Position size is a fixed notional ($10,000) scaled by confidence_pct/100,
    so a single low-confidence forecast can't dominate the equity curve —
    documented assumption, there being no per-trade sizing model to replay
    against historical forecasts.

Strategy segmentation
----------------------
`forecasts` has no strategy taxonomy — it is symbol/timeframe based, scored
by an ensemble of models recorded in `model_contributions` (dict of
model_name -> weight). The frontend's strategy names ("Momentum Breakout",
"Mean Reversion", ...) do not correspond to anything in that data, and we do
not fabricate per-strategy performance to satisfy the selector. `strategy`
is therefore accepted and stored as a label on the run (visible in
GET /backtest/runs and .../{id}) but does not filter or influence the
replayed results in any way. If this changes (e.g. a future strategy
taxonomy lands in trade_proposals), this filter can be wired in without
changing the endpoint shape.

Endpoints
---------
POST /backtest/run          — execute a new backtest synchronously
GET  /backtest/runs         — paginated list of past runs
GET  /backtest/runs/{id}    — full report for one run
"""
from __future__ import annotations

import logging
import statistics
from datetime import datetime, timezone
from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from api.dependencies import get_db

logger = logging.getLogger(__name__)
router = APIRouter()

# Fixed notional per replayed signal, scaled by confidence_pct/100 — see
# module docstring. This is a research-tool simplification, not a position
# sizing model.
_NOTIONAL_USD = 10_000.0


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class BacktestRunRequest(BaseModel):
    symbol: str
    timeframe: str
    strategy: str | None = None
    date_range_start: datetime
    date_range_end: datetime
    notes: str | None = None


class BacktestRunSummary(BaseModel):
    id: str
    created_at: str
    symbol: str
    timeframe: str
    strategy_name: str | None
    date_range_start: str
    date_range_end: str
    status: str
    notes: str | None


class BacktestRunDetail(BacktestRunSummary):
    results: dict[str, Any]
    error_message: str | None
    created_by: str | None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _row_to_summary(row: asyncpg.Record) -> BacktestRunSummary:
    return BacktestRunSummary(
        id=str(row["id"]),
        created_at=row["created_at"].isoformat(),
        symbol=row["symbol"],
        timeframe=row["timeframe"],
        strategy_name=row.get("strategy_name"),
        date_range_start=row["date_range_start"].isoformat(),
        date_range_end=row["date_range_end"].isoformat(),
        status=row["status"],
        notes=row.get("notes"),
    )


def _row_to_detail(row: asyncpg.Record) -> BacktestRunDetail:
    import json

    results = row["results"]
    if isinstance(results, str):
        results = json.loads(results) if results else {}
    return BacktestRunDetail(
        **_row_to_summary(row).model_dump(),
        results=results or {},
        error_message=row.get("error_message"),
        created_by=row.get("created_by"),
    )


def _max_streak(outcomes: list[bool]) -> int:
    """Longest run of consecutive True values in `outcomes` (win or loss streak)."""
    best = current = 0
    for o in outcomes:
        current = current + 1 if o else 0
        best = max(best, current)
    return best


def _run_backtest(forecast_rows: list[asyncpg.Record]) -> dict[str, Any]:
    """
    Pure computation over already-fetched forecast rows — kept separate from
    the DB layer so it's trivially unit-testable and so the endpoint stays
    honest about num_trades=0 rather than crashing when there's no usable
    historical data for the requested window.
    """
    trades: list[dict[str, Any]] = []

    for f in forecast_rows:
        direction = f["direction"]
        if direction not in ("bullish", "bearish"):
            continue  # neutral forecasts imply no position taken

        entry = f["price_at_creation"]
        exit_price = f["actual_price_at_expiry"]
        if entry is None or exit_price is None:
            continue

        entry = float(entry)
        exit_price = float(exit_price)
        if entry <= 0:
            continue

        raw_return_pct = (exit_price - entry) / entry * 100.0
        signed_return_pct = raw_return_pct if direction == "bullish" else -raw_return_pct

        confidence_pct = float(f["confidence_pct"]) if f["confidence_pct"] is not None else 50.0
        notional = _NOTIONAL_USD * max(min(confidence_pct, 100.0), 0.0) / 100.0
        pnl_usd = notional * (signed_return_pct / 100.0)

        holding_minutes = None
        if f["created_at"] and f["expiry_at"]:
            holding_minutes = (f["expiry_at"] - f["created_at"]).total_seconds() / 60.0

        trades.append({
            "forecast_id": str(f["id"]),
            "opened_at": f["created_at"].isoformat() if f["created_at"] else None,
            "closed_at": f["expiry_at"].isoformat() if f["expiry_at"] else None,
            "direction": "LONG" if direction == "bullish" else "SHORT",
            "entry_price": entry,
            "exit_price": exit_price,
            "return_pct": round(signed_return_pct, 4),
            "pnl_usd": round(pnl_usd, 2),
            "confidence_pct": confidence_pct,
            "market_regime": f["market_regime"],
            "holding_minutes": holding_minutes,
        })

    num_trades = len(trades)
    if num_trades == 0:
        return {
            "num_trades": 0,
            "num_forecasts_considered": len(forecast_rows),
            "total_return_pct": 0.0,
            "annual_return_pct": 0.0,
            "win_rate_pct": 0.0,
            "max_drawdown_pct": 0.0,
            "profit_factor": 0.0,
            "avg_trade_pnl_usd": 0.0,
            "avg_holding_time_minutes": None,
            "best_trade": None,
            "worst_trade": None,
            "longest_winning_streak": 0,
            "longest_losing_streak": 0,
            "equity_curve": [],
            "trade_distribution": [],
            "monthly_heatmap": [],
            "performance_by_regime": [],
            "performance_by_timeframe": [],
            "note": "No usable historical forecast data (evaluated, with a recorded outcome) in this window.",
        }

    trades.sort(key=lambda t: t["opened_at"] or "")

    wins = [t for t in trades if t["pnl_usd"] > 0]
    losses = [t for t in trades if t["pnl_usd"] <= 0]
    gross_profit = sum(t["pnl_usd"] for t in wins)
    gross_loss = abs(sum(t["pnl_usd"] for t in losses))

    equity_curve = []
    cumulative = 0.0
    peak = 0.0
    max_dd_pct = 0.0
    for t in trades:
        cumulative += t["pnl_usd"]
        peak = max(peak, cumulative)
        base = _NOTIONAL_USD + peak
        dd_pct = (peak - cumulative) / base * 100.0 if base > 0 else 0.0
        max_dd_pct = max(max_dd_pct, dd_pct)
        equity_curve.append({
            "timestamp": t["closed_at"] or t["opened_at"],
            "cumulative_pnl_usd": round(cumulative, 2),
            "drawdown_pct": round(dd_pct, 3),
        })

    total_return_pct = (cumulative / _NOTIONAL_USD) * 100.0
    days_span = None
    if trades[0]["opened_at"] and trades[-1]["closed_at"]:
        start = datetime.fromisoformat(trades[0]["opened_at"])
        end = datetime.fromisoformat(trades[-1]["closed_at"])
        days_span = max((end - start).total_seconds() / 86400.0, 1.0)
    annual_return_pct = (total_return_pct / days_span * 365.0) if days_span else total_return_pct

    holding_times = [t["holding_minutes"] for t in trades if t["holding_minutes"] is not None]

    win_loss_outcomes = [t["pnl_usd"] > 0 for t in trades]
    longest_win_streak = _max_streak(win_loss_outcomes)
    longest_loss_streak = _max_streak([not o for o in win_loss_outcomes])

    best_trade = max(trades, key=lambda t: t["pnl_usd"])
    worst_trade = min(trades, key=lambda t: t["pnl_usd"])

    # Trade distribution: histogram of return_pct into fixed buckets.
    buckets = [(-float("inf"), -5), (-5, -2), (-2, 0), (0, 2), (2, 5), (5, float("inf"))]
    labels = ["< -5%", "-5% to -2%", "-2% to 0%", "0% to 2%", "2% to 5%", "> 5%"]
    trade_distribution = []
    for (lo, hi), label in zip(buckets, labels):
        count = sum(1 for t in trades if lo <= t["return_pct"] < hi)
        trade_distribution.append({"bucket": label, "count": count})

    # Monthly heatmap: sum of pnl per calendar month.
    monthly: dict[str, float] = {}
    for t in trades:
        if not t["closed_at"]:
            continue
        month_key = t["closed_at"][:7]  # YYYY-MM
        monthly[month_key] = monthly.get(month_key, 0.0) + t["pnl_usd"]
    monthly_heatmap = [
        {"month": k, "pnl_usd": round(v, 2)} for k, v in sorted(monthly.items())
    ]

    # Performance by market regime — reuses forecasts.market_regime, when set.
    regimes: dict[str, list[float]] = {}
    for t in trades:
        key = t["market_regime"] or "unknown"
        regimes.setdefault(key, []).append(t["pnl_usd"])
    performance_by_regime = [
        {
            "regime": k,
            "num_trades": len(v),
            "total_pnl_usd": round(sum(v), 2),
            "win_rate_pct": round(sum(1 for x in v if x > 0) / len(v) * 100.0, 2),
        }
        for k, v in regimes.items()
    ]

    return {
        "num_trades": num_trades,
        "num_forecasts_considered": len(forecast_rows),
        "total_return_pct": round(total_return_pct, 3),
        "annual_return_pct": round(annual_return_pct, 3),
        "win_rate_pct": round(len(wins) / num_trades * 100.0, 2),
        "max_drawdown_pct": round(max_dd_pct, 3),
        "profit_factor": round(gross_profit / gross_loss, 3) if gross_loss > 0 else float("inf"),
        "avg_trade_pnl_usd": round(cumulative / num_trades, 2),
        "avg_holding_time_minutes": (
            round(statistics.mean(holding_times), 1) if holding_times else None
        ),
        "best_trade": best_trade,
        "worst_trade": worst_trade,
        "longest_winning_streak": longest_win_streak,
        "longest_losing_streak": longest_loss_streak,
        "equity_curve": equity_curve,
        "trade_distribution": trade_distribution,
        "monthly_heatmap": monthly_heatmap,
        "performance_by_regime": performance_by_regime,
        # Single timeframe per run by construction (it's a request param), so
        # this is a one-element breakdown rather than a genuine cross-section.
        "performance_by_timeframe": [
            {
                "timeframe": forecast_rows[0]["timeframe"] if forecast_rows else None,
                "num_trades": num_trades,
                "total_pnl_usd": round(cumulative, 2),
            }
        ],
    }


# ---------------------------------------------------------------------------
# POST /backtest/run
# ---------------------------------------------------------------------------


@router.post(
    "/run",
    response_model=BacktestRunDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Execute a backtest synchronously against historical forecast data",
)
async def run_backtest(
    body: BacktestRunRequest,
    db: asyncpg.Connection = Depends(get_db),
) -> BacktestRunDetail:
    if body.date_range_end <= body.date_range_start:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="date_range_end must be after date_range_start.",
        )

    run_row = await db.fetchrow(
        """
        INSERT INTO backtest_runs (
            symbol, timeframe, strategy_name, date_range_start, date_range_end,
            status, notes
        )
        VALUES ($1, $2, $3, $4, $5, 'running', $6)
        RETURNING id, created_at, symbol, timeframe, strategy_name,
                  date_range_start, date_range_end, status, results,
                  error_message, created_by, notes
        """,
        body.symbol,
        body.timeframe,
        body.strategy,
        body.date_range_start,
        body.date_range_end,
        body.notes,
    )
    run_id = run_row["id"]

    try:
        forecast_rows = await db.fetch(
            """
            SELECT id, symbol, timeframe, created_at, expiry_at, direction,
                   confidence_pct, price_at_creation, market_regime,
                   evaluated, actual_price_at_expiry
            FROM forecasts
            WHERE symbol = $1
              AND timeframe = $2
              AND created_at >= $3
              AND created_at <= $4
              AND evaluated = TRUE
              AND actual_price_at_expiry IS NOT NULL
            ORDER BY created_at ASC
            """,
            body.symbol,
            body.timeframe,
            body.date_range_start,
            body.date_range_end,
        )

        results = _run_backtest(forecast_rows)

        updated = await db.fetchrow(
            """
            UPDATE backtest_runs
            SET status = 'completed', results = $2::jsonb
            WHERE id = $1
            RETURNING id, created_at, symbol, timeframe, strategy_name,
                      date_range_start, date_range_end, status, results,
                      error_message, created_by, notes
            """,
            run_id,
            _to_jsonb(results),
        )
        return _row_to_detail(updated)

    except Exception as exc:
        logger.exception("backtest_run_failed run_id=%s", run_id)
        failed = await db.fetchrow(
            """
            UPDATE backtest_runs
            SET status = 'failed', error_message = $2
            WHERE id = $1
            RETURNING id, created_at, symbol, timeframe, strategy_name,
                      date_range_start, date_range_end, status, results,
                      error_message, created_by, notes
            """,
            run_id,
            str(exc),
        )
        return _row_to_detail(failed)


def _to_jsonb(obj: dict[str, Any]) -> str:
    import json

    return json.dumps(obj, default=str)


# ---------------------------------------------------------------------------
# GET /backtest/runs
# ---------------------------------------------------------------------------


@router.get(
    "/runs",
    response_model=list[BacktestRunSummary],
    summary="Paginated list of past backtest runs",
)
async def list_backtest_runs(
    symbol: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status", description="pending|running|completed|failed"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: asyncpg.Connection = Depends(get_db),
) -> list[BacktestRunSummary]:
    conditions = []
    params: list[Any] = []
    idx = 1

    if symbol:
        conditions.append(f"symbol = ${idx}")
        params.append(symbol)
        idx += 1

    if status_filter:
        conditions.append(f"status = ${idx}")
        params.append(status_filter.lower())
        idx += 1

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    params += [limit, offset]

    rows = await db.fetch(
        f"""
        SELECT id, created_at, symbol, timeframe, strategy_name,
               date_range_start, date_range_end, status, notes
        FROM backtest_runs
        {where_clause}
        ORDER BY created_at DESC
        LIMIT ${idx} OFFSET ${idx+1}
        """,
        *params,
    )

    return [_row_to_summary(r) for r in rows]


# ---------------------------------------------------------------------------
# GET /backtest/runs/{run_id}
# ---------------------------------------------------------------------------


@router.get(
    "/runs/{run_id}",
    response_model=BacktestRunDetail,
    summary="Full report for a single backtest run",
)
async def get_backtest_run(
    run_id: str,
    db: asyncpg.Connection = Depends(get_db),
) -> BacktestRunDetail:
    row = await db.fetchrow(
        """
        SELECT id, created_at, symbol, timeframe, strategy_name,
               date_range_start, date_range_end, status, results,
               error_message, created_by, notes
        FROM backtest_runs
        WHERE id = $1
        """,
        run_id,
    )

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Backtest run '{run_id}' not found.",
        )

    return _row_to_detail(row)
