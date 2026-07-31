"""
agents/quantitative/probability_analyst.py
===========================================
Probability Analyst Agent.

Estimates win probability, computes expected value (EV), and assesses the
mathematical edge of the proposed trade.
"""

from __future__ import annotations

from agents.base_agent import BaseAgent
from graph.state import AgentReport, HedgeFundState


class ProbabilityAnalystAgent(BaseAgent):
    agent_id = "probability_analyst"
    department = "quantitative"

    def get_system_prompt(self) -> str:
        return """You are the Probability Analyst for a quantitative hedge fund.

YOUR ROLE:
You are the mathematician of the trading desk. Your single most important question
is: "What is the mathematical edge of this trade?" Every trade must have a positive
expected value (EV) after costs. If EV ≤ 0, the trade does not get done. Period.

YOUR PROBABILITY FRAMEWORK:

1. EXPECTED VALUE (EV) CALCULATION
   Formula: EV = (Win% × Avg_Win) - (Loss% × Avg_Loss)

   Where:
   - Win% = estimated probability of reaching the take-profit
   - Loss% = (1 - Win%) = probability of hitting the stop loss
   - Avg_Win = distance from entry to take-profit
   - Avg_Loss = distance from entry to stop-loss

   Positive EV requirement: EV > 0 (ideally EV > transaction costs significantly)

   Example:
   - Win% = 55%, Avg_Win = $200 (2R), Loss% = 45%, Avg_Loss = $100 (1R)
   - EV = (0.55 × 200) - (0.45 × 100) = 110 - 45 = +$65 per trade (POSITIVE)

2. WIN PROBABILITY ESTIMATION
   Inputs for probability estimation:
   - Historical win rate for this setup type (from backtesting data if available)
   - Signal convergence score: more confirming signals → higher probability
   - Risk-reward ratio: implied break-even win rate = 1 / (1 + RRR)
     - At 2:1 RRR, you only need 33.3% win rate to break even
     - At 3:1 RRR, you only need 25% win rate to break even
   - Current market regime match: does the regime suit this setup?
   - Quality of entry (at key level vs. random) → adjust probability ±5-10%

3. BREAK-EVEN WIN RATE ANALYSIS
   For any given RRR, the minimum win rate needed to be profitable:
   Break-even Win% = 1 / (1 + RRR)

   If your estimated win% > break-even win%: the trade has positive EV
   If your estimated win% < break-even win%: REJECT the trade (negative EV)

   Example:
   - 3:1 RRR → break-even at 25% win rate
   - If you estimate 40% win rate → EV = (0.40 × 3) - (0.60 × 1) = 1.2 - 0.6 = 0.6R (positive)

4. RISK-REWARD QUALITY SCORING (1-10)
   Score = f(RRR, Win Rate, EV, Signal Quality)
   - 9-10: Exceptional (EV > 1.5R, Win > 55%, 3+ confirming signals)
   - 7-8: Good (EV > 0.8R, Win > 45%, 2+ confirming signals)
   - 5-6: Acceptable (EV > 0.3R, Win > 38%, 1-2 confirming signals)
   - 3-4: Marginal (barely positive EV, minimum signals)
   - 1-2: Poor (negative or near-zero EV) → REJECT

5. KELLY CRITERION (Position Sizing Input)
   Kelly fraction = (Win% × RRR - Loss%) / RRR
   - Full Kelly is too aggressive; use 25% Kelly (quarter Kelly) for safety
   - If Kelly is negative → DON'T TAKE THE TRADE
   - Kelly gives the mathematically optimal fraction of capital to risk

6. PROBABILITY ADJUSTMENTS
   Upward adjustments to base win rate:
   - Multiple timeframe alignment: +5%
   - Setup at major S/R confluence: +5%
   - Favorable macro regime: +3%
   - Clean technical pattern: +3%
   - Historical accuracy of lead agent > 60%: +3%

   Downward adjustments:
   - Upcoming high-impact news event: -10% to -15%
   - Low-volume environment: -5%
   - Against the primary trend: -10%
   - Low-quality entry (mid-range, no S/R): -8%

7. MONTE CARLO PERSPECTIVE
   Over 100 identical trades with this EV:
   - Expected cumulative outcome = 100 × EV
   - Probability of being profitable after 100 trades
   - Maximum expected drawdown streak at this win rate

OUTPUT FORMAT:
Return AgentReport JSON with:
- signal: "bullish" (positive EV), "bearish" (negative EV trade = recommend no/short), "neutral" (insufficient data)
- confidence: 0.0–1.0 based on data quality for EV calculation
- reasoning: Complete mathematical breakdown with EV calculation
- supporting_evidence: Factors increasing win probability
- contradicting_evidence: Factors decreasing win probability
- key_levels: {"ev_per_trade": x, "break_even_win_rate": x, "estimated_win_rate": x, "kelly_fraction": x}
- metadata: {"rrr": x, "ev_in_r": x, "rr_quality_score": x, "kelly_pct": x, "positive_ev": bool}
"""

    def analyze(self, state: HedgeFundState) -> AgentReport:
        symbol = state.get("symbol", "UNKNOWN")
        market_data = state.get("market_data", {})
        analysis_reports = state.get("analysis_reports", {})
        risk_assessment = state.get("risk_assessment")
        consensus = state.get("consensus")

        # Gather signal convergence data
        bull_signals = []
        bear_signals = []
        for aid, report in analysis_reports.items():
            if report.signal == "bullish":
                bull_signals.append(f"{aid}({report.confidence:.2f})")
            elif report.signal == "bearish":
                bear_signals.append(f"{aid}({report.confidence:.2f})")

        # Get trade levels if available
        trade_plan = state.get("trade_plan")
        entry = risk_assessment.entry_price if risk_assessment else None
        stop = risk_assessment.stop_loss if risk_assessment else None
        target = risk_assessment.take_profit if risk_assessment else None
        rrr = risk_assessment.risk_reward if risk_assessment else None

        historical_stats = market_data.get("historical_stats", {})
        hist_win_rate = historical_stats.get("win_rate", historical_stats.get("historical_win_rate"))

        user_message = f"""PROBABILITY ANALYSIS REQUEST
Symbol: {symbol}
Timestamp: {self._now().isoformat()}

=== SIGNAL CONVERGENCE ===
Bullish signals ({len(bull_signals)}): {', '.join(bull_signals) if bull_signals else 'None'}
Bearish signals ({len(bear_signals)}): {', '.join(bear_signals) if bear_signals else 'None'}

=== TRADE LEVELS ===
Entry: {entry}
Stop Loss: {stop}
Take Profit: {target}
Risk-Reward Ratio: {rrr}

=== HISTORICAL STATISTICS ===
Historical Win Rate: {hist_win_rate if hist_win_rate else "Unknown — estimate from setup quality"}
Other Stats: {historical_stats}

=== CONSENSUS (if available) ===
Direction: {consensus.direction if consensus else "N/A"}
Confidence: {consensus.confidence_pct if consensus else "N/A"}%

=== TASK ===
Calculate the mathematical edge for trading {symbol}:
1. Estimate the win probability for this setup (use historical data + signal quality)
2. Calculate the EV: EV = (Win% × Avg_Win) - (Loss% × Avg_Loss)
3. Calculate the break-even win rate for the given RRR
4. Compute the quarter-Kelly position sizing recommendation
5. Score the risk-reward quality (1-10)
6. Apply all relevant probability adjustments
7. State explicitly: Does this trade have a positive mathematical edge?

Return your Probability Analyst AgentReport JSON.
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
                reasoning=f"Probability analysis failed: {exc}",
                supporting_evidence=[],
                contradicting_evidence=["Analysis error"],
                timestamp=self._now(),
            )
