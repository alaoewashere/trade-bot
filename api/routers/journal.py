"""
api/routers/journal.py
=======================
Trade journal endpoints.

Endpoints
---------
GET   /journal            — paginated journal entries (filter by symbol/outcome/date/search)
GET   /journal/{entry_id}  — specific journal entry detail
POST  /journal             — create a manual journal entry
PATCH /journal/{entry_id}  — edit notes / lessons on an existing entry
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


class JournalEntryResponse(BaseModel):
    id: str
    trade_id: str | None
    symbol: str
    direction: str
    entry_price: float | None
    exit_price: float | None
    opened_at: str | None
    closed_at: str | None
    outcome: str | None
    pnl_usd: float | None
    ai_consensus_direction: str | None
    ai_confidence_pct: float | None
    agent_opinions: list[Any]
    market_regime: str | None
    risk_score: float | None
    emotional_notes: str | None
    execution_notes: str | None
    lessons_learned: str | None
    created_at: str


class JournalEntryCreate(BaseModel):
    trade_id: str | None = None
    symbol: str
    direction: str
    entry_price: float | None = None
    exit_price: float | None = None
    opened_at: datetime | None = None
    closed_at: datetime | None = None
    outcome: str | None = None
    pnl_usd: float | None = None
    ai_consensus_direction: str | None = None
    ai_confidence_pct: float | None = None
    agent_opinions: list[Any] = []
    market_regime: str | None = None
    risk_score: float | None = None
    emotional_notes: str | None = None
    execution_notes: str | None = None
    lessons_learned: str | None = None


class JournalEntryUpdate(BaseModel):
    emotional_notes: str | None = None
    execution_notes: str | None = None
    lessons_learned: str | None = None
    outcome: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SELECT_COLUMNS = """
    id, trade_id, symbol, direction, entry_price, exit_price,
    opened_at, closed_at, outcome, pnl_usd, ai_consensus_direction,
    ai_confidence_pct, agent_opinions, market_regime, risk_score,
    emotional_notes, execution_notes, lessons_learned, created_at
