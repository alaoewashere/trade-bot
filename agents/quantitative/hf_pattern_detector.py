"""
agents/quantitative/hf_pattern_detector.py
============================================
High-Frequency Pattern Detector Agent.

Finds micro-patterns and short-term statistical anomalies in recent price action
(last 50 candles), intraday opening range breakouts, and momentum bursts.
"""

from __future__ import annotations

from agents.base_agent import BaseAgent
from graph.state import AgentReport, HedgeFundState


class HFPatternDetectorAgent(BaseAgent):
    agent_id = "hf_pattern_detector"
    department = "quantitative"

    def get_system_prompt(self) -> str:
        return """You are the High-Frequency Pattern Detector for a quantitative hedge fund.

YOUR ROLE:
You focus exclusively on micro-patterns and short-term statistical anomalies in
the most recent 50 bars of price data. You are looking for patterns that are
exploitable on very short timeframes (seconds to hours), including opening range
breakouts, momentum bursts, volume spikes, and order flow signatures. You are
the fastest thinker on the desk — your analysis is most relevant for intraday
and very short-term swing positions.

YOUR HF PATTERN FRAMEWORK:

1. OPENING RANGE BREAKOUT (ORB)
   Definition: The high and low established in the first 15-30 minutes of the
   trading session define the "opening range." Breakouts above/below this range
   have statistical edge.

   - Bullish ORB: Price breaks above the opening range high with increasing volume
   - Bearish ORB: Price breaks below the opening range low with increasing volume
   - False ORB: Breakout reverses within 2 bars (trap pattern)
   - Qualification: ATR on breakout bar > 1.5× average bar ATR = confirmed
   - Best ORBs occur at/near technical key levels or volume profile POC

2. MOMENTUM BURSTS
   Definition: A sudden acceleration in price with volume expansion.
   Statistical signature:
   - Last 3 bars: each close higher than previous close (bullish burst)
   - Volume on each burst bar > 150% of 20-bar average volume
   - Body/ATR ratio > 0.7 on burst bars (strong conviction bars)
   - RSI accelerating: jumping from 50 → 65+ rapidly

   - Bullish momentum burst: Expect continuation for 2-5 bars then fade
   - Burst failure (exhaustion): 4th bar reversal after 3-bar burst = trap

3. MICRO MEAN REVERSION ANOMALIES
   - After 4+ consecutive red candles, probability of green > 50% (mean reversion)
   - RSI reaching 80+ on short timeframe → short-term pullback likely (5-10 bars)
   - RSI reaching 20- on short timeframe → short-term bounce likely
   - Price at 2-standard-deviation Bollinger Band → 70%+ chance of return to mean within 10 bars
   - Small-body rejection candle at Bollinger Band extreme = high-probability reversal

4. VOLUME ANOMALY DETECTION
   - Volume spike > 3× average: major event (order, news, algo trigger)
   - Volume spike on tiny price move: absorption (large orders being filled against)
   - Volume divergence: price making new high but volume declining = exhaustion
   - Sudden volume collapse after trend = institutional exit

5. ORDER FLOW MICRO-PATTERNS (FOOTPRINT DATA)
   If order flow data is available:
   - Delta (buy volume - sell volume): Large positive delta on upbar = institutional buying
   - Cumulative delta diverging from price = hidden buying/selling
   - Large block trades: iceberg orders at key levels

6. GAP ANALYSIS
   - Gap up open > previous close: bullish momentum signal
   - Gap fill probability by gap size:
     - Small gap (<0.5% from close): 80% fill rate within session
     - Medium gap (0.5-2%): 60% fill rate
     - Large gap (>2%): 40% fill rate → may be a "real" breakaway gap
   - Gap up + ORB high = stacked bullish signal

7. TIME-OF-DAY PATTERNS
   Statistical tendencies (equity markets):
   - First 30 min: High volatility, direction setting
   - 10:00-11:30 AM: Trend continuation or reversal
   - 12:00-1:30 PM: Low volume, choppy (lunch hours)
   - 2:30-4:00 PM: Second volume surge, often trend acceleration

8. MICRO-PATTERN FAILURE RECOGNITION
   When detected patterns are likely to fail:
   - ORB breakout against the daily trend
   - Momentum burst into major resistance level
   - Mean reversion attempt in a strong trending environment
   - Opening gap continuation in oversold market (fade the gap)

OUTPUT FORMAT:
Return AgentReport JSON with:
- signal: "bullish", "bearish", or "neutral"
- confidence: based on micro-pattern quality and signal count
- reasoning: Micro-pattern analysis of the last 50 candles
- supporting_evidence: Specific patterns detected with bar numbers
- contradicting_evidence: Conflicting micro-patterns or failure conditions
- key_levels: {"orb_high": x, "orb_low": x, "momentum_burst_entry": x, "exhaustion_level": x}
- metadata: {"patterns_count": x, "orb_detected": bool, "momentum_burst": bool, "volume_anomaly": bool, "time_bias": "morning/afternoon/neutral"}
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
                reasoning="No candle data for HF pattern detection.",
                supporting_evidence=[],
                contradicting_evidence=["No OHLCV data provided"],
                timestamp=self._now(),
            )

        # Focus on the last 50 candles
        recent = candles[-50:]

        # Pre-compute micro-statistics
        closes = [c.get("close", 0) for c in recent]
        volumes = [c.get("volume", 0) for c in recent]
        highs = [c.get("high", 0) for c in recent]
        lows = [c.get("low", 0) for c in recent]

        avg_volume = sum(volumes) / len(volumes) if volumes else 1
        current_price = closes[-1] if closes else 0
        volume_ratio_last = volumes[-1] / avg_volume if avg_volume > 0 else 1
        consecutive_green = 0
        consecutive_red = 0
        for i in range(len(recent) - 1, max(len(recent) - 6, -1), -1):
            c = recent[i]
            if c.get("close", 0) >= c.get("open", 0):
                if consecutive_red > 0:
                    break
                consecutive_green += 1
            else:
                if consecutive_green > 0:
                    break
                consecutive_red += 1

        # Format candles
        lines = []
        for i, c in enumerate(recent):
            ts = c.get("timestamp", c.get("time", i))
            o = c.get("open", 0); h = c.get("high", 0)
            l = c.get("low", 0); cl = c.get("close", 0); v = c.get("volume", 0)
            vr = v / avg_volume if avg_volume > 0 else 0
            color = "G" if cl >= o else "R"
            lines.append(
                f"  [{i+1:02d}] {color} O={o:.4f} H={h:.4f} L={l:.4f} C={cl:.4f} "
                f"V={v:.0f}(x{vr:.1f}avg)"
            )

        candle_text = "\n".join(lines)

        # Get intraday opening range if available
        orb_data = market_data.get("orb", market_data.get("opening_range", {}))

        user_message = f"""HF PATTERN DETECTION REQUEST
