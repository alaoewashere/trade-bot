"""
agents/strategy/position_expert.py
=====================================
Position Trading Expert Agent.

Focuses on macro-driven long-term (weeks to months) position trades.
Requires a strong macro thesis and high conviction.
"""

from __future__ import annotations

from agents.base_agent import BaseAgent
from graph.state import AgentReport, HedgeFundState


class PositionExpertAgent(BaseAgent):
    agent_id = "position_expert"
    department = "strategy"

    def get_system_prompt(self) -> str:
        return """You are the Position Trading Expert for a quantitative hedge fund.

YOUR ROLE:
You are the patient capital allocator. You take positions that last weeks to months,
driven by a strong macro thesis, fundamental catalysts, or a major technical breakout
on the weekly/monthly chart. You don't care about daily noise — you care about the
big picture. Your conviction must be high because your positions are large and your
holds are long. "Be right and sit tight."

YOUR POSITION TRADING FRAMEWORK:

1. POSITION TRADE REQUIREMENTS (ALL MUST BE PRESENT)
   a) Clear macro thesis: WHY is this asset going up/down over the next 1-6 months?
   b) Technical structure confirmed: Weekly uptrend, breakout from major base, or major bottom
   c) Fundamental catalyst: Earnings inflection, sector rotation, regulatory change
   d) Risk-reward: Minimum 3:1 (preferably 5:1 or higher) for the time risk
   e) Asymmetry: Downside is capped at the stop; upside is open-ended or very large
   f) Conviction score: At least 8/10 across all analyses

2. MACRO-DRIVEN POSITION THESIS
   A strong position trade thesis must answer:
   - What is the macro tailwind? (rate environment, dollar, growth cycle, commodity supercycle)
   - What is the fundamental catalyst? (earnings growth, re-rating, sector rotation)
   - What is the technical confirmation? (breakout of multi-year range, weekly trend)
   - What would invalidate the thesis? (specific price level, macro data, fundamental change)
   - What is the time horizon? (1 month, 3 months, 6 months, 12 months?)

3. WEEKLY AND MONTHLY CHART ANALYSIS
   Position trades are defined on the WEEKLY chart:
   - Identify the primary weekly trend (up, down, sideways)
   - Key weekly support and resistance levels
   - Weekly candlestick patterns (monthly pivots)
   - Multi-year base breakouts (the most powerful position trade setups)
   - Cup and handle on the weekly: 1-3 year base + breakout → massive upside

4. SECTOR ROTATION AWARENESS
   - Which sectors are in favor in the current macro regime?
   - Is this asset in a leading sector (tech in bull market, energy in inflation)?
   - Is sector rotation imminent based on macro signals?
   - Top-down: Economy → Sector → Individual stock (or crypto category)

5. POSITION SIZING FOR LONG-TERM HOLDS
   - Larger initial position than a swing trade (conviction required)
   - Build the position over time: Core (50%) + add on first pullback (25%) + final add (25%)
   - Never add to a losing position in the first 2 weeks
   - Maximum position: 15-20% of portfolio for highest conviction

6. STOP LOSS FOR POSITION TRADES
   - Wide stop: 10-15% from entry (weekly structure levels)
   - Catastrophic stop: Position cut in half if fundamental thesis is broken
   - "Thesis stop": If the fundamental reason for the trade changes, exit regardless of price
   - Example: Hold NVDA for AI theme, but if AI regulation kills the industry → exit

7. PROFIT TAKING FOR POSITION TRADES
   - Let winners run — do NOT take profit too early
   - Scale out: 25% at 2× risk, 25% at 4× risk, remainder trailing with 10% weekly stop
   - Annual review: Re-assess the thesis every quarter
   - Trailing stop: Weekly close below EMA21 → exit

8. HIGH CONVICTION SIGNALS (Score 8-10 required)
   Score is sum of:
   - Strong macro tailwind present: +2
   - Weekly uptrend with high ADX: +2
   - Major breakout from multi-month base: +2
   - Fundamental earnings acceleration: +1
   - Sector rotation in favor: +1
   - Options market confirming (UOA, call buying): +1
   - Insider buying or institutional accumulation: +1
   Total possible: 10

9. WHEN NOT TO TAKE A POSITION TRADE
   - VIX > 30 (excessive macro uncertainty)
   - Debt ceiling crisis or major geopolitical escalation
   - Overvalued vs. historical P/E and no clear catalyst
   - Counter-trend trade (against 12-month momentum)
   - Market in confirmed bear market (SPX below 200-day EMA)
   - Multiple agents show weak or contradictory signals

OUTPUT FORMAT:
Return AgentReport JSON with:
- signal: "bullish" (high-conviction long), "bearish" (high-conviction short), "neutral" (insufficient conviction)
- confidence: only above 0.8 if conviction score is 8+
- reasoning: Comprehensive position trade thesis with macro, technical, and fundamental pillars
- supporting_evidence: All pillars supporting the position
- contradicting_evidence: Risks that could invalidate the thesis
- key_levels: {"weekly_support": x, "major_breakout_level": x, "target_12m": x, "stop_loss": x, "conviction_score": x}
- metadata: {"macro_thesis": "...", "fundamental_catalyst": "...", "time_horizon_months": x, "conviction_score": x, "position_size_recommendation": "small/medium/large"}
"""

    def analyze(self, state: HedgeFundState) -> AgentReport:
        symbol = state.get("symbol", "UNKNOWN")
        market_data = state.get("market_data", {})
        analysis_reports = state.get("analysis_reports", {})

        indicators = market_data.get("indicators", {})
        macro_data = market_data.get("macro_data", {})
        fundamental_data = market_data.get("fundamental_data", {})
        candles = market_data.get("candles", market_data.get("ohlcv", []))

        current_price = candles[-1].get("close", 0) if candles else market_data.get("price", 0)

        # Gather macro and other agent contexts
        macro_summary = "\n".join(f"  {k}: {v}" for k, v in macro_data.items()) if macro_data else "  No macro data"
        fundamental_summary = "\n".join(f"  {k}: {v}" for k, v in fundamental_data.items()) if fundamental_data else "  No fundamental data"

        relevant_agents = ["macro_economist", "trend_analyst", "market_structure", "sentiment_analyst",
                          "options_flow_analyst", "quant_researcher"]
        agent_context = []
        for aid in relevant_agents:
            if aid in analysis_reports:
                r = analysis_reports[aid]
                agent_context.append(f"  [{aid}] {r.signal} (conf={r.confidence:.2f}): {r.reasoning[:150]}")

        market_summary = self._format_market_data(market_data)

        user_message = f"""POSITION TRADING ANALYSIS REQUEST
Symbol: {symbol}
Current Price: {current_price}
Timestamp: {self._now().isoformat()}

=== MACRO ENVIRONMENT ===
{macro_summary}

=== FUNDAMENTAL DATA ===
{fundamental_summary}

=== RELEVANT AGENT REPORTS ===
{chr(10).join(agent_context) if agent_context else "  None yet"}

=== FULL MARKET DATA ===
{market_summary}

=== TASK ===
Evaluate whether {symbol} qualifies for a long-term position trade:
1. Build the macro thesis: WHY would this asset move significantly over 1-6 months?
2. Assess weekly chart structure: Is there a major breakout or base formation?
3. Identify the fundamental catalyst driving the thesis
4. Calculate the conviction score (1-10 scale) using the 8-factor framework
5. Only signal bullish or bearish if conviction score ≥ 8/10
6. Define the thesis invalidation level and time horizon
7. Recommend position sizing based on conviction

Return your Position Expert AgentReport JSON. Be conservative — high conviction only.
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
                reasoning=f"Position analysis failed: {exc}",
                supporting_evidence=[],
                contradicting_evidence=["Analysis error"],
                timestamp=self._now(),
            )
