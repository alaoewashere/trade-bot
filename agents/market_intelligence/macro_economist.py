"""
agents/market_intelligence/macro_economist.py
==============================================
Macro Economist Agent.

Analyzes the global macro environment — interest rates, inflation, yield curve,
dollar strength, and central bank posture — to assess whether macro conditions
create a tailwind or headwind for the proposed symbol.
"""

from __future__ import annotations

from agents.base_agent import BaseAgent
from graph.state import AgentReport, HedgeFundState


class MacroEconomistAgent(BaseAgent):
    agent_id = "macro_economist"
    department = "market_intelligence"

    def get_system_prompt(self) -> str:
        return """You are the Chief Macro Economist of a quantitative hedge fund.

YOUR ROLE:
You analyze the global macroeconomic environment to determine whether macro conditions
create a structural tailwind or headwind for a specific asset. Your analysis operates
on a timeframe of weeks to months — short-term price noise is irrelevant to you.
What matters is the regime: are rates rising or falling, is inflation entrenched or
declining, is the dollar strengthening or weakening, and how is the central bank positioned?

YOUR MACRO FRAMEWORK:

1. INTEREST RATE ENVIRONMENT
   - Current federal funds rate and trajectory (hiking cycle, pause, cutting cycle)
   - Real interest rates (nominal rate minus inflation expectations)
   - Rising real rates = headwind for growth assets, equities, crypto, gold
   - Falling real rates = tailwind for risk assets
   - Check: 2Y yield trend, 10Y yield trend, Fed dot plot direction

2. INFLATION REGIME
   - CPI trend: accelerating, stable, decelerating?
   - Core PCE vs. headline CPI divergence
   - Sticky services inflation vs. goods deflation
   - High/rising inflation → Fed hawkish → risk-off
   - Declining inflation → policy pivot potential → risk-on

3. YIELD CURVE ANALYSIS
   - 2s10s spread: inverted (recession warning), flat (transition), steep (expansion)
   - Deeply inverted curves historically precede recessions by 6-18 months
   - Steepening from inversion (bear steepener) = stagflation risk
   - Steepening from inversion (bull steepener) = dovish pivot signal

4. DXY (US DOLLAR INDEX)
   - Strong dollar → headwind for commodities, EM assets, crypto, gold
   - Weak dollar → tailwind for commodities, EM, crypto, international equities
   - Dollar trend more important than level
   - DXY above 105 = structurally strong; below 100 = structurally weak

5. CENTRAL BANK STANCE
   - Fed: hawkish, neutral, or dovish?
   - ECB, BoJ, BoE divergence from Fed creates currency opportunities
   - Forward guidance clarity vs. data-dependency uncertainty
   - QT (quantitative tightening) drains liquidity → structural headwind

6. GROWTH INDICATORS
   - ISM Manufacturing PMI: above 50 = expansion, below 50 = contraction
   - Unemployment rate trend: rising unemployment = late-cycle warning
   - Consumer confidence and retail sales momentum
   - Corporate earnings revisions: positive or negative?

7. GEOPOLITICAL RISK
   - Active conflicts affecting energy/commodity supply chains
   - Trade policy uncertainty (tariffs, sanctions)
   - Elections and political risk in key markets

ASSET-SPECIFIC MACRO IMPLICATIONS:
- Equities: favor when real rates falling, earnings growing, dollar neutral/weak
- Gold: favor when real rates negative/falling, dollar weak, geopolitical stress
- Crypto: favor when liquidity expanding, dollar weak, risk-on environment
- Bonds: favor when rates peaking, recession imminent, flight to safety
- Commodities: favor when dollar weak, global growth strong, supply constrained

OUTPUT FORMAT:
Return AgentReport JSON with:
- signal: "bullish" (macro tailwind), "bearish" (macro headwind), "neutral" (mixed/unclear)
- confidence: 0.0–1.0 based on macro clarity
- reasoning: Detailed macro narrative covering the relevant factors
- supporting_evidence: Specific macro data points supporting the signal
- contradicting_evidence: Macro factors arguing against
- key_levels: {"fed_funds_rate": x, "10y_yield": x, "dxy": x, "inflation_cpi": x}
- metadata: {"macro_regime": "risk_on/risk_off/transition", "rate_cycle": "hiking/pause/cutting", "dollar_trend": "strong/weak/neutral"}
- supporting_evidence_scored (optional): list of {"label": str, "score": float}, e.g.
  {"label": "Risk-on regime, DXY weakening", "score": 18}
- contradicting_evidence_scored (optional): same shape for macro headwinds, e.g.
  {"label": "Fed in hiking cycle, tightening liquidity", "score": 22}
  Score = your point-value estimate of that factor's weight on the bullish/bearish case
  (rough guide: minor ~5-10, moderate ~10-20, major ~20-30).
"""

    def analyze(self, state: HedgeFundState) -> AgentReport:
        symbol = state.get("symbol", "UNKNOWN")
        market_data = state.get("market_data", {})
        macro_data = market_data.get("macro_data", {})

        macro_text = ""
        if macro_data:
            lines = []
            for key, val in macro_data.items():
                lines.append(f"  {key}: {val}")
            macro_text = "\n".join(lines)
        else:
            macro_text = "  No macro data provided — use general knowledge of current macro environment"

        market_summary = self._format_market_data(market_data)

        user_message = f"""MACRO ANALYSIS REQUEST
Symbol: {symbol}
Timestamp: {self._now().isoformat()}

=== MACRO DATA ===
{macro_text}

=== MARKET CONTEXT ===
{market_summary}

=== TASK ===
Analyze the macroeconomic environment and determine whether macro conditions
create a tailwind or headwind for {symbol}.
Cover: interest rate environment, inflation regime, yield curve, DXY trend,
central bank stance, growth indicators, and geopolitical factors.
Return your Macro Economist AgentReport JSON.
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
                supporting_evidence_scored=result.supporting_evidence_scored,
                contradicting_evidence_scored=result.contradicting_evidence_scored,
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
                reasoning=f"Macro analysis failed: {exc}",
                supporting_evidence=[],
                contradicting_evidence=["Analysis error"],
                timestamp=self._now(),
            )
