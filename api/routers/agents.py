"""
api/routers/agents.py
======================
Agent introspection and management endpoints.

Endpoints
---------
GET  /agents                   — list all 40 registered agents with metadata
GET  /agents/{agent_id}        — get a specific agent's detail
GET  /agents/{agent_id}/reports — paginated analysis reports from DB
GET  /agents/{agent_id}/performance — agent-level accuracy metrics (Phase 4: real, persisted)
GET  /agents/rankings          — all agents ranked by reliability_score (Phase 4)
POST /agents/{agent_id}/invoke — manually trigger an agent analysis (paper only)
"""
from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

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

    # --- Phase 4 additions (additive) ---
    # Computed on-the-fly from agent_decisions joined against resolved
    # forecasts/market_regimes (see _aggregate_agent_performance below) rather
    # than from a periodic snapshot table — see module docstring note near
    # get_agent_performance for why.
    win_rate_pct: float | None = None
    avg_return_pct: float | None = None
    reliability_score: float | None = None
    """0-100. See _reliability_score() docstring for the exact formula."""
    current_form_pct: float | None = None
    """Accuracy over the agent's last 20 resolved decisions."""
    all_time_accuracy_pct: float | None = None
    longest_winning_streak: int = 0
    longest_losing_streak: int = 0
    last_100_predictions: list[str] = Field(default_factory=list)
    """Chronological (oldest→newest) 'win' | 'loss' | 'pending', capped at 100."""
    success_by_regime: dict[str, float] = Field(default_factory=dict)
    success_by_timeframe: dict[str, float] = Field(default_factory=dict)
    success_by_asset: dict[str, float] = Field(default_factory=dict)
    resolved_decisions: int = 0
    pending_decisions: int = 0


class RankingEntry(BaseModel):
    agent_id: str
    department: str
    reliability_score: float
    accuracy_pct: float | None
    win_rate_pct: float | None
    resolved_decisions: int
    current_form_pct: float | None


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
# Phase 4: real agent performance aggregation
#
# We compute this on-the-fly from agent_decisions (joined against forecasts /
# market_regimes for timeframe/regime context) rather than maintaining a
# materialized agent_performance_snapshots table. Reasoning: the only existing
# periodic daemon in this repo is prediction_engine/evaluator.py, which is
# scoped to forecast calibration (symbol × timeframe × model), not per-agent
# stats — bolting an unrelated responsibility onto it would couple two
# concerns that should evolve independently, and there's no other scheduler
# convention to hook into safely. agent_decisions already has indexes on
# agent_id, symbol, decided_at, and outcome (migrations/init.sql), so a
# well-indexed on-the-fly query is simple and fast enough for the endpoint
# call volumes this is designed for (agent detail pages, a rankings table).
# If this ever becomes a hot path, the natural next step is a small dedicated
# daemon that periodically materializes exactly the aggregation below.
# ---------------------------------------------------------------------------

_DECISIONS_WITH_CONTEXT_SQL = """
    SELECT
        ad.agent_id, ad.symbol, ad.signal, ad.confidence, ad.outcome,
        ad.decided_at, ad.pnl_attribution,
        fc.timeframe AS nearest_timeframe,
        mr.regime AS nearest_regime
    FROM agent_decisions ad
    LEFT JOIN LATERAL (
        SELECT timeframe FROM forecasts f
        WHERE f.symbol = ad.symbol AND f.created_at <= ad.decided_at
        ORDER BY f.created_at DESC LIMIT 1
    ) fc ON TRUE
    LEFT JOIN LATERAL (
        SELECT regime FROM market_regimes m
        WHERE m.symbol = ad.symbol AND m.detected_at <= ad.decided_at
        ORDER BY m.detected_at DESC LIMIT 1
    ) mr ON TRUE
    WHERE ad.agent_id = $1
    ORDER BY ad.decided_at ASC
"""


def _wilson_lower_bound(wins: int, n: int, z: float = 1.96) -> float:
    """
    Wilson score interval lower bound for a binomial proportion — used so that
    an agent with e.g. 3/3 correct doesn't get treated as "100% reliable";
    small samples get pulled down toward uncertainty rather than just being
    trusted at face value.
    """
    if n <= 0:
        return 0.0
    p = wins / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n)
    return max(0.0, (centre - margin) / denom)


def _reliability_score(wins: int, n: int, avg_confidence: float, accuracy: float) -> float:
    """
    reliability_score (0-100) = 70% Wilson-lower-bound accuracy (rewards both
    high win rate AND enough samples to trust it) + 30% confidence calibration
    (penalizes agents whose stated confidence doesn't track their actual hit
    rate, in either direction). Weights are a design choice, not derived —
    documented here so they're easy to retune later.
    """
    if n <= 0:
        return 0.0
    wilson_lb = _wilson_lower_bound(wins, n)
    calibration = max(0.0, 1.0 - abs(avg_confidence - accuracy))
    return round((0.7 * wilson_lb + 0.3 * calibration) * 100.0, 2)


def _longest_streaks(resolved_outcomes: list[str]) -> tuple[int, int]:
    """resolved_outcomes: chronological list of 'correct'/'incorrect'."""
    longest_win = cur_win = 0
    longest_loss = cur_loss = 0
    for o in resolved_outcomes:
        if o == "correct":
            cur_win += 1
            cur_loss = 0
        elif o == "incorrect":
            cur_loss += 1
            cur_win = 0
        else:
            cur_win = cur_loss = 0
        longest_win = max(longest_win, cur_win)
        longest_loss = max(longest_loss, cur_loss)
    return longest_win, longest_loss


