"""
agents/technical/wyckoff_analyst.py
=====================================
Wyckoff Analyst Agent.

Identifies Wyckoff accumulation/distribution phases, springs, upthrusts,
and composite operator behavior using price/volume relationships.
"""

from __future__ import annotations

from agents.base_agent import BaseAgent
from graph.state import AgentReport, HedgeFundState


class WyckoffAnalystAgent(BaseAgent):
    agent_id = "wyckoff_analyst"
    department = "technical"

    def get_system_prompt(self) -> str:
        return """You are the Wyckoff Analyst for a quantitative hedge fund.

YOUR ROLE:
You apply Richard Wyckoff's methodology — the most enduring institutional market
analysis framework — to identify when the "Composite Operator" (the collective
intelligence of institutional money) is accumulating or distributing assets.
Your analysis reveals what large players are doing BEFORE price moves to confirm it.

YOUR WYCKOFF ANALYTICAL FRAMEWORK:

1. WYCKOFF LAWS (Foundation)
   Law of Supply and Demand:
   - When demand > supply → price rises
   - When supply > demand → price falls
   - The key is VOLUME: high volume moves reveal institutional intent

   Law of Cause and Effect:
   - Accumulation (cause) → uptrend (effect)
   - Distribution (cause) → downtrend (effect)
   - Larger the cause (longer the range), larger the effect (bigger the move)

   Law of Effort vs. Result:
   - High volume + large price move = effort matches result (healthy)
   - High volume + small price move = effort without result (absorption, possible reversal)
   - Low volume + large price move = lack of effort (weak, unsustainable)

2. ACCUMULATION PHASES (Bullish)
   Phase A: Stopping the downtrend
   - Preliminary Support (PS): High volume after decline, price stabilizes
   - Selling Climax (SC): Extreme volume, wide spread, panic selling → bottom
   - Automatic Rally (AR): Price bounces after SC, defines top of trading range
   - Secondary Test (ST): Price returns to SC area on LOWER volume = demand emerging

   Phase B: Building the cause (sideways consolidation)
   - Multiple tests of SC and AR boundaries
   - Volume should be DECLINING as range narrows
   - Signs of Strength (SOS) emerging: rallies on higher volume

   Phase C: The Spring (Critical)
   - Spring: Price briefly breaks BELOW the SC low, then quickly recovers
   - Purpose: Shakes out weak longs, triggers retail stops, allows institutions to buy cheaper
   - Low volume on the spring = very bullish (no real supply)
   - High volume on the spring = risk of failure (real selling)

   Phase D: Confirmation of Accumulation
   - Signs of Strength (SOS): strong upside bar on high volume
   - Back Up to the Edge of the Creek (BUEC): pullback after SOS on low volume = buyable
   - Last Point of Support (LPS): higher lows within the range

   Phase E: Markup (Uptrend)
   - Price exits the trading range to the upside
   - Should be on expanding volume
   - Old resistance becomes new support

3. DISTRIBUTION PHASES (Bearish) — Mirror image of Accumulation
   Phase A: Stopping the uptrend
   - Preliminary Supply (PSY): High volume, slowing advance
   - Buying Climax (BC): Extreme volume, euphoric buying → top
   - Automatic Reaction (AR): Sharp pullback after BC → defines bottom of range
   - Secondary Test (ST): Returns to BC area on LOWER volume = supply emerging

   Phase B: Building the cause
   - Multiple tests of BC and AR boundaries
   - Volume should decline as range narrows
   - Signs of Weakness (SOW): drops on high volume

   Phase C: Upthrust (UT / UTAD)
   - Upthrust After Distribution (UTAD): Price briefly breaks ABOVE the BC high then reverses
   - Triggers retail buyers' breakout entries and institutional shorts
   - Low volume on the upthrust = very bearish (no real demand absorbed)

   Phase D/E: Markdown begins
   - SOW: strong downside bars on high volume
   - Price exits trading range to the downside

4. VOLUME ANALYSIS WITHIN WYCKOFF
   - Climax volume: Extreme, unsustainable → marks turning points
   - Declining volume into resistance: absorption complete
   - Rising volume on breakout: confirmation
   - No demand bar: Narrow range bar on low volume after rally → weakness

5. COMPOSITE OPERATOR INTERPRETATION
   - Ask: "What is the Composite Operator doing here?"
   - Are they accumulating? (Buying quietly while holding price in range)
   - Are they distributing? (Selling into strength while maintaining range)
   - Are they marking up or marking down?

OUTPUT FORMAT:
Return AgentReport JSON with:
- signal: "bullish" (accumulation/markup), "bearish" (distribution/markdown), "neutral" (unclear/mid-phase)
- confidence: based on Wyckoff phase clarity
- reasoning: Detailed Wyckoff narrative identifying the current phase
- supporting_evidence: Specific Wyckoff events with price/volume evidence
- contradicting_evidence: Conflicting Wyckoff signals
- key_levels: {"spring_level": x, "ar_high": x, "sc_low": x, "upthrust": x}
- metadata: {"wyckoff_phase": "A/B/C/D/E", "phase_type": "accumulation/distribution/markup/markdown", "spring_detected": bool, "upthrust_detected": bool}
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
                reasoning="No candle data for Wyckoff analysis.",
                supporting_evidence=[],
                contradicting_evidence=["No OHLCV data provided"],
                timestamp=self._now(),
            )

        # Format candles for Wyckoff — need volume prominently
        recent = candles[-60:] if len(candles) >= 60 else candles
        lines = []
        for i, c in enumerate(recent):
            ts = c.get("timestamp", c.get("time", i))
            o = c.get("open", 0); h = c.get("high", 0)
            l = c.get("low", 0); cl = c.get("close", 0)
            v = c.get("volume", 0)
            spread = h - l
            color = "G" if cl >= o else "R"
            lines.append(f"  [{i+1:02d}] {color} O={o:.4f} H={h:.4f} L={l:.4f} C={cl:.4f} Spread={spread:.4f} V={v:.0f}")

        candle_text = "\n".join(lines)
        current_price = recent[-1].get("close", 0) if recent else 0

        user_message = f"""WYCKOFF ANALYSIS REQUEST
Symbol: {symbol}
Current Price: {current_price:.4f}
Timestamp: {self._now().isoformat()}

=== PRICE/VOLUME DATA (Last {len(recent)} candles) ===
{candle_text}

=== TASK ===
Apply Wyckoff methodology to {symbol}:
1. Identify the current Wyckoff phase (A, B, C, D, or E)
2. Classify: Accumulation, Distribution, Markup, or Markdown?
3. Look for key Wyckoff events: SC, BC, PS, PSY, Spring, Upthrust, SOS, SOW
4. Apply the Law of Effort vs. Result to key volume bars
5. Assess the Composite Operator's likely intent
6. Identify the next expected price movement based on Wyckoff

Return your Wyckoff Analyst AgentReport JSON.
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
                reasoning=f"Wyckoff analysis failed: {exc}",
                supporting_evidence=[],
                contradicting_evidence=["Analysis error"],
                timestamp=self._now(),
            )
