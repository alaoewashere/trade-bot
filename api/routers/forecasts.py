"""
api/routers/forecasts.py
=========================
Probabilistic price forecast endpoints.

Endpoints
---------
GET /forecasts                          — latest forecast for symbol × timeframe
GET /forecasts/{forecast_id}            — specific forecast by ID
GET /forecasts/calibration              — Brier score / accuracy calibration stats
GET /forecasts/leaderboard              — model accuracy ranking across all symbols
GET /forecasts/dashboard                — institutional terminal: all 8 TFs for one symbol
GET /forecasts/history                  — paginated prediction ledger with outcome/MFE/MAE (Phase 4)
"""
from __future__ import annotations

import logging
from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from api.dependencies import get_db

logger = logging.getLogger(__name__)
router = APIRouter()

# All timeframes published by the prediction engine
ALL_TIMEFRAMES = ["1m", "5m", "15m", "1h", "4h", "1d", "1w", "1M"]

# agent_id -> department, mirrored from agents/registry.py's AGENT_REGISTRY_MAP
# grouping comments (kept as a static mapping here since the registry itself
# only tracks module paths, not department labels).
_AGENT_DEPARTMENTS: dict[str, str] = {
    "cio_agent": "executive", "cro_agent": "executive", "portfolio_manager": "executive",
    "macro_economist": "market_intelligence", "news_analyst": "market_intelligence",
    "sentiment_analyst": "market_intelligence", "regulation_analyst": "market_intelligence",
    "trend_analyst": "technical", "price_action": "technical", "smc_expert": "technical",
    "wyckoff_analyst": "technical", "elliott_wave": "technical", "volume_profile": "technical",
    "market_structure": "technical",
    "quant_researcher": "quantitative", "probability_analyst": "quantitative",
    "ml_researcher": "quantitative", "backtesting_expert": "quantitative",
    "hf_pattern_detector": "quantitative",
    "options_flow_analyst": "options", "volatility_analyst": "options",
    "onchain_analyst": "on-chain", "funding_rate_analyst": "on-chain",
    "momentum_trader": "strategy", "mean_reversion": "strategy", "range_specialist": "strategy",
    "scalping_expert": "strategy", "swing_specialist": "strategy", "position_expert": "strategy",
    "trade_planner": "execution", "execution_bot": "execution", "liquidity_analyst": "execution",
    "exit_manager": "execution",
    "performance_analyst": "monitoring", "journal_ai": "monitoring", "learning_agent": "monitoring",
    "security_bot": "security", "emergency_bot": "security",
    "debate_moderator": "coordination", "consensus_engine": "coordination",
}


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class ForecastResponse(BaseModel):
    forecast_id: str
    symbol: str
    timeframe: str
    direction: str
    confidence_pct: float
    bull_probability: float
    bear_probability: float
    neutral_probability: float
    predicted_low: float
    predicted_high: float
    risk_score: float
    market_regime: str
    model_contributions: dict[str, float]
    supporting_evidence: list[str]
    contradicting_evidence: list[str]
    created_at: str
    expiry_at: str


class CalibrationStats(BaseModel):
    symbol: str
    timeframe: str
    window: int
    total_forecasts: int
    correct_direction: int
    accuracy_pct: float
    brier_score: float
    avg_confidence_pct: float
    overconfidence_bias: float
    calibration_at: str


class LeaderboardEntry(BaseModel):
    rank: int
    model_name: str
    symbol: str
    timeframe: str
    accuracy_pct: float
    brier_score: float
    total_forecasts: int
    avg_confidence_pct: float


class DashboardEntry(BaseModel):
    timeframe: str
    direction: str
    confidence_pct: float
    bull_probability: float
    bear_probability: float
    predicted_low: float
    predicted_high: float
    risk_score: float
    market_regime: str
    created_at: str
    expiry_at: str
    forecast_id: str | None


class ForecastDashboard(BaseModel):
    symbol: str
    generated_at: str
    overall_bias: str
    overall_confidence_pct: float
    timeframes: list[DashboardEntry]


class AgentContribution(BaseModel):
    agent_id: str
    signal: str
    confidence_pct: float
    reasoning: str | None
    outcome: str
    decided_at: str


class DepartmentGroup(BaseModel):
    department: str
    agents: list[AgentContribution]
    avg_confidence_pct: float
    dominant_signal: str


