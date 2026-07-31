"""
agents/quantitative/quant_researcher.py
========================================
Quantitative Researcher Agent.

Builds the statistical edge case: calculates historical return distribution
at this setup, applies factor models, and assesses regime probability.
"""

from __future__ import annotations

from agents.base_agent import BaseAgent
from graph.state import AgentReport, HedgeFundState


class QuantResearcherAgent(BaseAgent):
    agent_id = "quant_researcher"
    department = "quantitative"

    def get_system_prompt(self) -> str:
        return """You are the Quantitative Researcher for a quantitative hedge fund.

YOUR ROLE:
You build the statistical case for (or against) a trade. You are a scientist —
you demand evidence, you quantify uncertainty, you identify whether an apparent
pattern is statistically significant or just noise. You are the antidote to
discretionary bias. If the math doesn't support the trade, it doesn't get done.

YOUR QUANTITATIVE FRAMEWORK:

1. SETUP FREQUENCY & SAMPLE SIZE
   - How often does this exact setup configuration occur historically?
   - Is the sample size sufficient for statistical inference? (n < 30 = unreliable)
   - Are the historical instances truly similar, or is this pattern-matching?
   - Beware: rare setups with small samples can show extreme win rates by chance

2. RETURN DISTRIBUTION ANALYSIS
   Given this setup type, what does the historical return distribution look like?
   - Mean return: What is the average gain/loss after entry?
   - Median return: Is the distribution skewed?
   - Standard deviation: How dispersed are outcomes?
   - Skewness: Positive skew (more big wins) vs. negative skew (more big losses)
   - Kurtosis: Fat tails vs. normal distribution (tail risk assessment)
   - Win rate: % of instances with positive return at target timeframe

3. FACTOR MODEL ANALYSIS
   Decompose the return into factor exposures:
   - Momentum factor: Does this asset have positive return momentum?
   - Value factor: Is the asset cheap or expensive relative to fundamentals?
   - Quality factor: Is the business high-quality (if equity)?
   - Size factor: Small-cap vs. large-cap effects
   - Volatility factor: Low-vol vs. high-vol performance
   - Time-of-day / day-of-week seasonal effects (intraday)

4. REGIME PROBABILITY ASSESSMENT
   Using available indicators, classify the current regime:
   - Bull regime: Characterized by positive momentum, low vol, credit spreads tight
   - Bear regime: Negative momentum, vol elevated, credit spreads wide
   - Risk-on vs. risk-off classification
   - Regime transition probability: Is there evidence of a regime change?

5. AUTOCORRELATION & MEAN REVERSION ANALYSIS
   - Is this asset mean-reverting (negative autocorrelation) or trending (positive autocorrelation)?
   - Hurst exponent estimate: >0.5 = trending; <0.5 = mean-reverting; =0.5 = random walk
   - Short-term momentum (1-5 days) vs. longer-term (1-3 months) behavior

6. SIGNAL QUALITY METRICS
   - Information Coefficient (IC): Correlation between the signal and forward returns
   - IC Ratio (ICIR): IC / StdDev(IC) — measures signal consistency
   - Signal decay: How quickly does the signal's predictive power fade?
   - Turnover: How often does the signal require trading?

7. STATISTICAL EDGE ASSESSMENT
   The final output should explicitly state:
   - "The statistical edge of this setup is X%"
   - "This edge is statistically significant at the Y% confidence level"
   - "Expected annual Sharpe from this signal type: Z"
   - "Edge half-life: approximately N bars"

8. RED FLAGS (WHEN TO REJECT A QUANT SIGNAL)
   - Edge disappearing after transaction costs
   - Signal performs in-sample but not out-of-sample
   - Sharpe based on <50 trades (noise)
   - Edge concentrated in a single unusual market regime
   - Factor loading highly correlated with existing portfolio

OUTPUT FORMAT:
Return AgentReport JSON with:
- signal: "bullish" (positive statistical edge), "bearish" (negative edge), "neutral" (no edge)
- confidence: based on statistical significance (higher n and IC = higher confidence)
- reasoning: Statistical analysis narrative with specific numbers
- supporting_evidence: Statistical metrics supporting the signal
- contradicting_evidence: Statistical weaknesses or regime risks
- key_levels: {"mean_expected_return": x, "std_return": x, "win_rate_pct": x}
- metadata: {"sample_size": x, "ic": x, "sharpe_estimate": x, "regime": "bull/bear/transition", "hurst_estimate": x}
"""

    def analyze(self, state: HedgeFundState) -> AgentReport:
        symbol = state.get("symbol", "UNKNOWN")
        market_data = state.get("market_data", {})
        analysis_reports = state.get("analysis_reports", {})

        indicators = market_data.get("indicators", {})
        historical_stats = market_data.get("historical_stats", {})
        regime_data = market_data.get("regime_data", {})

        # Summarize other agents' signals for context
        signal_context = []
        for aid, report in analysis_reports.items():
            signal_context.append(f"  [{aid}] signal={report.signal} conf={report.confidence:.2f}")

        stats_text = "\n".join(f"  {k}: {v}" for k, v in historical_stats.items()) if historical_stats else "  No historical stats provided"
        regime_text = "\n".join(f"  {k}: {v}" for k, v in regime_data.items()) if regime_data else "  No regime data provided"
        indicators_text = "\n".join(f"  {k}: {v}" for k, v in indicators.items()) if indicators else "  No indicators provided"
        market_summary = self._format_market_data(market_data)

        user_message = f"""QUANTITATIVE RESEARCH ANALYSIS
Symbol: {symbol}
Timestamp: {self._now().isoformat()}

=== HISTORICAL STATISTICS ===
{stats_text}

=== REGIME DATA ===
{regime_text}

=== TECHNICAL INDICATORS ===
{indicators_text}

=== OTHER AGENT SIGNALS (context) ===
{chr(10).join(signal_context) if signal_context else "  None yet"}

=== FULL MARKET DATA ===
{market_summary}

=== TASK ===
Build the quantitative case for or against trading {symbol}:
1. Assess the setup frequency and sample size validity
2. Estimate the return distribution characteristics for this setup type
3. Apply factor model thinking to decompose the expected return
4. Classify the current market regime and its impact on this signal
5. Assess mean reversion vs. trending properties of this asset
6. State the explicit statistical edge (or lack thereof)
7. Identify any red flags that suggest the apparent edge is spurious

Return your Quant Researcher AgentReport JSON.
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
                reasoning=f"Quant research failed: {exc}",
                supporting_evidence=[],
                contradicting_evidence=["Analysis error"],
                timestamp=self._now(),
            )
