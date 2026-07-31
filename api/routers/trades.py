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
POST /trades/{trade_id}/close       — manually close a position (paper only)
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from api.dependencies import get_db

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


class TradeCloseRequest(BaseModel):
    reason: str = "Manual close via API"


class TimelineEvent(BaseModel):
    event_type: str
    description: str
    occurred_at: str
    metadata: dict[str, Any]


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

    return TradeStats(
        total_trades=total + open_count,
        open_trades=open_count,
        closed_trades=total,
        win_rate_pct=round(wins / total * 100.0, 2) if total > 0 else 0.0,
        total_pnl_usd=float(row["total_pnl"] or 0.0) if row else 0.0,
        avg_win_usd=float(row["avg_win"] or 0.0) if row else 0.0,
        avg_loss_usd=float(row["avg_loss"] or 0.0) if row else 0.0,
        profit_factor=round(profit_factor, 3),
        avg_risk_reward=float(row["avg_rr"] or 0.0) if row else 0.0,
        largest_win_usd=float(row["largest_win"] or 0.0) if row else 0.0,
        largest_loss_usd=float(row["largest_loss"] or 0.0) if row else 0.0,
        avg_duration_minutes=float(row["avg_duration_min"] or 0.0) if row else 0.0,
        measured_at=datetime.now(timezone.utc).isoformat(),
    )


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

    return {
        "trade_id": trade_id,
        "status": "closed",
        "closed_at": closed_at.isoformat(),
        "reason": body.reason,
        "message": "Position closed successfully.",
    }
