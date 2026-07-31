"""
api/routers/approvals.py
=========================
Human trade approval endpoints — the critical gate between AI consensus
and live order submission.

Every trade proposal that passes the AI analysis, strategy, debate,
consensus, and risk-gate pipeline is written to Redis as a pending approval
request.  A human operator must approve or reject it within the configured
timeout window before the LangGraph graph can continue to the execution
subgraph.

Endpoints
---------
GET  /approvals/pending                 — list all pending requests
GET  /approvals/{approval_id}           — fetch a specific request
POST /approvals/{approval_id}/approve   — approve and resume graph
POST /approvals/{approval_id}/reject    — reject the trade
POST /approvals/{approval_id}/request-info — ask the AI for more analysis
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from api.dependencies import get_redis

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class ApprovalDecision(BaseModel):
    reason: str = Field(default="", description="Optional human-readable justification.")


class ApprovalResponse(BaseModel):
    approval_id: str
    symbol: str
    direction: str
    confidence_pct: float
    risk_assessment: dict[str, Any]
    consensus_summary: str
    debate_excerpt: str
    expires_at: str
    created_at: str
    status: str


class ApprovalActionResponse(BaseModel):
    approval_id: str
    status: str
    decided_at: str
    reason: str
    message: str


class InfoRequestResponse(BaseModel):
    approval_id: str
    question: str
    submitted_at: str
    message: str


# ---------------------------------------------------------------------------
# Redis key helpers
# ---------------------------------------------------------------------------

_PENDING_ZSET = "approval:pending"


def _approval_key(approval_id: str) -> str:
    return f"approval:{approval_id}"


def _decision_key(approval_id: str) -> str:
    return f"approval:decisions:{approval_id}"


def _info_request_key(approval_id: str) -> str:
    return f"approval:info_requests:{approval_id}"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _fetch_approval_payload(
    approval_id: str,
    redis: aioredis.Redis,
) -> dict[str, Any]:
    """
    Read and deserialise an approval payload from Redis.

    Raises HTTP 404 if the approval does not exist (expired or unknown ID).
    """
    raw = await redis.get(_approval_key(approval_id))
    if raw is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Approval '{approval_id}' not found or has expired.",
        )
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Corrupted approval payload for '{approval_id}': {exc}",
        ) from exc


def _payload_to_response(payload: dict[str, Any]) -> ApprovalResponse:
    """Convert a raw Redis payload dict to an ApprovalResponse model."""
    return ApprovalResponse(
        approval_id=payload.get("approval_id", ""),
        symbol=payload.get("symbol", ""),
        direction=payload.get("direction", ""),
        confidence_pct=float(payload.get("confidence_pct", 0.0)),
        risk_assessment=payload.get("risk_assessment", {}),
        consensus_summary=payload.get("final_thesis", payload.get("consensus_summary", "")),
        debate_excerpt=payload.get("debate_excerpt", ""),
        expires_at=payload.get("expires_at", ""),
        created_at=payload.get("created_at", ""),
        status=payload.get("status", "pending"),
    )


async def _assert_still_pending(
    approval_id: str,
    payload: dict[str, Any],
) -> None:
    """Raise HTTP 409 Conflict if the approval is no longer in pending state."""
    current_status = payload.get("status", "pending")
    if current_status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Approval '{approval_id}' is no longer pending "
                f"(current status: {current_status})."
            ),
        )

    # Also check expiry
    expires_at_str: str | None = payload.get("expires_at")
    if expires_at_str:
        try:
            expires_at = datetime.fromisoformat(expires_at_str)
            if datetime.now(timezone.utc) > expires_at:
                raise HTTPException(
                    status_code=status.HTTP_410_GONE,
                    detail=f"Approval '{approval_id}' has expired.",
                )
        except ValueError:
            pass  # Malformed timestamp — allow through


# ---------------------------------------------------------------------------
# GET /pending
# ---------------------------------------------------------------------------


@router.get(
    "/pending",
    response_model=list[ApprovalResponse],
    summary="List pending trade approvals",
    description=(
        "Returns all trade proposals currently awaiting a human decision, "
        "ordered by expiry time (soonest first)."
    ),
)
async def get_pending_approvals(
    redis: aioredis.Redis = Depends(get_redis),
) -> list[ApprovalResponse]:
    # Read pending IDs from sorted set (score = expiry timestamp, ascending)
    now_ts = datetime.now(timezone.utc).timestamp()
    pending_ids: list[str] = await redis.zrangebyscore(
        _PENDING_ZSET,
        min=now_ts,  # only non-expired entries
        max="+inf",
    )

    results: list[ApprovalResponse] = []
    for approval_id in pending_ids:
        try:
            raw = await redis.get(_approval_key(approval_id))
            if raw is None:
                # Expired / removed — clean up the sorted set
                await redis.zrem(_PENDING_ZSET, approval_id)
                continue
            payload = json.loads(raw)
            if payload.get("status") == "pending":
                results.append(_payload_to_response(payload))
        except Exception as exc:
            logger.warning("get_pending: skipping %s — %s", approval_id, exc)

    return results


# ---------------------------------------------------------------------------
# GET /{approval_id}
# ---------------------------------------------------------------------------


@router.get(
    "/{approval_id}",
    response_model=ApprovalResponse,
    summary="Get a specific approval request",
)
async def get_approval(
    approval_id: str,
    redis: aioredis.Redis = Depends(get_redis),
) -> ApprovalResponse:
    payload = await _fetch_approval_payload(approval_id, redis)
    return _payload_to_response(payload)


# ---------------------------------------------------------------------------
# POST /{approval_id}/approve
# ---------------------------------------------------------------------------


@router.post(
    "/{approval_id}/approve",
    response_model=ApprovalActionResponse,
    summary="Approve a trade proposal",
    description=(
        "Approve a pending trade proposal.  The LangGraph graph will be notified "
        "via Redis and will resume the execution subgraph asynchronously."
    ),
)
async def approve_trade(
    approval_id: str,
    decision: ApprovalDecision,
    redis: aioredis.Redis = Depends(get_redis),
) -> ApprovalActionResponse:
    payload = await _fetch_approval_payload(approval_id, redis)
    await _assert_still_pending(approval_id, payload)

    decided_at = datetime.now(timezone.utc).isoformat()

    # Update the approval payload in Redis
    payload["status"] = "approved"
    payload["decided_at"] = decided_at
    payload["decision_reason"] = decision.reason

    decision_record = {
        "approval_id": approval_id,
        "status": "approved",
        "decided_at": decided_at,
        "reason": decision.reason,
        "symbol": payload.get("symbol"),
        "direction": payload.get("direction"),
    }

    async with redis.pipeline(transaction=True) as pipe:
        # Update main approval record
        pipe.set(_approval_key(approval_id), json.dumps(payload), keepttl=True)
        # Write decision record (consumed by graph resume logic)
        pipe.set(_decision_key(approval_id), json.dumps(decision_record), ex=3600)
        # Remove from pending sorted set
        pipe.zrem(_PENDING_ZSET, approval_id)
        # Publish event for real-time listeners
        pipe.publish(
            "approval:decisions",
            json.dumps({"approval_id": approval_id, "status": "approved"}),
        )
        await pipe.execute()

    logger.info(
        "trade approved: approval_id=%s symbol=%s direction=%s reason=%s",
        approval_id,
        payload.get("symbol"),
        payload.get("direction"),
        decision.reason or "(no reason provided)",
    )

    return ApprovalActionResponse(
        approval_id=approval_id,
        status="approved",
        decided_at=decided_at,
        reason=decision.reason,
        message=(
            f"Trade approved. The execution pipeline for "
            f"{payload.get('symbol')} {payload.get('direction')} will proceed."
        ),
    )


# ---------------------------------------------------------------------------
# POST /{approval_id}/reject
# ---------------------------------------------------------------------------


@router.post(
    "/{approval_id}/reject",
    response_model=ApprovalActionResponse,
    summary="Reject a trade proposal",
    description="Reject a pending trade proposal. The graph will route to the monitoring subgraph.",
)
async def reject_trade(
    approval_id: str,
    decision: ApprovalDecision,
    redis: aioredis.Redis = Depends(get_redis),
) -> ApprovalActionResponse:
    payload = await _fetch_approval_payload(approval_id, redis)
    await _assert_still_pending(approval_id, payload)

    decided_at = datetime.now(timezone.utc).isoformat()

    payload["status"] = "rejected"
    payload["decided_at"] = decided_at
    payload["decision_reason"] = decision.reason

    decision_record = {
        "approval_id": approval_id,
        "status": "rejected",
        "decided_at": decided_at,
        "reason": decision.reason,
        "symbol": payload.get("symbol"),
        "direction": payload.get("direction"),
    }

    async with redis.pipeline(transaction=True) as pipe:
        pipe.set(_approval_key(approval_id), json.dumps(payload), keepttl=True)
        pipe.set(_decision_key(approval_id), json.dumps(decision_record), ex=3600)
        pipe.zrem(_PENDING_ZSET, approval_id)
        pipe.publish(
            "approval:decisions",
            json.dumps({"approval_id": approval_id, "status": "rejected"}),
        )
        await pipe.execute()

    logger.info(
        "trade rejected: approval_id=%s symbol=%s reason=%s",
        approval_id,
        payload.get("symbol"),
        decision.reason or "(no reason provided)",
    )

    return ApprovalActionResponse(
        approval_id=approval_id,
        status="rejected",
        decided_at=decided_at,
        reason=decision.reason,
        message=(
            f"Trade rejected. The AI system will log this decision and continue monitoring "
            f"{payload.get('symbol')}."
        ),
    )


# ---------------------------------------------------------------------------
# POST /{approval_id}/request-info
# ---------------------------------------------------------------------------


@router.post(
    "/{approval_id}/request-info",
    response_model=InfoRequestResponse,
    summary="Request additional analysis before deciding",
    description=(
        "Submit a question to the debate_moderator agent requesting additional "
        "analysis before making an approval decision.  The question is stored in "
        "Redis where the next graph cycle's debate_moderator will pick it up."
    ),
)
async def request_more_info(
    approval_id: str,
    question: ApprovalDecision,
    redis: aioredis.Redis = Depends(get_redis),
) -> InfoRequestResponse:
    payload = await _fetch_approval_payload(approval_id, redis)
    await _assert_still_pending(approval_id, payload)

    if not question.reason.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A non-empty question is required in the 'reason' field.",
        )

    submitted_at = datetime.now(timezone.utc).isoformat()

    info_request = {
        "approval_id": approval_id,
        "question": question.reason,
        "submitted_at": submitted_at,
        "symbol": payload.get("symbol"),
        "direction": payload.get("direction"),
        "status": "pending_analysis",
    }

    # Append to the list of info requests for this approval
    await redis.rpush(
        _info_request_key(approval_id),
        json.dumps(info_request),
    )
    # Set expiry aligned with the approval itself
    await redis.expire(_info_request_key(approval_id), 3600)

    # Publish so the debate_moderator can pick it up in the next cycle
    await redis.publish(
        "approval:info_requests",
        json.dumps({"approval_id": approval_id, "question": question.reason}),
    )

    logger.info(
        "info_request: approval_id=%s symbol=%s question=%.80s",
        approval_id,
        payload.get("symbol"),
        question.reason,
    )

    return InfoRequestResponse(
        approval_id=approval_id,
        question=question.reason,
        submitted_at=submitted_at,
        message=(
            "Your question has been submitted to the AI debate team. "
            "Additional analysis will appear in the next cycle."
        ),
    )
