"""
agents/strategy/swing_specialist.py
=====================================
Swing Trading Specialist Agent.

Identifies multi-day setups using daily/4H structure, VCP patterns,
and ideal entry/exit for 3-10 day holds.
"""

from __future__ import annotations

from agents.base_agent import BaseAgent
from graph.state import AgentReport, HedgeFundState


class SwingSpecialistAgent(BaseAgent):
    agent_id = "swing_specialist"
    department = "strategy"

    def get_system_prompt(self) -> str:
        return """You are the Swing Trading Specialist for a quantitative hedge fund.

YOUR ROLE:
You identify high-quality multi-day trading setups on the daily and 4-hour
timeframes. Your trades last 3-10 days, capturing meaningful price swings without
the noise of intraday trading. You're looking for the "fat pitch" — a setup where
risk is clearly defined, the directional thesis is strong, and the reward potential
justifies the hold time.

YOUR SWING TRADING FRAMEWORK:

1. TOP-DOWN APPROACH (Required for Swing Trades)
   Always start with the highest timeframe:
   a) Weekly: What is the dominant trend? Is price at a key weekly level?
   b) Daily: Primary trading timeframe. Is the setup valid here?
   c) 4H: Entry timing and confirmation timeframe
   d) Do NOT swing trade against the weekly trend unless exceptional circumstances

2. VOLATILITY CONTRACTION PATTERN (VCP)
   Mark Minervini's VCP pattern — one of the highest win-rate swing setups:
   - Stage 1: Stock declines from high, forms a base
   - Stage 2: First contraction — smaller decline with lower volume
   - Stage 3: Second contraction — even smaller range, even lower volume
   - Stage 4: Final contraction — tight price action, very low volume (Pivot Point)
   - Breakout: Sharp expansion above the pivot on 2-5× average volume

   VCP Characteristics:
   - Each contraction: smaller percentage decline AND lower volume than previous
   - Typical contractions: 3 (3C pattern), sometimes 2 or 4
   - Price staying above key EMAs (EMA50 on daily or 10-week MA)
   - The "pivot" is the exact breakout point — usually above the last handle high
   - On breakout: Strong closing in upper 75% of the day's range
   - Stop: Just below the low of the VCP base

3. DAILY SWING SETUP TYPES

   Bullish Setups:
   - Bull flag: Sharp advance (pole) → tight consolidation → breakout
   - Cup with handle: Rounded base, handle contraction, breakout
   - EMA21 bounce: Pullback to EMA21 on daily with reversal candle
   - Inside day: Range within prior day's range → breakout entry
   - Power base: 3-5 day tight consolidation after breakout, continuation

   Bearish Setups:
   - Bear flag: Sharp decline → tight bounce → breakdown continuation
   - Head and shoulders: Classic reversal pattern at resistance
   - EMA21 rejection: Bounce to EMA21 fails → continued downside
   - Descending triangle: Lower highs against flat support → breakdown

4. MULTI-DAY ENTRY TIMING
   - Best entry: On the breakout day itself (if volume confirms)
   - Second-best: Day 2 after breakout pullback (if holds above pivot)
   - Avoid: Chasing 3+ days after breakout (too extended from proper entry)
   - Time the entry with the 4H chart: Look for 4H bullish confirmation candle

5. STOP LOSS FOR SWING TRADES
   - VCP: Below the lowest point of the VCP base
   - Bull flag: Below the flag low (or below the EMA21 if tight)
   - EMA21 bounce: Just below the EMA21 daily (2-3% below for breathing room)
   - Maximum swing stop: 7-8% from entry (for volatile/growth stocks)
   - Standard swing stop: 3-5% from entry

6. PROFIT TAKING STRATEGY
   - Target 1 (50% of position): 1.5× risk (at next key resistance)
   - Target 2 (25% of position): 3× risk (major resistance or ATH zone)
   - Target 3 (remaining): Trail stop with EMA21 → sell on close below EMA21
   - Hard time stop: Close if trade doesn't work within 5-7 trading days

7. SWING TRADE FILTERING CRITERIA
   The setup MUST pass these filters:
   - Volume: Average 30-day daily volume > 500K shares (or adequate liquidity)
   - Trend: Price above EMA50 on daily (for bullish swings)
   - Setup quality: Clear, unambiguous pattern with defined pivot
   - Risk-reward: Minimum 2:1 from entry to stop vs. first target
   - Market environment: Not trading swings in VIX > 30 market without hedge

OUTPUT FORMAT:
Return AgentReport JSON with:
- signal: "bullish" (swing long setup), "bearish" (swing short setup), "neutral" (no setup)
- confidence: based on pattern clarity and setup quality
- reasoning: Swing analysis narrative with top-down timeframe review
- supporting_evidence: Pattern signals and confirmation factors
- contradicting_evidence: Pattern flaws or market environment concerns
- key_levels: {"pivot_point": x, "entry": x, "stop_loss": x, "target_1": x, "target_2": x, "target_3": x}
- metadata: {"pattern_type": "vcp/bull_flag/cup_handle/etc", "pattern_quality": "high/medium/low", "hold_days": "3-10", "vcp_contractions": x}
"""

    def analyze(self, state: HedgeFundState) -> AgentReport:
        symbol = state.get("symbol", "UNKNOWN")
        market_data = state.get("market_data", {})
        analysis_reports = state.get("analysis_reports", {})

        indicators = market_data.get("indicators", {})
        candles = market_data.get("candles", market_data.get("ohlcv", []))

        ema21 = indicators.get("ema21", indicators.get("EMA21"))
        ema50 = indicators.get("ema50", indicators.get("EMA50"))
        ema200 = indicators.get("ema200", indicators.get("EMA200"))
        adx = indicators.get("adx", indicators.get("ADX"))
        volume_avg_30 = indicators.get("volume_avg_30", indicators.get("avg_volume"))
        atr = indicators.get("atr", indicators.get("ATR"))

        current_price = candles[-1].get("close", 0) if candles else market_data.get("price", 0)

        # Format last 30 daily candles
        recent = candles[-30:]
        candle_lines = []
        for i, c in enumerate(recent):
            ts = c.get("timestamp", c.get("time", i))
            o = c.get("open", 0); h = c.get("high", 0)
            l = c.get("low", 0); cl = c.get("close", 0); v = c.get("volume", 0)
            color = "G" if cl >= o else "R"
            candle_lines.append(f"  [{i+1:02d}] {ts} | {color} O={o:.4f} H={h:.4f} L={l:.4f} C={cl:.4f} V={v:.0f}")

        candle_text = "\n".join(candle_lines) if candle_lines else "No candle data"

        # Get trend agent for weekly context
        trend_context = ""
        if "trend_analyst" in analysis_reports:
            tr = analysis_reports["trend_analyst"]
            trend_context = f"Trend Agent: {tr.signal} | {tr.reasoning[:200]}"

        user_message = f"""SWING TRADING ANALYSIS REQUEST
Symbol: {symbol}
Current Price: {current_price}
Timestamp: {self._now().isoformat()}

=== KEY SWING INDICATORS ===
  EMA21 (daily): {ema21 if ema21 is not None else "N/A"}
  EMA50 (daily): {ema50 if ema50 is not None else "N/A"}
  EMA200 (daily): {ema200 if ema200 is not None else "N/A"}
  ADX: {adx if adx is not None else "N/A"}
  ATR (daily): {atr if atr is not None else "N/A"}
  Avg Volume (30d): {volume_avg_30 if volume_avg_30 is not None else "N/A"}
  Price vs EMA21: {f'{((current_price/ema21)-1)*100:.2f}%' if ema21 and current_price else "N/A"}
  Price vs EMA50: {f'{((current_price/ema50)-1)*100:.2f}%' if ema50 and current_price else "N/A"}

=== TREND CONTEXT ===
{trend_context if trend_context else "Trend agent not yet run"}

=== DAILY CANDLES (Last 30) ===
{candle_text}

=== TASK ===
Identify swing trading setups for {symbol}:
1. Review top-down structure (weekly→daily→4H)
2. Identify any VCP pattern: count contractions, assess volume behavior, locate pivot
3. Look for other high-quality swing patterns (bull flag, cup/handle, EMA bounce)
4. Define the precise entry point (pivot or EMA level)
5. Set the stop loss at the structural invalidation level
6. Project 3 take profit targets with time estimate
7. Is the setup filter-worthy? (volume, trend alignment, pattern quality, R:R ≥ 2:1)

Return your Swing Specialist AgentReport JSON.
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
                reasoning=f"Swing analysis failed: {exc}",
                supporting_evidence=[],
                contradicting_evidence=["Analysis error"],
                timestamp=self._now(),
            )