class AgreementSummary(BaseModel):
    total_agents: int
    agreeing_agents: int
    disagreeing_agents: int
    agreement_pct: float
    dissenting_agent_ids: list[str]


class ForecastExplanation(BaseModel):
    forecast_id: str
    symbol: str
    timeframe: str
    direction: str
    confidence_pct: float
    final_thesis: str
    supporting_evidence: list[str]
    contradicting_evidence: list[str]
    departments: list[DepartmentGroup]
    agreement: AgreementSummary
    generated_at: str
    # --- Phase 4 additions (additive) ---
    supporting_evidence_scored: list[dict[str, Any]] = Field(default_factory=list)
    contradicting_evidence_scored: list[dict[str, Any]] = Field(default_factory=list)
    bullish_score: float = 0.0
    bearish_score: float = 0.0
    net_ai_score: float = 0.0


# ---------------------------------------------------------------------------
# GET /forecasts/history — Phase 4 prediction ledger
# ---------------------------------------------------------------------------


class ForecastHistoryEntry(BaseModel):
    forecast_id: str
    symbol: str
    timeframe: str
    created_at: str
    expiry_at: str
    price_at_creation: float
    direction: str
    confidence_pct: float
    bull_probability: float
    bear_probability: float
    predicted_low: float
    predicted_high: float
    market_regime: str | None
    reasoning_summary: str | None
    # Evaluation / outcome (null until evaluator.py resolves the forecast)
    evaluated: bool
    outcome: str | None
    actual_price_at_expiry: float | None
    actual_direction: str | None
    direction_correct: bool | None
    range_hit: bool | None
    absolute_error_pct: float | None
    duration_minutes: int | None
    high_touched: float | None
    low_touched: float | None
    mfe: float | None
    mae: float | None
    tp_price: float | None
    sl_price: float | None
    tp_hit: bool | None
    sl_hit: bool | None


class ForecastHistoryPage(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[ForecastHistoryEntry]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _row_to_forecast(row: asyncpg.Record) -> ForecastResponse:
    """Convert an asyncpg Record to ForecastResponse."""
    import json as _json

    def _parse_json(val: Any) -> Any:
        if isinstance(val, str):
            try:
                return _json.loads(val)
            except Exception:
                return {}
        return val or {}

    def _parse_list(val: Any) -> list:
        if isinstance(val, list):
            return val
        if isinstance(val, str):
            try:
                return _json.loads(val)
            except Exception:
                return []
        return []

    return ForecastResponse(
        forecast_id=str(row["forecast_id"]),
        symbol=row["symbol"],
        timeframe=row["timeframe"],
        direction=row["direction"],
        confidence_pct=float(row["confidence_pct"]),
        bull_probability=float(row["bull_probability"]),
        bear_probability=float(row["bear_probability"]),
        neutral_probability=float(row.get("neutral_probability", 0.0)),
        predicted_low=float(row["predicted_low"]),
        predicted_high=float(row["predicted_high"]),
        risk_score=float(row["risk_score"]),
        market_regime=row.get("market_regime", "unknown"),
        model_contributions=_parse_json(row.get("model_contributions")),
        supporting_evidence=_parse_list(row.get("supporting_evidence")),
        contradicting_evidence=_parse_list(row.get("contradicting_evidence")),
        created_at=row["created_at"].isoformat(),
        expiry_at=row["expiry_at"].isoformat(),
    )


# ---------------------------------------------------------------------------
# GET /forecasts
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=ForecastResponse,
    summary="Latest forecast for a symbol and timeframe",
)
async def get_latest_forecast(
    symbol: str = Query(..., description="Trading symbol, e.g. BTC/USDT"),
    timeframe: str = Query(default="1h", description="Timeframe: 1m 5m 15m 1h 4h 1d 1w 1M"),
    db: asyncpg.Connection = Depends(get_db),
) -> ForecastResponse:
    row = await db.fetchrow(
        """
        SELECT forecast_id, symbol, timeframe, direction,
               confidence_pct, bull_probability, bear_probability, neutral_probability,
               predicted_low, predicted_high, risk_score, market_regime,
               model_contributions, supporting_evidence, contradicting_evidence,
               created_at, expiry_at
        FROM forecasts
        WHERE symbol = $1 AND timeframe = $2
        ORDER BY created_at DESC
        LIMIT 1
        """,
        symbol,
        timeframe,
    )

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No forecast found for {symbol} / {timeframe}.",
        )

    return _row_to_forecast(row)


