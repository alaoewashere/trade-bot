"""
Redis-backed state manager for the hedge-fund AI graph.

Stores short-lived agent state, graph run state, and the human-in-the-loop
approval workflow.  All data is JSON-serialised so external tools (dashboards,
CLI scripts) can inspect it without a Python client.

Key layout
----------
agent:state:{agent_id}            STRING  JSON, TTL 1h
graph:state:{run_id}              STRING  JSON, TTL 24h
approval:pending                  ZSET    member=approval_id, score=epoch timestamp
approval:detail:{approval_id}     STRING  JSON, TTL 24h
approval:decision:{approval_id}   STRING  "approved"|"rejected", TTL 24h
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Optional

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

_AGENT_STATE_TTL  = 3_600      # 1 hour
_GRAPH_STATE_TTL  = 86_400     # 24 hours
_APPROVAL_TTL     = 86_400     # 24 hours
_DECISION_TTL     = 86_400

_PENDING_ZSET     = "approval:pending"


def _agent_key(agent_id: str) -> str:
    return f"agent:state:{agent_id}"


def _graph_key(run_id: str) -> str:
    return f"graph:state:{run_id}"


def _detail_key(approval_id: str) -> str:
    return f"approval:detail:{approval_id}"


def _decision_key(approval_id: str) -> str:
    return f"approval:decision:{approval_id}"


class RedisStateManager:
    """
    Centralised Redis state store for agents, graph runs, and approvals.

    All methods are coroutines and require an already-connected
    ``redis.asyncio.Redis`` client passed at construction.

    Example::

        state_mgr = RedisStateManager(redis_client)

        # Agent state
        await state_mgr.set_agent_state("technical_agent", {"last_signal": "BUY"})
        s = await state_mgr.get_agent_state("technical_agent")

        # Approval workflow
        approval_id = "appr-001"
        await state_mgr.push_approval(approval_id, {"action": "buy", "qty": 0.5})
        pending = await state_mgr.get_pending_approvals()
        await state_mgr.set_approval_decision(approval_id, "approved")
        decision = await state_mgr.get_approval_decision(approval_id)
    """

    def __init__(self, redis_client: aioredis.Redis) -> None:
        self._r = redis_client

    # ------------------------------------------------------------------
    # Agent state
    # ------------------------------------------------------------------

    async def set_agent_state(self, agent_id: str, state_dict: dict) -> None:
        """
        Persist agent state with a 1-hour TTL.

        Args:
            agent_id:   Unique agent identifier (e.g. "technical_agent").
            state_dict: Arbitrary JSON-serialisable dict.
        """
        key = _agent_key(agent_id)
        try:
            payload = json.dumps(state_dict, default=_json_default)
            await self._r.setex(key, _AGENT_STATE_TTL, payload)
        except Exception:
            logger.exception("set_agent_state failed for agent %s", agent_id)

    async def get_agent_state(self, agent_id: str) -> Optional[dict]:
        """
        Retrieve agent state.

        Returns:
            State dict, or None if absent / expired.
        """
        key = _agent_key(agent_id)
        try:
            raw = await self._r.get(key)
        except Exception:
            logger.exception("get_agent_state failed for agent %s", agent_id)
            return None

        if raw is None:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Corrupt agent state for %s — returning None", agent_id)
            return None

    async def delete_agent_state(self, agent_id: str) -> None:
        """Remove agent state immediately (e.g. after agent shutdown)."""
        await self._r.delete(_agent_key(agent_id))

    # ------------------------------------------------------------------
    # Graph / run state
    # ------------------------------------------------------------------

    async def set_graph_state(self, run_id: str, state: dict) -> None:
        """
        Persist a HedgeFundState snapshot for *run_id* with a 24-hour TTL.

        Args:
            run_id: LangGraph run / thread ID.
            state:  Full graph state dict (must be JSON-serialisable).
        """
        key = _graph_key(run_id)
        try:
            payload = json.dumps(state, default=_json_default)
            await self._r.setex(key, _GRAPH_STATE_TTL, payload)
        except Exception:
            logger.exception("set_graph_state failed for run %s", run_id)

    async def get_graph_state(self, run_id: str) -> Optional[dict]:
        """
        Retrieve a graph state snapshot.

        Returns:
            State dict, or None if absent / expired.
        """
        key = _graph_key(run_id)
        try:
            raw = await self._r.get(key)
        except Exception:
            logger.exception("get_graph_state failed for run %s", run_id)
            return None

        if raw is None:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Corrupt graph state for run %s — returning None", run_id)
            return None

    async def delete_graph_state(self, run_id: str) -> None:
        """Remove a graph state entry."""
        await self._r.delete(_graph_key(run_id))

    # ------------------------------------------------------------------
    # Approval workflow
    # ------------------------------------------------------------------

    async def push_approval(self, approval_id: str, details: dict) -> None:
        """
        Add a trade proposal to the pending-approval sorted set.

        The score is the current Unix timestamp so approvals can be
        retrieved in chronological order.

        Args:
            approval_id: Unique identifier for this approval request.
            details:     Proposal dict (trade details, risk metrics, etc.).
        """
        score = time.time()
        detail_key = _detail_key(approval_id)
        try:
            payload = json.dumps(
                {"approval_id": approval_id, "timestamp": score, **details},
                default=_json_default,
            )
            async with self._r.pipeline(transaction=True) as pipe:
                pipe.setex(detail_key, _APPROVAL_TTL, payload)
                pipe.zadd(_PENDING_ZSET, {approval_id: score})
                await pipe.execute()
            logger.info("Approval %s pushed to pending queue", approval_id)
        except Exception:
            logger.exception("push_approval failed for %s", approval_id)

    async def pop_approval(self, approval_id: str) -> Optional[dict]:
        """
        Retrieve and remove a specific approval from the pending set.

        Args:
            approval_id: Approval to remove.

        Returns:
            Detail dict, or None if not found.
        """
        detail_key = _detail_key(approval_id)
        try:
            async with self._r.pipeline(transaction=True) as pipe:
                pipe.get(detail_key)
                pipe.zrem(_PENDING_ZSET, approval_id)
                pipe.delete(detail_key)
                results = await pipe.execute()
            raw = results[0]
        except Exception:
            logger.exception("pop_approval failed for %s", approval_id)
            return None

        if raw is None:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    async def get_pending_approvals(self) -> list[dict]:
        """
        Return all pending approvals in chronological order (oldest first).

        Returns:
            List of approval detail dicts.
        """
        try:
            ids: list[str] = await self._r.zrange(_PENDING_ZSET, 0, -1)
        except Exception:
            logger.exception("get_pending_approvals: zrange failed")
            return []

        if not ids:
            return []

        approvals: list[dict] = []
        for approval_id in ids:
            try:
                raw = await self._r.get(_detail_key(approval_id))
                if raw:
                    approvals.append(json.loads(raw))
            except Exception:
                logger.warning(
                    "Could not load approval detail for %s", approval_id
                )
        return approvals

    async def get_pending_approval_ids(self) -> list[str]:
        """Return just the IDs from the pending sorted set."""
        try:
            return await self._r.zrange(_PENDING_ZSET, 0, -1)
        except Exception:
            logger.exception("get_pending_approval_ids failed")
            return []

    async def set_approval_decision(
        self,
        approval_id: str,
        decision: str,  # "approved" | "rejected"
    ) -> None:
        """
        Record a human (or automated) decision for an approval request.

        Also removes the request from the pending sorted set.

        Args:
            approval_id: Approval being decided.
            decision:    "approved" or "rejected".
        """
        if decision not in ("approved", "rejected"):
            raise ValueError(f"decision must be 'approved' or 'rejected', got {decision!r}")

        decision_key = _decision_key(approval_id)
        try:
            async with self._r.pipeline(transaction=True) as pipe:
                pipe.setex(decision_key, _DECISION_TTL, decision)
                pipe.zrem(_PENDING_ZSET, approval_id)
                await pipe.execute()
            logger.info("Approval %s → %s", approval_id, decision)
        except Exception:
            logger.exception("set_approval_decision failed for %s", approval_id)

    async def get_approval_decision(self, approval_id: str) -> Optional[str]:
        """
        Retrieve the decision for an approval request.

        Returns:
            "approved", "rejected", or None if no decision has been recorded yet.
        """
        try:
            raw = await self._r.get(_decision_key(approval_id))
        except Exception:
            logger.exception("get_approval_decision failed for %s", approval_id)
            return None

        return raw if isinstance(raw, str) else (raw.decode() if raw else None)

    # ------------------------------------------------------------------
    # General-purpose convenience helpers
    # ------------------------------------------------------------------

    async def set_value(
        self, key: str, value: Any, ttl: int = _AGENT_STATE_TTL
    ) -> None:
        """Generic set with JSON serialisation and optional TTL."""
        try:
            payload = json.dumps(value, default=_json_default)
            if ttl > 0:
                await self._r.setex(key, ttl, payload)
            else:
                await self._r.set(key, payload)
        except Exception:
            logger.exception("set_value failed for key %s", key)

    async def get_value(self, key: str) -> Any:
        """Generic get with JSON deserialisation."""
        try:
            raw = await self._r.get(key)
            return json.loads(raw) if raw else None
        except Exception:
            logger.exception("get_value failed for key %s", key)
            return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _json_default(obj: object) -> object:
    """Fallback serialiser for numpy types."""
    try:
        import numpy as np
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
    except ImportError:
        pass
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")
