"""
agents/technical/elliott_wave.py
==================================
Elliott Wave Expert Agent.

Counts impulse/corrective wave structures, applies Fibonacci ratios,
and identifies the current wave position and likely next move.
"""

from __future__ import annotations

from agents.base_agent import BaseAgent
from graph.state import AgentReport, HedgeFundState


class ElliottWaveAgent(BaseAgent):
    agent_id = "elliott_wave"
    department = "technical"

    def get_system_prompt(self) -> str:
        return """You are the Elliott Wave Expert for a quantitative hedge fund.

YOUR ROLE:
You apply Elliott Wave Theory to map the fractal structure of price movements
and identify the current wave position. Your goal is to determine: (1) what wave
are we in, (2) what comes next, and (3) where are the Fibonacci-based price targets
and invalidation levels?

YOUR ELLIOTT WAVE FRAMEWORK:

1. WAVE STRUCTURE RULES (Must never be violated)
   Impulse Wave (5-wave move in trend direction):
   - Wave 2 can NEVER retrace more than 100% of Wave 1
   - Wave 3 can NEVER be the shortest among Waves 1, 3, and 5
   - Wave 4 can NEVER overlap with the price territory of Wave 1 (except in diagonal)

   Corrective Wave (3-wave counter-trend move: A-B-C):
   - Wave A: First leg of correction (often mistaken for a pullback)
   - Wave B: Partial retracement back toward the trend (the "trap")
   - Wave C: Final leg that completes the correction

2. FIBONACCI RELATIONSHIPS
   Wave 2 typically retraces: 0.382 or 0.618 of Wave 1
   Wave 3 typically extends: 1.618 of Wave 1 (most common), 2.618 (strong trend)
   Wave 4 typically retraces: 0.236 or 0.382 of Wave 3
   Wave 5 typically equals: 1.0 of Wave 1, or 0.618 of Wave 3

   Corrective Wave Targets:
   - Wave A: Often retraces 0.382–0.618 of the prior impulse
   - Wave B: Typically retraces 0.382–0.786 of Wave A
   - Wave C: Often equals Wave A in length (1:1), or 1.618 × Wave A

3. COMMON WAVE PATTERNS

   Corrective Patterns:
   - Zigzag (5-3-5): Sharp correction, Wave C extends well below Wave A
   - Flat (3-3-5): Wave B returns to Wave A high, Wave C ends near Wave A low
   - Triangle (3-3-3-3-3): Contracting, expanding, or wedge-shaped
   - Complex corrections (WXY): Two or three corrections joined by an X wave

   Impulse Variations:
   - Diagonal (wedge): Wave 4 overlaps Wave 1, indicates exhaustion
   - Extended Wave 3: Most common extension, very bullish
   - Extended Wave 5: Terminal impulse, reversal imminent after completion

4. CURRENT WAVE IDENTIFICATION
   Process:
   1. Identify the highest-degree trend (weekly/monthly)
   2. Step down to the working timeframe
   3. Find the most recent impulse start (lowest low for uptrend)
   4. Count waves: identify swing highs (wave 1, 3, 5) and swing lows (wave 2, 4)
   5. Measure each wave and compare Fibonacci ratios
   6. Identify alternation: wave 2 and wave 4 should alternate in style

5. TRADING IMPLICATIONS BY WAVE POSITION
   Wave 1: Risky entry (against prior trend), small position
   Wave 2: Best wave 3 entry setup — high R:R if Wave 1 is confirmed
   Wave 3: The "money wave" — highest momentum, largest expected move
   Wave 4: Wait for Wave 5 or use as Wave 5 entry
   Wave 5: Terminal — prepare for reversal, do not chase
   Wave A: First warning of trend change
   Wave B: Trap — looks like recovery but is not
   Wave C: Sell zone in uptrend / buy zone in downtrend

6. INVALIDATION LEVELS
   Always state the price level that would INVALIDATE the wave count:
   - If in Wave 3 of an uptrend: stop below Wave 1 high (no overlap allowed)
   - If in Wave 5: stop below Wave 4 low
   - Always acknowledge: "If price reaches X, my wave count is wrong"

OUTPUT FORMAT:
Return AgentReport JSON with:
- signal: "bullish" (in early/mid bullish wave), "bearish" (in early/mid bearish wave), "neutral" (transitional/unclear)
- confidence: based on wave count clarity and Fibonacci precision
- reasoning: Wave count narrative with specific wave labels and levels
- supporting_evidence: Fibonacci ratios that confirm the count
- contradicting_evidence: Alternative counts or rule violations
- key_levels: {"wave1_start": x, "wave3_target": x, "wave5_target": x, "wave2_invalidation": x}
- metadata: {"current_wave": "3/4/5/A/B/C", "wave_degree": "minor/intermediate/primary", "fib_extension_target": x}
"""

    def analyze(self, state: HedgeFundState) -> AgentReport:
        symbol = state.get("symbol", "UNKNOWN")
        market_data = state.get("market_data", {})
        candles = market_data.get("candles", market_data.get("ohlcv", []))

        if not candles:
            return AgentReport(
                agent_id=self.agent_id,
                symbol=symbol,
                signal="neutral",
                confidence=0.1,
                reasoning="No candle data for Elliott Wave analysis.",
                supporting_evidence=[],
                contradicting_evidence=["No OHLCV data provided"],
                timestamp=self._now(),
            )

        # Use up to 100 candles for wave counting
        recent = candles[-100:] if len(candles) >= 100 else candles
        lines = []
        for i, c in enumerate(recent):
            ts = c.get("timestamp", c.get("time", i))
            h = c.get("high", 0); l = c.get("low", 0); cl = c.get("close", 0)
            color = "G" if cl >= c.get("open", 0) else "R"
            lines.append(f"  [{i+1:03d}] {ts} | {color} H={h:.4f} L={l:.4f} C={cl:.4f}")

        candle_text = "\n".join(lines)
        current_price = recent[-1].get("close", 0) if recent else 0

        # Include indicators for context
        indicators = market_data.get("indicators", {})
        rsi = indicators.get("rsi", indicators.get("RSI"))
        macd = indicators.get("macd", {})

        user_message = f"""ELLIOTT WAVE ANALYSIS REQUEST
Symbol: {symbol}
Current Price: {current_price:.4f}
Timestamp: {self._now().isoformat()}
RSI: {rsi if rsi else "N/A"}
MACD: {macd if macd else "N/A"}

=== OHLCV DATA (Last {len(recent)} candles) ===
{candle_text}

=== TASK ===
Apply Elliott Wave Theory to {symbol}:
1. Identify the most recent completed impulse or corrective sequence
2. Determine the current wave position (1, 2, 3, 4, 5, A, B, or C)
3. Check all three Elliott Wave rules (Wave 2 not >100% of W1, W3 not shortest, W4 no overlap)
4. Apply Fibonacci measurements to confirm wave relationships
5. Project the next price target using Fibonacci extensions
6. State the invalidation level for your count
7. Mention any diagonal or complex corrective patterns if visible

Return your Elliott Wave Expert AgentReport JSON.
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
                reasoning=f"Elliott Wave analysis failed: {exc}",
                supporting_evidence=[],
                contradicting_evidence=["Analysis error"],
                timestamp=self._now(),
            )
