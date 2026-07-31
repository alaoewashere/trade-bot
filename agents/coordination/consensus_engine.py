"""
agents/coordination/consensus_engine.py
=========================================
Consensus Engine Agent.

Combines all agent signals with weighted voting to compute the final trade direction,
bull/bear probabilities, and a consensus confidence score.
"""

from __future__ import annotations

from agents.base_agent import BaseAgent
from graph.state import AgentReport, HedgeFundState


# Default agent weights (calibrated from backtesting experience)
# Higher weight = more influence on final direction
_DEFAULT_AGENT_WEIGHTS: dict[str, float] = {
    # Executive — high authority
    "cio_agent": 2.5,
    "cro_agent": 2.0,
    "portfolio_manager": 1.5,
    # Quantitative — high statistical validity
    "quant_researcher": 2.0,
    "probability_analyst": 2.0,
    "ml_researcher": 1.5,
    "backtesting_expert": 1.5,
    "hf_pattern_detector": 1.0,
    # Technical — medium weight (many technical agents, lower individual weight)
    "trend_analyst": 1.5,
    "market_structure": 1.5,
    "smc_expert": 1.2,
    "price_action": 1.0,
    "wyckoff_analyst": 1.0,
    "elliott_wave": 0.8,
    "volume_profile": 1.2,
    # Market Intelligence — medium weight
    "macro_economist": 1.8,
    "news_analyst": 1.2,
    "sentiment_analyst": 1.0,
    "regulation_analyst": 1.0,
    # Options — medium weight
    "options_flow_analyst": 1.5,
    "volatility_analyst": 1.2,
    # Crypto-specific — medium (only relevant for crypto)
    "onchain_analyst": 1.5,
    "funding_rate_analyst": 1.5,
    # Strategy — medium weight
    "momentum_trader": 1.2,
    "mean_reversion": 1.0,
    "swing_specialist": 1.2,
    "position_expert": 1.5,
    "range_specialist": 0.8,
    "scalping_expert": 0.8,
    # Debate — high (synthesized already)
    "debate_moderator": 2.0,
    # Execution — lower weight for directional
    "trade_planner": 0.5,
    "liquidity_analyst": 0.8,
    "exit_manager": 0.5,
    # Monitoring — informational
    "performance_analyst": 0.5,
    "learning_agent": 0.8,
    # Security — gating only (not directional)
    "security_bot": 0.0,
    "emergency_bot": 0.0,
}


