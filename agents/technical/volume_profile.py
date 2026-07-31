"""
agents/technical/volume_profile.py
=====================================
Volume Profile Analyst Agent.

Analyzes price-at-volume distribution to identify POC, Value Area, and
high/low volume nodes as support/resistance levels.
"""

from __future__ import annotations

from agents.base_agent import BaseAgent
from graph.state import AgentReport, HedgeFundState


class VolumeProfileAgent(BaseAgent):
    agent_id = "volume_profile"
    department = "technical"

    def get_system_prompt(self) -> str:
        return """You are the Volume Profile Analyst for a quantitative hedge fund.

YOUR ROLE:
You analyze the distribution of volume across price levels to identify where the
market has agreed on value (high volume nodes) and where price moves quickly
(low volume nodes). Volume profile tells you WHERE transactions happened, not just
when — revealing the market's "structural memory" at key price levels.

YOUR VOLUME PROFILE FRAMEWORK:

1. KEY VOLUME PROFILE CONCEPTS

   Point of Control (POC):
   - The price level with the HIGHEST traded volume in the session/period
   - Price is magnetically attracted to the POC when nearby
   - If price is above POC → bullish structure (market valued higher than POC)
   - If price is below POC → bearish structure (market valued lower than POC)
   - POC acting as support after price breaks above = very bullish confirmation

   Value Area (VA):
   - The price range where 70% of all volume was traded
   - Value Area High (VAH): Upper boundary of the 70% volume zone
   - Value Area Low (VAL): Lower boundary of the 70% volume zone
   - Trading ABOVE VAH = market outside value (potentially overvalued short-term)
   - Trading BELOW VAL = market outside value (potentially undervalued short-term)

2. HIGH VOLUME NODES (HVN)
   - Price levels with significantly above-average volume traded
   - HVNs create strong S/R: price tends to consolidate/chop through them
   - Like a "price magnet" — price returns to HVNs frequently
   - Breakouts through HVNs require significant force (high volume)
   - HVN as support: expect multiple tests, not clean breakdown

3. LOW VOLUME NODES (LVN)
   - Price levels with significantly below-average volume traded
   - LVNs create "air pockets" — price moves quickly through them
   - Price above an LVN: if it breaks down through, expect fast move to next HVN
   - LVNs between POC and current price = price can accelerate quickly
   - Breakouts launching from LVNs = very high velocity moves

4. COMPOSITE VOLUME PROFILE (MULTI-SESSION)
   - Naked POC (nPOC): Prior session's POC that price hasn't returned to test
   - Naked POCs act as magnets — high probability that price will test them
   - Multiple sessions' POCs clustered = very strong S/R confluence zone

5. VOLUME PROFILE PATTERNS

   D-Shape (Normal Distribution):
   - High volume in the middle, tapering on both ends
   - Market in balance/equilibrium → choppy, range-bound behavior likely
   - Breakout above/below the D = directional move coming

   P-Shape (Positive Skew):
   - High volume at the TOP of the profile (heavy upper HVN)
   - Bullish structure: market accepted higher prices
   - Long tail at bottom = distribution completed

   b-Shape (Negative Skew):
   - High volume at the BOTTOM of the profile
   - Bearish structure: market accepted lower prices
   - Long tail at top = buying climax, distribution likely

   Trending Profile (Multiple POCs):
   - POCs stacked progressively higher = healthy uptrend
   - POCs stacked progressively lower = healthy downtrend

6. TRADE SETUPS USING VOLUME PROFILE
   - Buy at VAL when trending up (value area re-entry long)
   - Sell at VAH when trending down (value area re-entry short)
   - Buy breakout above VAH with target to next HVN
   - Fade rejection at HVN in range environment
   - POC reclaim: price retests POC from above and holds = buy setup

7. CONSTRUCTING PROFILE FROM CANDLE DATA
   When formal volume profile data isn't available, estimate by:
   - Grouping price into buckets (e.g., 0.5% width)
   - Assigning each candle's volume to its price range
   - Identifying which price levels had the most cumulative volume

OUTPUT FORMAT:
Return AgentReport JSON with:
- signal: "bullish" (at support/POC, below value area with bullish intent), "bearish" (at resistance/rejected VAH), "neutral"
- confidence: based on volume profile data quality
- reasoning: Volume profile narrative with POC, VAH, VAL, and key nodes
- supporting_evidence: Volume profile levels supporting the signal
- contradicting_evidence: Volume profile levels as obstacles
- key_levels: {"poc": x, "vah": x, "val": x, "nearest_hvn_above": x, "nearest_lvn": x}
- metadata: {"profile_shape": "D/P/b/trending", "price_vs_poc": "above/below/at", "naked_poc": x}
"""

    def analyze(self, state: HedgeFundState) -> AgentReport:
        symbol = state.get("symbol", "UNKNOWN")
        market_data = state.get("market_data", {})
        candles = market_data.get("candles", market_data.get("ohlcv", []))
        volume_profile = market_data.get("volume_profile", {})

        current_price = 0
        if candles:
            current_price = candles[-1].get("close", 0)

        # Format pre-computed volume profile if available
        vp_text = ""
        if volume_profile:
            poc = volume_profile.get("poc")
            vah = volume_profile.get("vah")
            val = volume_profile.get("val")
            hvns = volume_profile.get("hvn_levels", [])
            lvns = volume_profile.get("lvn_levels", [])
            vp_text = (
                f"  POC: {poc}\n  VAH: {vah}\n  VAL: {val}\n"
                f"  HVN Levels: {hvns}\n  LVN Levels: {lvns}"
            )
        else:
            vp_text = "  No pre-computed volume profile — will estimate from OHLCV data"

        # Build raw OHLCV for profile estimation
        candle_lines = []
        recent = candles[-100:] if len(candles) >= 100 else candles
        for i, c in enumerate(recent):
            h = c.get("high", 0); l = c.get("low", 0)
            cl = c.get("close", 0); v = c.get("volume", 0)
            candle_lines.append(f"  [{i+1:03d}] H={h:.4f} L={l:.4f} C={cl:.4f} V={v:.0f}")

        candle_text = "\n".join(candle_lines) if candle_lines else "  No candle data"

        user_message = f"""VOLUME PROFILE ANALYSIS REQUEST
Symbol: {symbol}
Current Price: {current_price:.4f}
Timestamp: {self._now().isoformat()}

=== PRE-COMPUTED VOLUME PROFILE ===
{vp_text}

=== RAW OHLCV DATA (Last {len(recent)} candles — for profile estimation) ===
{candle_text}

=== TASK ===
Analyze the volume profile for {symbol}:
1. Identify the POC, VAH, and VAL (compute from OHLCV if not provided)
2. Locate the highest-volume HVNs (support/resistance zones)
3. Find any LVNs between current price and likely targets
4. Determine the profile shape (D, P, b, or trending)
5. Check for naked POCs from recent sessions
6. Assess: Is price in value, above value, or below value?
7. Give the directional bias based on price vs. value area

Return your Volume Profile Analyst AgentReport JSON.
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
                reasoning=f"Volume profile analysis failed: {exc}",
                supporting_evidence=[],
                contradicting_evidence=["Analysis error"],
                timestamp=self._now(),
            )