def _aggregate_agent_performance(rows: list[asyncpg.Record]) -> dict[str, Any]:
    """Turn raw agent_decisions+context rows (chronological) into the full stat set."""
    total = len(rows)
    resolved = [r for r in rows if r["outcome"] in ("correct", "incorrect")]
    pending = [r for r in rows if r["outcome"] == "pending"]
    wins = sum(1 for r in resolved if r["outcome"] == "correct")
    n_resolved = len(resolved)

    accuracy = (wins / n_resolved) if n_resolved else None
    avg_confidence = (
        sum(float(r["confidence"] or 0.0) for r in rows) / total if total else 0.0
    )
    returns = [float(r["pnl_attribution"]) for r in rows if r["pnl_attribution"] is not None]
    avg_return = sum(returns) / len(returns) if returns else None

    last_20 = resolved[-20:]
    current_form = (
        sum(1 for r in last_20 if r["outcome"] == "correct") / len(last_20) * 100.0
        if last_20
        else None
    )

    longest_win, longest_loss = _longest_streaks([r["outcome"] for r in resolved])

    last_100 = resolved[-100:]
    last_100_predictions = ["win" if r["outcome"] == "correct" else "loss" for r in last_100]

    def _bucket_success(key: str) -> dict[str, float]:
        buckets: dict[str, list[int]] = {}
        for r in resolved:
            bucket_key = r[key]
            if not bucket_key:
                continue
            buckets.setdefault(bucket_key, [0, 0])
            buckets[bucket_key][1] += 1
            if r["outcome"] == "correct":
                buckets[bucket_key][0] += 1
        return {
            k: round(wins_ / total_ * 100.0, 2)
            for k, (wins_, total_) in buckets.items()
            if total_ > 0
        }

    success_by_regime = _bucket_success("nearest_regime")
    success_by_timeframe = _bucket_success("nearest_timeframe")
    success_by_asset = _bucket_success("symbol")

    reliability = _reliability_score(
        wins, n_resolved, avg_confidence, accuracy if accuracy is not None else 0.5
    )

    return {
        "total_reports": total,
        "resolved_decisions": n_resolved,
        "pending_decisions": len(pending),
        "avg_confidence": round(avg_confidence, 4),
        "accuracy_pct": round(accuracy * 100.0, 2) if accuracy is not None else None,
        "win_rate_pct": round(accuracy * 100.0, 2) if accuracy is not None else None,
        "avg_return_pct": round(avg_return, 4) if avg_return is not None else None,
        "reliability_score": reliability,
        "current_form_pct": round(current_form, 2) if current_form is not None else None,
        "all_time_accuracy_pct": round(accuracy * 100.0, 2) if accuracy is not None else None,
        "longest_winning_streak": longest_win,
        "longest_losing_streak": longest_loss,
        "last_100_predictions": last_100_predictions,
        "success_by_regime": success_by_regime,
        "success_by_timeframe": success_by_timeframe,
        "success_by_asset": success_by_asset,
        "bullish_count": sum(1 for r in rows if r["signal"] == "bullish"),
        "bearish_count": sum(1 for r in rows if r["signal"] == "bearish"),
        "neutral_count": sum(1 for r in rows if r["signal"] == "neutral"),
        "no_signal_count": sum(1 for r in rows if r["signal"] == "no_signal"),
    }


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
    summary="Agent-level accuracy, reliability, and regime/timeframe/asset breakdowns",
    description=(
        "Phase 4: computed for real from agent_decisions (joined against forecasts/"
        "market_regimes for context) — previously this endpoint queried tables "
        "(agent_reports, forecast_outcomes) that don't exist in this schema and "
        "would 500 at runtime; it now reads the tables that are actually persisted."
    ),
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

    rows = await db.fetch(_DECISIONS_WITH_CONTEXT_SQL, agent_id)

    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No performance data found for agent '{agent_id}'.",
        )

    stats = _aggregate_agent_performance(rows)

    return AgentPerformance(
        agent_id=agent_id,
        measured_at=datetime.now(timezone.utc).isoformat(),
        brier_score=None,  # per-agent Brier requires a probabilistic signal agents don't emit; see calibration_stats for model-level Brier.
        **stats,
    )


# ---------------------------------------------------------------------------
# GET /agents/rankings
# ---------------------------------------------------------------------------


@router.get(
    "/rankings",
    response_model=list[RankingEntry],
    summary="All agents ranked by reliability_score (leaderboard)",
)
async def get_agent_rankings(
    min_decisions: int = Query(
        default=1, ge=0, description="Only include agents with at least this many resolved decisions"
    ),
    db: asyncpg.Connection = Depends(get_db),
) -> list[RankingEntry]:
    agent_ids = await db.fetch("SELECT DISTINCT agent_id FROM agent_decisions")
    entries: list[RankingEntry] = []

    for row in agent_ids:
        agent_id = row["agent_id"]
        if agent_id not in AGENT_REGISTRY_MAP:
            continue
        decision_rows = await db.fetch(_DECISIONS_WITH_CONTEXT_SQL, agent_id)
        if not decision_rows:
            continue
        stats = _aggregate_agent_performance(decision_rows)
        if stats["resolved_decisions"] < min_decisions:
            continue
        entries.append(
            RankingEntry(
                agent_id=agent_id,
                department=_detect_department(AGENT_REGISTRY_MAP[agent_id]),
                reliability_score=stats["reliability_score"] or 0.0,
                accuracy_pct=stats["accuracy_pct"],
                win_rate_pct=stats["win_rate_pct"],
                resolved_decisions=stats["resolved_decisions"],
                current_form_pct=stats["current_form_pct"],
            )
        )

    entries.sort(key=lambda e: e.reliability_score, reverse=True)
    return entries


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
