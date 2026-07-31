"""
agents/executive/cro_agent.py
==============================
Chief Risk Officer Agent.

Assesses the risk of proposed trades. The CRO is the last line of defense —
their default posture is NO until the evidence overwhelmingly justifies YES.
"""

from __future__ import annotations

from agents.base_agent import BaseAgent
from graph.state import AgentReport, HedgeFundState


class CROAgent(BaseAgent):
    agent_id = "cro_agent"
    department = "executive"

    def get_system_prompt(self) -> str:
        return """You are the Chief Risk Officer (CRO) of a quantitative hedge fund.

YOUR CORE MANDATE:
Your job is to say NO more than YES. You are the last line of defense before capital is deployed.
Every trade that passes through you must survive a rigorous risk examination. You are not here to
find reasons to trade — you are here to find reasons NOT to trade, and to quantify every risk
that the trading team may have overlooked.

YOUR RISK FRAMEWORK:

1. CORRELATION RISK
   - Does this trade increase portfolio correlation? If the portfolio already has 3 tech longs,
     adding another is doubling correlation exposure.
   - Check if the proposed asset moves similarly to existing open positions.
   - Correlation above 0.7 with existing positions = require position size reduction.

2. DRAWDOWN RISK
   - What is the maximum historical drawdown for this asset/setup?
   - If the stop is hit, what % of monthly P&L does that represent?
   - Is the current drawdown already elevated? A portfolio at -5% this month needs smaller bets.

3. PORTFOLIO HEAT
   - Portfolio heat = total capital at risk across all open positions as % of equity
   - Maximum allowable heat: 6% of equity at any one time
   - New trade must not push total heat above this threshold
   - Heat already at 4%+ → REJECT or drastically reduce size

4. TAIL RISK
   - What is the 95% VaR and 99% CVaR for this position?
   - Are there upcoming events (earnings, Fed decisions, CPI) that create gap risk?
   - Crypto positions carry liquidation cascade risk — require wider stops
   - Black swan scenario: if this trade loses 3x the expected amount, is the fund solvent?

5. LIQUIDITY RISK
   - Can the position be exited quickly if needed?
   - Is the 24h volume sufficient to absorb the planned trade size without significant slippage?
   - Illiquid instruments require forced risk reduction

6. CONCENTRATION RISK
   - Single-name concentration: no more than 20% of capital in one symbol
   - Sector concentration: no more than 35% in one sector
   - Crypto: no more than 25% in crypto total

7. MODEL RISK
   - Is the agent consensus based on diverse, independent signals?
   - Are all bullish agents looking at the same (correlated) indicators?
   - Overfit signals must be penalized in risk assessment

DECISION CRITERIA:
- APPROVED (bullish signal): All major risk criteria pass, position size is reasonable
- PARTIAL APPROVAL: Approve with reduced size (note in reasoning)
- REJECTED (bearish signal): One or more hard limits breached, or insufficient justification

OUTPUT FORMAT:
Return AgentReport JSON with:
- signal: "bullish" (approved), "bearish" (rejected), or "neutral" (conditional/reduced)
- confidence: your certainty in the risk assessment
- reasoning: Detailed risk memo covering all applicable risk categories
- supporting_evidence: Reasons the risk is acceptable
- contradicting_evidence: Risk flags and concerns
- key_levels: {"max_position_size_usd": x, "max_risk_usd": x, "portfolio_heat_current_pct": x}
- metadata: {"approved": bool, "rejection_reasons": [...], "recommended_size_reduction_pct": 0}
"""

    def analyze(self, state: HedgeFundState) -> AgentReport:
        symbol = state.get("symbol", "UNKNOWN")
        market_data = state.get("market_data", {})
        analysis_reports = state.get("analysis_reports", {})
        risk_assessment = state.get("risk_assessment")
        consensus = state.get("consensus")
        kill_switch = state.get("kill_switch_active", False)
        circuit_breaker = state.get("circuit_breaker_tripped", False)

        # Hard gates — if either safety system is active, immediate reject
        if kill_switch or circuit_breaker:
            return AgentReport(
                agent_id=self.agent_id,
                symbol=symbol,
                signal="bearish",
                confidence=1.0,
                reasoning="HARD STOP: Kill switch or circuit breaker is active. No new positions allowed.",
                supporting_evidence=[],
                contradicting_evidence=["Kill switch active" if kill_switch else "Circuit breaker tripped"],
                timestamp=self._now(),
                metadata={"approved": False, "rejection_reasons": ["safety_system_active"]},
            )

        # Gather context
        portfolio_data = market_data.get("portfolio", {})
        current_heat = portfolio_data.get("portfolio_heat_pct", 0.0)
        open_positions = portfolio_data.get("open_positions", [])

        agent_summary = []
        for aid, report in analysis_reports.items():
            agent_summary.append(f"[{aid}] {report.signal} (conf={report.confidence:.2f})")

        risk_ctx = ""
        if risk_assessment:
            risk_ctx = f"""
Risk Assessment (from RiskEngine):
  position_size_usd={risk_assessment.position_size_usd}
  max_risk_usd={risk_assessment.max_risk_usd}
  portfolio_heat_pct={risk_assessment.portfolio_heat_pct}
  var_95={risk_assessment.var_95}
  correlation_check={risk_assessment.correlation_check}
  liquidity_check={risk_assessment.liquidity_check}
  rejection_reasons={risk_assessment.rejection_reasons}
"""

        market_summary = self._format_market_data(market_data)

        user_message = f"""CRO RISK REVIEW
Symbol: {symbol}
Current Portfolio Heat: {current_heat:.1f}%
Open Positions: {len(open_positions)}
Kill Switch: {kill_switch} | Circuit Breaker: {circuit_breaker}

Agent Signals:
{chr(10).join(agent_summary) if agent_summary else "None yet"}

{risk_ctx}

Market Data:
{market_summary}

Consensus Direction: {consensus.direction if consensus else "Not yet determined"}
Consensus Confidence: {consensus.confidence_pct if consensus else "N/A"}%

Conduct your full risk review. Check correlation, drawdown, portfolio heat, tail risk,
liquidity, concentration, and model risk. Return your CRO AgentReport JSON.
Remember: your default is NO. The burden of proof is on the trade to be approved.
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
                signal="bearish",
                confidence=0.9,
                reasoning=f"CRO analysis error — defaulting to REJECT for safety: {exc}",
                supporting_evidence=[],
                contradicting_evidence=["Analysis failure — risk cannot be assessed"],
                timestamp=self._now(),
                metadata={"approved": False, "rejection_reasons": ["analysis_error"]},
            )
