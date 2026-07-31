"""
api/routers/agents.py
======================
Agent introspection and management endpoints.

Endpoints
---------
GET  /agents                   — list all 40 registered agents with metadata
GET  /agents/{agent_id}        — get a specific agent's detail
GET  /agents/{agent_id}/reports — paginated analysis reports from DB
GET  /agents/{agent_id}/performance — agent-level accuracy metrics
POST /agents/{agent_id}/invoke — manually trigger an agent analysis (paper only)
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from agents.registry import AGENT_REGISTRY_MAP, AgentRegistry
from api.dependencies import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class AgentSummary(BaseModel):
    agent_id: str
    class_path: str
    department: str
    loaded: bool


class AgentDetail(BaseModel):
    agent_id: str
    class_path: str
    department: str
    loaded: bool
    total_reports: int
    last_report_at: str | None
    avg_confidence: float | None
    signal_distribution: dict[str, int]


class AgentReportResponse(BaseModel):
    report_id: str
    agent_id: str
    symbol: str
    signal: str
    confidence: float
    reasoning: str
    supporting_evidence: list[str]
    contradicting_evidence: list[str]
    key_levels: dict[str, float]
    created_at: str


class AgentPerformance(BaseModel):
    agent_id: str
    total_reports: int
    bullish_count: int
    bearish_count: int
    neutral_count: int
    no_signal_count: int
    avg_confidence: float
    accuracy_pct: float | None
    brier_score: float | None
    measured_at: str


class InvokeRequest(BaseModel):
    symbol: str
    timeframe: str = "1h"
    market_data: dict[str, Any] = {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _detect_department(class_path: str) -> str:
    """Extract department from the dotted class path."""
    parts = class_path.split(".")
    if len(parts) >= 3:
        return parts[1].replace("_", " ").title()
    return "unknown"


# ---------------------------------------------------------------------------
# GET /agents
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=list[AgentSummary],
    summary="List all 40 registered agents",
)
async def list_agents() -> list[AgentSummary]:
    result: list[AgentSummary] = []
    for agent_id, class_path in sorted(AGENT_REGISTRY_MAP.items()):
        loaded = agent_id in AgentRegistry._cache
        result.append(
            AgentSummary(
                agent_id=agent_id,
                class_path=class_path,
                department=_detect_department(class_path),
                loaded=loaded,
            )
        )
    return result


# ---------------------------------------------------------------------------
# GET /agents/{agent_id}
# ---------------------------------------------------------------------------


@router.get(
    "/{agent_id}",
    response_model=AgentDetail,
    summary="Get a specific agent's details and DB statistics",
)
async def get_agent(
    agent_id: str,
    db: asyncpg.Connection = Depends(get_db),
) -> AgentDetail:
    if agent_id not in AGENT_REGISTRY_MAP:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{agent_id}' is not registered.",
        )

    row = await db.fetchrow(
        """
        SELECT
            COUNT(*)                          AS total_reports,
            MAX(created_at)                   AS last_report_at,
            AVG(confidence)                   AS avg_confidence,
            COUNT(*) FILTER (WHERE signal = 'bullish')   AS bullish,
            COUNT(*) FILTER (WHERE signal = 'bearish')   AS bearish,
            COUNT(*) FILTER (WHERE signal = 'neutral')   AS neutral,
            COUNT(*) FILTER (WHERE signal = 'no_signal') AS no_signal
        FROM agent_reports
        WHERE agent_id = $1
        """,
        agent_id,
    )

    class_path = AGENT_REGISTRY_MAP[agent_id]
    loaded = agent_id in AgentRegistry._cache

    return AgentDetail(
        agent_id=agent_id,
        class_path=class_path,
        department=_detect_department(class_path),
        loaded=loaded,
        total_reports=int(row["total_reports"]) if row else 0,
        last_report_at=row["last_report_at"].isoformat() if row and row["last_report_at"] else None,
        avg_confidence=float(row["avg_confidence"]) if row and row["avg_confidence"] else None,
        signal_distribution={
            "bullish": int(row["bullish"]) if row else 0,
            "bearish": int(row["bearish"]) if row else 0,
            "neutral": int(row["neutral"]) if row else 0,
            "no_signal": int(row["no_signal"]) if row else 0,
        },
    )


# ---------------------------------------------------------------------------
# GET /agents/{agent_id}/reports
# ---------------------------------------------------------------------------


@router.get(
    "/{agent_id}/reports",
    response_model=list[AgentReportResponse],
    summary="Paginated analysis reports from an agent",
)
async def get_agent_reports(
    agent_id: str,
    symbol: str | None = Query(default=None, description="Filter by symbol"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: asyncpg.Connection = Depends(get_db),
) -> list[AgentReportResponse]:
    if agent_id not in AGENT_REGISTRY_MAP:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{agent_id}' is not registered.",
        )

    if symbol:
        rows = await db.fetch(
            """
            SELECT report_id, agent_id, symbol, signal, confidence,
                   reasoning, supporting_evidence, contradicting_evidence,
                   key_levels, created_at
            FROM agent_reports
            WHERE agent_id = $1 AND symbol = $2
            ORDER BY created_at DESC
            LIMIT $3 OFFSET $4
            """,
            agent_id, symbol, limit, offset,
        )
    else:
        rows = await db.fetch(
            """
            SELECT report_id, agent_id, symbol, signal, confidence,
                   reasoning, supporting_evidence, contradicting_evidence,
                   key_levels, created_at
            FROM agent_reports
            WHERE agent_id = $1
            ORDER BY created_at DESC
            LIMIT $2 OFFSET $3
            """,
            agent_id, limit, offset,
        )

    return [
        AgentReportResponse(
            report_id=str(r["report_id"]),
            agent_id=r["agent_id"],
            symbol=r["symbol"],
            signal=r["signal"],
            confidence=float(r["confidence"]),
            reasoning=r["reasoning"],
            supporting_evidence=r["supporting_evidence"] or [],
            contradicting_evidence=r["contradicting_evidence"] or [],
            key_levels=r["key_levels"] or {},
            created_at=r["created_at"].isoformat(),
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# GET /agents/{agent_id}/performance
# ---------------------------------------------------------------------------


@router.get(
    "/{agent_id}/performance",
    response_model=AgentPerformance,
    summary="Agent-level accuracy and signal distribution metrics",
)
async def get_agent_performance(
    agent_id: str,
    db: asyncpg.Connection = Depends(get_db),
) -> AgentPerformance:
    if agent_id not in AGENT_REGISTRY_MAP:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{agent_id}' is not registered.",
        )

    row = await db.fetchrow(
        """
        SELECT
            COUNT(ar.report_id)                             AS total_reports,
            COUNT(*) FILTER (WHERE ar.signal = 'bullish')   AS bullish_count,
            COUNT(*) FILTER (WHERE ar.signal = 'bearish')   AS bearish_count,
            COUNT(*) FILTER (WHERE ar.signal = 'neutral')   AS neutral_count,
            COUNT(*) FILTER (WHERE ar.signal = 'no_signal') AS no_signal_count,
            AVG(ar.confidence)                              AS avg_confidence,
            -- Directional accuracy against actual market outcome
            AVG(
                CASE
                    WHEN fo.actual_direction IS NOT NULL
                     AND ((ar.signal = 'bullish' AND fo.actual_direction = 'bullish')
                       OR (ar.signal = 'bearish' AND fo.actual_direction = 'bearish')
                       OR (ar.signal = 'neutral' AND fo.actual_direction = 'neutral'))
                    THEN 1.0
                    WHEN fo.actual_direction IS NOT NULL THEN 0.0
                    ELSE NULL
                END
            ) * 100                                         AS accuracy_pct,
            AVG(
                CASE
                    WHEN fo.actual_direction = 'bullish' THEN POWER(1 - ar.confidence, 2)
                    WHEN fo.actual_direction = 'bearish' THEN POWER(1 - ar.confidence, 2)
                    WHEN fo.actual_direction IS NOT NULL   THEN POWER(ar.confidence, 2)
                    ELSE NULL
                END
            )                                               AS brier_score
        FROM agent_reports ar
        LEFT JOIN forecast_outcomes fo
            ON fo.symbol = ar.symbol AND fo.outcome_timeframe = '1h'
            AND fo.settled_at BETWEEN ar.created_at AND ar.created_at + INTERVAL '2 hours'
        WHERE ar.agent_id = $1
        """,
        agent_id,
    )

    if row is None or row["total_reports"] == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No performance data found for agent '{agent_id}'.",
        )

    return AgentPerformance(
        agent_id=agent_id,
        total_reports=int(row["total_reports"]),
        bullish_count=int(row["bullish_count"]),
        bearish_count=int(row["bearish_count"]),
        neutral_count=int(row["neutral_count"]),
        no_signal_count=int(row["no_signal_count"]),
        avg_confidence=float(row["avg_confidence"] or 0.0),
        accuracy_pct=float(row["accuracy_pct"]) if row["accuracy_pct"] is not None else None,
        brier_score=float(row["brier_score"]) if row["brier_score"] is not None else None,
        measured_at=datetime.now(timezone.utc).isoformat(),
    )


# ---------------------------------------------------------------------------
# POST /agents/{agent_id}/invoke
# ---------------------------------------------------------------------------


@router.post(
    "/{agent_id}/invoke",
    summary="Manually invoke an agent analysis (paper mode only)",
    description=(
        "Directly trigger a single agent analysis outside of the main graph cycle. "
        "Only available in paper trading mode.  Returns the AgentReport."
    ),
)
async def invoke_agent(
    agent_id: str,
    body: InvokeRequest,
) -> dict[str, Any]:
    from config.settings import get_settings
    settings = get_settings()

    if settings.is_live:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Manual agent invocation is not permitted in live trading mode.",
        )

    if agent_id not in AGENT_REGISTRY_MAP:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{agent_id}' is not registered.",
        )

    try:
        agent = AgentRegistry.get(agent_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load agent '{agent_id}': {exc}",
        ) from exc

    minimal_state = {
        "symbol": body.symbol,
        "timeframe": body.timeframe,
        "market_data": body.market_data,
        "timestamp": datetime.now(timezone.utc),
        "current_phase": "manual_invoke",
        "analysis_reports": {},
        "strategy_signals": [],
        "debate_transcript": [],
        "consensus": None,
        "risk_assessment": None,
        "human_approval_required": False,
        "human_approval_status": None,
        "approval_id": None,
        "approval_deadline": None,
        "trade_plan": None,
        "order_ids": [],
        "execution_report": None,
        "forecasts": {},
        "market_regime": None,
        "circuit_breaker_tripped": False,
        "kill_switch_active": False,
        "news_blackout_active": False,
        "errors": [],
        "warnings": [],
        "iteration_count": 0,
    }

    try:
        result = agent(minimal_state)
        reports = result.get("analysis_reports", {})
        report = reports.get(agent_id)

        if report is not None:
            return {
                "agent_id": agent_id,
                "symbol": body.symbol,
                "signal": report.signal,
                "confidence": report.confidence,
                "reasoning": report.reasoning,
                "supporting_evidence": report.supporting_evidence,
                "contradicting_evidence": report.contradicting_evidence,
                "key_levels": report.key_levels,
                "timestamp": report.timestamp.isoformat(),
            }

        return {"agent_id": agent_id, "result": result, "note": "Non-standard output format"}

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent '{agent_id}' raised an exception: {exc}",
        ) from exc