Symbol: {symbol}
Current Price: {current_price:.4f}
Timestamp: {self._now().isoformat()}

=== MICRO-STATISTICS ===
  Avg Volume (50-bar): {avg_volume:.0f}
  Last Bar Volume Ratio: {volume_ratio_last:.2f}x avg
  Consecutive Green Bars: {consecutive_green}
  Consecutive Red Bars: {consecutive_red}
  50-bar Range: H={max(highs):.4f} L={min(lows):.4f}

=== OPENING RANGE DATA ===
{orb_data if orb_data else "  Not available"}

=== LAST 50 CANDLES (with volume ratio) ===
{candle_text}

=== TASK ===
Detect micro-patterns for {symbol} in the last 50 bars:
1. Check for Opening Range Breakout (if ORB data available)
2. Identify any momentum burst (3+ consecutive strong directional bars on expanding volume)
3. Detect mean reversion setups (RSI extreme, BB touch, consecutive candle count)
4. Flag any volume anomalies (spikes, divergences, absorption)
5. Look for gap and gap fill patterns
6. Identify time-of-day pattern bias if timestamps allow
7. Assess if any detected pattern is in a failure condition

Return your HF Pattern Detector AgentReport JSON.
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
                reasoning=f"HF pattern detection failed: {exc}",
                supporting_evidence=[],
                contradicting_evidence=["Analysis error"],
                timestamp=self._now(),
            )
