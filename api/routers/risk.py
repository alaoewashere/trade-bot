"""
api/routers/risk.py
====================
Risk monitoring and management endpoints.

Endpoints
---------
GET  /risk/assessments              — paginated risk assessment history
GET  /risk/assessments/{id}         — specific risk assessment detail
GET  /risk/limits                   — current risk limit configuration
POST /risk/limits                   — update risk limits (paper only)
GET  /risk/violations               — recent limit violations / rejections
GET  /risk/var                      — current portfolio VaR summary
GET  /risk/heatmap                  — portfolio heat and correlation matrix
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from api.dependencies import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class RiskAssessmentResponse(BaseModel):
    assessment_id: str
    symbol: str
    direction: str
    approved: bool
    position_size_usd: float
    position_size_units: float
    entry_price: float
    stop_loss: float
    take_profit: float
    risk_reward: float
    max_risk_usd: float
    portfolio_heat_pct: float
    var_95: float
    correlation_check: bool
    liquidity_check: bool
    rejection_reasons: list[str]
    consensus_confidence_pct: float | None
    created_at: str
    cvar_95: float
    kelly_fraction: float
    expected_value_usd: float
    risk_category: str


class RiskLimitsResponse(BaseModel):
    max_daily_loss_usd: float
    max_weekly_loss_usd: float
    max_monthly_drawdown_usd: float
    max_position_size_usd: float
    max_leverage: float
    max_portfolio_heat_pct: float
    max_open_positions: int
    min_confidence_pct: float
    min_risk_reward: float
    min_liquidity_24h_usd: float
    max_portfolio_correlation: float
    approval_timeout_minutes: int
    environment: str


class RiskLimitsUpdate(BaseModel):
    max_daily_loss_usd: float | None = None
    max_position_size_usd: float | None = None
    max_portfolio_heat_pct: float | None = None
    max_open_positions: int | None = None
    min_confidence_pct: float | None = None
    min_risk_reward: float | None = None


class RiskViolation(BaseModel):
    violation_id: str
    violation_type: str
    symbol: str
    direction: str | None
    severity: str  # warning | error | critical
    message: str
    context: dict[str, Any]
    occurred_at: str


class VaRSummary(BaseModel):
    portfolio_var_95_usd: float
    portfolio_var_99_usd: float
    worst_position_var_usd: str | None
    total_positions_value_usd: float
    methodology: str
    calculated_at: str


class HeatmapEntry(BaseModel):
    symbol: str
    position_size_usd: float
    risk_usd: float
    heat_pct: float
    var_95_usd: float
    direction: str


class PortfolioHeatmap(BaseModel):
    total_heat_pct: float
    equity_usd: float
    positions: list[HeatmapEntry]
    calculated_at: str


# ---------------------------------------------------------------------------
# GET /risk/assessments
# ---------------------------------------------------------------------------


@router.get(
    "/assessments",
    response_model=list[RiskAssessmentResponse],
    summary="Paginated risk assessment history",
)
async def list_risk_assessments(
    symbol: str | None = Query(default=None),
    approved_only: bool = Query(default=False),
    rejected_only: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: asyncpg.Connection = Depends(get_db),
) -> list[RiskAssessmentResponse]:
    conditions = []
    params: list[Any] = []
    idx = 1

    if symbol:
        conditions.append(f"symbol = ${idx}")
        params.append(symbol)
        idx += 1

    if approved_only:
        conditions.append("approved = TRUE")
    elif rejected_only:
        conditions.append("approved = FALSE")

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    params += [limit, offset]

    rows = await db.fetch(
        f"""
        SELECT
            assessment_id, symbol, direction, approved,
            position_size_usd, position_size_units, entry_price,
            stop_loss, take_profit, risk_reward, max_risk_usd,
            portfolio_heat_pct, var_95, correlation_check, liquidity_check,
            rejection_reasons, consensus_confidence_pct, created_at,
            cvar_95, kelly_fraction, expected_value_usd, risk_category
        FROM risk_assessments
        {where}
        ORDER BY created_at DESC
        LIMIT ${idx} OFFSET ${idx+1}
        """,
        *params,
    )

    return [
        RiskAssessmentResponse(
            assessment_id=str(r["assessment_id"]),
            symbol=r["symbol"],
            direction=r.get("direction", ""),
            approved=bool(r["approved"]),
            position_size_usd=float(r["position_size_usd"] or 0.0),
            position_size_units=float(r["position_size_units"] or 0.0),
            entry_price=float(r["entry_price"] or 0.0),
            stop_loss=float(r["stop_loss"] or 0.0),
            take_profit=float(r["take_profit"] or 0.0),
            risk_reward=float(r["risk_reward"] or 0.0),
            max_risk_usd=float(r["max_risk_usd"] or 0.0),
            portfolio_heat_pct=float(r["portfolio_heat_pct"] or 0.0),
            var_95=float(r["var_95"] or 0.0),
            correlation_check=bool(r["correlation_check"]),
            liquidity_check=bool(r["liquidity_check"]),
            rejection_reasons=r["rejection_reasons"] or [],
            consensus_confidence_pct=(
                float(r["consensus_confidence_pct"]) if r.get("consensus_confidence_pct") else None
            ),
            created_at=r["created_at"].isoformat(),
            cvar_95=float(r["cvar_95"] or 0.0),
            kelly_fraction=float(r["kelly_fraction"] or 0.0),
            expected_value_usd=float(r["expected_value_usd"] or 0.0),
            risk_category=r.get("risk_category", "medium"),
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# GET /risk/assessments/{assessment_id}
# ---------------------------------------------------------------------------


@router.get(
    "/assessments/{assessment_id}",
    response_model=RiskAssessmentResponse,
    summary="Get a specific risk assessment",
)
async def get_risk_assessment(
    assessment_id: str,
    db: asyncpg.Connection = Depends(get_db),
) -> RiskAssessmentResponse:
    row = await db.fetchrow(
        """
        SELECT
            assessment_id, symbol, direction, approved,
            position_size_usd, position_size_units, entry_price,
            stop_loss, take_profit, risk_reward, max_risk_usd,
            portfolio_heat_pct, var_95, correlation_check, liquidity_check,
            rejection_reasons, consensus_confidence_pct, created_at,
            cvar_95, kelly_fraction, expected_value_usd, risk_category
        FROM risk_assessments
        WHERE assessment_id = $1
        """,
        assessment_id,
    )

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Risk assessment '{assessment_id}' not found.",
        )

    return RiskAssessmentResponse(
        assessment_id=str(row["assessment_id"]),
        symbol=row["symbol"],
        direction=row.get("direction", ""),
        approved=bool(row["approved"]),
        position_size_usd=float(row["position_size_usd"] or 0.0),
        position_size_units=float(row["position_size_units"] or 0.0),
        entry_price=float(row["entry_price"] or 0.0),
        stop_loss=float(row["stop_loss"] or 0.0),
        take_profit=float(row["take_profit"] or 0.0),
        risk_reward=float(row["risk_reward"] or 0.0),
        max_risk_usd=float(row["max_risk_usd"] or 0.0),
        portfolio_heat_pct=float(row["portfolio_heat_pct"] or 0.0),
        var_95=float(row["var_95"] or 0.0),
        correlation_check=bool(row["correlation_check"]),
        liquidity_check=bool(row["liquidity_check"]),
        rejection_reasons=row["rejection_reasons"] or [],
        consensus_confidence_pct=(
            float(row["consensus_confidence_pct"]) if row.get("consensus_confidence_pct") else None
        ),
        created_at=row["created_at"].isoformat(),
        cvar_95=float(row["cvar_95"] or 0.0),
        kelly_fraction=float(row["kelly_fraction"] or 0.0),
        expected_value_usd=float(row["expected_value_usd"] or 0.0),
        risk_category=row.get("risk_category", "medium"),
    )


# ---------------------------------------------------------------------------
# GET /risk/limits
# ---------------------------------------------------------------------------


@router.get(
    "/limits",
    response_model=RiskLimitsResponse,
    summary="Current risk limit configuration",
)
async def get_risk_limits() -> RiskLimitsResponse:
    from config.settings import get_settings
    from risk.limits import (
        MAX_PORTFOLIO_HEAT_PCT,
        MAX_OPEN_POSITIONS,
        MIN_CONFIDENCE_PCT,
        MIN_RISK_REWARD,
        MIN_LIQUIDITY_24H_USD,
        MAX_PORTFOLIO_CORRELATION,
    )

    settings = get_settings()

    return RiskLimitsResponse(
        max_daily_loss_usd=settings.max_daily_loss,
        max_weekly_loss_usd=settings.max_weekly_loss,
        max_monthly_drawdown_usd=settings.max_monthly_drawdown,
        max_position_size_usd=settings.max_position_size_usd,
        max_leverage=settings.max_leverage,
        max_portfolio_heat_pct=MAX_PORTFOLIO_HEAT_PCT,
        max_open_positions=MAX_OPEN_POSITIONS,
        min_confidence_pct=MIN_CONFIDENCE_PCT,
        min_risk_reward=MIN_RISK_REWARD,
        min_liquidity_24h_usd=MIN_LIQUIDITY_24H_USD,
        max_portfolio_correlation=MAX_PORTFOLIO_CORRELATION,
        approval_timeout_minutes=settings.approval_timeout_minutes,
        environment=settings.environment,
    )


# ---------------------------------------------------------------------------
# POST /risk/limits
# ---------------------------------------------------------------------------


@router.post(
    "/limits",
    summary="Update risk limits (paper trading mode only)",
)
async def update_risk_limits(
    body: RiskLimitsUpdate,
    db: asyncpg.Connection = Depends(get_db),
) -> dict[str, Any]:
    from config.settings import get_settings

    settings = get_settings()
    if settings.is_live:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Risk limit updates are not permitted in live trading mode.",
        )

    updates: dict[str, Any] = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No limit values provided.",
        )

    # Persist to DB for audit trail
    await db.execute(
        """
        INSERT INTO risk_limit_overrides (override_data, applied_at, operator)
        VALUES ($1, NOW(), 'api_user')
        """,
        updates,
    )

    return {
        "status": "updated",
        "updated_fields": list(updates.keys()),
        "note": "Limits updated in DB. Restart the graph to apply in-memory changes.",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# GET /risk/violations
# ---------------------------------------------------------------------------


@router.get(
    "/violations",
    response_model=list[RiskViolation],
    summary="Recent risk limit violations and rejection events",
)
async def get_risk_violations(
    severity: str | None = Query(default=None, description="warning | error | critical"),
    limit: int = Query(default=50, ge=1, le=500),
    db: asyncpg.Connection = Depends(get_db),
) -> list[RiskViolation]:
    conditions = []
    params: list[Any] = []
    idx = 1

    if severity:
        conditions.append(f"severity = ${idx}")
        params.append(severity)
        idx += 1

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    params.append(limit)

    rows = await db.fetch(
        f"""
        SELECT
            violation_id, violation_type, symbol, direction,
            severity, message, context, occurred_at
        FROM risk_violations
        {where}
        ORDER BY occurred_at DESC
        LIMIT ${idx}
        """,
        *params,
    )

    return [
        RiskViolation(
            violation_id=str(r["violation_id"]),
            violation_type=r["violation_type"],
            symbol=r["symbol"],
            direction=r.get("direction"),
            severity=r["severity"],
            message=r["message"],
            context=r["context"] or {},
            occurred_at=r["occurred_at"].isoformat(),
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# GET /risk/var
# ---------------------------------------------------------------------------


@router.get(
    "/var",
    response_model=VaRSummary,
    summary="Current portfolio Value-at-Risk summary",
)
async def get_var(
    db: asyncpg.Connection = Depends(get_db),
) -> VaRSummary:
    row = await db.fetchrow(
        """
        SELECT
            SUM(var_95)   AS portfolio_var_95,
            SUM(var_99)   AS portfolio_var_99,
            SUM(filled_price * quantity) AS total_value,
            symbol || ' ' || direction AS worst_pos
        FROM trades t
        LEFT JOIN risk_assessments ra ON ra.symbol = t.symbol AND ra.approved = TRUE
            AND ra.created_at = (
                SELECT MAX(ra2.created_at) FROM risk_assessments ra2
                WHERE ra2.symbol = t.symbol
            )
        WHERE t.status = 'open'
        GROUP BY t.symbol, t.direction
        ORDER BY var_95 DESC
        LIMIT 1
        """,
    )

    return VaRSummary(
        portfolio_var_95_usd=float(row["portfolio_var_95"] or 0.0) if row else 0.0,
        portfolio_var_99_usd=float(row["portfolio_var_99"] or 0.0) if row else 0.0,
        worst_position_var_usd=row["worst_pos"] if row else None,
        total_positions_value_usd=float(row["total_value"] or 0.0) if row else 0.0,
        methodology="Parametric VaR (95% / 99% confidence, 1-day horizon)",
        calculated_at=datetime.now(timezone.utc).isoformat(),
    )


# ---------------------------------------------------------------------------
# GET /risk/heatmap
# ---------------------------------------------------------------------------


@router.get(
    "/heatmap",
    response_model=PortfolioHeatmap,
    summary="Portfolio heat map by position",
)
async def get_heatmap(
    db: asyncpg.Connection = Depends(get_db),
) -> PortfolioHeatmap:
    equity_row = await db.fetchrow(
        "SELECT equity_usd FROM portfolio_equity ORDER BY recorded_at DESC LIMIT 1"
    )
    equity = float(equity_row["equity_usd"]) if equity_row else 10_000.0

    rows = await db.fetch(
        """
        SELECT
            t.symbol,
            t.direction,
            t.filled_price * t.quantity                                  AS position_size_usd,
            ABS(t.filled_price - t.stop_loss) * t.quantity               AS risk_usd,
            COALESCE(ra.var_95, 0)                                        AS var_95
        FROM trades t
        LEFT JOIN risk_assessments ra ON ra.symbol = t.symbol AND ra.approved = TRUE
            AND ra.created_at = (
                SELECT MAX(ra2.created_at) FROM risk_assessments ra2 WHERE ra2.symbol = t.symbol
            )
        WHERE t.status = 'open'
        ORDER BY risk_usd DESC
        """,
    )

    positions: list[HeatmapEntry] = []
    total_heat = 0.0

    for r in rows:
        risk_usd = float(r["risk_usd"] or 0.0)
        heat_pct = risk_usd / equity * 100 if equity > 0 else 0.0
        total_heat += heat_pct

        positions.append(
            HeatmapEntry(
                symbol=r["symbol"],
                position_size_usd=float(r["position_size_usd"] or 0.0),
                risk_usd=risk_usd,
                heat_pct=round(heat_pct, 2),
                var_95_usd=float(r["var_95"] or 0.0),
                direction=r["direction"],
            )
        )

    return PortfolioHeatmap(
        total_heat_pct=round(total_heat, 2),
        equity_usd=equity,
        positions=positions,
        calculated_at=datetime.now(timezone.utc).isoformat(),
    )
