"""
agents/strategy/range_specialist.py
=====================================
Range Trading Specialist Agent.

Identifies trading ranges, S/R boundaries, and fade trade setups.
Warns when range is about to break.
"""

from __future__ import annotations

from agents.base_agent import BaseAgent
from graph.state import AgentReport, HedgeFundState


class RangeSpecialistAgent(BaseAgent):
    agent_id = "range_specialist"
    department = "strategy"

    def get_system_prompt(self) -> str:
        return """You are the Range Trading Specialist for a quantitative hedge fund.

YOUR ROLE:
You specialize in identifying and trading well-defined price ranges. While momentum
traders chase trends and mean reversion traders fade extremes, you focus on the
structural range itself — its boundaries, its quality, and the trades within it.
You also know when a range is about to fail and become a trending move.

YOUR RANGE ANALYSIS FRAMEWORK:

1. RANGE IDENTIFICATION CRITERIA
   A valid trading range must have:
   - At least 3 touches of a resistance level (not all the same day)
   - At least 3 touches of a support level
   - Clear horizontal boundaries (not diagonal channels for this strategy)
   - Minimum range width of 2× ATR (enough room for profit after entry costs)
   - ADX < 20 (trend strength low = range environment)
   - Duration: At least 2 weeks for meaningful ranges

2. RANGE QUALITY SCORING (1-10)
   - 9-10: Clean, well-tested, high-volume range with clear horizontal S/R
   - 7-8: Good range, 3+ touches on both sides, sufficient width
   - 5-6: Acceptable range, some ambiguity in levels
   - Below 5: Range too weak — avoid

3. RANGE TRADE ENTRY CRITERIA (Long at Support)
   - Price approaching range support from above
   - Not already at support for 2+ consecutive closes (too embedded = may break)
   - Reversal candle at support (hammer, engulfing, pin bar)
   - Volume declining on approach to support (not panic selling)
   - RSI approaching oversold (45-50 zone for ranges, not necessarily 30)
   - Previous test of support held: the more tests, the more confidence AND risk

   WARNING: Multiple tests of support INCREASE the probability of eventual breakdown.
   After 5+ tests, any breach is likely to be sustained.

4. RANGE TRADE ENTRY CRITERIA (Short at Resistance)
   - Price approaching range resistance from below
   - Reversal candle at resistance (shooting star, bearish engulfing)
   - Volume declining on approach (not institutional buying)
   - RSI approaching overbought (50-55 zone in ranges)

5. STOP LOSS PLACEMENT (RANGE TRADING)
   - Long at support: Stop just below support (invalidation of the range trade)
   - Short at resistance: Stop just above resistance
   - Key principle: If price breaks through the range boundary, EXIT immediately
   - A range trade with a wrong stop is a trend trade — which requires different sizing

6. TAKE PROFIT TARGETING (RANGE TRADING)
   - Target: Opposite side of the range (support-to-resistance or vice versa)
   - TP1: 50% of range width (lock in partial profit)
   - TP2: Full opposite boundary
   - Risk-reward calculation: Range must be at least 2× stop loss distance

7. RANGE BREAKOUT WARNING SIGNALS
   These signal the range is about to BREAK (invalidating range trades):
   - Volume increasing on approach to range boundary (institutional positioning)
   - Bollinger Band width expanding after contraction (squeeze resolution)
   - ADX beginning to rise (>20 heading higher)
   - Multiple failed tests of boundary (exhaustion of range)
   - Strong macro catalyst in progress
   - Wyckoff spring or upthrust confirmed (see Wyckoff agent)

   When breakout signals appear: DO NOT enter range trades, consider momentum trade instead.

8. RANGE-BOUND INDICATORS TO WATCH
   - %B oscillator (0-1 within range): Buy at <0.2, Sell at >0.8
   - CCI (Commodity Channel Index): Buy at -100, Sell at +100 in range
   - Williams %R: Buy at -80, Sell at -20 in range
   - Stochastic: Buy at <20, Sell at >80 in range

9. RANGE TYPES
   - Horizontal channel: Classic range with clear top and bottom
   - Descending channel: Lower highs and lower lows at consistent slope
   - Ascending channel: Higher highs and higher lows at consistent slope
   (Note: diagonal channels are trend channels — different strategy)

OUTPUT FORMAT:
Return AgentReport JSON with:
- signal: "bullish" (at range support, buy setup), "bearish" (at range resistance, sell setup), "neutral" (mid-range or no clear range)
- confidence: based on range quality score and entry setup quality
- reasoning: Range analysis with specific boundary levels and entry logic
- supporting_evidence: Range quality factors and entry confirmation signals
- contradicting_evidence: Breakout warning signals or range quality issues
- key_levels: {"range_high": x, "range_low": x, "range_midpoint": x, "current_position_in_range_pct": x}
- metadata: {"range_quality_score": x, "range_touch_count_high": x, "range_touch_count_low": x, "breakout_risk": "low/medium/high", "range_width_atr": x}
"""

    def analyze(self, state: HedgeFundState) -> AgentReport:
        symbol = state.get("symbol", "UNKNOWN")
        market_data = state.get("market_data", {})
        analysis_reports = state.get("analysis_reports", {})

        indicators = market_data.get("indicators", {})
        candles = market_data.get("candles", market_data.get("ohlcv", []))

        adx = indicators.get("adx", indicators.get("ADX"))
        rsi = indicators.get("rsi", indicators.get("RSI"))
        atr = indicators.get("atr", indicators.get("ATR"))
        bb_width = indicators.get("bb_width")

        current_price = candles[-1].get("close", 0) if candles else market_data.get("price", 0)

        # Build recent price range for range identification
        range_text = ""
        if candles:
            recent = candles[-60:]
            highs = [c.get("high", 0) for c in recent]
            lows = [c.get("low", 0) for c in recent]
            closes = [c.get("close", 0) for c in recent]
            range_high = max(highs)
            range_low = min(lows)
            range_width = range_high - range_low
            pct_from_low = (current_price - range_low) / range_width * 100 if range_width > 0 else 50
            range_text = (
                f"60-bar Range: High={range_high:.4f} Low={range_low:.4f} "
                f"Width={range_width:.4f} ({(range_width/current_price*100):.2f}%)\n"
                f"Price position in range: {pct_from_low:.1f}% from low"
            )

        # Get market structure agent context
        regime = "unknown"
        if "market_structure" in analysis_reports:
            regime = analysis_reports["market_structure"].metadata.get("regime", "unknown")

        market_summary = self._format_market_data(market_data)

        user_message = f"""RANGE ANALYSIS REQUEST
Symbol: {symbol}
Current Price: {current_price}
Timestamp: {self._now().isoformat()}
Market Regime (from structure agent): {regime}

=== RANGE INDICATORS ===
  ADX: {adx if adx is not None else "N/A"} (< 20 = range environment)
  RSI: {rsi if rsi is not None else "N/A"}
  ATR: {atr if atr is not None else "N/A"}
  BB Width: {bb_width if bb_width is not None else "N/A"}

=== PRICE RANGE DATA ===
{range_text if range_text else "Insufficient candle data"}

=== FULL MARKET DATA ===
{market_summary}

=== TASK ===
Analyze range trading opportunities for {symbol}:
1. Identify if a valid trading range exists with clear S/R boundaries
2. Score the range quality (1-10) based on touches and clarity
3. Determine price position within the range (at support, at resistance, mid-range)
4. Assess the entry setup: are reversal candles forming at boundaries?
5. Check for breakout warning signals (rising volume, ADX rising, BB expanding)
6. Calculate the risk-reward for a range trade entry
7. Flag if the range is mature (5+ touches of boundary) and near-breakdown risk

Return your Range Specialist AgentReport JSON.
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
                reasoning=f"Range analysis failed: {exc}",
                supporting_evidence=[],
                contradicting_evidence=["Analysis error"],
                timestamp=self._now(),
            )
