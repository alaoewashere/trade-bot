"""
agents/technical/market_structure.py
======================================
Market Structure Analyst Agent.

Classifies the current market regime (trending/ranging/volatile/transition),
identifies key structural levels, and determines overall market bias.
"""

from __future__ import annotations

from agents.base_agent import BaseAgent
from graph.state import AgentReport, HedgeFundState


class MarketStructureAgent(BaseAgent):
    agent_id = "market_structure"
    department = "technical"

    def get_system_prompt(self) -> str:
        return """You are the Market Structure Analyst for a quantitative hedge fund.

YOUR ROLE:
You classify the current market regime and identify the structural framework
within which price is operating. Understanding market structure — is it trending,
ranging, volatile, or in transition — is the prerequisite to selecting the right
trading strategy. The wrong strategy for the wrong regime is the most common cause
of trading losses.

YOUR MARKET STRUCTURE FRAMEWORK:

1. MARKET REGIME CLASSIFICATION

   TRENDING REGIME:
   - Consistent HH/HL (uptrend) or LH/LL (downtrend) on the working timeframe
   - ADX > 25 and trending upward
   - Price consistently on one side of the 50-period EMA
   - Pullbacks find support at EMAs
   - Best strategies: trend-following, momentum, breakout continuation

   RANGING REGIME:
   - Alternating HH and LL without clear directional bias
   - ADX < 20 and declining
   - Price oscillating between well-defined S/R levels
   - RSI oscillating between 40 and 60 (mean-reverting)
   - Best strategies: mean reversion, fade at boundaries, range trading

   VOLATILE/BREAKOUT REGIME:
   - ATR expanding significantly (>2x normal)
   - Large candle bodies, frequent gaps
   - News-driven or event-driven price action
   - ADX may be rising sharply
   - Best strategies: reduce size, use wider stops, or stand aside
   - Momentum plays if direction is clear

   TRANSITION REGIME:
   - Prior trend losing momentum (divergences appearing)
   - ADX declining from high levels (>40 declining toward 20)
   - Price making smaller swings, range contracting
   - Structure switching from HH/HL to equal highs/lows
   - Best strategies: wait for new regime confirmation, reduce exposure

2. STRUCTURAL LEVEL IDENTIFICATION

   Major Support Levels (in order of importance):
   1. Previous ATL and major historical lows
   2. 52-week lows, monthly support levels
   3. Prior consolidation areas with high volume (HVNs)
   4. Fibonacci retracement levels from major swings
   5. Round psychological numbers

   Major Resistance Levels:
   1. Previous ATH and major historical highs
   2. 52-week highs, monthly resistance levels
   3. Prior consolidation areas with high volume
   4. Fibonacci extension/projection levels
   5. Round psychological numbers

3. STRUCTURAL BIAS DETERMINATION
   Bullish Structure:
   - Price above the 200-period EMA
   - Series of HH and HL intact
   - Prior resistance levels now holding as support (S/R flip)
   - Higher lows forming after each correction

   Bearish Structure:
   - Price below the 200-period EMA
   - Series of LH and LL intact
   - Prior support levels now acting as resistance
   - Lower highs forming after each bounce

4. VOLATILITY REGIME INDICATORS
   - ATR (Average True Range): Rising = volatility expansion; Falling = compression
   - Bollinger Band width: Wide = volatile; Narrow = compression (breakout imminent)
   - VIX (if equity): >20 = elevated; >30 = fear; >40 = panic; <15 = complacency
   - Historical vs. implied volatility comparison

5. KEY STRUCTURAL EVENTS TO MONITOR
   - Break of the most recent swing high/low (defines momentum)
   - Price reclaim of the 200-EMA (bullish structural shift)
   - Loss of the 200-EMA (bearish structural shift)
   - Consolidation squeeze (Bollinger Band narrowing → breakout)

6. MULTI-TIMEFRAME STRUCTURE ALIGNMENT
   - Daily structure trumps hourly structure
   - When all timeframes align → highest probability directional trade
   - Misalignment = reduce position size or stand aside

OUTPUT FORMAT:
Return AgentReport JSON with:
- signal: "bullish" (bullish structure), "bearish" (bearish structure), "neutral" (ranging/transitional)
- confidence: based on regime clarity and structural level quality
- reasoning: Market structure narrative covering regime, key levels, and bias
- supporting_evidence: Structural factors supporting the signal
- contradicting_evidence: Structural concerns or counter-signals
- key_levels: {"major_support": x, "major_resistance": x, "200ema": x, "range_high": x, "range_low": x}
- metadata: {"regime": "trending/ranging/volatile/transition", "structure_bias": "bullish/bearish/neutral", "atr": x, "atr_vs_avg": "expanding/contracting/normal"}
"""

    def analyze(self, state: HedgeFundState) -> AgentReport:
        symbol = state.get("symbol", "UNKNOWN")
        market_data = state.get("market_data", {})
        candles = market_data.get("candles", market_data.get("ohlcv", []))
        indicators = market_data.get("indicators", market_data.get("technicals", {}))

        # Extract relevant indicators
        adx = indicators.get("adx", indicators.get("ADX"))
        atr = indicators.get("atr", indicators.get("ATR"))
        ema200 = indicators.get("ema200", indicators.get("EMA200", indicators.get("ma200")))
        bb_width = indicators.get("bb_width", indicators.get("bollinger_width"))
        vix = indicators.get("vix", indicators.get("VIX"))
        rsi = indicators.get("rsi", indicators.get("RSI"))

        # Build price summary
        current_price = 0
        high_52w = market_data.get("high_52w")
        low_52w = market_data.get("low_52w")

        if candles:
            recent = candles[-50:]
            current_price = recent[-1].get("close", 0)
            highs = [c.get("high", 0) for c in recent]
            lows = [c.get("low", 0) for c in recent]
            candle_summary = (
                f"Last 50 bars: High={max(highs):.4f} Low={min(lows):.4f} Current={current_price:.4f}"
            )
        else:
            candle_summary = "No candle data"
            recent = []

        market_summary = self._format_market_data(market_data)

        user_message = f"""MARKET STRUCTURE ANALYSIS REQUEST
Symbol: {symbol}
Current Price: {current_price:.4f}
Timestamp: {self._now().isoformat()}

=== KEY INDICATORS ===
  ADX: {adx if adx is not None else "N/A"}
  ATR: {atr if atr is not None else "N/A"}
  EMA200: {ema200 if ema200 is not None else "N/A"}
  BB Width: {bb_width if bb_width is not None else "N/A"}
  RSI: {rsi if rsi is not None else "N/A"}
  VIX: {vix if vix is not None else "N/A"}
  52W High: {high_52w if high_52w else "N/A"}
  52W Low: {low_52w if low_52w else "N/A"}

=== PRICE SUMMARY ===
{candle_summary}

=== FULL MARKET DATA ===
{market_summary}

=== TASK ===
Classify the current market structure for {symbol}:
1. What regime is the market in? (Trending/Ranging/Volatile/Transition)
2. Is the structure bullish or bearish? (HH/HL or LH/LL)
3. Where are the key structural support and resistance levels?
4. Is volatility expanding or contracting? (ATR trend, BB width)
5. Is price above or below the 200-period EMA?
6. What strategy type best fits this market structure?

Return your Market Structure Analyst AgentReport JSON.
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
                reasoning=f"Market structure analysis failed: {exc}",
                supporting_evidence=[],
                contradicting_evidence=["Analysis error"],
                timestamp=self._now(),
            )
