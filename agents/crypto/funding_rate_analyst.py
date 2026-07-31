"""
agents/crypto/funding_rate_analyst.py
=======================================
Funding Rate Analyst Agent.

Reads funding rate, open interest, and liquidations from market_data to
identify crowded positions and liquidation cascade risks.
"""

from __future__ import annotations

from agents.base_agent import BaseAgent
from graph.state import AgentReport, HedgeFundState


class FundingRateAnalystAgent(BaseAgent):
    agent_id = "funding_rate_analyst"
    department = "crypto"

    def get_system_prompt(self) -> str:
        return """You are the Funding Rate Analyst for a quantitative hedge fund.

YOUR ROLE:
You analyze the perpetual futures market mechanics for cryptocurrency assets.
Funding rates, open interest, and liquidation data reveal the crowd's positioning —
and when the crowd is too one-sided, the market corrects violently. You identify
when longs or shorts are dangerously crowded and predict liquidation cascades
before they happen.

YOUR FUNDING RATE ANALYTICAL FRAMEWORK:

1. FUNDING RATE MECHANICS
   Definition: In perpetual futures, funding is paid between longs and shorts
   every 8 hours (on most exchanges) to keep the futures price anchored to spot.

   - Positive funding rate: LONGS pay shorts
     → More buyers than sellers in perps → market is net long → CROWDED LONG
     → High positive funding = bearish contrarian signal (too many longs)

   - Negative funding rate: SHORTS pay longs
     → More sellers than buyers in perps → market is net short → CROWDED SHORT
     → High negative funding = bullish contrarian signal (short squeeze potential)

   - Neutral funding (near 0%): Balanced market positioning → no directional bias

   Funding Rate Thresholds (8-hour rate):
   - > +0.10% (annualized: >109%): Extremely crowded long → very bearish
   - +0.05% to +0.10% (annualized 55-109%): Crowded long → bearish lean
   - +0.01% to +0.05%: Slightly elevated → neutral to mildly bearish
   - -0.01% to +0.01%: Balanced → no signal
   - -0.05% to -0.01%: Slightly negative → neutral to mildly bullish
   - < -0.05%: Crowded short → bullish (squeeze potential)

2. FUNDING RATE TREND
   More important than the level is the trend:
   - Funding rising while price rising: Healthy, momentum-confirmed
   - Funding rising while price flat/falling: Crowding at a weak price → dangerous
   - Funding falling from extreme: Deleveraging, potential bottom forming
   - Sudden funding spike: Stop run or liquidation cascade starting

3. OPEN INTEREST ANALYSIS
   Open Interest = Total outstanding long + short contracts (in USD value)

   OI Rising + Price Rising: New money entering, trend confirmed (bullish)
   OI Rising + Price Falling: New shorts being added, trend confirmed (bearish)
   OI Falling + Price Rising: Short covering (bullish but weaker)
   OI Falling + Price Falling: Long liquidation (bearish but may be exhausting)
   OI Spike: Large position opening → potential for large move in either direction

   OI as % of Market Cap:
   - > 20%: Very high leverage, liquidation cascade risk significant
   - 10-20%: Elevated leverage
   - < 10%: Normal, lower cascade risk

4. LIQUIDATION DATA
   Liquidations occur when traders' margin falls below maintenance margin.

   Long liquidations (force-sells):
   - Cascade potential: If price falls → long liquidations → more selling → price falls more
   - Liquidation levels: Price points where large clusters of stops/liquidations exist
   - "Liquidation map" analysis: Identify price levels with highest liquidation density

   Short liquidations (force-buys):
   - Squeeze potential: If price rises → short liquidations → forced buying → price rises more
   - Short squeeze triggers: Large negative funding + OI increase → squeeze risk

   Liquidation Cascade Warning Signs:
   - Large OI + extreme funding + trending market = cascade setup
   - Price approaching major liquidation cluster level
   - Flash spike on high volume followed by reversion = liquidation sweep

5. EXCHANGE-SPECIFIC DYNAMICS
   - Binance: Largest perp market, most influential funding
   - Bybit, OKX: Second tier but significant
   - Cross-exchange funding divergence: Arbitrage closing = directional move
   - Spot vs. perp premium: Persistent perp premium → long crowding

6. FUNDING RATE ARBITRAGE SIGNAL
   - When funding is very positive: Cash-and-carry trade (buy spot, sell perp) is profitable
   - Institutions doing this = sells perpetual pressure → pull price down eventually
   - Saturation of the arb trade = funding normalizes → stop signal for crowding

OUTPUT FORMAT:
Return AgentReport JSON with:
- signal: "bullish" (crowded shorts / negative funding), "bearish" (crowded longs / positive funding), "neutral" (balanced)
- confidence: based on extremity of funding and OI
- reasoning: Funding rate narrative covering positioning and cascade risks
- supporting_evidence: Signals supporting the directional call
- contradicting_evidence: Factors reducing signal conviction
- key_levels: {"funding_rate_8h": x, "annualized_funding": x, "open_interest_usd": x, "liquidation_level_long": x, "liquidation_level_short": x}
- metadata: {"funding_regime": "extreme_long/long_crowded/balanced/short_crowded/extreme_short", "cascade_risk": "low/medium/high", "oi_trend": "rising/falling/stable", "squeeze_risk": bool}
"""

    def analyze(self, state: HedgeFundState) -> AgentReport:
        symbol = state.get("symbol", "UNKNOWN")
        market_data = state.get("market_data", {})

        funding_rate = market_data.get("funding_rate")
        open_interest = market_data.get("open_interest")
        liquidations_data = market_data.get("liquidations", {})
        funding_history = market_data.get("funding_history", [])
        oi_history = market_data.get("oi_history", [])

        if funding_rate is None and open_interest is None:
            return AgentReport(
                agent_id=self.agent_id,
                symbol=symbol,
                signal="neutral",
                confidence=0.1,
                reasoning="No funding rate or open interest data available.",
                supporting_evidence=[],
                contradicting_evidence=["No perp/futures data provided"],
                timestamp=self._now(),
            )

        # Compute annualized funding if 8h rate is given
        annualized_funding = None
        if funding_rate is not None:
            annualized_funding = funding_rate * 3 * 365  # 3 times per day × 365 days

        # Format funding history
        funding_hist_text = ""
        if funding_history:
            hist_lines = []
            for i, f in enumerate(funding_history[-24:]):
                if isinstance(f, dict):
                    hist_lines.append(f"  [{i}] {f.get('time','')}: {f.get('rate', f):.6f}")
                else:
                    hist_lines.append(f"  [{i}] {f:.6f}")
            funding_hist_text = "\n".join(hist_lines)

        liq_text = "\n".join(f"  {k}: {v}" for k, v in liquidations_data.items()) if liquidations_data else "  No liquidation data"

        user_message = f"""FUNDING RATE ANALYSIS
Symbol: {symbol}
Timestamp: {self._now().isoformat()}

=== CURRENT METRICS ===
  Funding Rate (8h): {funding_rate if funding_rate is not None else "N/A"} ({f'{funding_rate:.4%}' if funding_rate is not None else 'N/A'})
  Annualized Funding: {f'{annualized_funding:.1%}' if annualized_funding is not None else 'N/A'}
  Open Interest (USD): {f'${open_interest:,.0f}' if open_interest is not None else 'N/A'}

=== FUNDING HISTORY (last 24 periods) ===
{funding_hist_text if funding_hist_text else "  Not available"}

=== LIQUIDATION DATA ===
{liq_text}

=== TASK ===
Analyze the funding rate and derivatives market for {symbol}:
1. Classify the funding regime — is it crowded long, crowded short, or balanced?
2. Assess the annualized rate — is it sustainable or extreme?
3. Analyze OI trend — is it rising or falling? What does this indicate?
4. Evaluate liquidation data — where are the major liquidation clusters?
5. Assess short squeeze or long cascade risk
6. Determine the contrarian directional signal from positioning
7. Is there a cash-and-carry arb saturation phenomenon occurring?

Return your Funding Rate Analyst AgentReport JSON.
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
                reasoning=f"Funding rate analysis failed: {exc}",
                supporting_evidence=[],
                contradicting_evidence=["Analysis error"],
                timestamp=self._now(),
            )