# ---------------------------------------------------------------------------
# GET /forecasts/calibration
# ---------------------------------------------------------------------------


@router.get(
    "/calibration",
    response_model=CalibrationStats,
    summary="Forecast calibration statistics",
    description=(
        "Returns Brier score, directional accuracy, and overconfidence bias "
        "for a given symbol × timeframe over a rolling window of forecasts."
    ),
)
async def get_calibration(
    symbol: str = Query(..., description="Trading symbol"),
    timeframe: str = Query(default="1h"),
    window: int = Query(default=100, ge=10, le=10000, description="Number of past forecasts to analyse"),
    db: asyncpg.Connection = Depends(get_db),
) -> CalibrationStats:
    from datetime import datetime, timezone

    row = await db.fetchrow(
        """
        WITH recent AS (
            SELECT
                f.forecast_id,
                f.direction,
                f.confidence_pct,
                f.bull_probability,
                f.bear_probability,
                f.neutral_probability,
                -- Outcome: 1 if direction matched actual, 0 otherwise
                CASE
                    WHEN fo.actual_direction = f.direction THEN 1
                    ELSE 0
                END AS correct,
                -- Brier score component for the predicted probability of the outcome class
                CASE
                    WHEN fo.actual_direction = 'bullish'  THEN POWER(1 - f.bull_probability, 2)
                    WHEN fo.actual_direction = 'bearish'  THEN POWER(1 - f.bear_probability, 2)
                    WHEN fo.actual_direction = 'neutral'  THEN POWER(1 - f.neutral_probability, 2)
                    ELSE 1.0
                END AS brier_component
            FROM forecasts f
            JOIN forecast_outcomes fo ON fo.forecast_id = f.forecast_id
            WHERE f.symbol = $1 AND f.timeframe = $2
            ORDER BY f.created_at DESC
            LIMIT $3
        )
        SELECT
            COUNT(*)                      AS total_forecasts,
            SUM(correct)                  AS correct_direction,
            AVG(correct) * 100            AS accuracy_pct,
            AVG(brier_component)          AS brier_score,
            AVG(confidence_pct)           AS avg_confidence_pct,
            AVG(confidence_pct) - AVG(correct) * 100 AS overconfidence_bias
        FROM recent
        """,
        symbol,
        timeframe,
        window,
    )

    if row is None or row["total_forecasts"] == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No calibration data available for {symbol} / {timeframe}.",
        )

    return CalibrationStats(
        symbol=symbol,
        timeframe=timeframe,
        window=window,
        total_forecasts=int(row["total_forecasts"]),
        correct_direction=int(row["correct_direction"] or 0),
        accuracy_pct=float(row["accuracy_pct"] or 0.0),
        brier_score=float(row["brier_score"] or 0.0),
        avg_confidence_pct=float(row["avg_confidence_pct"] or 0.0),
        overconfidence_bias=float(row["overconfidence_bias"] or 0.0),
        calibration_at=datetime.now(timezone.utc).isoformat(),
    )


# ---------------------------------------------------------------------------
# GET /forecasts/leaderboard
# ---------------------------------------------------------------------------