"""


def _row_to_entry(row: asyncpg.Record) -> JournalEntryResponse:
    return JournalEntryResponse(
        id=str(row["id"]),
        trade_id=str(row["trade_id"]) if row["trade_id"] else None,
        symbol=row["symbol"],
        direction=row["direction"],
        entry_price=float(row["entry_price"]) if row["entry_price"] is not None else None,
        exit_price=float(row["exit_price"]) if row["exit_price"] is not None else None,
        opened_at=row["opened_at"].isoformat() if row["opened_at"] else None,
        closed_at=row["closed_at"].isoformat() if row["closed_at"] else None,
        outcome=row["outcome"],
        pnl_usd=float(row["pnl_usd"]) if row["pnl_usd"] is not None else None,
        ai_consensus_direction=row["ai_consensus_direction"],
        ai_confidence_pct=(
            float(row["ai_confidence_pct"]) if row["ai_confidence_pct"] is not None else None
        ),
        agent_opinions=row["agent_opinions"] or [],
        market_regime=row["market_regime"],
        risk_score=float(row["risk_score"]) if row["risk_score"] is not None else None,
        emotional_notes=row["emotional_notes"],
        execution_notes=row["execution_notes"],
        lessons_learned=row["lessons_learned"],
        created_at=row["created_at"].isoformat(),
    )


# ---------------------------------------------------------------------------
# GET /journal
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=list[JournalEntryResponse],
    summary="Paginated trade journal history",
)
async def list_journal_entries(
    symbol: str | None = Query(default=None),
    outcome: str | None = Query(default=None, description="WIN | LOSS | BE"),
    since: str | None = Query(default=None, description="ISO datetime filter (closed_at >=)"),
    until: str | None = Query(default=None, description="ISO datetime filter (closed_at <=)"),
    search: str | None = Query(default=None, description="Full-text search across notes fields"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: asyncpg.Connection = Depends(get_db),
) -> list[JournalEntryResponse]:
    conditions: list[str] = []
    params: list[Any] = []
    idx = 1

    if symbol:
        conditions.append(f"symbol = ${idx}")
        params.append(symbol)
        idx += 1

    if outcome:
        conditions.append(f"outcome = ${idx}")
        params.append(outcome.upper())
        idx += 1

    if since:
        conditions.append(f"closed_at >= ${idx}")
        params.append(since)
        idx += 1

    if until:
        conditions.append(f"closed_at <= ${idx}")
        params.append(until)
        idx += 1

    if search:
        conditions.append(
            f"""to_tsvector('english',
                COALESCE(emotional_notes, '') || ' ' ||
                COALESCE(execution_notes, '') || ' ' ||
                COALESCE(lessons_learned, '')
            ) @@ plainto_tsquery('english', ${idx})"""
        )
        params.append(search)
        idx += 1

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    params += [limit, offset]

    rows = await db.fetch(
        f"""
        SELECT {_SELECT_COLUMNS}
        FROM trade_journal
        {where}
        ORDER BY COALESCE(closed_at, created_at) DESC
        LIMIT ${idx} OFFSET ${idx+1}
        """,
        *params,
    )

    return [_row_to_entry(r) for r in rows]


# ---------------------------------------------------------------------------
# GET /journal/{entry_id}
# ---------------------------------------------------------------------------


@router.get(
    "/{entry_id}",
    response_model=JournalEntryResponse,
    summary="Get a specific journal entry",
)
async def get_journal_entry(
    entry_id: str,
    db: asyncpg.Connection = Depends(get_db),
) -> JournalEntryResponse:
    row = await db.fetchrow(
        f"SELECT {_SELECT_COLUMNS} FROM trade_journal WHERE id = $1",
        entry_id,
    )

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Journal entry '{entry_id}' not found.",
        )

    return _row_to_entry(row)


# ---------------------------------------------------------------------------
# POST /journal
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=JournalEntryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a manual journal entry",
)
async def create_journal_entry(
    body: JournalEntryCreate,
    db: asyncpg.Connection = Depends(get_db),
) -> JournalEntryResponse:
    row = await db.fetchrow(
        f"""
        INSERT INTO trade_journal (
            trade_id, symbol, direction, entry_price, exit_price,
            opened_at, closed_at, outcome, pnl_usd, ai_consensus_direction,
            ai_confidence_pct, agent_opinions, market_regime, risk_score,
            emotional_notes, execution_notes, lessons_learned
        )
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17)
        RETURNING {_SELECT_COLUMNS}
        """,
        body.trade_id,
        body.symbol,
        body.direction,
        body.entry_price,
        body.exit_price,
        body.opened_at,
        body.closed_at,
        body.outcome,
        body.pnl_usd,
        body.ai_consensus_direction,
        body.ai_confidence_pct,
        body.agent_opinions,
        body.market_regime,
        body.risk_score,
        body.emotional_notes,
        body.execution_notes,
        body.lessons_learned,
    )

    logger.info("journal_entry_created symbol=%s direction=%s", body.symbol, body.direction)
    return _row_to_entry(row)


# ---------------------------------------------------------------------------
# PATCH /journal/{entry_id}
# ---------------------------------------------------------------------------


@router.patch(
    "/{entry_id}",
    response_model=JournalEntryResponse,
    summary="Edit notes / lessons on an existing journal entry",
)
async def update_journal_entry(
    entry_id: str,
    body: JournalEntryUpdate,
    db: asyncpg.Connection = Depends(get_db),
) -> JournalEntryResponse:
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No fields provided to update.",
        )

    set_clauses = []
    params: list[Any] = []
    idx = 1
    for field, value in updates.items():
        set_clauses.append(f"{field} = ${idx}")
        params.append(value)
        idx += 1

    params.append(entry_id)

    row = await db.fetchrow(
        f"""
        UPDATE trade_journal
        SET {', '.join(set_clauses)}
        WHERE id = ${idx}
        RETURNING {_SELECT_COLUMNS}
        """,
        *params,
    )

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Journal entry '{entry_id}' not found.",
        )

    return _row_to_entry(row)
