"""
agents/coordination/weight_calculator.py
=========================================
Pure-Python (no LLM) consensus weight calculation grounded in real, persisted
agent performance data.

This module exists so that ConsensusEngineAgent's weighted voting does not
depend entirely on `learning_agent` (an LLM call) getting the arithmetic right
each run. It computes suggested weights directly from `agent_decisions` joined
against evaluated `forecasts` outcomes and blends them with the static
`_DEFAULT_AGENT_WEIGHTS` prior in consensus_engine.py.

FORMULA
-------
For an agent with `n` resolved decisions and observed directional accuracy `acc`
(fraction in [0, 1]):

1. Shrinkage toward 0.5 (coin-flip) for small samples — a naive win-rate from
   3 decisions is not trustworthy. We blend the observed accuracy with a 0.5
   prior using a pseudo-count `k` (default 20):

       shrunk_acc = (acc * n + 0.5 * k) / (n + k)

   This is a standard Bayesian-style shrinkage estimator (equivalent to adding
   `k` virtual coin-flip observations). As n -> infinity, shrunk_acc -> acc.
   As n -> 0, shrunk_acc -> 0.5 (no information -> no adjustment).

2. Map shrunk accuracy to a raw multiplier centered on 1.0 at 50% accuracy:

       raw_multiplier = 1.0 + (shrunk_acc - 0.5) * 4.0

   i.e. 50% accuracy -> 1.0x (neutral), 75% -> 2.0x, 25% -> 0.0x (before clamp),
   100% -> 3.0x. The slope (4.0) is chosen so a fully-shrunk agent lands exactly
   on the existing consensus_engine.py clamp bounds [0.1, 3.0] at the extremes.

3. Blend with the existing static default weight (the human-calibrated prior
   from backtesting experience) rather than replacing it outright — this keeps
   a single noisy sample from swinging an agent's influence wildly even after
   shrinkage, and preserves the hand-tuned relative ordering between agent
   roles (e.g. cio_agent > trade_planner) when performance data is thin:

       suggested_weight = default_weight * blend + raw_multiplier * default_weight_unit * (1 - blend)

   Concretely we blend on the multiplier itself:

       final_weight = default_weight * (blend_factor + (1 - blend_factor) * raw_multiplier)

   where blend_factor -> 1.0 (weight ~= default) when n is small, and
   blend_factor -> 0.0 (weight ~= default_weight * raw_multiplier, i.e. fully
   performance-driven) as n grows past ~30 decisions.

       blend_factor = k_blend / (k_blend + n),   k_blend = 30

4. Clamp to [0.1, 3.0] to match consensus_engine.py's existing bounds.

This keeps the "prior" (default weight) dominant until an agent has a
meaningful track record (>=30 decisions), then lets real performance take
over, exactly mirroring the shrinkage-toward-default approach the phase spec
asked for.
"""
from __future__ import annotations

import structlog

logger = structlog.get_logger(__name__)

# Pseudo-count for accuracy shrinkage toward 50% (coin-flip prior).
_ACCURACY_SHRINKAGE_K = 20.0

# Pseudo-count controlling how fast we trust real performance over the
# static default weight. At n = 30 decisions, blend_factor = 0.5 (equal say).
_BLEND_K = 30.0

# Multiplier slope: how many "weight multiples" a 50-percentage-point swing in
# shrunk accuracy is worth. 0.5 -> 2.0 across the 0%-100% band with 4.0 slope.
_MULTIPLIER_SLOPE = 4.0

WEIGHT_MIN = 0.1
WEIGHT_MAX = 3.0


def shrunk_accuracy(win_count: int, total_count: int, k: float = _ACCURACY_SHRINKAGE_K) -> float:
    """Bayesian-shrinkage accuracy estimate, pulled toward 0.5 for small samples."""
    if total_count <= 0:
        return 0.5
    acc = win_count / total_count
    return (acc * total_count + 0.5 * k) / (total_count + k)


