"""
agents/execution/trade_planner.py
====================================
Trade Planner Agent.

Given consensus + risk assessment, defines a precise trade plan:
entry type, entry zones, stop loss, take profit levels, and execution timing notes.
"""

from __future__ import annotations

from agents.base_agent import BaseAgent
from graph.state import AgentReport, HedgeFundState


class TradePlannerAgent(BaseAgent):
    agent_id = "trade_planner"
    department = "execution"

    def get_system_prompt(self) -> str:
        return """You are the Trade Planner for a quantitative hedge fund.

YOUR ROLE:
You translate the investment committee's consensus and risk assessment into a
precise, actionable trade plan. You are the bridge between analysis and execution.
Every detail of the trade must be specified before it is sent to execution —
entry type, price zones, stop loss, take profit levels, position sizing, and
timing considerations. Ambiguity in trade planning leads to poor execution.

YOUR TRADE PLANNING FRAMEWORK:

1. ENTRY TYPE SELECTION
   Market Order:
   - Use when: High-urgency breakout, very liquid market, small size
   - Risk: Slippage on illiquid assets; avoid in wide spread environments
   - Best for: Momentum entries, breakouts, news-driven moves

   Limit Order:
   - Use when: Pullback entry, range-bound market, high spread
   - Advantage: Better fill price, lower slippage
   - Risk: May not get filled if price doesn't reach limit
   - Set limit: At the specific S/R level or EMA being targeted

   Stop-Limit Order:
   - Use when: Breakout above resistance (don't buy until price confirms)
   - Stop trigger: Above resistance level
   - Limit: 0.1-0.5% above stop to ensure fill in fast markets
   - Risk: Price may gap through both stop and limit (no fill in fast market)

2. ENTRY ZONE DEFINITION
   Never specify a single entry price — specify a zone:
   - Entry Zone Low: The ideal entry (at the best price in the zone)
   - Entry Zone High: The maximum acceptable entry price
   - Zone width: Typically 0.2-0.5% for liquid assets, 0.5-1.0% for illiquid
   - If price enters the zone: start accumulating
   - If price reaches zone high: stop adding (risk is too close)

3. STOP LOSS SPECIFICATION
   Requirements for a valid stop loss:
   - Must be at a structural level (not arbitrary dollar amount)
   - Must invalidate the trade thesis if hit
   - Must be calculated BEFORE entry (not after)
   - Distance from entry: 0.5-3% for swing, 3-8% for position trades
   - Never move the stop FURTHER from entry (only closer, to protect profit)

   Stop Types:
   - Hard stop: Fixed price level sent as a stop order
   - Mental stop: Monitored manually (higher skill required)
   - ATR-based stop: Entry - (N × ATR) where N = 1.5-2.5

4. TAKE PROFIT LEVELS (MULTI-TARGET APPROACH)
   Always use multiple take profit levels to optimize exit:
   - TP1 (33% of position): 1× risk distance from entry (lock in quick profit)
   - TP2 (33% of position): 2× risk distance OR next key S/R level
   - TP3 (remaining 34%): 3× risk OR major structural target
   - After TP1: Move stop to breakeven
   - After TP2: Trail stop below the most recent swing low

5. TRAILING STOP SPECIFICATION
   - Activate trailing stop after TP1 hit
   - Trail distance: 1× ATR behind price
   - Or: Trail behind EMA21 on the trade timeframe
   - Trailing stop percentage: Typically 2-5% for swings, 5-10% for position trades

6. TIMING AND EXECUTION NOTES
   - Time of day: Specify preferred execution window
   - Market conditions: "Execute only if volume > X" or "Execute only on pullback to Y"
   - Catalyst awareness: "Do not execute within 30 minutes of FOMC/earnings"
   - Order staging: "Split order into 3 tranches over 30 minutes to minimize impact"

7. POSITION SIZE CONFIRMATION
   Use risk assessment parameters:
   - Position size in USD: From risk assessment
   - Position size in units: USD / entry price
   - Maximum risk per trade: From portfolio settings (typically 1-2% of equity)
   - Kelly fraction applied: Quarter-Kelly from probability analyst

8. CONTINGENCY RULES
   - If TP1 not reached within 3 days: Evaluate re-entry conditions
   - If price gaps through stop: Close at market immediately
   - If correlation with existing positions suddenly spikes: Reduce size by 50%
   - If VIX spikes >25% intraday: Reduce all new positions by 50%

OUTPUT FORMAT:
Return AgentReport JSON with:
- signal: "bullish" (long plan ready), "bearish" (short plan ready), "neutral" (no valid plan)
- confidence: based on plan precision and signal consensus quality
- reasoning: Detailed trade plan narrative
- supporting_evidence: Plan justification points
- contradicting_evidence: Execution risks and caveats
- key_levels: {"entry_low": x, "entry_high": x, "stop_loss": x, "tp1": x, "tp2": x, "tp3": x}
- metadata: {"entry_type": "market/limit/stop_limit", "position_size_usd": x, "risk_usd": x, "rrr": x, "timing_note": "...", "contingencies": [...]}
"""

    def analyze(self, state: HedgeFundState) -> AgentReport:
        symbol = state.get("symbol", "UNKNOWN")
        market_data = state.get("market_data", {})
        consensus = state.get("consensus")
        risk_assessment = state.get("risk_assessment")
        analysis_reports = state.get("analysis_reports", {})

        if not consensus:
            return AgentReport(
                agent_id=self.agent_id,
                symbol=symbol,
                signal="neutral",
                confidence=0.0,
                reasoning="No consensus available — cannot create trade plan without direction.",
                supporting_evidence=[],
                contradicting_evidence=["Consensus not yet established"],
                timestamp=self._now(),
            )

        # Get key levels from technical agents
        key_levels_summary = []
        for aid in ["smc_expert", "volume_profile", "market_structure", "trend_analyst", "price_action"]:
            if aid in analysis_reports:
                r = analysis_reports[aid]
                if r.key_levels:
                    levels_str = ", ".join(f"{k}={v}" for k, v in list(r.key_levels.items())[:3])
                    key_levels_summary.append(f"  [{aid}]: {levels_str}")

        risk_text = ""
        if risk_assessment:
            risk_text = f"""
Risk Assessment:
  Position Size: ${risk_assessment.position_size_usd:,.0f}
  Entry: {risk_assessment.entry_price}
  Stop: {risk_assessment.stop_loss}
  Target: {risk_assessment.take_profit}
  RRR: {risk_assessment.risk_reward:.2f}
  Max Risk: ${risk_assessment.max_risk_usd:,.0f}
  Portfolio Heat: {risk_assessment.portfolio_heat_pct:.2f}%
"""

        candles = market_data.get("candles", market_data.get("ohlcv", []))
        current_price = candles[-1].get("close", 0) if candles else market_data.get("price", 0)
        indicators = market_data.get("indicators", {})
        atr = indicators.get("atr", indicators.get("ATR"))
        spread = market_data.get("spread")
        volume_24h = market_data.get("volume_24h")

        user_message = f"""TRADE PLANNING REQUEST
Symbol: {symbol}
Current Price: {current_price}
Timestamp: {self._now().isoformat()}

=== CONSENSUS DIRECTION ===
Direction: {consensus.direction}
Confidence: {consensus.confidence_pct:.1f}%
Bull Probability: {consensus.bull_probability:.1%}
Bear Probability: {consensus.bear_probability:.1%}
Final Thesis: {consensus.final_thesis[:300]}

{risk_text}

=== KEY TECHNICAL LEVELS (from agents) ===
{chr(10).join(key_levels_summary) if key_levels_summary else "  No levels extracted yet"}

=== MARKET EXECUTION CONTEXT ===
  ATR: {atr if atr else "N/A"}
  Bid-Ask Spread: {spread if spread else "N/A"}
  24h Volume: {f'${volume_24h:,.0f}' if volume_24h else "N/A"}

=== TASK ===
Create a detailed trade plan for {symbol} based on the consensus direction ({consensus.direction}):
1. Select entry type (market/limit/stop_limit) and justify
2. Define the precise entry zone (low and high price)
3. Set stop loss at the structural invalidation level
4. Define 3 take profit targets with scaling logic
5. Specify trailing stop activation and parameters
6. Add execution timing notes (time of day, condition triggers)
7. Specify contingency rules for adverse scenarios

Return your Trade Planner AgentReport JSON with the complete trade plan.
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
                reasoning=f"Trade planning failed: {exc}",
                supporting_evidence=[],
                contradicting_evidence=["Planning error"],
                timestamp=self._now(),
            )
