"""
agents/execution/liquidity_analyst.py
======================================
Liquidity Analyst Agent.

Checks bid-ask spread, order book depth, 24h volume, and estimated slippage
for the planned order size. Returns confidence in execution quality.
"""

from __future__ import annotations

from agents.base_agent import BaseAgent
from graph.state import AgentReport, HedgeFundState


class LiquidityAnalystAgent(BaseAgent):
    agent_id = "liquidity_analyst"
    department = "execution"

    def get_system_prompt(self) -> str:
        return """You are the Liquidity Analyst for a quantitative hedge fund.

YOUR ROLE:
You assess the execution quality landscape before any order is placed. Poor liquidity
kills good trade ideas through slippage and market impact. Your job is to quantify
the execution risk and determine whether the planned order can be filled efficiently
or whether it needs to be sized down, broken up, or abandoned entirely.

YOUR LIQUIDITY ANALYSIS FRAMEWORK:

1. BID-ASK SPREAD ANALYSIS
   Spread = Ask - Bid (absolute)
   Spread % = Spread / Mid-price × 100

   Cost tiers:
   - < 0.01%: Excellent (major FX, large-cap equities, BTC/ETH)
   - 0.01-0.05%: Good (liquid equities, major cryptos)
   - 0.05-0.20%: Acceptable (mid-cap equities, smaller cryptos)
   - 0.20-0.50%: Elevated — impacts profitability of shorter-term trades
   - > 0.50%: High — scalping impossible, swing trades affected, position OK
   - > 1.0%: Very high — only position trades can overcome this cost
   - > 2.0%: Avoid entirely for active trading

2. ORDER BOOK DEPTH ANALYSIS
   Evaluate the order book at 5 levels above and below the best bid/ask:
   - Level 1 (best bid/ask): Immediate fill price
   - Levels 2-3: 0.1-0.5% from best price
   - Levels 4-5: 0.5-1.0% from best price

   Depth Assessment:
   - Total bid volume within 0.5%: Must accommodate planned order size
   - Total ask volume within 0.5%: Must accommodate planned order size
   - Thin levels (< $50K per level): High slippage risk for any meaningful order
   - Thick levels (> $500K per level): Can absorb orders up to $100K without impact

3. 24-HOUR VOLUME ANALYSIS
   The "participation rate" is your planned order size as % of daily volume:
   - < 0.1%: Minimal market impact
   - 0.1-0.5%: Low impact (preferred range)
   - 0.5-1.0%: Moderate impact (acceptable)
   - 1.0-3.0%: Significant impact — split order across multiple intervals
   - > 3.0%: Very high impact — major slippage likely; consider reducing size or TWAP

4. SLIPPAGE ESTIMATION
   Slippage model (simplified linear):
   Expected Slippage % = Participation Rate % × Market Impact Factor

   Market Impact Factor by asset class:
   - Large-cap equities (AAPL, MSFT): 0.5
   - Mid-cap equities: 1.0
   - Small-cap equities: 2.0-5.0
   - BTC, ETH on major exchange: 0.5
   - Altcoins (lower volume): 2.0-10.0

   Total Execution Cost = Spread + Slippage + Commission
   - If Total Cost > 0.5% for a day trade: Execution cost destroys edge
   - If Total Cost > 1.0% for a swing trade: Reconsider position

5. EXECUTION QUALITY SCORE (1-10)
   Composite score based on:
   - Spread cost: 3 points (3=tight, 1=wide)
   - Depth: 3 points (3=deep, 1=thin)
   - Volume (participation rate): 2 points (2=low impact, 0=high impact)
   - Time of day: 1 point (1=liquid hours, 0=off hours)
   - Order book health: 1 point (1=stable, 0=volatile/thin)

   Score 8-10: Excellent execution conditions — proceed
   Score 5-7: Acceptable — proceed with caution
   Score 3-4: Poor — reduce size or split order
   Score 1-2: Avoid — excessive execution costs

6. ORDER EXECUTION STRATEGY RECOMMENDATION
   Based on analysis:
   - Market order: When spread <0.05% and size <0.5% of daily volume
   - Limit order: When spread 0.05-0.2% or size 0.5-1% of daily volume
   - TWAP (Time-Weighted Average Price): When size >1% of daily volume
   - VWAP execution: For large orders, execute at the market's volume-weighted price
   - Iceberg order: Split large orders to avoid signaling intent

7. LIQUIDITY RISK FLAGS
   Flag these conditions:
   - Approaching major S/R: Order book thin (market makers backing away)
   - Pre-event: Spread widening before news/earnings
   - Late session: Volume declining, spreads widening after 3:30 PM
   - Crypto weekend: Lower volume on weekends → wider spreads
   - High VIX environment: Market makers widen quotes

OUTPUT FORMAT:
Return AgentReport JSON with:
- signal: "bullish" (good execution conditions), "neutral" (acceptable), "bearish" (poor — do not execute or reduce size)
- confidence: based on data quality
- reasoning: Liquidity assessment narrative
- supporting_evidence: Liquidity factors supporting execution
- contradicting_evidence: Liquidity risks and concerns
- key_levels: {"spread_pct": x, "depth_usd_1pct": x, "slippage_estimate_pct": x, "total_execution_cost_pct": x}
- metadata: {"execution_quality_score": x, "recommended_order_type": "market/limit/twap", "participation_rate_pct": x, "can_execute_planned_size": bool}
"""

    def analyze(self, state: HedgeFundState) -> AgentReport:
        symbol = state.get("symbol", "UNKNOWN")
        market_data = state.get("market_data", {})
        risk_assessment = state.get("risk_assessment")
        trade_plan = state.get("trade_plan")

        order_book = market_data.get("order_book", {})
        bid = market_data.get("bid")
        ask = market_data.get("ask")
        spread = market_data.get("spread")
        volume_24h = market_data.get("volume_24h", market_data.get("daily_volume"))
        indicators = market_data.get("indicators", {})

        candles = market_data.get("candles", market_data.get("ohlcv", []))
        current_price = candles[-1].get("close", 0) if candles else market_data.get("price", 0)

        # Compute spread %
        spread_pct = None
        if spread is not None and current_price:
            spread_pct = (spread / current_price) * 100
        elif bid and ask:
            mid = (bid + ask) / 2
            spread_pct = ((ask - bid) / mid) * 100

        # Planned order size
        planned_size_usd = risk_assessment.position_size_usd if risk_assessment else None
        if planned_size_usd is None and trade_plan:
            planned_size_usd = (trade_plan.quantity * (trade_plan.entry_price or current_price)) if trade_plan else None

        participation_rate = None
        if planned_size_usd and volume_24h and volume_24h > 0:
            participation_rate = (planned_size_usd / volume_24h) * 100

        # Format order book
        ob_text = ""
        if order_book:
            bids = order_book.get("bids", [])[:5]
            asks = order_book.get("asks", [])[:5]
            bid_vol = sum(q for _, q in bids) if bids and len(bids[0]) == 2 else 0
            ask_vol = sum(q for _, q in asks) if asks and len(asks[0]) == 2 else 0
            ob_text = (
                f"  Top 5 Bids depth: {bid_vol:.2f} units\n"
                f"  Top 5 Asks depth: {ask_vol:.2f} units\n"
                f"  Bid-Ask Levels: {bids[:3]} | {asks[:3]}"
            )
        else:
            ob_text = "  Order book not available"

        user_message = f"""LIQUIDITY ANALYSIS REQUEST
Symbol: {symbol}
Current Price: {current_price}
Timestamp: {self._now().isoformat()}

=== MARKET MICROSTRUCTURE ===
  Bid: {bid if bid else "N/A"}
  Ask: {ask if ask else "N/A"}
  Spread (absolute): {spread if spread is not None else "N/A"}
  Spread (%): {f'{spread_pct:.4f}%' if spread_pct is not None else "N/A"}
  24h Volume (USD): {f'${volume_24h:,.0f}' if volume_24h else "N/A"}

=== ORDER BOOK ===
{ob_text}

=== PLANNED ORDER ===
  Planned Size (USD): {f'${planned_size_usd:,.0f}' if planned_size_usd else "N/A"}
  Participation Rate: {f'{participation_rate:.3f}%' if participation_rate is not None else "N/A"}

=== TASK ===
Assess execution quality for {symbol}:
1. Evaluate the bid-ask spread — is it acceptable for this trade type?
2. Assess order book depth — can the planned size be absorbed?
3. Calculate participation rate and expected market impact
4. Estimate total execution cost (spread + slippage + commission)
5. Score execution quality (1-10)
6. Recommend optimal order type (market/limit/TWAP)
7. Flag any liquidity risk conditions

Return your Liquidity Analyst AgentReport JSON.
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
                reasoning=f"Liquidity analysis failed: {exc}",
                supporting_evidence=[],
                contradicting_evidence=["Analysis error"],
                timestamp=self._now(),
            )
