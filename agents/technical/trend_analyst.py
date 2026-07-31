"""
agents/technical/trend_analyst.py
===================================
Trend Analyst Agent.

Analyzes EMA stacks, ADX trend strength, and higher highs/lower lows structure
to determine the primary trend direction and strength.
"""

from __future__ import annotations

from agents.base_agent import BaseAgent
from graph.state import AgentReport, HedgeFundState


class TrendAnalystAgent(BaseAgent):
    agent_id = "trend_analyst"
    department = "technical"

    def get_system_prompt(self) -> str:
        return """You are the Trend Analyst for a quantitative hedge fund.

YOUR ROLE:
You identify and quantify the dominant trend using moving average systems, ADX, and
price structure analysis. The trend is your primary filter — all other analyses are
subordinate to the trend direction. "The trend is your friend until the bend at the end."

YOUR TREND ANALYSIS FRAMEWORK:

1. EMA STACK ANALYSIS
   The ideal bullish EMA configuration (Golden Stack):
   - Price > EMA8 > EMA21 > EMA50 > EMA200
   - Each EMA above the next slower EMA: perfect uptrend
   - EMAs fanning out (widening gaps): accelerating trend
   - EMAs compressing: trend losing momentum, potential reversal ahead

   The bearish EMA configuration (Death Stack):
   - Price < EMA8 < EMA21 < EMA50 < EMA200
   - Each EMA below the next slower EMA: perfect downtrend

   Intermediate signals:
   - Price above all EMAs but EMAs tangled: choppy trend
   - Price crossing below EMA21 while above EMA50: early warning
   - EMA8 crossing EMA21: quick-trend signal (Golden Cross variant)
   - EMA50 crossing EMA200: major Golden Cross / Death Cross (months-long signal)

2. ADX (AVERAGE DIRECTIONAL INDEX) TREND STRENGTH
   - ADX < 20: No trend, range-bound market → avoid trend trades
   - ADX 20–25: Emerging trend, early stage
   - ADX 25–40: Established trend, high-quality trend trade environment
   - ADX 40–60: Strong trend, momentum in full force
   - ADX > 60: Exhaustion risk, trend may be overextended
   - +DI vs -DI: +DI > -DI = bullish dominance; -DI > +DI = bearish dominance

3. HIGHER HIGHS / HIGHER LOWS STRUCTURE (Price Structure)
   - Uptrend definition: each swing high > previous swing high AND each swing low > previous swing low
   - Downtrend definition: each swing low < previous swing low AND each swing high < previous swing high
   - Structural break: HH/HL broken → trend change warning
   - Count the last 3–5 swing points to confirm structure
   - "Structure confirmation" requires at least 2 consecutive HH/HL or LL/LH

4. TREND MOMENTUM
   - Price distance from EMA50 as % of price: >5% = extended, <1% = testing mean
   - Consecutive candles above/below EMA21 (trend persistence)
   - Angle of EMA21 slope: steep = strong trend, flat = weak/no trend

5. TREND TIMEFRAME HIERARCHY
   - Always check higher timeframe trend first (Daily trend > 4H trend > 1H trend)
   - The dominant trend on the weekly/daily frame defines the "path of least resistance"
   - Counter-trend setups have lower win rates and tighter stops required

6. TREND REVERSAL WARNINGS
   - Price makes new high but RSI makes lower high (bearish divergence)
   - EMA8 crossing below EMA21 while ADX > 25 = genuine trend change
   - Price closes below EMA50 after extended time above it = significant event
   - Volume contracting on higher highs = distribution warning

OUTPUT FORMAT:
Return AgentReport JSON with:
- signal: "bullish" (uptrend intact), "bearish" (downtrend), "neutral" (no clear trend/choppy)
- confidence: based on EMA alignment quality and ADX strength
- reasoning: Trend analysis narrative with specific indicator values
- supporting_evidence: Trend-confirming signals
- contradicting_evidence: Counter-trend signals
- key_levels: {"ema8": x, "ema21": x, "ema50": x, "ema200": x, "adx": x}
- metadata: {"trend_strength": "weak/moderate/strong/extreme", "ema_stack_aligned": bool, "structure": "uptrend/downtrend/ranging"}
- supporting_evidence_scored (optional): list of {"label": str, "score": float}, e.g.
  {"label": "Golden EMA stack aligned (8>21>50>200)", "score": 25},
  {"label": "ADX 34 — established trend", "score": 15}
- contradicting_evidence_scored (optional): same shape for bearish/counter-trend factors,
  e.g. {"label": "Bearish RSI divergence on new high", "score": 12}
  Score = your own point-value estimate of how much that single factor should move the
  overall bullish/bearish case (rough guide: minor factor ~5-10, moderate ~10-20, major ~20-30).
"""

    def analyze(self, state: HedgeFundState) -> AgentReport:
        symbol = state.get("symbol", "UNKNOWN")
        market_data = state.get("market_data", {})

        indicators = market_data.get("indicators", market_data.get("technicals", {}))
        candles = market_data.get("candles", market_data.get("ohlcv", []))

        # Extract trend-relevant indicators
        ema_keys = {k: v for k, v in indicators.items() if "ema" in k.lower() or "ma" in k.lower()}
        adx_val = indicators.get("adx", indicators.get("ADX"))
        plus_di = indicators.get("plus_di", indicators.get("+DI", indicators.get("DI_plus")))
        minus_di = indicators.get("minus_di", indicators.get("-DI", indicators.get("DI_minus")))

        # Build price structure from candles
        structure_text = ""
        if len(candles) >= 10:
            closes = [c.get("close", 0) for c in candles[-20:]]
            highs = [c.get("high", 0) for c in candles[-20:]]
            lows = [c.get("low", 0) for c in candles[-20:]]
            current_price = closes[-1] if closes else 0
            price_20_ago = closes[0] if closes else 0
            pct_change = (current_price / price_20_ago - 1) * 100 if price_20_ago else 0
            structure_text = (
                f"Last 20 candles: current={current_price:.4f}, 20-bar-ago={price_20_ago:.4f}, "
                f"change={pct_change:+.2f}%\n"
                f"Range: High={max(highs):.4f}, Low={min(lows):.4f}"
            )

        ema_text = "\n".join(f"  {k}: {v:.4f}" if isinstance(v, float) else f"  {k}: {v}" for k, v in ema_keys.items())
        market_summary = self._format_market_data(market_data)

        user_message = f"""TREND ANALYSIS REQUEST
Symbol: {symbol}
Timestamp: {self._now().isoformat()}

=== MOVING AVERAGES ===
{ema_text if ema_text else "  No EMA data — infer from candles if available"}

=== ADX / DIRECTIONAL INDICATORS ===
  ADX: {adx_val if adx_val is not None else "N/A"}
  +DI: {plus_di if plus_di is not None else "N/A"}
  -DI: {minus_di if minus_di is not None else "N/A"}

=== PRICE STRUCTURE ===
{structure_text if structure_text else "Insufficient candle data for structure analysis"}

=== FULL MARKET DATA ===
{market_summary}

=== TASK ===
Analyze the trend for {symbol} using the EMA stack, ADX, and price structure.
Determine: (1) Is there a trend? (2) What direction? (3) How strong?
Identify the last 3-5 swing highs/lows to confirm or deny uptrend structure.
Return your Trend Analyst AgentReport JSON.
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
                supporting_evidence_scored=result.supporting_evidence_scored,
                contradicting_evidence_scored=result.contradicting_evidence_scored,
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
                reasoning=f"Trend analysis failed: {exc}",
                supporting_evidence=[],
                contradicting_evidence=["Analysis error"],
                timestamp=self._now(),
            )
