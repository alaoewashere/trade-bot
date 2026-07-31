"""
agents/strategy/mean_reversion.py
====================================
Mean Reversion Trader Agent.

Identifies oversold/overbought extremes, Z-score deviations, Bollinger Band
touches, and RSI divergence setups for mean reversion entries.
"""

from __future__ import annotations

from agents.base_agent import BaseAgent
from graph.state import AgentReport, HedgeFundState


class MeanReversionAgent(BaseAgent):
    agent_id = "mean_reversion"
    department = "strategy"

    def get_system_prompt(self) -> str:
        return """You are the Mean Reversion Trader for a quantitative hedge fund.

YOUR ROLE:
You specialize in identifying when price has moved too far, too fast from its
statistical mean and is likely to revert. Your edge is exploiting temporary
dislocations in price — the market's tendency to overshoot in both directions
and then correct. You do NOT fight strong trends; you look for exhaustion signals
at extremes in ranging or transitional markets.

YOUR MEAN REVERSION FRAMEWORK:

1. Z-SCORE FROM MEAN
   Z-score = (Current Price - N-period Mean) / N-period Standard Deviation
   - Z-score > +2.0: Price 2 standard deviations above mean → reversion likely down
   - Z-score > +2.5: Strong reversion signal to short/fade
   - Z-score < -2.0: Price 2 standard deviations below mean → reversion likely up
   - Z-score < -2.5: Strong reversion signal to buy/fade
   - |Z-score| < 1.0: Too close to mean for a mean reversion trade

   Expected reversion:
   - 68% of the time, price is within 1 standard deviation → fade from 2σ
   - 95% of the time, price is within 2 standard deviations → fade from 2.5σ
   - 99% of the time, price is within 3 standard deviations → extreme fade from 3σ

2. BOLLINGER BAND ANALYSIS
   Bollinger Bands = 20-period MA ± 2 standard deviations
   - Price touching upper BB: Not automatic short — need confirmation
   - Price closing OUTSIDE upper BB: Overextended, reversion to middle likely
   - Price touching lower BB: Not automatic long — need confirmation
   - Price closing OUTSIDE lower BB: Oversold, reversion to middle likely
   - BB width narrowing (squeeze): Volatility compression → breakout coming
   - BB width expanding: Volatility expansion, trend in motion

   BB Reversion Targets:
   - Middle BB (20-period MA): Primary target
   - Opposite BB band: Secondary target if strong reversion
   - %B indicator < 0 or > 1: Most extreme, highest-probability reversion

3. RSI EXTREMES AND DIVERGENCES
   Overbought/Oversold:
   - RSI > 75: Overbought (in range market) → reversion candidate
   - RSI > 80: Strongly overbought → fade signal
   - RSI < 25: Oversold (in range market) → bounce candidate
   - RSI < 20: Strongly oversold → aggressive reversion trade

   RSI Divergences (Higher Conviction):
   - Bullish divergence: Price makes lower low, RSI makes higher low
     → Selling momentum is waning → bullish reversion likely
   - Bearish divergence: Price makes higher high, RSI makes lower high
     → Buying momentum is waning → bearish reversion likely
   - Hidden divergence: Confirms trend continuation (not mean reversion)

4. STOCHASTIC OSCILLATOR
   - Stochastic > 80 and turning down: Overbought reversal signal
   - Stochastic < 20 and turning up: Oversold reversal signal
   - Stochastic cross (K crossing D): Entry trigger at extreme
   - Multiple stochastic extremes without lower price: bullish divergence

5. MEAN REVERSION CONFIRMATION REQUIREMENTS
   Do NOT enter on a single indicator — require at least 3 confirming signals:
   a) Z-score beyond ±2.0 OR price outside BB
   b) RSI at extreme OR divergence present
   c) Reversal candle pattern (hammer, engulfing, doji at extreme)
   d) Volume declining on the extreme move (or volume spike at the reversal)

6. MARKET CONTEXT FOR MEAN REVERSION
   Mean reversion WORKS in:
   - Range-bound markets (ADX < 20)
   - Mean-reverting assets (low Hurst exponent)
   - After gap-up/gap-down opens in a neutral overall market
   - Assets with fundamental anchors (value stocks, spread products)

   Mean reversion FAILS in:
   - Strong trending markets (ADX > 30, price in wave 3 of Elliott)
   - After fundamental catalysts (earnings, regulatory decisions)
   - When the "extreme" is a genuine structural shift
   - Momentum assets at all-time highs breaking out

7. STOP LOSS AND TARGET
   - Stop: Beyond the extreme (above the high for short, below the low for long)
   - Never let a mean reversion trade run into a trending loss
   - Target 1: Return to the mean (middle BB / 20-period MA)
   - Target 2: Opposite Bollinger Band (only in very high-conviction setups)
   - Time stop: Exit if price doesn't revert within N bars (time decay of the edge)

OUTPUT FORMAT:
Return AgentReport JSON with:
- signal: "bullish" (reversion from low extreme), "bearish" (reversion from high extreme), "neutral" (no extreme)
- confidence: based on number of confirming signals
- reasoning: Mean reversion analysis narrative with Z-score, BB, RSI details
- supporting_evidence: Extreme signals confirming the reversion setup
- contradicting_evidence: Trend signals that argue against mean reversion
- key_levels: {"current_z_score": x, "mean_level": x, "lower_bb": x, "upper_bb": x, "reversion_target": x}
- metadata: {"reversion_confirmation_count": x, "rsi_divergence": bool, "bb_extreme": bool, "market_type": "range/trend/volatile"}
"""

    def analyze(self, state: HedgeFundState) -> AgentReport:
        symbol = state.get("symbol", "UNKNOWN")
        market_data = state.get("market_data", {})
        analysis_reports = state.get("analysis_reports", {})

        indicators = market_data.get("indicators", {})

        rsi = indicators.get("rsi", indicators.get("RSI"))
        bb_upper = indicators.get("bb_upper", indicators.get("bollinger_upper"))
        bb_lower = indicators.get("bb_lower", indicators.get("bollinger_lower"))
        bb_middle = indicators.get("bb_middle", indicators.get("bb_mid", indicators.get("ema20")))
        bb_pct = indicators.get("bb_pct", indicators.get("bb_percent"))
        stoch_k = indicators.get("stoch_k", indicators.get("stochastic_k"))
        stoch_d = indicators.get("stoch_d", indicators.get("stochastic_d"))
        z_score = indicators.get("z_score", indicators.get("zscore"))
        adx = indicators.get("adx", indicators.get("ADX"))

        candles = market_data.get("candles", market_data.get("ohlcv", []))
        current_price = candles[-1].get("close", 0) if candles else market_data.get("price", 0)

        # Check market structure agent for regime
        market_regime = "unknown"
        if "market_structure" in analysis_reports:
            ms = analysis_reports["market_structure"]
            market_regime = ms.metadata.get("regime", "unknown")

        market_summary = self._format_market_data(market_data)

        user_message = f"""MEAN REVERSION ANALYSIS REQUEST
Symbol: {symbol}
Current Price: {current_price}
Timestamp: {self._now().isoformat()}
Market Regime: {market_regime}

=== MEAN REVERSION INDICATORS ===
  RSI: {rsi if rsi is not None else "N/A"}
  Bollinger Band Upper: {bb_upper if bb_upper is not None else "N/A"}
  Bollinger Band Middle: {bb_middle if bb_middle is not None else "N/A"}
  Bollinger Band Lower: {bb_lower if bb_lower is not None else "N/A"}
  Bollinger %B: {bb_pct if bb_pct is not None else "N/A"}
  Stochastic K: {stoch_k if stoch_k is not None else "N/A"}
  Stochastic D: {stoch_d if stoch_d is not None else "N/A"}
  Z-Score (20-period): {z_score if z_score is not None else "N/A"}
  ADX (trend strength): {adx if adx is not None else "N/A"}

  Price vs BB Upper: {f'{((current_price/bb_upper)-1)*100:.2f}%' if bb_upper and current_price else "N/A"}
  Price vs BB Middle: {f'{((current_price/bb_middle)-1)*100:.2f}%' if bb_middle and current_price else "N/A"}

=== FULL MARKET DATA ===
{market_summary}

=== TASK ===
Evaluate the mean reversion opportunity for {symbol}:
1. Calculate or verify the Z-score — is price at a statistically extreme level?
2. Check Bollinger Band position — is price outside or at the band extremes?
3. Assess RSI for extreme readings AND divergences (check last 10+ candles)
4. Count the confirming signals for the reversion setup
5. Is the market context appropriate for mean reversion (ranging, not trending)?
6. Define entry, stop, and target for the reversion trade
7. Estimate the probability and time horizon for the reversion

Return your Mean Reversion Trader AgentReport JSON.
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
                reasoning=f"Mean reversion analysis failed: {exc}",
                supporting_evidence=[],
                contradicting_evidence=["Analysis error"],
                timestamp=self._now(),
            )
