"""
agents/executive/portfolio_manager.py
======================================
Portfolio Manager Agent.

Reviews current open positions, diversification, correlation, and sector
exposure to determine whether the portfolio can absorb a new position.
"""

from __future__ import annotations

from agents.base_agent import BaseAgent
from graph.state import AgentReport, HedgeFundState


class PortfolioManagerAgent(BaseAgent):
    agent_id = "portfolio_manager"
    department = "executive"

    def get_system_prompt(self) -> str:
        return """You are the Portfolio Manager of a quantitative hedge fund.

YOUR ROLE:
You are responsible for maintaining a well-diversified, risk-balanced portfolio.
Before any new position is added, you evaluate whether the portfolio structure
can absorb it without creating dangerous concentrations or correlation clusters.

YOUR ANALYTICAL FRAMEWORK:

1. CURRENT EXPOSURE REVIEW
   - What sectors/themes are currently overweight?
   - What is the current net market exposure (delta-adjusted)?
   - Is the portfolio currently long-heavy, short-heavy, or balanced?
   - What is the total number of open positions vs. the target maximum?

2. DIVERSIFICATION ANALYSIS
   - Does the proposed new symbol add meaningful diversification?
   - Is it correlated (>0.6) with any existing position?
   - Does it belong to an already-crowded sector in the portfolio?
   - Geographic diversification: is the portfolio concentrated in one market?

3. CORRELATION CLUSTER RISK
   - Group existing positions by correlation cluster
   - Identify "hidden concentration" — positions that appear different but move together
   - Example: holding AAPL + MSFT + QQQ is a triple-count of tech exposure

4. POSITION SIZING CONTEXT
   - What is current available capital after existing position margin?
   - Is the account in drawdown? Drawdowns require defensive, smaller position sizing.
   - Does adding this position bring us closer to or further from our target Sharpe ratio?

5. REBALANCING SIGNALS
   - Are any existing positions oversized relative to their current alpha signal?
   - Should any existing position be trimmed to make room for the new one?
   - Are there any positions that should be closed to reduce sector concentration?

6. PORTFOLIO HEALTH INDICATORS
   - Current portfolio beta vs. benchmark
   - Gross exposure and net exposure percentages
   - Maximum single-position size relative to portfolio: target ≤ 15%
   - Target number of uncorrelated positions: 5–15

SIGNAL LOGIC:
- "bullish" = portfolio can absorb the new position without structural issues
- "neutral" = portfolio can absorb with minor adjustments (note them)
- "bearish" = portfolio is too concentrated/correlated; new position not recommended

OUTPUT FORMAT:
Return AgentReport JSON with:
- signal: "bullish", "neutral", or "bearish"
- confidence: certainty in portfolio capacity assessment
- reasoning: portfolio health narrative
- supporting_evidence: factors supporting new position addition
- contradicting_evidence: portfolio constraints that argue against
- key_levels: {"available_capital_usd": x, "current_positions_count": x, "max_positions": x}
- metadata: {"sector_concentrations": {}, "correlation_flags": [], "rebalance_suggestions": []}
"""

    def analyze(self, state: HedgeFundState) -> AgentReport:
        symbol = state.get("symbol", "UNKNOWN")
        market_data = state.get("market_data", {})
        timeframe = state.get("timeframe", "unknown")

        portfolio_data = market_data.get("portfolio", {})
        open_positions = portfolio_data.get("open_positions", [])
        available_capital = portfolio_data.get("available_capital_usd", 0)
        total_equity = portfolio_data.get("total_equity_usd", 0)
        sector_exposure = portfolio_data.get("sector_exposure", {})
        net_exposure_pct = portfolio_data.get("net_exposure_pct", 0)
        gross_exposure_pct = portfolio_data.get("gross_exposure_pct", 0)
        current_drawdown_pct = portfolio_data.get("current_drawdown_pct", 0)

        positions_text = ""
        if open_positions:
            lines = []
            for pos in open_positions:
                lines.append(
                    f"  {pos.get('symbol','?')} | side={pos.get('side','?')} | "
                    f"size_usd={pos.get('size_usd',0):,.0f} | pnl_pct={pos.get('pnl_pct',0):.2f}% | "
                    f"sector={pos.get('sector','?')}"
                )
            positions_text = "\n".join(lines)
        else:
            positions_text = "  No open positions"

        sector_text = "\n".join(
            f"  {sector}: {pct:.1f}%" for sector, pct in sector_exposure.items()
        ) if sector_exposure else "  No sector data available"

        user_message = f"""PORTFOLIO REVIEW — New Position Request
Proposed Symbol: {symbol}
Timeframe: {timeframe}

=== CURRENT PORTFOLIO STATUS ===
Total Equity: ${total_equity:,.0f}
Available Capital: ${available_capital:,.0f}
Open Positions: {len(open_positions)}
Net Exposure: {net_exposure_pct:.1f}%
Gross Exposure: {gross_exposure_pct:.1f}%
Current Drawdown: {current_drawdown_pct:.2f}%

=== OPEN POSITIONS ===
{positions_text}

=== SECTOR EXPOSURE ===
{sector_text}

=== TASK ===
Evaluate whether adding a new position in {symbol} is prudent given the current
portfolio structure. Check diversification, correlation risk, sector concentration,
and available capacity. Return your Portfolio Manager AgentReport JSON.
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
                reasoning=f"Portfolio Manager analysis failed: {exc}",
                supporting_evidence=[],
                contradicting_evidence=["Analysis error"],
                timestamp=self._now(),
            )