def compute_agent_weight(
    agent_id: str,
    default_weight: float,
    win_count: int,
    total_count: int,
) -> float:
    """
    Compute a single agent's suggested consensus weight from its real track record.

    Parameters
    ----------
    agent_id:
        Agent identifier (used only for logging).
    default_weight:
        The static prior weight from consensus_engine._DEFAULT_AGENT_WEIGHTS.
        Agents with a default of 0.0 (gating-only, e.g. security_bot) are
        returned unchanged — they are not directional voters.
    win_count:
        Number of resolved decisions where the agent's directional signal
        matched the eventual profitable/correct outcome.
    total_count:
        Total number of resolved (non-pending) decisions for the agent.

    Returns
    -------
    float
        Suggested weight, clamped to [WEIGHT_MIN, WEIGHT_MAX].
    """
    if default_weight <= 0.0:
        return default_weight

    if total_count <= 0:
        return max(WEIGHT_MIN, min(WEIGHT_MAX, default_weight))

    acc = shrunk_accuracy(win_count, total_count)
    raw_multiplier = 1.0 + (acc - 0.5) * _MULTIPLIER_SLOPE

    blend_factor = _BLEND_K / (_BLEND_K + total_count)
    performance_weight = default_weight * raw_multiplier
    final_weight = default_weight * blend_factor + performance_weight * (1.0 - blend_factor)

    clamped = max(WEIGHT_MIN, min(WEIGHT_MAX, final_weight))
    logger.debug(
        "weight_calculator_agent",
        agent_id=agent_id,
        default_weight=default_weight,
        win_count=win_count,
        total_count=total_count,
        shrunk_accuracy=round(acc, 4),
        blend_factor=round(blend_factor, 4),
        final_weight=round(clamped, 4),
    )
    return clamped


async def compute_weights_from_db(
    db,
    default_weights: dict[str, float],
    lookback_days: int = 90,
) -> dict[str, float]:
    """
    On-the-fly computation of suggested consensus weights for every agent in
    `default_weights`, sourced from `agent_decisions` (outcome column) over a
    rolling lookback window.

    We deliberately compute this on-the-fly rather than maintaining a
    materialized `agent_performance_snapshots` table: there is no existing
    daemon/scheduler in this repo other than prediction_engine/evaluator.py
    (which is scoped to forecast calibration, not agent-level stats), and
    piggybacking an unrelated responsibility onto it would couple two concerns
    that should evolve independently. A well-indexed on-the-fly aggregation
    (idx_agent_decisions_agent_id, idx_agent_decisions_outcome already exist in
    migrations/init.sql) is safer and simpler for now; if this endpoint's query
    latency becomes a problem under load, promoting it to a periodic snapshot
    written by a new small daemon is the natural next step.

    Parameters
    ----------
    db:
        asyncpg connection/pool with `.fetch(...)`.
    default_weights:
        The static prior weights (consensus_engine._DEFAULT_AGENT_WEIGHTS).
    lookback_days:
        Only resolved decisions in the last N days are considered, so weights
        track recent regime performance rather than all-time history.

    Returns
    -------
    dict[str, float]
        agent_id -> suggested weight, for every agent with resolved decisions
        in the window. Agents with no data are omitted (caller should fall
        back to the static default for those).
    """
    rows = await db.fetch(
        """
        SELECT
            agent_id,
            COUNT(*) FILTER (WHERE outcome = 'correct')                       AS win_count,
            COUNT(*) FILTER (WHERE outcome IN ('correct', 'incorrect'))      AS total_count
        FROM agent_decisions
        WHERE decided_at >= NOW() - ($1 || ' days')::INTERVAL
          AND outcome IN ('correct', 'incorrect')
        GROUP BY agent_id
        """,
        str(lookback_days),
    )

    weights: dict[str, float] = {}
    for row in rows:
        agent_id = row["agent_id"]
        if agent_id not in default_weights:
            continue
        weights[agent_id] = compute_agent_weight(
            agent_id=agent_id,
            default_weight=default_weights[agent_id],
            win_count=int(row["win_count"] or 0),
            total_count=int(row["total_count"] or 0),
        )
    return weights
