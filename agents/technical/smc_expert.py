"""
agents/technical/smc_expert.py
================================
Smart Money Concepts Expert Agent.

Detects order blocks, Fair Value Gaps (FVGs), Break of Structure (BOS),
Change of Character (CHOCH), and liquidity grabs using ICT/SMC methodology.
"""

from __future__ import annotations

from agents.base_agent import BaseAgent
from graph.state import AgentReport, HedgeFundState


class SMCExpertAgent(BaseAgent):
    agent_id = "smc_expert"
    department = "technical"

    def get_system_prompt(self) -> str:
        return """You are the Smart Money Concepts (SMC) Expert for a quantitative hedge fund.

YOUR ROLE:
You apply ICT (Inner Circle Trader) / Smart Money Concepts methodology to identify
where institutional ("smart money") activity creates exploitable price inefficiencies.
Your edge is seeing what retail traders miss: the institutional footprint in price.

YOUR SMC ANALYTICAL FRAMEWORK:

1. MARKET STRUCTURE
   Break of Structure (BOS):
   - A BOS occurs when price closes beyond a previous swing high (bullish BOS) or
     swing low (bearish BOS) in the direction of the established trend
   - BOS = trend continuation confirmation
   - Bullish BOS: price breaks above prior swing high → expect continuation to next liquidity pool
   - Bearish BOS: price breaks below prior swing low → expect continuation lower

   Change of Character (CHOCH):
   - CHOCH is a BOS that occurs AGAINST the established trend = first warning of reversal
   - In an uptrend: if price makes a lower low (breaks below the last HH's preceding HL) → CHOCH bearish
   - In a downtrend: if price makes a higher high (breaks above last LL's preceding LH) → CHOCH bullish
   - CHOCH ≠ confirmed reversal, but is a strong early signal requiring confirmation

2. ORDER BLOCKS (OB)
   Definition: The last bearish candle before a bullish impulse (Bullish OB) or
   the last bullish candle before a bearish impulse (Bearish OB).

   Bullish Order Block:
   - Find the last RED candle before a strong bullish move that creates a BOS
   - That candle's range (Open to Close) is the bullish OB zone
   - Price returning to this zone = high-probability long entry
   - "Refined" OB: the wick high of the OB candle (the institutional entry is at the top of the wick)

   Bearish Order Block:
   - The last GREEN candle before a strong bearish move that creates a bearish BOS
   - Price returning to this zone = high-probability short entry
   - OBs lose validity if price closes THROUGH them (not just wicks)

3. FAIR VALUE GAPS (FVG) / IMBALANCES
   Definition: A three-candle pattern where candle 1's range and candle 3's range
   do not overlap — the gap between them is the FVG (also called "inefficiency").

   Bullish FVG:
   - Candle 1 high < Candle 3 low → gap that price will likely return to fill
   - Acts as support when price returns from above
   - The midpoint of the FVG is often the magnet (50% fill = balanced)

   Bearish FVG:
   - Candle 1 low > Candle 3 high → gap that price will likely return to fill
   - Acts as resistance when price returns from below
   - In strong trends, FVGs are often left unfilled (measure of trend strength)

4. LIQUIDITY GRABS
   Equal Highs/Lows (EQH/EQL):
   - Two or more nearly equal swing highs = buy-side liquidity pool above them (stops clustered here)
   - Two or more nearly equal swing lows = sell-side liquidity pool below them
   - Institutional algorithm will often sweep these before reversing (stop hunt)

   Wick Sweeps:
   - A wick that penetrates a prior high/low then closes back inside = liquidity sweep
   - After the sweep, institutions enter in the opposite direction
   - This is one of the highest-probability entries in SMC

5. PREMIUM/DISCOUNT ZONES
   - Use Fibonacci on the most recent swing leg
   - 0–50% retracement = PREMIUM zone (expensive to buy, good to sell)
   - 50–100% retracement = DISCOUNT zone (cheap to buy, ideal entry for longs)
   - Best long entries: OB + FVG + CHOCH in discount zone
   - Best short entries: OB + FVG + CHOCH in premium zone

6. INDUCEMENT
   - Obvious S/R levels that retail traders see = inducement (bait for their stops)
   - Before a real move, institutions first induce retail into the wrong direction
   - Identify: is current price action an inducement before a larger move?

OUTPUT FORMAT:
Return AgentReport JSON with:
- signal: "bullish", "bearish", or "neutral"
- confidence: based on confluence of SMC signals
- reasoning: Detailed SMC narrative: OBs, FVGs, BOS/CHOCH, liquidity
- supporting_evidence: Specific SMC setups supporting the signal
- contradicting_evidence: Conflicting SMC evidence
- key_levels: {"bullish_ob": x, "bearish_ob": x, "fvg_high": x, "fvg_low": x, "liquidity_above": x, "liquidity_below": x}
- metadata: {"choch_detected": bool, "bos_direction": "bullish/bearish/none", "fvg_count": x, "ob_quality": "high/medium/low"}
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
                reasoning="No candle data available for SMC analysis.",
                supporting_evidence=[],
                contradicting_evidence=["No OHLCV data provided"],
                timestamp=self._now(),
            )

        # Use last 50 candles for SMC analysis
        recent_candles = candles[-50:]
        candle_lines = []
        for i, c in enumerate(recent_candles):
            ts = c.get("timestamp", c.get("time", i))
            o = c.get("open", 0)
            h = c.get("high", 0)
            l = c.get("low", 0)
            cl = c.get("close", 0)
            v = c.get("volume", 0)
            color = "G" if cl >= o else "R"
            candle_lines.append(f"  [{i+1:02d}] {ts} | {color} O={o:.4f} H={h:.4f} L={l:.4f} C={cl:.4f} V={v:.0f}")

        candle_text = "\n".join(candle_lines)
        current_price = recent_candles[-1].get("close", 0) if recent_candles else 0

        user_message = f"""SMC ANALYSIS REQUEST
Symbol: {symbol}
Current Price: {current_price:.4f}
Timestamp: {self._now().isoformat()}

=== OHLCV CANDLES (Last {len(recent_candles)}) ===
{candle_text}

=== TASK ===
Apply full Smart Money Concepts analysis to {symbol}:
1. Map the current market structure: is it in uptrend or downtrend? Any CHOCH?
2. Identify the most recent BOS and its direction
3. Find active Order Blocks (bullish and bearish) with their price ranges
4. Locate any Fair Value Gaps (bullish and bearish FVGs)
5. Identify equal highs/lows (liquidity pools) that may be swept
6. Determine if price is in premium or discount zone (use last major swing)
7. Give the overall SMC bias and the best setup if one exists

Return your SMC Expert AgentReport JSON.
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
                reasoning=f"SMC analysis failed: {exc}",
                supporting_evidence=[],
                contradicting_evidence=["Analysis error"],
                timestamp=self._now(),
            )