@router.get(
    "/leaderboard",
    response_model=list[LeaderboardEntry],
    summary="Model accuracy leaderboard across all symbols and timeframes",
)
async def get_leaderboard(
    limit: int = Query(default=20, ge=1, le=100),
    db: asyncpg.Connection = Depends(get_db),
) -> list[LeaderboardEntry]:
    rows = await db.fetch(
        """
        WITH ranked AS (
            SELECT
                mc.model_name,
                f.symbol,
                f.timeframe,
                COUNT(*)                   AS total_forecasts,
                AVG(
                    CASE WHEN fo.actual_direction = f.direction THEN 1.0 ELSE 0.0 END
                ) * 100                    AS accuracy_pct,
                AVG(
                    CASE
                        WHEN fo.actual_direction = 'bullish' THEN POWER(1 - f.bull_probability, 2)
                        WHEN fo.actual_direction = 'bearish' THEN POWER(1 - f.bear_probability, 2)
                        WHEN fo.actual_direction = 'neutral' THEN POWER(1 - f.neutral_probability, 2)
                        ELSE 1.0
                    END
                )                          AS brier_score,
                AVG(f.confidence_pct)      AS avg_confidence_pct,
                ROW_NUMBER() OVER (
                    ORDER BY
                        AVG(CASE WHEN fo.actual_direction = f.direction THEN 1.0 ELSE 0.0 END) DESC,
                        AVG(CASE
                            WHEN fo.actual_direction = 'bullish' THEN POWER(1 - f.bull_probability, 2)
                            WHEN fo.actual_direction = 'bearish' THEN POWER(1 - f.bear_probability, 2)
                            ELSE 1.0
                        END) ASC
                ) AS rank
            FROM forecasts f
            JOIN forecast_outcomes fo ON fo.forecast_id = f.forecast_id
            JOIN model_contributions mc ON mc.forecast_id = f.forecast_id
            GROUP BY mc.model_name, f.symbol, f.timeframe
            HAVING COUNT(*) >= 10
        )
        SELECT * FROM ranked
        ORDER BY rank
        LIMIT $1
        """,
        limit,
    )

    return [
        LeaderboardEntry(
            rank=int(row["rank"]),
            model_name=row["model_name"],
            symbol=row["symbol"],
            timeframe=row["timeframe"],
            accuracy_pct=float(row["accuracy_pct"]),
            brier_score=float(row["brier_score"]),
            total_forecasts=int(row["total_forecasts"]),
            avg_confidence_pct=float(row["avg_confidence_pct"]),
        )
        for row in rows
    ]


# ---------------------------------------------------------------------------
# GET /forecasts/dashboard
# ---------------------------------------------------------------------------


@router.get(
    "/dashboard",
    response_model=ForecastDashboard,
    summary="Institutional terminal dashboard — all 8 timeframes for one symbol",
    description=(
        "Returns the latest forecast for every supported timeframe for a given symbol. "
        "Designed for a Bloomberg-style terminal view.  Missing timeframes return a "
        "placeholder entry rather than an error."
    ),
)
async def get_dashboard(
    symbol: str = Query(..., description="Trading symbol, e.g. BTC/USDT"),
    db: asyncpg.Connection = Depends(get_db),
) -> ForecastDashboard:
    from datetime import datetime, timezone

    rows = await db.fetch(
        """
        SELECT DISTINCT ON (timeframe)
               forecast_id, symbol, timeframe, direction,
               confidence_pct, bull_probability, bear_probability, neutral_probability,
               predicted_low, predicted_high, risk_score, market_regime,
               created_at, expiry_at
        FROM forecasts
        WHERE symbol = $1
        ORDER BY timeframe, created_at DESC
        """,
        symbol,
    )

    row_by_tf: dict[str, Any] = {r["timeframe"]: r for r in rows}

    entries: list[DashboardEntry] = []
    for tf in ALL_TIMEFRAMES:
        row = row_by_tf.get(tf)
        if row:
            entries.append(
                DashboardEntry(
                    timeframe=tf,
                    direction=row["direction"],
                    confidence_pct=float(row["confidence_pct"]),
                    bull_probability=float(row["bull_probability"]),
                    bear_probability=float(row["bear_probability"]),
                    predicted_low=float(row["predicted_low"]),
                    predicted_high=float(row["predicted_high"]),
                    risk_score=float(row["risk_score"]),
                    market_regime=row.get("market_regime", "unknown"),
                    created_at=row["created_at"].isoformat(),
                    expiry_at=row["expiry_at"].isoformat(),
                    forecast_id=str(row["forecast_id"]),
                )
            )
        else:
            now = datetime.now(timezone.utc).isoformat()
            entries.append(
                DashboardEntry(
                    timeframe=tf,
                    direction="neutral",
                    confidence_pct=0.0,
                    bull_probability=0.0,
                    bear_probability=0.0,
                    predicted_low=0.0,
                    predicted_high=0.0,
                    risk_score=10.0,
                    market_regime="unknown",
                    created_at=now,
                    expiry_at=now,
                    forecast_id=None,
                )
            )

    # Compute overall bias from available forecasts
    bull_votes = sum(1 for e in entries if e.direction == "bullish" and e.confidence_pct > 0)
    bear_votes = sum(1 for e in entries if e.direction == "bearish" and e.confidence_pct > 0)
    available = [e for e in entries if e.confidence_pct > 0]

    if bull_votes > bear_votes:
        overall_bias = "bullish"
    elif bear_votes > bull_votes:
        overall_bias = "bearish"
    else:
        overall_bias = "neutral"

    avg_confidence = (
        sum(e.confidence_pct for e in available) / len(available) if available else 0.0
    )

    return ForecastDashboard(
        symbol=symbol,
        generated_at=datetime.now(timezone.utc).isoformat(),
        overall_bias=overall_bias,
        overall_confidence_pct=round(avg_confidence, 2),
        timeframes=entries,
    )