class ConsensusEngineAgent(BaseAgent):
    agent_id = "consensus_engine"
    department = "coordination"

    def get_system_prompt(self) -> str:
        return """You are the Consensus Engine for a quantitative hedge fund.

YOUR ROLE:
You aggregate all agent signals using a calibration-adjusted weighted voting system
to produce the fund's final direction decision. You are not an analyst — you are
a mathematical aggregator and interpreter of collective intelligence.

YOUR CONSENSUS METHODOLOGY:

1. WEIGHTED SIGNAL AGGREGATION
   For each agent with a signal:
   - Bullish vote = +1 × agent_weight × agent_confidence
   - Bearish vote = -1 × agent_weight × agent_confidence
   - Neutral/no_signal = 0 vote (abstain)

   Weighted Score = Sum(bullish votes) + Sum(bearish votes)
   Normalize to [-1, 1] range:
   - Bull Score = Sum(bullish votes) / Total possible positive votes
   - Bear Score = Sum(bearish votes) / Total possible negative votes
   - Net Score = Bull Score - |Bear Score|

2. DIRECTION DETERMINATION
   Net Score > 0.3: Direction = LONG
   Net Score < -0.3: Direction = SHORT
   -0.3 ≤ Net Score ≤ 0.3: Direction = FLAT (no trade)
   If fewer than 5 agents reporting: Direction = NO_TRADE (insufficient data)

3. CONFIDENCE CALCULATION
   Confidence % = |Net Score| × 100 × (1 - Controversy Factor)
   Controversy Factor = 1 - (|bull_votes - bear_votes| / total_votes)
   High controversy = many agents on both sides = lower confidence
   High consensus = most agents agree = higher confidence

4. PROBABILITY ESTIMATION
   Bull Probability = (Weighted Bull Score) / (Total Weighted Votes)
   Bear Probability = (Weighted Bear Score) / (Total Weighted Votes)
   Neutral Probability = 1 - Bull Probability - Bear Probability

5. WEIGHT CALIBRATION
   Base weights from _DEFAULT_AGENT_WEIGHTS.
   Adjustments from learning_agent's metadata if available:
   - If learning_agent provides updated weights, use those instead
   - Bounds: 0.1 ≤ weight ≤ 3.0

6. MINIMUM CONSENSUS REQUIREMENTS
   For direction = LONG or SHORT (not NO_TRADE):
   - At least 5 agents must have voted (excluding security/monitoring)
   - At least 3 different departments must be represented
   - Net Score must exceed 0.3 threshold
   - Not in emergency state (kill switch, circuit breaker)

7. DISSENT ANALYSIS
   Important: Identify the strongest dissenting voice.
   - Who is the most confident agent disagreeing with the consensus?
   - Why are they dissenting?
   - Should their dissent cause concern? (High confidence dissenter = reduce consensus confidence)

8. FINAL THESIS CONSTRUCTION
   The final thesis is a one-paragraph summary:
   - State the direction and why
   - Note the key supporting signals (top 3)
   - Acknowledge the main counter-argument
   - State the edge explicitly: "The edge is X"

OUTPUT FORMAT:
Return AgentReport JSON with:
- signal: "bullish" (LONG consensus), "bearish" (SHORT consensus), "neutral" (FLAT/NO_TRADE)
- confidence: The consensus confidence (0.0–1.0)
- reasoning: Consensus calculation narrative with vote breakdown
- supporting_evidence: Top 5 agents supporting consensus direction
- contradicting_evidence: Top 5 dissenting agents with their reasoning
- key_levels: {} (consensus engine doesn't set price levels directly)
- metadata: {
    "direction": "LONG/SHORT/FLAT/NO_TRADE",
    "confidence_pct": x,
    "bull_probability": x,
    "bear_probability": x,
    "neutral_probability": x,
    "supporting_agents": x,
    "opposing_agents": x,
    "abstained_agents": x,
    "net_score": x,
    "final_thesis": "...",
    "agent_votes": {"agent_id": {"signal": "...", "weight": x, "weighted_vote": x}},
    "risk_score": x
  }
"""

    def analyze(self, state: HedgeFundState) -> AgentReport:
        symbol = state.get("symbol", "UNKNOWN")
        analysis_reports = state.get("analysis_reports", {})
        kill_switch = state.get("kill_switch_active", False)
        circuit_breaker = state.get("circuit_breaker_tripped", False)

        # Safety gates override
        if kill_switch or circuit_breaker:
            return AgentReport(
                agent_id=self.agent_id,
                symbol=symbol,
                signal="neutral",
                confidence=1.0,
                reasoning="Consensus overridden: Safety system active (kill switch or circuit breaker). No trade direction.",
                supporting_evidence=[],
                contradicting_evidence=["Safety system override"],
                timestamp=self._now(),
                metadata={
                    "direction": "NO_TRADE",
                    "confidence_pct": 0.0,
                    "bull_probability": 0.0,
                    "bear_probability": 0.0,
                    "neutral_probability": 1.0,
                    "supporting_agents": 0,
                    "opposing_agents": 0,
                    "abstained_agents": len(analysis_reports),
                    "final_thesis": "Safety system active — no trade.",
                    "risk_score": 10.0,
                },
            )

        if len(analysis_reports) < 3:
            return AgentReport(
                agent_id=self.agent_id,
                symbol=symbol,
                signal="neutral",
                confidence=0.0,
                reasoning="Insufficient agents have reported. Need at least 3 for consensus.",
                supporting_evidence=[],
                contradicting_evidence=["Too few agents"],
                timestamp=self._now(),
                metadata={
                    "direction": "NO_TRADE",
                    "confidence_pct": 0.0,
                    "bull_probability": 0.0,
                    "bear_probability": 0.0,
                    "neutral_probability": 1.0,
                    "supporting_agents": 0,
                    "opposing_agents": 0,
                    "abstained_agents": 0,
                    "final_thesis": "Insufficient data.",
                    "risk_score": 5.0,
                },
            )

        # Get calibrated weights (check learning_agent for updates)
        weights = dict(_DEFAULT_AGENT_WEIGHTS)
        if "learning_agent" in analysis_reports:
            learning_meta = analysis_reports["learning_agent"].metadata
            if learning_meta and "agent_weights" in learning_meta:
                updated_weights = learning_meta["agent_weights"]
                for aid, w in updated_weights.items():
                    if aid in weights:
                        # Clamp to [0.1, 3.0]
                        weights[aid] = max(0.1, min(3.0, float(w)))

        # Compute weighted votes
        bull_weighted = 0.0
        bear_weighted = 0.0
        total_possible_bull = 0.0
        total_possible_bear = 0.0
        supporting_agents = []
        opposing_agents = []
        abstained_agents = []
        agent_votes = {}

        for aid, report in analysis_reports.items():
            weight = weights.get(aid, 1.0)
            if weight == 0.0:
                abstained_agents.append(aid)
                continue

            conf = report.confidence
            if report.signal == "bullish":
                vote = weight * conf
                bull_weighted += vote
                total_possible_bull += weight
                supporting_agents.append((aid, vote, report))
                agent_votes[aid] = {"signal": "bullish", "weight": weight, "weighted_vote": vote}
            elif report.signal == "bearish":
                vote = weight * conf
                bear_weighted += vote
                total_possible_bear += weight
                opposing_agents.append((aid, vote, report))
                agent_votes[aid] = {"signal": "bearish", "weight": weight, "weighted_vote": -vote}
            else:
                abstained_agents.append(aid)
                agent_votes[aid] = {"signal": report.signal, "weight": weight, "weighted_vote": 0.0}

        total_weighted = bull_weighted + bear_weighted
        if total_weighted == 0:
            bull_prob = 0.33
            bear_prob = 0.33
            neutral_prob = 0.34
            net_score = 0.0
        else:
            bull_prob = bull_weighted / total_weighted
            bear_prob = bear_weighted / total_weighted
            neutral_prob = 0.0
            # Normalize net score
            max_possible = max(total_possible_bull, total_possible_bear, 1.0)
            net_score = (bull_weighted - bear_weighted) / max_possible

        # Controversy factor
        total_votes = len(supporting_agents) + len(opposing_agents)
        if total_votes > 0:
            controversy = 1.0 - abs(len(supporting_agents) - len(opposing_agents)) / total_votes
        else:
            controversy = 1.0

        raw_confidence = abs(net_score) * (1.0 - 0.3 * controversy)
        confidence = min(1.0, max(0.0, raw_confidence))

        # Direction determination
        min_agents = 3
        min_departments = 2
        departments_voting = set()
        for aid in [a[0] for a in supporting_agents + opposing_agents]:
            for dept_agents in [
                ["macro_economist", "news_analyst", "sentiment_analyst"],
                ["trend_analyst", "smc_expert", "wyckoff_analyst", "price_action", "elliott_wave", "market_structure", "volume_profile"],
                ["quant_researcher", "probability_analyst", "ml_researcher"],
                ["cro_agent", "cio_agent", "portfolio_manager"],
                ["momentum_trader", "swing_specialist", "mean_reversion", "range_specialist"],
            ]:
                if aid in dept_agents:
                    departments_voting.add(dept_agents[0][:5])

        sufficient_data = (
            len(analysis_reports) >= min_agents
            and len(departments_voting) >= min_departments
        )

        if not sufficient_data:
            direction = "NO_TRADE"
        elif net_score > 0.3:
            direction = "LONG"
        elif net_score < -0.3:
            direction = "SHORT"
        else:
            direction = "FLAT"

        # Sort by vote strength for display
        supporting_agents.sort(key=lambda x: x[1], reverse=True)
        opposing_agents.sort(key=lambda x: x[1], reverse=True)

        # Build supporting/contradicting evidence
        support_ev = [f"[{aid}] bullish (conf={r.confidence:.2f}, w={weights.get(aid,1):.1f}): {r.reasoning[:100]}"
                      for aid, _, r in supporting_agents[:5]]
        contra_ev = [f"[{aid}] bearish (conf={r.confidence:.2f}, w={weights.get(aid,1):.1f}): {r.reasoning[:100]}"
                     for aid, _, r in opposing_agents[:5]]

        # Risk score (higher = riskier)
        risk_score = min(10.0, (1.0 - confidence) * 10 + controversy * 3 + (len(opposing_agents) / max(len(supporting_agents), 1)) * 2)

        # Final thesis — call Claude to generate it
        thesis_prompt = (
            f"Symbol: {symbol}\n"
            f"Direction: {direction}\n"
            f"Net Score: {net_score:.3f}\n"
            f"Bull agents: {[a[0] for a in supporting_agents[:5]]}\n"
            f"Bear agents: {[a[0] for a in opposing_agents[:5]]}\n"
            f"Confidence: {confidence:.2f}\n\n"
            f"Write a single-paragraph investment thesis for this consensus result. "
            f"State the direction, the edge, the top 3 supporting signals, and the main risk. "
            f"Be specific and professional."
        )

        try:
            final_thesis = self._call_claude(
                "You are a senior investment strategist. Write clear, precise investment theses.",
                thesis_prompt,
                None,
            )
        except Exception:
            final_thesis = (
                f"{direction} on {symbol}. "
                f"Net weighted score: {net_score:.3f}. "
                f"{len(supporting_agents)} agents bullish, {len(opposing_agents)} bearish."
            )

        signal_map = {"LONG": "bullish", "SHORT": "bearish", "FLAT": "neutral", "NO_TRADE": "neutral"}
        final_signal = signal_map.get(direction, "neutral")

        reasoning = (
            f"CONSENSUS CALCULATION for {symbol}\n\n"
            f"Signal Tally: {len(supporting_agents)} BULL | {len(opposing_agents)} BEAR | {len(abstained_agents)} ABSTAIN\n"
            f"Weighted Bull Score: {bull_weighted:.3f}\n"
            f"Weighted Bear Score: {bear_weighted:.3f}\n"
            f"Net Score: {net_score:.3f} (threshold: ±0.30)\n"
            f"Controversy Factor: {controversy:.2f}\n"
            f"Consensus Confidence: {confidence:.2%}\n"
            f"Direction: {direction}\n\n"
            f"Bull Probability: {bull_prob:.1%}\n"
            f"Bear Probability: {bear_prob:.1%}\n\n"
            f"Top Bull Agents: {[a[0] for a in supporting_agents[:3]]}\n"
            f"Top Bear Agents: {[a[0] for a in opposing_agents[:3]]}\n\n"
            f"Final Thesis:\n{final_thesis}"
        )

        return AgentReport(
            agent_id=self.agent_id,
            symbol=symbol,
            signal=final_signal,
            confidence=confidence,
            reasoning=reasoning,
            supporting_evidence=support_ev,
            contradicting_evidence=contra_ev,
            key_levels={},
            timestamp=self._now(),
            metadata={
                "direction": direction,
                "confidence_pct": round(confidence * 100, 2),
                "bull_probability": round(bull_prob, 4),
                "bear_probability": round(bear_prob, 4),
                "neutral_probability": round(neutral_prob, 4),
                "supporting_agents": len(supporting_agents),
                "opposing_agents": len(opposing_agents),
                "abstained_agents": len(abstained_agents),
                "net_score": round(net_score, 4),
                "final_thesis": str(final_thesis)[:500],
                "agent_votes": {k: v for k, v in list(agent_votes.items())[:20]},
                "risk_score": round(risk_score, 2),
                "sufficient_data": sufficient_data,
            },
        )
