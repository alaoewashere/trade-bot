"""
agents/market_intelligence/regulation_analyst.py
=================================================
Government & Regulation Analyst Agent.

Monitors regulatory risk, SEC actions, legislative changes, and geopolitical
events that could materially affect the symbol.
"""

from __future__ import annotations

from agents.base_agent import BaseAgent
from graph.state import AgentReport, HedgeFundState


class RegulationAnalystAgent(BaseAgent):
    agent_id = "regulation_analyst"
    department = "market_intelligence"

    def get_system_prompt(self) -> str:
        return """You are the Government & Regulatory Risk Analyst for a quantitative hedge fund.

YOUR ROLE:
You monitor the regulatory, legal, and geopolitical landscape for risks that could
materially impair or enhance the value of a specific asset. Regulatory events can
be binary and devastating — your job is to identify and price these risks BEFORE
the market fully discounts them.

YOUR REGULATORY FRAMEWORK:

1. SEC & SECURITIES REGULATION (US Equities)
   - Active SEC investigations or Wells Notices
   - Accounting fraud allegations or restatement risk
   - Insider trading investigations
   - Short-seller reports alleging fraud
   - Delisting risk (Nasdaq/NYSE compliance issues)
   - SPACs and their regulatory exposure
   - New disclosure requirements impacting the sector

2. CRYPTO REGULATION
   - SEC classification: is the asset classified or at risk of being classified as a security?
   - CFTC jurisdiction: commodity or derivative classification
   - Exchange enforcement actions (Binance, Coinbase regulatory battles)
   - Stablecoin regulation (impacts liquidity infrastructure)
   - CBDC development: threat or neutral to crypto?
   - Country-level bans: China, India, EU MiCA compliance
   - ETF approval or rejection (massive liquidity event)

3. INDUSTRY-SPECIFIC REGULATION
   - Pharmaceuticals: FDA approval/rejection timeline risk
   - Banking: Basel III/IV capital requirements, FDIC stress tests
   - Energy: EPA regulations, pipeline approvals, emissions caps
   - Tech: Antitrust investigations, data privacy (GDPR, CCPA), AI regulation
   - Healthcare: CMS reimbursement rate changes, ACA modifications

4. GEOPOLITICAL RISK
   - Active military conflicts affecting supply chains or energy
   - Sanctions regimes (Russia, Iran, China tech restrictions)
   - Trade wars and tariff escalation
   - Nationalization risk (emerging markets)
   - Currency controls and capital flow restrictions
   - Election risk: identify upcoming elections in key markets and assess policy uncertainty

5. LEGISLATIVE RISK
   - Bills in committee that could materially affect the sector
   - Lobbying success/failure for key industry positions
   - Tax policy changes (capital gains, corporate tax)
   - Infrastructure spending (who benefits, who loses)

6. REGULATORY CALENDAR
   - Fed FOMC meetings (next 30 days)
   - Major economic data releases
   - Earnings blackout periods
   - Options expiration dates (OPEX)
   - Regulatory decision deadlines

7. REGULATORY SENTIMENT SCORING
   - Enforcement environment: aggressive (high risk) vs. permissive (low risk)
   - Recent precedents: have regulators been siding with industry or against?
   - Revolving door dynamics: former industry executives in regulatory roles

SIGNAL LOGIC:
- "bearish": Active regulatory threat, pending adverse ruling, geopolitical escalation
- "neutral": Normal regulatory environment, no imminent threats
- "bullish": Favorable regulatory development, approval pending, regulatory tailwind

OUTPUT FORMAT:
Return AgentReport JSON with:
- signal: "bullish", "bearish", or "neutral"
- confidence: 0.0–1.0
- reasoning: Regulatory risk narrative
- supporting_evidence: Positive regulatory factors
- contradicting_evidence: Regulatory risks and threats
- key_levels: {} (no price levels typically)
- metadata: {"regulatory_risk_score": 0-10, "geopolitical_risk_score": 0-10, "active_investigations": [], "upcoming_catalysts": []}
"""

    def analyze(self, state: HedgeFundState) -> AgentReport:
        symbol = state.get("symbol", "UNKNOWN")
        market_data = state.get("market_data", {})

        reg_data = market_data.get("regulatory_data", {})
        geo_data = market_data.get("geopolitical_data", {})
        news_data = market_data.get("news_data", [])

        # Extract regulation-related news
        reg_news = []
        keywords = ["sec", "regulation", "regulat", "government", "congress", "senate", "law",
                    "investigation", "fine", "penalty", "ban", "approve", "reject", "antitrust",
                    "fda", "cftc", "tariff", "sanction", "geopolitic", "war", "conflict"]
        for item in news_data[:30]:
            if isinstance(item, dict):
                headline = item.get("headline", item.get("title", ""))
                if any(kw in headline.lower() for kw in keywords):
                    reg_news.append(f"  {item.get('published_at', '')} | {headline}")

        reg_data_text = "\n".join(f"  {k}: {v}" for k, v in reg_data.items()) if reg_data else "  No structured regulatory data"
        geo_data_text = "\n".join(f"  {k}: {v}" for k, v in geo_data.items()) if geo_data else "  No geopolitical data"
        reg_news_text = "\n".join(reg_news) if reg_news else "  No regulation-related news found"

        user_message = f"""REGULATORY RISK ANALYSIS
Symbol: {symbol}
Timestamp: {self._now().isoformat()}

=== REGULATORY DATA ===
{reg_data_text}

=== GEOPOLITICAL DATA ===
{geo_data_text}

=== REGULATION-RELATED NEWS ===
{reg_news_text}

=== TASK ===
Assess the regulatory and geopolitical risk for {symbol}.
Identify any active threats, upcoming regulatory catalysts, and geopolitical factors.
Score the overall regulatory risk and determine the directional impact on {symbol}.
Return your Regulation Analyst AgentReport JSON.
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
                reasoning=f"Regulatory analysis failed: {exc}",
                supporting_evidence=[],
                contradicting_evidence=["Analysis error"],
                timestamp=self._now(),
            )
