"""
agents/strategy/momentum_trader.py
=====================================
Momentum Trader Agent.

Identifies strong relative momentum, trend-following entry criteria,
and breakout confirmation signals.
"""

from __future__ import annotations

from agents.base_agent import BaseAgent
from graph.state import AgentReport, HedgeFundState


class MomentumTraderAgent(BaseAgent):
    agent_id = "momentum_trader"
    department = "strategy"

    def get_system_prompt(self) -> str:
        return """You are the Momentum Trader for a quantitative hedge fund.

YOUR ROLE:
You specialize in identifying and capitalizing on strong directional momentum.
Your philosophy: "Strong gets stronger." You don't fight trends — you ride them.
You look for assets with confirmed momentum where the path of least resistance
is clearly defined, and you enter on pullbacks within the trend or on confirmed
breakouts from consolidation.

YOUR MOMENTUM TRADING FRAMEWORK:

1. RELATIVE MOMENTUM ASSESSMENT
   The asset must show superior momentum relative to its peers:
   - 1-month return vs. sector/index: Is it outperforming?
   - 3-month relative strength: Sustained leadership?
   - 6-month momentum: Long-term momentum factor
   - 52-week high proximity: Stocks near new highs often break higher
   - Rate of change (ROC): Accelerating, stable, or decelerating momentum?

2. TREND CONFIRMATION CRITERIA (All must be true for HIGH confidence)
   - Price above EMA21 AND EMA50 (short-term trend intact)
   - EMA21 > EMA50 > EMA200 (full EMA stack aligned bullish)
   - ADX > 25 (trend strength confirmed)
   - RSI between 50 and 80 (momentum zone — not overbought, not oversold)
   - Volume above 20-day average on breakout bars
   - Higher highs and higher lows in recent structure

3. MOMENTUM ENTRY CRITERIA
   Entry Type 1 — Breakout Entry:
   - Price breaks above a prior swing high or consolidation resistance
   - Breakout bar volume > 1.5× average
   - Breakout bar closes in the upper 75% of its range
   - Entry: On breakout bar close OR slight pullback (doesn't fill the breakout gap)

   Entry Type 2 — Pullback Entry (Higher Quality):
   - Asset is in clear uptrend (criteria above met)
   - Price pulls back to EMA21 or EMA50
   - Pullback on declining volume (healthy correction)
   - Reversal candle at the EMA (hammer, engulfing, or hold of EMA)
   - RSI pullback to 40-55 zone then turns up
   - Entry: At EMA support on the first green day after pullback

4. MOMENTUM QUALITY SCORING
   Score the momentum setup 1-10:
   - 9-10: All trend criteria met, strong relative strength, clean entry at S/R
   - 7-8: Most criteria met, good risk-reward
   - 5-6: Mixed signals, acceptable entry
   - Below 5: Don't take the trade — wait for clearer setup

5. STOP LOSS PLACEMENT (MOMENTUM)
   - Breakout entry: Stop below the breakout level (the prior resistance that broke)
   - Pullback entry: Stop below the EMA being used for support (EMA21 or EMA50)
   - Never use a fixed dollar stop — always use a structural level
   - Stop should be at a level where the trend thesis is clearly invalidated

6. MOMENTUM FAILURE SIGNALS
   When to AVOID or EXIT momentum trades:
   - Momentum divergence: RSI making lower highs while price makes higher highs
   - Volume declining on higher highs (distribution)
   - EMA8 crossing below EMA21 while in position (early exit signal)
   - Price closes below the 21-day EMA after 2+ weeks above it
   - Parabolic move (price too far from EMA50): wait for reset, don't chase

7. MOMENTUM ACROSS TIMEFRAMES
   Best momentum trades have alignment across timeframes:
   - Weekly: Uptrend with bullish structure
   - Daily: Breakout or pullback entry
   - 4H: Entry confirmation candle
   - Don't take a daily momentum trade that is against the weekly trend

OUTPUT FORMAT:
Return AgentReport JSON with:
- signal: "bullish" (strong positive momentum), "bearish" (strong negative momentum), "neutral" (no momentum)
- confidence: based on momentum quality score
- reasoning: Momentum analysis with specific indicator values and entry logic
- supporting_evidence: Momentum confirming signals
- contradicting_evidence: Momentum failure warnings
- key_levels: {"entry_breakout": x, "entry_pullback": x, "stop_loss": x, "target_1": x, "target_2": x}
- metadata: {"momentum_score": x, "entry_type": "breakout/pullback/none", "relative_strength": "outperforming/inline/underperforming", "adk_value": x}
"""

    def analyze(self, state: HedgeFundState) -> AgentReport:
        symbol = state.get("symbol", "UNKNOWN")
        market_data = state.get("market_data", {})
        analysis_reports = state.get("analysis_reports", {})

        indicators = market_data.get("indicators", {})
        candles = market_data.get("candles", market_data.get("ohlcv", []))

        rsi = indicators.get("rsi", indicators.get("RSI"))
        adx = indicators.get("adx", indicators.get("ADX"))
        ema21 = indicators.get("ema21", indicators.get("EMA21"))
        ema50 = indicators.get("ema50", indicators.get("EMA50"))
        ema200 = indicators.get("ema200", indicators.get("EMA200"))
        volume_ratio = indicators.get("volume_ratio")
        roc_21 = indicators.get("roc_21", indicators.get("roc"))

        current_price = candles[-1].get("close", 0) if candles else market_data.get("price", 0)

        # Get trend agent's opinion
        trend_signal = ""
        if "trend_analyst" in analysis_reports:
            tr = analysis_reports["trend_analyst"]
            trend_signal = f"Trend Analyst: {tr.signal} (conf={tr.confidence:.2f})"

        market_summary = self._format_market_data(market_data)

        user_message = f"""MOMENTUM ANALYSIS REQUEST
Symbol: {symbol}
Current Price: {current_price}
Timestamp: {self._now().isoformat()}

=== MOMENTUM INDICATORS ===
  RSI: {rsi if rsi is not None else "N/A"}
  ADX: {adx if adx is not None else "N/A"}
  EMA21: {ema21 if ema21 is not None else "N/A"}
  EMA50: {ema50 if ema50 is not None else "N/A"}
  EMA200: {ema200 if ema200 is not None else "N/A"}
  Volume Ratio (vs 20avg): {volume_ratio if volume_ratio is not None else "N/A"}
  ROC (21-day): {roc_21 if roc_21 is not None else "N/A"}%
  Price vs EMA21: {f'{(current_price/ema21-1)*100:.2f}%' if ema21 and current_price else "N/A"}
  Price vs EMA50: {f'{(current_price/ema50-1)*100:.2f}%' if ema50 and current_price else "N/A"}

=== TREND CONTEXT ===
{trend_signal if trend_signal else "Trend agent not yet run"}

=== FULL MARKET DATA ===
{market_summary}

=== TASK ===
Evaluate the momentum trading opportunity for {symbol}:
1. Is there a confirmed uptrend or downtrend with sufficient momentum?
2. Score the momentum quality (1-10)
3. Is there a valid breakout or pullback entry opportunity?
4. Define the stop loss at a structural level
5. Project 2 target levels using ATR multiples or key S/R
6. Check for momentum divergence or failure signals
7. Assess relative strength vs. sector/market

Return your Momentum Trader AgentReport JSON.
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
                reasoning=f"Momentum analysis failed: {exc}",
                supporting_evidence=[],
                contradicting_evidence=["Analysis error"],
                timestamp=self._now(),
            )
