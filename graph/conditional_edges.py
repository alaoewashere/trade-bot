"""
graph/conditional_edges.py
===========================
All LangGraph conditional edge routing logic for the master hedge fund graph.

Every method is a pure function of state — no side-effects, no I/O.
This makes the routing logic trivially testable in isolation.
"""
from __future__ import annotations

from graph.state import HedgeFundState


class EdgeRouter:
    """
    Static collection of routing functions used as LangGraph conditional edges.

    Each method receives the current HedgeFundState and returns the name of
    the next node to visit.
    """

    @staticmethod
    def after_security_check(state: HedgeFundState) -> str:
        """
        Route after security_bot runs.

        Priority order:
          1. Kill switch active  → emergency_bot
          2. Circuit breaker or news blackout → monitoring_subgraph (skip cycle)
          3. All clear → prediction_engine_node
        """
        if state.get("kill_switch_active"):
            return "emergency_bot"
        if state.get("circuit_breaker_tripped") or state.get("news_blackout_active"):
            return "monitoring_subgraph"
        return "prediction_engine_node"

    @staticmethod
    def after_consensus(state: HedgeFundState) -> str:
        """
        Route after the debate_subgraph produces a ConsensusResult.

        Routes to monitoring (no trade) if:
          - No consensus was produced.
          - Direction is NO_TRADE or FLAT.
          - Confidence is below the 55% threshold.
          - Risk score exceeds 8.0 / 10.0.

        Otherwise routes to the risk gate for position sizing.
        """
        consensus = state.get("consensus")

        if consensus is None:
            return "monitoring_subgraph"

        if consensus.direction in ("NO_TRADE", "FLAT"):
            return "monitoring_subgraph"

        if consensus.confidence_pct < 55.0:
            return "monitoring_subgraph"

        if consensus.risk_score > 8.0:
            return "monitoring_subgraph"

        return "risk_gate_node"

    @staticmethod
    def after_risk_gate(state: HedgeFundState) -> str:
        """
        Route after the CRO + RiskEngine evaluation.

        Routes to monitoring if risk_assessment is absent or not approved.
        Otherwise routes to the human approval node.
        """
        risk = state.get("risk_assessment")

        if risk is None or not risk.approved:
            return "monitoring_subgraph"

        return "human_approval_node"

    @staticmethod
    def after_human_approval(state: HedgeFundState) -> str:
        """
        Route after the human approval gate.

        Routes to execution only if status is "approved".
        Any other status (rejected, expired, pending after timeout)
        routes to monitoring.
        """
        status = state.get("human_approval_status")

        if status == "approved":
            return "execution_subgraph"

        return "monitoring_subgraph"

    @staticmethod
    def after_emergency(state: HedgeFundState) -> str:
        """
        Route after the emergency_bot runs.

        Always proceeds to monitoring so that the journal and learning
        agents can record the emergency event before the cycle ends.
        """
        return "monitoring_subgraph"
