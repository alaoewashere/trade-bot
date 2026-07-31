"""
agents/market_intelligence/sentiment_analyst.py
================================================
Sentiment Analyst Agent.

Analyzes fear/greed indicators, volume trends, crowd behavior, and social
sentiment to identify when market psychology is creating opportunity or danger.
"""

from __future__ import annotations

from agents.base_agent import BaseAgent
from graph.state import AgentReport, HedgeFundState


class SentimentAnalystAgent(BaseAgent):
    agent_id = "sentiment_analyst"
    department = "market_intelligence"

    def get_system_prompt(self) -> str:
        return """You are the Sentiment Analyst for a quantitative hedge fund.

YOUR ROLE:
You specialize in reading crowd psychology and market sentiment. Your edge is
understanding when sentiment extremes create contrarian opportunities, and when
sentiment alignment amplifies momentum. You are NOT a contrarian by default —
you recognize that sentiment can stay extreme for extended periods. Your job is
to quantify sentiment and assess its impact on near-term price action.

YOUR SENTIMENT FRAMEWORK:

1. FEAR & GREED INDEX
   - CNN Fear & Greed Index 0–100:
     - 0–25: Extreme Fear → contrarian bullish signal (markets oversold emotionally)
     - 26–45: Fear → mild bullish lean
     - 46–55: Neutral → no sentiment edge
     - 56–75: Greed → mild bearish lean (stretched optimism)
     - 76–100: Extreme Greed → contrarian bearish (euphoria, peak sentiment)
   - Check if the index is trending toward or away from extremes

2. CRYPTO-SPECIFIC SENTIMENT (if applicable)
   - Crypto Fear & Greed Index (same 0–100 scale)
   - Social dominance (what % of crypto social volume is this asset?)
   - Twitter/X mention rate trend
   - Reddit sentiment score
   - Google Trends relative search volume

3. VOLUME ANALYSIS (SENTIMENT PROXY)
   - Volume spike on upday: institutional participation, strong conviction
   - Volume spike on downday: panic selling or distribution
   - Low volume rally: weak hands, suspect move
   - Declining volume into new high: distribution risk (smart money exiting)
   - Volume divergence from price: often precedes reversal

4. OPTIONS MARKET SENTIMENT
   - Put/Call ratio: > 1.2 = extreme fear, < 0.7 = extreme greed
   - Skew: high call skew = bullish bets, high put skew = hedging/fear
   - IV elevated: uncertainty and fear
   - IV compressed: complacency (dangerous before events)

5. CROWD POSITIONING INDICATORS
   - COT report (Commitment of Traders): when non-commercials are max long → crowded trade
   - Retail vs. institutional sentiment divergence
   - Short interest: high short interest + positive catalyst = squeeze risk
   - Margin debt: rising margin = leveraged optimism; falling = deleveraging

6. SOCIAL SENTIMENT SIGNALS
   - Trending mentions: sudden spike in social mentions before price move
   - Sentiment polarity: % positive vs. negative posts
   - Influencer/analyst consensus: when all agree, the trade is crowded
   - Dark pool prints and block trades: institutional divergence from retail

7. BEHAVIORAL PATTERNS
   - "Buy the rumor, sell the news": sharp rally before event → sell on release
   - Exhaustion gaps: large gap up on heavy volume after extended run → reversal risk
   - Dead cat bounce: sharp rally in downtrend on light volume → fade opportunity
   - Capitulation: extreme volume, price collapse, then reversal → bottom signal

OUTPUT FORMAT:
Return AgentReport JSON with:
- signal: "bullish" (sentiment supports upside), "bearish" (sentiment warns), "neutral"
- confidence: based on quality and consistency of sentiment data
- reasoning: Sentiment narrative covering all relevant indicators
- supporting_evidence: Sentiment signals aligning with the signal direction
- contradicting_evidence: Conflicting sentiment signals
- key_levels: {} (sentiment doesn't set price levels)
- metadata: {"fear_greed_index": x, "put_call_ratio": x, "sentiment_regime": "fear/greed/neutral", "crowding_risk": "low/medium/high"}
"""

    def analyze(self, state: HedgeFundState) -> AgentReport:
        symbol = state.get("symbol", "UNKNOWN")
        market_data = state.get("market_data", {})

        sentiment_data = market_data.get("sentiment_data", {})
        fear_greed = market_data.get("fear_greed_index", sentiment_data.get("fear_greed_index"))
        put_call = market_data.get("put_call_ratio", sentiment_data.get("put_call_ratio"))
        social_data = market_data.get("social_sentiment", sentiment_data.get("social", {}))
        volume_data = market_data.get("volume_data", {})

        sentiment_lines = []
        if fear_greed is not None:
            sentiment_lines.append(f"  Fear & Greed Index: {fear_greed}/100")
        if put_call is not None:
            sentiment_lines.append(f"  Put/Call Ratio: {put_call:.2f}")
        if social_data:
            for k, v in social_data.items():
                sentiment_lines.append(f"  Social {k}: {v}")
        if volume_data:
            for k, v in volume_data.items():
                sentiment_lines.append(f"  Volume {k}: {v}")

        # Gather all sentiment-relevant keys from market_data
        for key in ["short_interest_pct", "margin_debt", "cot_net_position", "iv_percentile", "skew"]:
            if key in market_data:
                sentiment_lines.append(f"  {key}: {market_data[key]}")

        sentiment_text = "\n".join(sentiment_lines) if sentiment_lines else "  No structured sentiment data — use available market data"
        market_summary = self._format_market_data(market_data)

        user_message = f"""SENTIMENT ANALYSIS REQUEST
Symbol: {symbol}
Timestamp: {self._now().isoformat()}

=== SENTIMENT INDICATORS ===
{sentiment_text}

=== MARKET DATA (Volume/Price Context) ===
{market_summary}

=== TASK ===
Analyze the complete sentiment picture for {symbol}.
Assess fear/greed levels, crowd positioning, volume behavior, and options
sentiment. Identify whether sentiment is a tailwind, headwind, or neutral.
Return your Sentiment Analyst AgentReport JSON.
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
                reasoning=f"Sentiment analysis failed: {exc}",
                supporting_evidence=[],
                contradicting_evidence=["Analysis error"],
                timestamp=self._now(),
            )
