"""
graph/state.py
==============
Core state definitions for the Hedge Fund AI LangGraph pipeline.

All models are immutable by design (frozen=True where applicable) to prevent
accidental mutation inside agent nodes. HedgeFundState is a TypedDict so that
LangGraph can merge partial updates returned by each node.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field
from typing_extensions import TypedDict


# ---------------------------------------------------------------------------
# Agent-level models
# ---------------------------------------------------------------------------


class AgentReport(BaseModel):
    """Output produced by a single analysis agent."""

    agent_id: str
    symbol: str
    signal: Literal["bullish", "bearish", "neutral", "no_signal"]
    confidence: float = Field(..., ge=0.0, le=1.0, description="0 = no confidence, 1 = maximum")
    reasoning: str
    supporting_evidence: list[str] = Field(default_factory=list)
    contradicting_evidence: list[str] = Field(default_factory=list)
    key_levels: dict[str, Any] = Field(default_factory=dict)  # flexible — allows float or str values
    timestamp: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)

    # --- Phase 4 additions (additive, optional, backward compatible) ---
    # Structured, numeric counterpart to the flat-string evidence lists above.
    # Not every agent populates these yet (see agents/coordination/consensus_engine.py
    # for the graceful fallback to confidence-weighted voting when absent).
    # score is a signed point value, e.g. +22 for a strong bullish factor, -11 for
    # a moderate bearish one — magnitude/sign convention is left to each agent, the
    # consensus engine only sums what's present.
    supporting_evidence_scored: list[dict[str, Any]] = Field(default_factory=list)
    """Each item: {"label": str, "score": float (positive)}."""
    contradicting_evidence_scored: list[dict[str, Any]] = Field(default_factory=list)
    """Each item: {"label": str, "score": float (positive magnitude of the bearish/contra factor)}."""

    model_config = {"frozen": True}


class StrategySignal(BaseModel):
    """Actionable trading signal produced by a strategy agent."""

    strategy_id: str
    symbol: str
    direction: Literal["LONG", "SHORT", "FLAT"]
    entry_zone_low: float
    entry_zone_high: float
    stop_loss: float
    take_profit: float
    risk_reward: float
    confidence: float = Field(..., ge=0.0, le=1.0)
    timeframe: str
    reasoning: str
    invalidation_conditions: list[str] = Field(default_factory=list)

    model_config = {"frozen": True}


# ---------------------------------------------------------------------------
# Debate / consensus models
# ---------------------------------------------------------------------------


class DebateMessage(BaseModel):
    """A single contribution to the multi-agent debate."""

    round_number: int
    agent_id: str
    position: Literal["bull", "bear", "neutral"]
    argument: str
    evidence: list[str] = Field(default_factory=list)
    rebuttal_to: str | None = None
    timestamp: datetime

    model_config = {"frozen": True}


class ConsensusResult(BaseModel):
    """Aggregated verdict produced by the ConsensusEngine after the debate."""

    direction: Literal["LONG", "SHORT", "FLAT", "NO_TRADE"]
    confidence_pct: float = Field(..., ge=0.0, le=100.0)
    bull_probability: float = Field(..., ge=0.0, le=1.0)
    bear_probability: float = Field(..., ge=0.0, le=1.0)
    neutral_probability: float = Field(..., ge=0.0, le=1.0)
    supporting_agents: int
    opposing_agents: int
    abstained_agents: int
    final_thesis: str
    risk_score: float = Field(..., ge=0.0, le=10.0)
    recommended_timeframe: str
    agent_weights: dict[str, float] = Field(default_factory=dict)

    # --- Phase 4 additions (additive) ---
    # Aggregate of whatever supporting_evidence_scored/contradicting_evidence_scored
    # is present across analysis_reports this cycle (see consensus_engine.py). Agents
    # that don't provide scored evidence simply don't contribute to these sums — they
    # still count via the pre-existing confidence-weighted vote above.
    bullish_score: float = 0.0
    bearish_score: float = 0.0
    net_ai_score: float = 0.0

    model_config = {"frozen": True}


# ---------------------------------------------------------------------------
# Risk models
# ---------------------------------------------------------------------------


class RiskAssessment(BaseModel):
    """Output of the RiskEngine evaluation."""

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
    rejection_reasons: list[str] = Field(default_factory=list)

    # --- Phase 1 risk center additions (additive only) ---
    cvar_95: float = 0.0
    """Expected Shortfall at 95%: mean loss in the worst 5% of simulated outcomes."""
    kelly_fraction: float = 0.0
    """Kelly-suggested fraction of equity to risk, clamped to [0, 0.25]."""
    expected_value_usd: float = 0.0
    """EV = winprob*max_profit - (1-winprob)*max_loss, in USD."""
    risk_category: Literal["very_low", "low", "medium", "high", "extreme"] = "medium"
    """Composite risk bucket derived from risk_score/heat/VaR — see RiskEngine."""

    model_config = {"frozen": True}


# ---------------------------------------------------------------------------
# Execution models
# ---------------------------------------------------------------------------


class TradePlan(BaseModel):
    """Fully specified trade instruction ready for execution."""

    symbol: str
    direction: Literal["LONG", "SHORT"]
    entry_type: Literal["market", "limit", "stop_limit"]
    entry_price: float | None = None
    quantity: float
    stop_loss: float
    take_profit_levels: list[float]
    trailing_stop_pct: float | None = None
    time_in_force: Literal["GTC", "IOC", "FOK", "DAY"] = "GTC"
    broker: str
    notes: str

    model_config = {"frozen": True}


class ExecutionReport(BaseModel):
    """Outcome record returned by the execution layer."""

    success: bool
    trade_id: str | None = None
    broker_order_id: str | None = None
    filled_price: float | None = None
    filled_quantity: float | None = None
    commission: float = 0.0
    slippage: float = 0.0
    error_message: str | None = None
    timestamp: datetime

    model_config = {"frozen": True}


# ---------------------------------------------------------------------------
# Forecast model
# ---------------------------------------------------------------------------


class Forecast(BaseModel):
    """Probabilistic price forecast produced by the ensemble models."""

    symbol: str
    timeframe: str
    direction: Literal["bullish", "bearish", "neutral"]
    confidence_pct: float = Field(..., ge=0.0, le=100.0)
    bull_probability: float = Field(..., ge=0.0, le=1.0)
    bear_probability: float = Field(..., ge=0.0, le=1.0)
    predicted_low: float
    predicted_high: float
    risk_score: float = Field(..., ge=0.0, le=10.0)
    market_regime: str
    model_contributions: dict[str, float] = Field(default_factory=dict)
    supporting_evidence: list[str] = Field(default_factory=list)
    contradicting_evidence: list[str] = Field(default_factory=list)
    created_at: datetime
    expiry_at: datetime

    model_config = {"frozen": True}


# ---------------------------------------------------------------------------
# Graph state
# ---------------------------------------------------------------------------


class HedgeFundState(TypedDict, total=False):
    """
    Central state object threaded through every LangGraph node.

    LangGraph merges dict-typed fields by shallow update; list-typed fields
    are replaced (not appended) unless the node logic appends explicitly.
    """

    # ------------------------------------------------------------------
    # Identity / context
    # ------------------------------------------------------------------
    symbol: str
    timeframe: str
    market_data: dict[str, Any]
    timestamp: datetime
    current_phase: str
    iteration_count: int

    # ------------------------------------------------------------------
    # Analysis layer
    # ------------------------------------------------------------------
    analysis_reports: dict[str, AgentReport]
    strategy_signals: list[StrategySignal]

    # ------------------------------------------------------------------
    # Debate / consensus layer
    # ------------------------------------------------------------------
    debate_transcript: list[DebateMessage]
    consensus: ConsensusResult | None

    # ------------------------------------------------------------------
    # Risk layer
    # ------------------------------------------------------------------
    risk_assessment: RiskAssessment | None

    # ------------------------------------------------------------------
    # Human-in-the-loop approval
    # ------------------------------------------------------------------
    human_approval_required: bool
    human_approval_status: Literal["pending", "approved", "rejected", "expired"] | None
    approval_id: str | None
    approval_deadline: datetime | None

    # ------------------------------------------------------------------
    # Execution layer
    # ------------------------------------------------------------------
    trade_plan: TradePlan | None
    order_ids: list[str]
    execution_report: ExecutionReport | None

    # ------------------------------------------------------------------
    # Intelligence layer
    # ------------------------------------------------------------------
    forecasts: dict[str, Forecast]
    market_regime: str | None

    # Phase 4: per-agent {"win_count": int, "total_count": int} resolved-decision
    # stats, computed by agents.coordination.weight_calculator.compute_weights_from_db
    # (a DB call — populated by whatever assembles state before invoking the graph,
    # since agent nodes themselves run synchronously with no DB handle). When
    # present, consensus_engine.py uses it to derive real-performance-grounded
    # weights as a fallback/default that runs BEFORE the learning_agent LLM override.
    agent_performance_stats: dict[str, dict[str, int]]

    # ------------------------------------------------------------------
    # Safety / control flags
    # ------------------------------------------------------------------
    circuit_breaker_tripped: bool
    kill_switch_active: bool
    news_blackout_active: bool

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------
    errors: list[str]
    warnings: list[str]
