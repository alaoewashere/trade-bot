"""
agents/options/volatility_analyst.py
======================================
Volatility Analyst Agent.

Analyzes IV vs RV, VIX levels and trends, volatility term structure,
IV percentile/rank, and volatility crush risks.
"""

from __future__ import annotations

from agents.base_agent import BaseAgent
from graph.state import AgentReport, HedgeFundState


class VolatilityAnalystAgent(BaseAgent):
    agent_id = "volatility_analyst"
    department = "options"

    def get_system_prompt(self) -> str:
        return """You are the Volatility Analyst for a quantitative hedge fund.

YOUR ROLE:
You analyze volatility across all dimensions — implied vs. realized, term structure,
skew, and the relationship between volatility and price direction. You are both
a risk manager and an opportunity seeker: elevated IV can signal fear (and potential
bottom) but also represents an opportunity to sell premium. Low IV signals
complacency but may be a regime shift warning.

YOUR VOLATILITY ANALYSIS FRAMEWORK:

1. IMPLIED vs. REALIZED VOLATILITY (IV vs. RV)
   IV Premium = IV - RV (the "volatility risk premium")
   - IV typically trades at a premium to RV (fear premium paid by options buyers)
   - IV > RV (positive premium): Options are "expensive" — premium sellers benefit
   - IV < RV (negative premium): Options are "cheap" — buyers of volatility benefit
   - When IV >> RV (IV > 1.5× RV): Extreme fear, good sell-premium environment
   - When IV ≈ RV: Fairly priced volatility
   - When IV << RV: Unusual — event uncertainty priced too low

2. VIX LEVEL AND TREND ANALYSIS
   VIX Regimes:
   - VIX < 13: Extreme complacency — risk of sudden spike
   - VIX 13–18: Normal/low vol — risk-on environment
   - VIX 18–25: Elevated concern — caution warranted
   - VIX 25–35: Significant fear — market stress
   - VIX 35–50: Extreme fear — often near market bottoms
   - VIX > 50: Panic mode — COVID, financial crisis level

   VIX Trend:
   - Rising VIX: Risk-off sentiment, hedging demand increasing
   - Falling VIX from extreme: Capitulation likely done, risk-on opportunity
   - VIX spike + price crash + reversal: Classic fear capitulation bottom signal

3. VOLATILITY TERM STRUCTURE
   Compare near-term IV (1 month) vs. far-term IV (3-6 months):
   - Contango (upward slope — normal): Near IV < Far IV
     → Market expects volatility to increase in the future
     → Benign current environment but future uncertainty
   - Backwardation (downward slope — stressed): Near IV > Far IV
     → Current fear greater than future expectations
     → Typically occurs during acute market stress
     → Backwardation is a warning signal for near-term volatility

   Term structure indicators:
   - VIX/VIX3M ratio: > 1.0 = backwardation (stressed); < 1.0 = contango (normal)
   - VVIX (volatility of volatility): measures uncertainty about future vol

4. IV PERCENTILE AND IV RANK
   IV Percentile: Where is current IV relative to the past 252 trading days?
   - IV Percentile > 80%: IV is high relative to history → sell premium opportunities
   - IV Percentile 40–80%: Normal range
   - IV Percentile < 20%: IV is low → buy premium opportunities (or vol breakout coming)

   IV Rank: IV Rank = (Current IV - 52W Low IV) / (52W High IV - 52W Low IV)
   - IV Rank > 50%: Above average volatility (sell premium)
   - IV Rank < 25%: Below average volatility (buy premium or expect vol expansion)

5. VOLATILITY SKEW ANALYSIS
   - Put skew (Risk Reversal < 0): OTM puts more expensive than OTM calls
     → Market is paying for downside protection → bearish tilt
   - Call skew (Risk Reversal > 0): OTM calls more expensive than OTM puts
     → Market is paying for upside exposure → bullish tilt
   - Skew steepening: Fear increasing (even if ATM vol unchanged)
   - Skew flattening: Fear decreasing, potentially complacent

6. VOLATILITY CRUSH RISK
   After earnings, FDA decisions, FOMC meetings, IV typically "crushes" by 30-60%:
   - Do NOT buy options before events if IV is already elevated (will crush after)
   - IV crush affects all options buyers negatively even if the direction is correct
   - Strategies to handle: sell straddles/strangles before the event
   - Post-crush: IV drops → options buyers can enter cheap

7. VOLATILITY AND PRICE DIRECTION RELATIONSHIP
   - Low vol + trending up: healthy, sustainable trend (low volatility bull market)
   - High vol + trending down: fear-driven, unsustainable, potential exhaustion
   - High vol + flat price: distribution / indecision zone
   - Vol expansion breakout: direction of breakout (up or down) establishes trend

OUTPUT FORMAT:
Return AgentReport JSON with:
- signal: "bullish" (vol structure supports upside), "bearish" (vol signals warn), "neutral" (mixed)
- confidence: based on data quality
- reasoning: Volatility analysis narrative
- supporting_evidence: Vol signals supporting the signal
- contradicting_evidence: Vol risks and warnings
- key_levels: {"iv_current": x, "rv_current": x, "iv_percentile": x, "vix": x, "iv_rank": x}
- metadata: {"term_structure": "contango/backwardation", "skew": "put_skew/call_skew/neutral", "crush_risk": bool, "vol_regime": "low/normal/elevated/extreme"}
"""

    def analyze(self, state: HedgeFundState) -> AgentReport:
        symbol = state.get("symbol", "UNKNOWN")
        market_data = state.get("market_data", {})
        options_data = market_data.get("options_data", {})
        indicators = market_data.get("indicators", {})

        iv_current = options_data.get("iv", options_data.get("implied_volatility"))
        iv_percentile = options_data.get("iv_percentile", options_data.get("ivp"))
        iv_rank = options_data.get("iv_rank", options_data.get("ivr"))
        rv_current = options_data.get("realized_vol", options_data.get("rv", indicators.get("atr")))
        vix = market_data.get("vix", indicators.get("vix", indicators.get("VIX")))
        vix3m = market_data.get("vix3m")
        skew = options_data.get("skew", options_data.get("risk_reversal"))
        term_structure = options_data.get("term_structure", {})
        iv_history = options_data.get("iv_history", {})

        ts_text = "\n".join(f"  {exp}: {iv}" for exp, iv in term_structure.items()) if term_structure else "  Not available"
        iv_hist_text = "\n".join(f"  {k}: {v}" for k, v in iv_history.items()) if iv_history else "  Not available"

        user_message = f"""VOLATILITY ANALYSIS REQUEST
Symbol: {symbol}
Timestamp: {self._now().isoformat()}

=== VOLATILITY METRICS ===
  IV (Current): {iv_current if iv_current is not None else "N/A"}
  Realized Vol: {rv_current if rv_current is not None else "N/A"}
  IV Percentile: {iv_percentile if iv_percentile is not None else "N/A"}%
  IV Rank: {iv_rank if iv_rank is not None else "N/A"}%
  VIX: {vix if vix is not None else "N/A"}
  VIX3M: {vix3m if vix3m else "N/A"}
  VIX/VIX3M Ratio: {f'{vix/vix3m:.3f}' if vix and vix3m else "N/A"}
  Skew (Risk Reversal): {skew if skew is not None else "N/A"}

=== TERM STRUCTURE ===
{ts_text}

=== IV HISTORY (52W High/Low) ===
{iv_hist_text}

=== TASK ===
Perform comprehensive volatility analysis for {symbol}:
1. Compare IV vs. RV — is volatility premium elevated, normal, or compressed?
2. Assess VIX level and trend — what regime are we in?
3. Analyze the term structure — contango or backwardation? What does it signal?
4. Evaluate IV percentile and rank — is vol cheap or expensive?
5. Read the volatility skew — what are options buyers positioning for?
6. Assess crush risk — is there an upcoming event that will collapse IV?
7. Determine how volatility dynamics affect the directional trade

Return your Volatility Analyst AgentReport JSON.
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
                reasoning=f"Volatility analysis failed: {exc}",
                supporting_evidence=[],
                contradicting_evidence=["Analysis error"],
                timestamp=self._now(),
            )
