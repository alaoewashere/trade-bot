"""
graph/subgraphs/debate_subgraph.py
====================================
Debate subgraph — orchestrates a structured 3-round adversarial debate
between the analysis agents, followed by a consensus synthesis pass.

Flow
----
  debate_moderator  ──>  consensus_engine  ──>  END

Node: debate_moderator
    Reads all analysis_reports and strategy_signals from state.
    Constructs a structured 3-round debate transcript (DebateMessage list).
    Writes result into state["debate_transcript"].

Node: consensus_engine
    Reads the debate_transcript plus the raw analysis_reports.
    Produces a ConsensusResult synthesising all agent views.
    Writes result into state["consensus"].
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from langgraph.graph import StateGraph, END

from graph.state import (
    ConsensusResult,
    DebateMessage,
    HedgeFundState,
    AgentReport,
    StrategySignal,
)
from agents.registry import AgentRegistry

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Debate moderator node
# ---------------------------------------------------------------------------


class _DebateModeratorNode:
    """
    Runs the debate_moderator agent to generate a 3-round structured debate.

    The moderator agent is expected to return a dict containing:
      - "debate_transcript": list[DebateMessage]
    or fall back gracefully and synthesize one from raw reports.
    """

    def __init__(self) -> None:
        self._agent = AgentRegistry.get("debate_moderator")

    def __call__(self, state: HedgeFundState) -> dict[str, Any]:
        existing_errors: list[str] = list(state.get("errors", []))

        try:
            result: dict[str, Any] = self._agent(state)

            # The debate_moderator agent should populate debate_transcript.
            transcript: list[DebateMessage] = result.get("debate_transcript", [])

            # If the agent did not produce a transcript (e.g. it wrote
            # analysis_reports instead), synthesise a minimal transcript
            # from whatever analysis_reports exist.
            if not transcript:
                transcript = _synthesize_transcript_from_reports(
                    state.get("analysis_reports", {}),
                    state.get("strategy_signals", []),
                    state.get("symbol", "UNKNOWN"),
                )

            update: dict[str, Any] = {
                "debate_transcript": transcript,
                "current_phase": "debate_complete",
            }

            new_errors = result.get("errors", [])
            if new_errors:
                update["errors"] = existing_errors + new_errors

            return update

        except Exception as exc:
            error_msg = f"debate_moderator error: {exc}"
            logger.error(error_msg, exc_info=True)

            # Fallback: create a minimal transcript so the graph can continue.
            fallback_transcript = _synthesize_transcript_from_reports(
                state.get("analysis_reports", {}),
                state.get("strategy_signals", []),
                state.get("symbol", "UNKNOWN"),
            )
            return {
                "debate_transcript": fallback_transcript,
                "current_phase": "debate_complete",
                "errors": [*existing_errors, error_msg],
            }


def _synthesize_transcript_from_reports(
    reports: dict[str, AgentReport],
    signals: list[StrategySignal],
    symbol: str,
) -> list[DebateMessage]:
    """
    Build a minimal DebateMessage list from raw agent reports.

    Used as a fallback when the debate_moderator agent fails.  Produces a
    single round of messages — one per agent that has an opinion.
    """
    transcript: list[DebateMessage] = []
    now = datetime.now(timezone.utc)

    for round_num in range(1, 4):
        for agent_id, report in reports.items():
            position_map = {
                "bullish": "bull",
                "bearish": "bear",
                "neutral": "neutral",
                "no_signal": "neutral",
            }
            position = position_map.get(report.signal, "neutral")

            msg = DebateMessage(
                round_number=round_num,
                agent_id=agent_id,
                position=position,  # type: ignore[arg-type]
                argument=report.reasoning,
                evidence=report.supporting_evidence[:3],
                rebuttal_to=None,
                timestamp=now,
            )
            transcript.append(msg)

    return transcript


# ---------------------------------------------------------------------------
# Consensus engine node
# ---------------------------------------------------------------------------


class _ConsensusEngineNode:
    """
    Runs the consensus_engine agent to synthesize a ConsensusResult.

    The consensus_engine agent is expected to return a dict with:
      - "consensus": ConsensusResult
    or place the result in "analysis_reports" (legacy interface).

    Falls back to a rule-based aggregation if the agent fails.
    """

    def __init__(self) -> None:
        self._agent = AgentRegistry.get("consensus_engine")

    def __call__(self, state: HedgeFundState) -> dict[str, Any]:
        existing_errors: list[str] = list(state.get("errors", []))

        try:
            result: dict[str, Any] = self._agent(state)

            consensus: ConsensusResult | None = result.get("consensus")

            # If consensus is not in the direct result, check if the agent
            # placed it inside analysis_reports under its own key.
            if consensus is None:
                reports = result.get("analysis_reports", {})
                consensus_report = reports.get("consensus_engine")
                if consensus_report is not None:
                    # The agent may have encoded the ConsensusResult as metadata.
                    meta = getattr(consensus_report, "metadata", {})
                    raw_consensus = meta.get("consensus_result")
                    if isinstance(raw_consensus, ConsensusResult):
                        consensus = raw_consensus
                    elif isinstance(raw_consensus, dict):
                        try:
                            consensus = ConsensusResult.model_validate(raw_consensus)
                        except Exception:
                            pass

            if consensus is None:
                consensus = _rule_based_consensus(
                    state.get("analysis_reports", {}),
                    state.get("strategy_signals", []),
                    state.get("symbol", "UNKNOWN"),
                )

            update: dict[str, Any] = {
                "consensus": consensus,
                "current_phase": "consensus_complete",
            }

            new_errors = result.get("errors", [])
            if new_errors:
                update["errors"] = existing_errors + new_errors

            return update

        except Exception as exc:
            error_msg = f"consensus_engine error: {exc}"
            logger.error(error_msg, exc_info=True)

            # Fallback rule-based consensus so the graph can continue.
            consensus = _rule_based_consensus(
                state.get("analysis_reports", {}),
                state.get("strategy_signals", []),
                state.get("symbol", "UNKNOWN"),
            )
            return {
                "consensus": consensus,
                "current_phase": "consensus_complete",
                "errors": [*existing_errors, error_msg],
            }


def _rule_based_consensus(
    reports: dict[str, AgentReport],
    signals: list[StrategySignal],
    symbol: str,
) -> ConsensusResult:
    """
    Simple majority-vote consensus used as a fallback when the LLM agent fails.

    Tallies bull / bear / neutral votes weighted by each agent's confidence
    and returns a ConsensusResult.
    """
    bull_weight = 0.0
    bear_weight = 0.0
    neutral_weight = 0.0
    total_weight = 0.0

    signal_map = {"bullish": "bull", "bearish": "bear", "neutral": "neutral", "no_signal": "neutral"}
    agent_weights: dict[str, float] = {}

    # Phase 4: aggregate whatever numeric scored evidence agents provided this
    # cycle (see graph/state.py AgentReport.supporting_evidence_scored /
    # contradicting_evidence_scored). Agents that don't populate these yet
    # simply contribute 0 here — they still count fully via the
    # confidence-weighted vote above/below.
    bullish_score = 0.0
    bearish_score = 0.0

    for agent_id, report in reports.items():
        weight = report.confidence
        agent_weights[agent_id] = weight
        total_weight += weight
        side = signal_map.get(report.signal, "neutral")
        if side == "bull":
            bull_weight += weight
        elif side == "bear":
            bear_weight += weight
        else:
            neutral_weight += weight

        for item in report.supporting_evidence_scored:
            try:
                bullish_score += float(item.get("score", 0.0))
            except (TypeError, ValueError):
                continue
        for item in report.contradicting_evidence_scored:
            try:
                bearish_score += float(item.get("score", 0.0))
            except (TypeError, ValueError):
                continue

    net_ai_score = bullish_score - bearish_score

    if total_weight == 0:
        return ConsensusResult(
            direction="NO_TRADE",
            confidence_pct=0.0,
            bull_probability=0.0,
            bear_probability=0.0,
            neutral_probability=1.0,
            supporting_agents=0,
            opposing_agents=0,
            abstained_agents=len(reports),
            final_thesis="No analysis data available — no trade recommended.",
            risk_score=10.0,
            recommended_timeframe="1h",
            agent_weights=agent_weights,
            bullish_score=round(bullish_score, 4),
            bearish_score=round(bearish_score, 4),
            net_ai_score=round(net_ai_score, 4),
        )

    bull_prob = bull_weight / total_weight
    bear_prob = bear_weight / total_weight
    neutral_prob = neutral_weight / total_weight

    if bull_prob > bear_prob and bull_prob > neutral_prob:
        direction = "LONG"
        confidence_pct = bull_prob * 100.0
        supporting = sum(1 for r in reports.values() if r.signal == "bullish")
        opposing = sum(1 for r in reports.values() if r.signal == "bearish")
    elif bear_prob > bull_prob and bear_prob > neutral_prob:
        direction = "SHORT"
        confidence_pct = bear_prob * 100.0
        supporting = sum(1 for r in reports.values() if r.signal == "bearish")
        opposing = sum(1 for r in reports.values() if r.signal == "bullish")
    else:
        direction = "FLAT"
        confidence_pct = neutral_prob * 100.0
        supporting = sum(1 for r in reports.values() if r.signal == "neutral")
        opposing = sum(1 for r in reports.values() if r.signal not in ("neutral", "no_signal"))

    abstained = sum(1 for r in reports.values() if r.signal == "no_signal")

    # Risk score: higher uncertainty = higher risk
    uncertainty = 1.0 - max(bull_prob, bear_prob, neutral_prob)
    risk_score = round(uncertainty * 10.0, 2)

    return ConsensusResult(
        direction=direction,  # type: ignore[arg-type]
        confidence_pct=round(confidence_pct, 2),
        bull_probability=round(bull_prob, 4),
        bear_probability=round(bear_prob, 4),
        neutral_probability=round(neutral_prob, 4),
        supporting_agents=supporting,
        opposing_agents=opposing,
        abstained_agents=abstained,
        final_thesis=(
            f"Rule-based consensus: {direction} with {confidence_pct:.1f}% confidence "
            f"({supporting} supporting, {opposing} opposing, {abstained} abstained)."
        ),
        risk_score=risk_score,
        recommended_timeframe="1h",
        agent_weights=agent_weights,
        bullish_score=round(bullish_score, 4),
        bearish_score=round(bearish_score, 4),
        net_ai_score=round(net_ai_score, 4),
    )


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


def build_debate_subgraph():
    """
    Construct and compile the debate subgraph.

    Returns
    -------
    CompiledGraph
        A compiled LangGraph subgraph ready to be embedded in the master graph.
    """
    builder: StateGraph = StateGraph(HedgeFundState)

    builder.add_node("debate_moderator", _DebateModeratorNode())
    builder.add_node("consensus_engine", _ConsensusEngineNode())

    builder.set_entry_point("debate_moderator")
    builder.add_edge("debate_moderator", "consensus_engine")
    builder.add_edge("consensus_engine", END)

    return builder.compile()
