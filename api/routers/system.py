"""
api/routers/system.py
======================
System control endpoints — kill switch, circuit breakers, and overall status.

Endpoints
---------
POST /system/kill-switch/activate     — halt all trading immediately
POST /system/kill-switch/deactivate   — re-enable trading
GET  /system/kill-switch/status       — current kill switch state
GET  /system/circuit-breakers         — circuit breaker state + daily PnL
POST /system/circuit-breakers/reset   — reset after cooldown
GET  /system/status                   — full system health snapshot
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from api.dependencies import get_redis
from risk.circuit_breakers import CircuitBreaker, KillSwitch, SafetyGate

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class KillSwitchActivateRequest(BaseModel):
    reason: str = Field(..., min_length=1, description="Human-readable reason for activation.")
    operator: str = Field(default="api_user", description="Identity of the operator.")


class KillSwitchDeactivateRequest(BaseModel):
    operator: str = Field(default="api_user", description="Identity of the operator.")


class CircuitBreakerResetRequest(BaseModel):
    operator: str = Field(default="api_user", description="Identity of the operator.")


class KillSwitchStatusResponse(BaseModel):
    active: bool
    reason: str | None
    operator: str | None
    activated_at: str | None = None
    deactivated_at: str | None = None
    checked_at: str


class CircuitBreakerResponse(BaseModel):
    tripped: bool
    reason: str | None
    tripped_at: str | None
    cooldown_minutes: int | None
    reset_at: str | None
    daily_pnl_usd: float
    consecutive_losses: int
    checked_at: str


class SystemStatusResponse(BaseModel):
    status: str  # "all_clear" | "degraded" | "halted"
    environment: str
    kill_switch: dict
    circuit_breaker: dict
    daily_pnl_usd: float
    consecutive_losses: int
    all_clear: bool
    active_agents: int
    checked_at: str


# ---------------------------------------------------------------------------
# Kill switch endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/kill-switch/activate",
    summary="EMERGENCY: Halt all trading immediately",
    description=(
        "Arms the kill switch.  All subsequent safety gate checks across every "
        "running graph instance will block order submission immediately."
    ),
)
async def activate_kill_switch(
    body: KillSwitchActivateRequest,
    redis: aioredis.Redis = Depends(get_redis),
) -> dict:
    ks = KillSwitch(redis)
    await ks.activate(reason=body.reason, operator=body.operator)

    logger.critical(
        "KILL SWITCH ACTIVATED via API: reason=%s operator=%s",
        body.reason,
        body.operator,
    )

    return {
        "status": "activated",
        "reason": body.reason,
        "operator": body.operator,
        "activated_at": datetime.now(timezone.utc).isoformat(),
        "message": "Kill switch armed. All trading halted immediately.",
    }


@router.post(
    "/kill-switch/deactivate",
    summary="Re-enable trading after kill switch",
    description="Disarms the kill switch, allowing the graph to resume trading.",
)
async def deactivate_kill_switch(
    body: KillSwitchDeactivateRequest,
    redis: aioredis.Redis = Depends(get_redis),
) -> dict:
    ks = KillSwitch(redis)

    # Confirm it was actually active to avoid accidental resets
    if not await ks.is_active():
        return {
            "status": "already_inactive",
            "operator": body.operator,
            "message": "Kill switch was not active.",
        }

    await ks.deactivate(operator=body.operator)

    logger.warning(
        "Kill switch deactivated via API: operator=%s", body.operator
    )

    return {
        "status": "deactivated",
        "operator": body.operator,
        "deactivated_at": datetime.now(timezone.utc).isoformat(),
        "message": "Kill switch disarmed. Trading may resume after operator confirmation.",
    }


@router.get(
    "/kill-switch/status",
    response_model=KillSwitchStatusResponse,
    summary="Get current kill switch state",
)
async def kill_switch_status(
    redis: aioredis.Redis = Depends(get_redis),
) -> KillSwitchStatusResponse:
    ks = KillSwitch(redis)
    state = await ks.get_status()

    return KillSwitchStatusResponse(
        active=bool(state.get("active", False)),
        reason=state.get("reason"),
        operator=state.get("operator"),
        activated_at=state.get("activated_at"),
        deactivated_at=state.get("deactivated_at"),
        checked_at=datetime.now(timezone.utc).isoformat(),
    )


# ---------------------------------------------------------------------------
# Circuit breaker endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/circuit-breakers",
    response_model=CircuitBreakerResponse,
    summary="Get circuit breaker state and daily PnL",
)
async def get_circuit_breakers(
    redis: aioredis.Redis = Depends(get_redis),
) -> CircuitBreakerResponse:
    cb = CircuitBreaker(redis)
    state = await cb.get_state()
    daily_pnl = await cb.get_daily_pnl()
    consecutive_losses = await cb.get_consecutive_losses()

    return CircuitBreakerResponse(
        tripped=bool(state.get("tripped", False)),
        reason=state.get("reason"),
        tripped_at=state.get("tripped_at"),
        cooldown_minutes=state.get("cooldown_minutes"),
        reset_at=state.get("reset_at"),
        daily_pnl_usd=daily_pnl,
        consecutive_losses=consecutive_losses,
        checked_at=datetime.now(timezone.utc).isoformat(),
    )


@router.post(
    "/circuit-breakers/reset",
    summary="Reset the circuit breaker after cooldown",
    description=(
        "Manually reset the circuit breaker after the cooldown period has elapsed. "
        "Also resets the daily PnL and consecutive-loss counters."
    ),
)
async def reset_circuit_breaker(
    body: CircuitBreakerResetRequest,
    redis: aioredis.Redis = Depends(get_redis),
) -> dict:
    cb = CircuitBreaker(redis)

    if not await cb.check():
        return {
            "status": "not_tripped",
            "message": "Circuit breaker is not currently tripped.",
            "operator": body.operator,
        }

    await cb.reset(operator=body.operator)

    logger.warning(
        "Circuit breaker reset via API: operator=%s", body.operator
    )

    return {
        "status": "reset",
        "operator": body.operator,
        "reset_at": datetime.now(timezone.utc).isoformat(),
        "message": "Circuit breaker reset. Daily PnL and consecutive loss counters cleared.",
    }


# ---------------------------------------------------------------------------
# System status
# ---------------------------------------------------------------------------


@router.get(
    "/status",
    response_model=SystemStatusResponse,
    summary="Full system status snapshot",
    description=(
        "Returns a composite snapshot of all system components: kill switch, "
        "circuit breaker, daily PnL, active agent count, and service connectivity."
    ),
)
async def system_status(
    redis: aioredis.Redis = Depends(get_redis),
) -> SystemStatusResponse:
    from config.settings import get_settings
    from agents.registry import AGENT_REGISTRY_MAP

    settings = get_settings()
    gate = SafetyGate(redis)

    composite = await gate.get_status()

    ks = composite["kill_switch"]
    cb = composite["circuit_breaker"]
    all_clear: bool = composite["all_clear"]

    if ks.get("active"):
        overall_status = "halted"
    elif cb.get("tripped"):
        overall_status = "degraded"
    elif all_clear:
        overall_status = "all_clear"
    else:
        overall_status = "degraded"

    return SystemStatusResponse(
        status=overall_status,
        environment=settings.environment,
        kill_switch=ks,
        circuit_breaker=cb,
        daily_pnl_usd=composite["daily_pnl"],
        consecutive_losses=composite["consecutive_losses"],
        all_clear=all_clear,
        active_agents=len(AGENT_REGISTRY_MAP),
        checked_at=composite["checked_at"],
    )