@router.get(
    "/history",
    response_model=ForecastHistoryPage,
    summary="Paginated prediction history / validation ledger",
    description=(
        "Full prediction records — creation snapshot plus resolved outcome fields "
        "(win/loss/expired, MFE/MAE, duration, TP/SL breach) once evaluator.py has "
        "resolved them. This is the ledger Phase 5's chart will plot markers from."
    ),
)
async def get_forecast_history(
    symbol: str | None = Query(default=None, description="Filter by trading symbol"),
    timeframe: str | None = Query(default=None, description="Filter by timeframe"),
    outcome: str | None = Query(
        default=None, description="Filter by outcome: win, loss, expired, pending"
    ),
    since: str | None = Query(default=None, description="ISO timestamp — created_at >= since"),
    until: str | None = Query(default=None, description="ISO timestamp — created_at <= until"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: asyncpg.Connection = Depends(get_db),
) -> ForecastHistoryPage:
    conditions: list[str] = []
    params: list[Any] = []

    def _add(cond_tmpl: str, value: Any) -> None:
        params.append(value)
        conditions.append(cond_tmpl.format(n=len(params)))

    if symbol:
        _add("symbol = ${n}", symbol)
    if timeframe:
        _add("timeframe = ${n}", timeframe)
    if outcome:
        _add("outcome = ${n}", outcome)
    if since:
        _add("created_at >= ${n}::TIMESTAMPTZ", since)
    if until:
        _add("created_at <= ${n}::TIMESTAMPTZ", until)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    total_row = await db.fetchrow(
        f"SELECT COUNT(*) AS total FROM forecasts {where_clause}", *params
    )
    total = int(total_row["total"]) if total_row else 0

    params.append(limit)
    limit_idx = len(params)
    params.append(offset)
    offset_idx = len(params)

    rows = await db.fetch(
        f"""
        SELECT id AS forecast_id, symbol, timeframe, created_at, expiry_at,
               price_at_creation, direction, confidence_pct, bull_probability,
               bear_probability, predicted_low, predicted_high, market_regime,
               supporting_evidence, contradicting_evidence,
               evaluated, outcome, actual_price_at_expiry, actual_direction,
               direction_correct, range_hit, absolute_error_pct, duration_minutes,
               high_touched, low_touched, mfe, mae, tp_price, sl_price, tp_hit, sl_hit
        FROM forecasts
        {where_clause}
        ORDER BY created_at DESC
        LIMIT ${limit_idx} OFFSET ${offset_idx}
        """,
        *params,
    )

    import json as _json

    def _reasoning_summary(row: asyncpg.Record) -> str | None:
        raw = row["supporting_evidence"]
        if isinstance(raw, str):
            try:
                raw = _json.loads(raw)
            except Exception:
                raw = None
        if isinstance(raw, list) and raw:
            return "; ".join(str(x) for x in raw[:3])
        return None

    items = [
        ForecastHistoryEntry(
            forecast_id=str(r["forecast_id"]),
            symbol=r["symbol"],
            timeframe=r["timeframe"],
            created_at=r["created_at"].isoformat(),
            expiry_at=r["expiry_at"].isoformat(),
            price_at_creation=float(r["price_at_creation"]) if r["price_at_creation"] is not None else 0.0,
            direction=r["direction"],
            confidence_pct=float(r["confidence_pct"]) if r["confidence_pct"] is not None else 0.0,
            bull_probability=float(r["bull_probability"]) if r["bull_probability"] is not None else 0.0,
            bear_probability=float(r["bear_probability"]) if r["bear_probability"] is not None else 0.0,
            predicted_low=float(r["predicted_low"]) if r["predicted_low"] is not None else 0.0,
            predicted_high=float(r["predicted_high"]) if r["predicted_high"] is not None else 0.0,
            market_regime=r["market_regime"],
            reasoning_summary=_reasoning_summary(r),
            evaluated=bool(r["evaluated"]),
            outcome=r["outcome"],
            actual_price_at_expiry=float(r["actual_price_at_expiry"]) if r["actual_price_at_expiry"] is not None else None,
            actual_direction=r["actual_direction"],
            direction_correct=r["direction_correct"],
            range_hit=r["range_hit"],
            absolute_error_pct=float(r["absolute_error_pct"]) if r["absolute_error_pct"] is not None else None,
            duration_minutes=r["duration_minutes"],
            high_touched=float(r["high_touched"]) if r["high_touched"] is not None else None,
            low_touched=float(r["low_touched"]) if r["low_touched"] is not None else None,
            mfe=float(r["mfe"]) if r["mfe"] is not None else None,
            mae=float(r["mae"]) if r["mae"] is not None else None,
            tp_price=float(r["tp_price"]) if r["tp_price"] is not None else None,
            sl_price=float(r["sl_price"]) if r["sl_price"] is not None else None,
            tp_hit=r["tp_hit"],
            sl_hit=r["sl_hit"],
        )
        for r in rows
    ]

    return ForecastHistoryPage(total=total, limit=limit, offset=offset, items=items)


# ---------------------------------------------------------------------------
# GET /forecasts/{forecast_id}
# ---------------------------------------------------------------------------


@router.get(
    "/{forecast_id}",
    response_model=ForecastResponse,
    summary="Get a specific forecast by ID",
)
async def get_forecast_by_id(
    forecast_id: str,
    db: asyncpg.Connection = Depends(get_db),
) -> ForecastResponse:
    row = await db.fetchrow(
        """
        SELECT forecast_id, symbol, timeframe, direction,
               confidence_pct, bull_probability, bear_probability, neutral_probability,
               predicted_low, predicted_high, risk_score, market_regime,
               model_contributions, supporting_evidence, contradicting_evidence,
               created_at, expiry_at
        FROM forecasts
        WHERE forecast_id = $1
        """,
        forecast_id,
    )

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Forecast '{forecast_id}' not found.",
        )

    return _row_to_forecast(row)


