"""
agents/monitoring/learning_agent.py
=====================================
Learning Agent.

Reviews patterns across recent winning and losing trades to identify which
agents/strategies perform best in the current regime. Suggests weight adjustments
for the ConsensusEngine. Uses claude-opus-4-7 for deep pattern recognition.
"""

from __future__ import annotations

from agents.base_agent import BaseAgent
from graph.state import AgentReport, HedgeFundState


class LearningAgentAgent(BaseAgent):
    agent_id = "learning_agent"
    department = "monitoring"

    def __init__(self) -> None:
        super().__init__()
        # Use opus for deeper pattern analysis
        self._agent_config["model"] = "claude-opus-4-7"
        self._agent_config["max_tokens"] = 8192

    def get_system_prompt(self) -> str:
        return """You are the Learning Agent for a quantitative hedge fund.

YOUR ROLE:
You are the fund's adaptive intelligence layer. You continuously analyze the
patterns across recent trades to identify which agents, strategies, and signals
are performing well in the current market regime — and which are failing. You then
recommend evidence-based weight adjustments to the ConsensusEngine to improve
future decision quality. You are the system's memory and its teacher.

YOUR LEARNING FRAMEWORK:

1. AGENT PERFORMANCE TRACKING
   For each agent, maintain a performance scorecard:
   - Number of signals given (bullish/bearish/neutral)
   - Signal accuracy rate: % of times agent signal aligned with profitable outcome
   - False positive rate: Agent said bullish, trade lost money
   - False negative rate: Agent said bearish/neutral, missed winning trade
   - Confidence calibration: Do high-confidence signals actually win more?
   - Regime-specific accuracy: How accurate is each agent in bull vs. bear vs. ranging markets?

2. STRATEGY PERFORMANCE BY REGIME
   Analyze which strategies work in which regimes:
   - Bull regime: Do momentum agents outperform mean reversion?
   - Bear regime: Do mean reversion agents fail? Do short strategies work?
   - Volatile regime: Do all trend-following strategies fail?
   - Ranging regime: Do momentum strategies fail? Do range strategies succeed?
   - Build a regime-strategy performance matrix

3. AGENT WEIGHT ADJUSTMENT RECOMMENDATIONS
   Current weight = default (1.0 for all agents)
   Propose new weights based on recent performance:
   - Agent with 75%+ accuracy in current regime: Weight = 1.5-2.0
   - Agent with 50-75% accuracy: Weight = 1.0 (unchanged)
   - Agent with 25-50% accuracy: Weight = 0.5-0.75
   - Agent with <25% accuracy in current regime: Weight = 0.1-0.25

   Rules for weight adjustments:
   - Minimum sample size: 10 signals before adjusting weight
   - Maximum weight: 2.5 (no single agent dominates)
   - Minimum weight: 0.1 (never completely silence an agent)
   - Decay: Weights decay toward 1.0 over time (avoid over-fitting to recent regime)
   - Never boost an agent more than +0.5 per review cycle

4. PATTERN RECOGNITION ACROSS TRADES
   Identify recurring profitable and loss patterns:
   - Setup patterns: Which specific setups have highest win rates?
   - Timing patterns: Are morning entries better than afternoon?
   - Duration patterns: Are shorter holds more profitable than longer?
   - Symbol patterns: Are certain asset classes performing better?
   - Indicator patterns: Which indicator combinations have been most predictive?

5. COGNITIVE BIAS DETECTION
   Identify if the system is exhibiting collective biases:
   - Recency bias: Over-weighting recent performance
   - Confirmation bias: Agents reinforcing each other's errors
   - Regime blindness: Failing to detect regime changes
   - Overconfidence: All agents giving high-confidence signals that are wrong

6. META-LEARNING INSIGHTS
   Higher-order observations about the system:
   - Is consensus being reached too quickly (insufficient debate)?
   - Are dissenting agents being appropriately valued?
   - Is the debate moderator balancing bull and bear arguments fairly?
   - Are low-confidence correct signals being rewarded?
   - Should the CIO be given more or less authority?

7. REGIME CHANGE DETECTION
   Using trade outcomes and market data:
   - Has the current regime changed in the past 20 trades?
   - If yes: Which agents were early in detecting the change?
   - Recalibrate weights for the new regime
   - Alert the system that a regime transition is occurring

8. LEARNING REPORT OUTPUT
   The learning agent produces:
   - Agent accuracy matrix (regime × agent)
   - Weight adjustment recommendations with evidence
   - Identified patterns in winning vs. losing trades
   - Regime assessment: current regime and predicted transition
   - System health score (1-10)

OUTPUT FORMAT:
Return AgentReport JSON with:
- signal: "bullish" (system learning well, improving), "bearish" (system making systematic errors, needs correction), "neutral" (insufficient data or stable)
- confidence: based on data quantity and pattern clarity
- reasoning: Deep learning analysis narrative with specific agent performance data
- supporting_evidence: Positive learning signals and well-performing agents
- contradicting_evidence: Systematic errors and poorly performing agents
- key_levels: {} (learning agent doesn't set price levels)
- metadata: {"agent_weights": {"agent_id": weight, ...}, "regime_detected": "...", "system_health_score": x, "top_performing_agent": "...", "worst_performing_agent": "...", "recommended_adjustments": [...]}
"""

    def analyze(self, state: HedgeFundState) -> AgentReport:
        symbol = state.get("symbol", "UNKNOWN")
        market_data = state.get("market_data", {})
        analysis_reports = state.get("analysis_reports", {})

        recent_trades = market_data.get("recent_trades", market_data.get("trade_history", []))
        performance_data = market_data.get("performance_data", {})
        agent_performance_history = market_data.get("agent_performance_history", {})

        if not recent_trades and not agent_performance_history:
            return AgentReport(
                agent_id=self.agent_id,
                symbol=symbol,
                signal="neutral",
                confidence=0.1,
                reasoning="Insufficient trade history for learning analysis. Need at least 10 recent trades.",
                supporting_evidence=[],
                contradicting_evidence=["No recent_trades or agent_performance_history provided"],
                timestamp=self._now(),
            )

        # Build agent performance summary
        agent_perf_text = ""
        if agent_performance_history:
            lines = []
            for agent_id, perf in agent_performance_history.items():
                if isinstance(perf, dict):
                    acc = perf.get("accuracy_pct", "?")
                    n = perf.get("n_signals", "?")
                    regime_acc = perf.get("regime_accuracy", {})
                    lines.append(f"  [{agent_id}] accuracy={acc}% n={n} regime_breakdown={regime_acc}")
                else:
                    lines.append(f"  [{agent_id}]: {perf}")
            agent_perf_text = "\n".join(lines)
        else:
            agent_perf_text = "  No historical agent performance data — analyze from recent trades"

        # Summarize recent trades
        trade_lines = []
        for i, t in enumerate(recent_trades[-30:]):
            if isinstance(t, dict):
                agents_that_called_it = t.get("calling_agents", {})
                pnl = t.get("pnl_usd", t.get("pnl", 0))
                win = "WIN" if pnl > 0 else "LOSS"
                trade_lines.append(
                    f"  [{i+1}] {t.get('symbol','?')} {t.get('direction','?')} | "
                    f"P&L=${pnl:,.0f} [{win}] | agents={agents_that_called_it}"
                )
        trades_text = "\n".join(trade_lines) if trade_lines else "  No recent trade data"

        # Current agent signals for context
        current_signals = []
        for aid, r in analysis_reports.items():
            current_signals.append(f"  [{aid}]: {r.signal} ({r.confidence:.2f})")

        user_message = f"""LEARNING AGENT ANALYSIS
Symbol: {symbol}
Timestamp: {self._now().isoformat()}

=== AGENT PERFORMANCE HISTORY ===
{agent_perf_text}

=== RECENT TRADES (last 30) ===
{trades_text}

=== CURRENT AGENT SIGNALS (this cycle) ===
{chr(10).join(current_signals) if current_signals else "  None yet"}

=== PERFORMANCE SUMMARY ===
{performance_data}

=== TASK ===
Conduct deep learning analysis for the hedge fund system:
1. Analyze each agent's accuracy across recent trades — identify winners and losers
2. Detect the current market regime from trade outcomes and market conditions
3. Build regime-specific agent accuracy assessments
4. Recommend specific weight adjustments for the ConsensusEngine
5. Identify recurring patterns in winning vs. losing trades
6. Detect any systematic biases in the current AI committee
7. Assess whether a regime change has occurred or is imminent
8. Score overall system health (1-10) and identify the top improvement priority

Return your Learning Agent AgentReport JSON with comprehensive weight recommendations.
"""

        try:
            result = self._call_claude(self.get_system_prompt(), user_message, AgentReport)
            return AgentReport(
                agent_id=self.agent_id,
                symbol=symbol,
                signal=result.signal,
                confidence=result.confidence,
                reasoning=result.reasoning,
                supporting_evidence=result.supporting_evidence,
                contradicting_evidence=result.contradicting_evidence,
                key_levels=result.key_levels,
                timestamp=self._now(),
                metadata=result.metadata,
            )
        except Exception as exc:
            return AgentReport(
                agent_id=self.agent_id,
                symbol=symbol,
                signal="neutral",
                confidence=0.0,
                reasoning=f"Learning analysis failed: {exc}",
                supporting_evidence=[],
                contradicting_evidence=["Analysis error"],
                timestamp=self._now(),
            )
