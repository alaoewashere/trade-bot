"""
api/routers/alerts.py
======================
Alert Center endpoints — backed by the `alerts` table
(migrations/versions/0004_alerts.sql). Alerts are written by
alerts/generator.py, hooked into existing side-effect points (see that
module's docstring for which hooks are wired vs documented TODOs).

Endpoints
---------
GET  /alerts                     — paginated, filterable by type/severity/acknowledged/symbol
POST /alerts/{id}/acknowledge    — mark a single alert acknowledged
GET  /alerts/unread-count        — count of unacknowledged alerts (optionally by severity)
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


class AlertResponse(BaseModel):
    id: str
    created_at: str
    alert_type: str
    severity: str
    symbol: str | None
    message: str
    payload: dict[str, Any]
    acknowledged: bool
    acknowledged_at: str | None


class UnreadCountResponse(BaseModel):
    unread_count: int
    by_severity: dict[str, int]


def _row_to_alert(row: asyncpg.Record) -> AlertResponse:
    return AlertResponse(
        id=str(row["id"]),
        created_at=row["created_at"].isoformat(),
        alert_type=row["alert_type"],
        severity=row["severity"],
        symbol=row["symbol"],
        message=row["message"],
        payload=row["payload"] or {},
        acknowledged=bool(row["acknowledged"]),
        acknowledged_at=row["acknowledged_at"].isoformat() if row["acknowledged_at"] else None,
    )


@router.get("", response_model=list[AlertResponse], summary="Paginated alert list")
async def list_alerts(
    alert_type: str | None = Query(default=None),
    severity: str | None = Query(default=None, description="info | warning | critical"),
    acknowledged: bool | None = Query(default=None),
    symbol: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: asyncpg.Connection = Depends(get_db),
) -> list[AlertResponse]:
    conditions: list[str] = []
    params: list[Any] = []
    idx = 1

    if alert_type:
        conditions.append(f"alert_type = ${idx}")
        params.append(alert_type)
        idx += 1
    if severity:
        conditions.append(f"severity = ${idx}")
        params.append(severity)
        idx += 1
    if acknowledged is not None:
        conditions.append(f"acknowledged = ${idx}")
        params.append(acknowledged)
        idx += 1
    if symbol:
        conditions.append(f"symbol = ${idx}")
        params.append(symbol)
        idx += 1

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    params.extend([limit, offset])

    rows = await db.fetch(
        f"""
        SELECT id, created_at, alert_type, severity, symbol, message, payload,
               acknowledged, acknowledged_at
        FROM alerts
        {where_clause}
        ORDER BY created_at DESC
        LIMIT ${idx} OFFSET ${idx + 1}
        """,
        *params,
    )
    return [_row_to_alert(r) for r in rows]


@router.post(
    "/{alert_id}/acknowledge",
    response_model=AlertResponse,
    summary="Acknowledge a single alert",
)
async def acknowledge_alert(
    alert_id: str,
    db: asyncpg.Connection = Depends(get_db),
) -> AlertResponse:
    row = await db.fetchrow(
        """
        UPDATE alerts
        SET acknowledged = TRUE, acknowledged_at = $1
        WHERE id = $2
        RETURNING id, created_at, alert_type, severity, symbol, message, payload,
                  acknowledged, acknowledged_at
        """,
        datetime.now(timezone.utc),
        alert_id,
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert '{alert_id}' not found.",
        )
    return _row_to_alert(row)


@router.get(
    "/unread-count",
    response_model=UnreadCountResponse,
    summary="Count of unacknowledged alerts",
)
async def get_unread_count(
    db: asyncpg.Connection = Depends(get_db),
) -> UnreadCountResponse:
    rows = await db.fetch(
        """
        SELECT severity, COUNT(*) AS cnt
        FROM alerts
        WHERE acknowledged = FALSE
        GROUP BY severity
        """
    )
    by_severity = {r["severity"]: int(r["cnt"]) for r in rows}
    return UnreadCountResponse(
        unread_count=sum(by_severity.values()),
        by_severity=by_severity,
    )