# ---------------------------------------------------------------------------
# GET /forecasts/{forecast_id}/explain
# ---------------------------------------------------------------------------


@router.get(
    "/{forecast_id}/explain",
    response_model=ForecastExplanation,
    summary="Full agent-by-agent explanation of a forecast's consensus",
    description=(
        "Aggregates existing agent_decisions and the originating trade_proposal's "
        "debate_summary/agent_signals (no new agent logic) into a department-grouped "
        "explanation: who contributed, who agreed vs disagreed, and the final thesis."
    ),
)
async def explain_forecast(
    forecast_id: str,
    db: asyncpg.Connection = Depends(get_db),
) -> ForecastExplanation:
    forecast = await db.fetchrow(
        """
        SELECT forecast_id, symbol, timeframe, direction, confidence_pct,
               supporting_evidence, contradicting_evidence, created_at, expiry_at
        FROM forecasts
        WHERE forecast_id = $1
        """,
        forecast_id,
    )
    if forecast is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Forecast '{forecast_id}' not found.",
        )

    import json as _json

    def _parse_list(val: Any) -> list:
        if isinstance(val, list):
            return val
        if isinstance(val, str):
            try:
                return _json.loads(val)
            except Exception:
                return []
        return []

    # Agent decisions in the window this forecast covers, for the same symbol.
    decisions = await db.fetch(
        """
        SELECT agent_id, signal, confidence, reasoning, outcome, decided_at,
               supporting_evidence_scored, contradicting_evidence_scored
        FROM agent_decisions
        WHERE symbol = $1 AND decided_at BETWEEN $2 AND $3
        ORDER BY decided_at DESC
        """,
        forecast["symbol"],
        forecast["created_at"],
        forecast["expiry_at"],
    )

    # Phase 4: aggregate whatever numeric scored evidence is present across the
    # agent_decisions in this window (populated when agents provide
    # AgentReport.supporting_evidence_scored / contradicting_evidence_scored —
    # see graph/state.py). Agents without scored evidence simply contribute 0.
    scored_support: list[dict[str, Any]] = []
    scored_contra: list[dict[str, Any]] = []
    bullish_score = 0.0
    bearish_score = 0.0
    for d in decisions:
        sup = d["supporting_evidence_scored"]
        con = d["contradicting_evidence_scored"]
        if isinstance(sup, str):
            try:
                sup = _json.loads(sup)
            except Exception:
                sup = None
        if isinstance(con, str):
            try:
                con = _json.loads(con)
            except Exception:
                con = None
        if isinstance(sup, list):
            for item in sup:
                if isinstance(item, dict) and "score" in item:
                    scored_support.append({**item, "agent_id": d["agent_id"]})
                    try:
                        bullish_score += float(item["score"])
                    except (TypeError, ValueError):
                        pass
        if isinstance(con, list):
            for item in con:
                if isinstance(item, dict) and "score" in item:
                    scored_contra.append({**item, "agent_id": d["agent_id"]})
                    try:
                        bearish_score += float(item["score"])
                    except (TypeError, ValueError):
                        pass
    net_ai_score = bullish_score - bearish_score

    # Final thesis — pulled from the most recent matching trade_proposal's
    # debate_summary JSONB rather than re-derived (ConsensusResult.final_thesis
    # is serialized there when the proposal is persisted).
    proposal = await db.fetchrow(
        """
        SELECT debate_summary
        FROM trade_proposals
        WHERE symbol = $1
        ORDER BY ABS(EXTRACT(EPOCH FROM (proposed_at - $2::TIMESTAMPTZ)))
        LIMIT 1
        """,
        forecast["symbol"],
        forecast["created_at"],
    )
    final_thesis = "No consensus thesis on record for this forecast."
    if proposal and proposal["debate_summary"]:
        debate = proposal["debate_summary"]
        if isinstance(debate, str):
            try:
                debate = _json.loads(debate)
            except Exception:
                debate = {}
        if isinstance(debate, dict):
            final_thesis = debate.get("final_thesis", final_thesis)

    # Group by department
    by_dept: dict[str, list[AgentContribution]] = {}
    for d in decisions:
        dept = _AGENT_DEPARTMENTS.get(d["agent_id"], "other")
        by_dept.setdefault(dept, []).append(
            AgentContribution(
                agent_id=d["agent_id"],
                signal=d["signal"],
                confidence_pct=round(float(d["confidence"] or 0.0) * 100.0, 2),
                reasoning=d["reasoning"],
                outcome=d["outcome"],
                decided_at=d["decided_at"].isoformat(),
            )
        )

    departments: list[DepartmentGroup] = []
    for dept, agents in sorted(by_dept.items()):
        avg_conf = sum(a.confidence_pct for a in agents) / len(agents) if agents else 0.0
        signal_counts: dict[str, int] = {}
        for a in agents:
            signal_counts[a.signal] = signal_counts.get(a.signal, 0) + 1
        dominant = max(signal_counts, key=signal_counts.get) if signal_counts else "neutral"
        departments.append(
            DepartmentGroup(
                department=dept,
                agents=agents,
                avg_confidence_pct=round(avg_conf, 2),
                dominant_signal=dominant,
            )
        )

    # Agreement summary: an agent "agrees" if its signal direction matches the
    # forecast's overall direction (bullish/bearish), "neutral"/"no_signal" and
    # opposite-direction agents count as dissenting.
    direction_signal_map = {"bullish": "bullish", "bearish": "bearish"}
    forecast_signal = direction_signal_map.get(forecast["direction"], forecast["direction"])

    all_agents = [a for group in departments for a in group.agents]
    total_agents = len(all_agents)
    agreeing = [a for a in all_agents if a.signal == forecast_signal]
    dissenting = [a for a in all_agents if a.signal != forecast_signal]

    agreement = AgreementSummary(
        total_agents=total_agents,
        agreeing_agents=len(agreeing),
        disagreeing_agents=len(dissenting),
        agreement_pct=round((len(agreeing) / total_agents * 100.0) if total_agents else 0.0, 2),
        dissenting_agent_ids=[a.agent_id for a in dissenting],
    )

    from datetime import datetime, timezone

    return ForecastExplanation(
        forecast_id=str(forecast["forecast_id"]),
        symbol=forecast["symbol"],
        timeframe=forecast["timeframe"],
        direction=forecast["direction"],
        confidence_pct=float(forecast["confidence_pct"]),
        final_thesis=final_thesis,
        supporting_evidence=_parse_list(forecast["supporting_evidence"]),
        contradicting_evidence=_parse_list(forecast["contradicting_evidence"]),
        departments=departments,
        agreement=agreement,
        generated_at=datetime.now(timezone.utc).isoformat(),
        supporting_evidence_scored=scored_support,
        contradicting_evidence_scored=scored_contra,
        bullish_score=round(bullish_score, 4),
        bearish_score=round(bearish_score, 4),
        net_ai_score=round(net_ai_score, 4),
    )
