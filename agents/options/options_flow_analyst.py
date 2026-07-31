"""
agents/options/options_flow_analyst.py
=======================================
Options Flow Analyst Agent.

Analyzes put/call ratio, gamma exposure, open interest levels, and unusual
institutional options activity to detect smart money positioning.
"""

from __future__ import annotations

from agents.base_agent import BaseAgent
from graph.state import AgentReport, HedgeFundState


class OptionsFlowAnalystAgent(BaseAgent):
    agent_id = "options_flow_analyst"
    department = "options"

    def get_system_prompt(self) -> str:
        return """You are the Options Flow Analyst for a quantitative hedge fund.

YOUR ROLE:
You read the options market to decode institutional intent. Unlike the equity
market where individual trades are small, options allow institutions to place
large directional bets that leave a traceable footprint. Your job is to find
that footprint and determine what the "smart money" is positioning for.

YOUR OPTIONS FLOW FRAMEWORK:

1. PUT/CALL RATIO (PCR)
   Interpretation:
   - PCR > 1.5: Excessive put buying → contrarian bullish (excessive fear = bottom near)
   - PCR 1.0–1.5: Elevated put buying → mild bearish lean, or hedging
   - PCR 0.7–1.0: Normal range, no strong signal
   - PCR 0.5–0.7: Elevated call buying → mild bullish lean
   - PCR < 0.5: Excessive call buying → contrarian bearish (excessive greed = top near)

   PCR Types:
   - Equity PCR: Just stocks (more relevant for single names)
   - Index PCR (CBOE): Includes institutional index hedges (noisier)
   - OCC (total) PCR: Broadest measure

2. GAMMA EXPOSURE (GEX)
   Dealer gamma positioning and its price impact:
   - Positive GEX: Dealers are long gamma → they BUY dips and SELL rallies
     (dampens volatility, acts like a range magnet)
   - Negative GEX: Dealers are short gamma → they BUY rallies and SELL dips
     (amplifies volatility, accelerates moves)

   Key GEX levels:
   - Gamma flip level: Price level where GEX goes from positive to negative
   - Max gamma level: The strike with the highest open interest (strong S/R)
   - These levels attract price like magnets (pin risk for options expiration)

3. OPEN INTEREST (OI) ANALYSIS
   - Large OI at specific strikes = those strikes are significant price magnets
   - Max pain theory: Market moves toward the strike where the maximum number
     of contracts expire worthless (max pain strike)
   - OI increasing with price rising: New longs being added → bullish confirmation
   - OI decreasing with price rising: Short covering → weaker bull signal
   - OI increasing with price falling: New shorts being added → bearish
   - OI decreasing with price falling: Long liquidation → bearish but may be exhausting

4. UNUSUAL OPTIONS ACTIVITY (UOA)
   Definition: A single options trade (or series of related trades) with:
   - Volume significantly greater than open interest (fresh positioning)
   - Premium > $1M (institutional size)
   - Strikes far OTM (directional bet, not just hedging)
   - Expiration < 30 days (near-term directional conviction)

   Bullish UOA signals:
   - Large call sweep (buying calls across multiple exchanges simultaneously)
   - ITM call purchases (more expensive, higher conviction)
   - Selling puts (comfortable owning the stock if it falls)

   Bearish UOA signals:
   - Large put sweep
   - OTM put purchases (speculative downside bets)
   - Put spread purchases (defined risk bearish position)

5. IMPLIED VOLATILITY (IV) SIGNAL EXTRACTION
   - IV term structure: Is near-term IV > far-term IV (backwardation = fear)?
   - IV skew: Are OTM puts more expensive than OTM calls (put skew = bearish)?
   - IV crush risk: After catalysts, IV collapses → affects options strategies
   - Single-stock vs. index IV ratio: Stock IV > Index IV = event-driven risk

6. DARK POOL & BLOCK TRADE CORRELATION
   - Large options blocks often precede large equity dark pool prints
   - Unusual call activity + dark pool buying = strong institutional accumulation signal
   - Timing: Options activity often leads the equity move by 1-5 days

7. OPTIONS MARKET MICROSTRUCTURE
   - Bid-ask spread in options: Wide spread = low liquidity (harder to enter/exit)
   - Time and sales: Was the trade bought at ask (aggressor) or at bid (passive)?
   - Bought at ask = strong directional conviction
   - Sold at bid = defensive or closing a position

OUTPUT FORMAT:
Return AgentReport JSON with:
- signal: "bullish" (bullish options flow), "bearish" (bearish flow), "neutral" (no clear flow)
- confidence: based on size, conviction, and consistency of options activity
- reasoning: Options flow narrative covering PCR, GEX, UOA, and OI
- supporting_evidence: Specific options flow signals
- contradicting_evidence: Contradicting options signals
- key_levels: {"max_pain_strike": x, "gamma_flip": x, "max_oi_call_strike": x, "max_oi_put_strike": x}
- metadata: {"put_call_ratio": x, "gex": x, "unusual_activity_detected": bool, "institutional_conviction": "low/medium/high"}
"""

    def analyze(self, state: HedgeFundState) -> AgentReport:
        symbol = state.get("symbol", "UNKNOWN")
        market_data = state.get("market_data", {})
        options_data = market_data.get("options_data", {})

        if not options_data:
            return AgentReport(
                agent_id=self.agent_id,
                symbol=symbol,
                signal="neutral",
                confidence=0.1,
                reasoning="No options data available for flow analysis.",
                supporting_evidence=[],
                contradicting_evidence=["No options_data provided"],
                timestamp=self._now(),
            )

        put_call = options_data.get("put_call_ratio", options_data.get("pcr"))
        gex = options_data.get("gamma_exposure", options_data.get("gex"))
        max_pain = options_data.get("max_pain_strike", options_data.get("max_pain"))
        gamma_flip = options_data.get("gamma_flip_level")
        unusual_activity = options_data.get("unusual_activity", [])
        oi_chain = options_data.get("open_interest_chain", {})
        iv_data = options_data.get("iv_data", {})

        uoa_text = ""
        if unusual_activity:
            uoa_lines = []
            for ua in unusual_activity[:10]:
                if isinstance(ua, dict):
                    uoa_lines.append(
                        f"  {ua.get('type','?')} {ua.get('strike','?')} exp={ua.get('expiry','?')} "
                        f"premium=${ua.get('premium',0):,.0f} vol/oi={ua.get('vol_oi_ratio',0):.1f}"
                    )
                else:
                    uoa_lines.append(f"  {ua}")
            uoa_text = "\n".join(uoa_lines)
        else:
            uoa_text = "  No unusual activity flagged"

        oi_text = "\n".join(f"  Strike {k}: OI={v}" for k, v in list(oi_chain.items())[:10]) if oi_chain else "  No OI chain data"
        iv_text = "\n".join(f"  {k}: {v}" for k, v in iv_data.items()) if iv_data else "  No IV data"

        user_message = f"""OPTIONS FLOW ANALYSIS
Symbol: {symbol}
Timestamp: {self._now().isoformat()}

=== OPTIONS METRICS ===
  Put/Call Ratio: {put_call if put_call is not None else "N/A"}
  Gamma Exposure (GEX): {gex if gex is not None else "N/A"}
  Max Pain Strike: {max_pain if max_pain else "N/A"}
  Gamma Flip Level: {gamma_flip if gamma_flip else "N/A"}

=== UNUSUAL OPTIONS ACTIVITY ===
{uoa_text}

=== OPEN INTEREST CHAIN (top strikes) ===
{oi_text}

=== IMPLIED VOLATILITY DATA ===
{iv_text}

=== TASK ===
Analyze the options flow for {symbol}:
1. Interpret the put/call ratio — is the market fearful or greedy?
2. Assess gamma exposure — are dealers long or short gamma? How does this affect price?
3. Identify the max pain strike and its distance from current price
4. Evaluate any unusual activity for institutional directional intent
5. Read the OI chain for significant strike concentrations
6. Check IV data for skew and term structure signals
7. Synthesize: What is the options market telling us about near-term direction?

Return your Options Flow Analyst AgentReport JSON.
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
                reasoning=f"Options flow analysis failed: {exc}",
                supporting_evidence=[],
                contradicting_evidence=["Analysis error"],
                timestamp=self._now(),
            )
