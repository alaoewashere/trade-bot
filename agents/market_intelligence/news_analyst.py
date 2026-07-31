"""
agents/market_intelligence/news_analyst.py
==========================================
News Analyst Agent.

Reads news_data from market_data, scores headlines for market impact,
and identifies which sector/asset is affected and in what direction.
"""

from __future__ import annotations

from agents.base_agent import BaseAgent
from graph.state import AgentReport, HedgeFundState


class NewsAnalystAgent(BaseAgent):
    agent_id = "news_analyst"
    department = "market_intelligence"

    def get_system_prompt(self) -> str:
        return """You are the News Analyst for a quantitative hedge fund.

YOUR ROLE:
You monitor, score, and interpret financial news in real-time to identify market-moving
information. You are not a journalist — you are an analyst whose job is to assess
the MARKET IMPACT of news events on a specific symbol.

YOUR NEWS ANALYSIS FRAMEWORK:

1. HEADLINE IMPACT SCORING (0–10 scale)
   - 0–2: Noise, background information, no expected price impact
   - 3–5: Moderate impact, may affect sentiment but not fundamentals
   - 6–8: Significant impact — earnings surprises, major data beats/misses, M&A
   - 9–10: Market-moving — major policy shifts, systemic events, black swans

2. DIRECTIONAL ASSESSMENT
   For each high-impact headline, determine:
   - Is the news DIRECTLY about the symbol or a closely related company/sector?
   - Does it affect supply/demand, earnings, regulation, or macro backdrop?
   - Is the impact IMMEDIATE (price gap likely) or GRADUAL (trend development)?
   - Is the news already PRICED IN (stale) or FRESH (actionable)?

3. SENTIMENT CLASSIFICATION
   - Hard positive: Earnings beat, upgrade, M&A premium, buyback, major contract
   - Soft positive: Sector rotation inflows, macro tailwind, analyst optimism
   - Hard negative: Earnings miss, SEC investigation, product recall, credit downgrade
   - Soft negative: Macro headwind, sector rotation outflows, insider selling
   - Ambiguous: Restructuring, leadership change, geopolitical headline without clear impact

4. NEWS HALF-LIFE ASSESSMENT
   - Earnings surprises: 1–3 day half-life (immediate adjustment)
   - Regulatory news: Weeks to months (gradual repricing)
   - M&A: Immediate (binary on deal close/break)
   - Macro data: Hours to days (absorbed quickly)
   - Geopolitical: Variable (depends on escalation risk)

5. MARKET CONTEXT
   - Is the news confirming or contradicting the prevailing trend?
   - Is the market over-reacting (opportunity) or correctly pricing?
   - What is the second-order effect? (e.g., rising oil prices → airlines hurt, energy wins)

6. INFORMATION HIERARCHY
   - Primary sources (SEC filings, central bank statements) > secondary (media)
   - Quantitative data (GDP, CPI, earnings) > qualitative (analyst opinion)
   - Recent news (< 24h) > stale news (> 48h)

OUTPUT FORMAT:
Return AgentReport JSON with:
- signal: "bullish" (net positive news), "bearish" (net negative news), "neutral" (noise/mixed)
- confidence: based on impact scores and relevance
- reasoning: Summary of key news items and their assessed market impact
- supporting_evidence: Specific headlines supporting the signal
- contradicting_evidence: Contradicting or offsetting news
- key_levels: {} (news analyst typically does not set price levels)
- metadata: {"top_stories": [...], "avg_impact_score": x, "news_freshness_hours": x}
"""

    def analyze(self, state: HedgeFundState) -> AgentReport:
        symbol = state.get("symbol", "UNKNOWN")
        market_data = state.get("market_data", {})
        news_data = market_data.get("news_data", [])

        if not news_data:
            return AgentReport(
                agent_id=self.agent_id,
                symbol=symbol,
                signal="neutral",
                confidence=0.1,
                reasoning="No news data available for analysis.",
                supporting_evidence=[],
                contradicting_evidence=["No news data provided"],
                timestamp=self._now(),
                metadata={"top_stories": [], "avg_impact_score": 0},
            )

        # Format news items
        news_lines = []
        for i, item in enumerate(news_data[:20]):  # Limit to 20 most recent
            if isinstance(item, dict):
                headline = item.get("headline", item.get("title", str(item)))
                source = item.get("source", "unknown")
                published = item.get("published_at", item.get("time", "unknown"))
                sentiment = item.get("sentiment", "")
                news_lines.append(f"  [{i+1}] {published} | {source} | {headline} {f'(pre-scored: {sentiment})' if sentiment else ''}")
            else:
                news_lines.append(f"  [{i+1}] {item}")

        news_text = "\n".join(news_lines)

        user_message = f"""NEWS ANALYSIS REQUEST
Symbol: {symbol}
Timestamp: {self._now().isoformat()}
Total News Items: {len(news_data)}

=== RECENT NEWS ===
{news_text}

=== TASK ===
Score and interpret these news items for their market impact on {symbol}.
Identify the most impactful headlines, assess directional bias, determine
if news is fresh/actionable or stale. Return your News Analyst AgentReport JSON.
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
                reasoning=f"News analysis failed: {exc}",
                supporting_evidence=[],
                contradicting_evidence=["Analysis error"],
                timestamp=self._now(),
            )
