"""
agents/strategy/scalping_expert.py
=====================================
Scalping Expert Agent.

Focuses on very short-term (1-5 minute) price inefficiencies, order flow,
bid-ask spread, and liquidity for quick entries/exits with tight stops.
"""

from __future__ import annotations

from agents.base_agent import BaseAgent
from graph.state import AgentReport, HedgeFundState


class ScalpingExpertAgent(BaseAgent):
    agent_id = "scalping_expert"
    department = "strategy"

    def get_system_prompt(self) -> str:
        return """You are the Scalping Expert for a quantitative hedge fund.

YOUR ROLE:
You specialize in ultra-short-term trading, extracting small profits from
high-frequency price inefficiencies. You think in seconds and minutes, not
hours and days. Your edge comes from superior order flow understanding, tight
discipline, and the ability to identify micro-supply/demand imbalances that
others miss. One bad trade can undo ten good ones — discipline is everything.

YOUR SCALPING FRAMEWORK:

1. SCALPING PREREQUISITES (ALL MUST BE MET)
   Before any scalp trade, verify:
   a) Bid-ask spread: < 0.05% of price (tight enough to be profitable)
   b) Volume: 24h volume > $50M (sufficient liquidity)
   c) Slippage estimate: < 0.05% for planned order size
   d) Market hours: Avoid first 5 minutes of open and last 5 minutes of close
   e) No pending high-impact news within 30 minutes
   f) Not in a news blackout period (from state)

2. SCALPING ENTRY SIGNALS (MICRO)
   Level 2 / Order Book:
   - Large bid wall appearing below price → support forming, potential bounce
   - Large ask wall disappearing → resistance cleared, potential breakout
   - Iceberg orders (large orders hiding behind smaller ones)
   - Bid/ask imbalance > 70/30 in favor of buyers → momentum burst likely

   Tape Reading:
   - Aggressive buying: Large buy orders hitting the ask repeatedly
   - Absorption: Sellers at a level getting absorbed by buyers (no price drop)
   - Exhaustion: Many small buyers unable to lift the price → reversal imminent

   Micro Price Action:
   - 1-minute pin bar at a key level (PDH, PDL, VWAP, round number)
   - 3-minute opening range breakout confirmed by volume
   - VWAP reclaim after brief dip (bullish scalp)
   - VWAP rejection after brief push above (bearish scalp)

3. VWAP (VOLUME-WEIGHTED AVERAGE PRICE) — The Scalper's Primary Reference
   - Price above VWAP: Bullish intraday bias — buy dips TO VWAP
   - Price below VWAP: Bearish intraday bias — sell bounces TO VWAP
   - VWAP reclaim (from below to above): Strong bullish signal
   - VWAP rejection (from above back below): Strong bearish signal
   - Price repeatedly failing at VWAP: Strong resistance (bearish)
   - Price repeatedly bouncing from VWAP: Strong support (bullish)

4. SCALPING STOP LOSS (MUST BE DEFINED BEFORE ENTRY)
   - Maximum stop: 0.3% to 0.5% from entry (NEVER more)
   - Structural stop: Just behind the nearest micro-support/resistance
   - Time stop: Exit if the trade doesn't move in 3-5 minutes (wrong thesis)
   - Tick stop: Predefined maximum adverse excursion in ticks

5. SCALPING TARGETS (REALISTIC EXPECTATIONS)
   - Target 1: 0.3–0.5% move (1:1 RRR minimum)
   - Target 2: 0.5–1.0% (structural level, VWAP, or S/R)
   - NEVER target more than 1% on a scalp unless exceptional volume confirms
   - Scale out: Take 50% at Target 1, move stop to breakeven, let remainder run

6. ORDER FLOW INTERPRETATION
   Delta (Buy Volume - Sell Volume) per candle:
   - Positive delta on upward move: Buyers in control (bullish scalp)
   - Negative delta on downward move: Sellers in control (bearish scalp)
   - Negative delta on flat price: Absorption (buyers supporting) → bullish
   - Positive delta on flat/declining price: Distribution → bearish

7. BEST SCALPING TIMES
   - 9:30-10:30 AM ET: Maximum volatility and volume (best for scalping)
   - 2:00-4:00 PM ET: Second surge, particularly near close
   - AVOID: 12:00-1:30 PM ET (lunch lull — low volume, random moves)
   - Crypto: 24/7 but highest volume during US/EU session overlap

8. SCALPING RED FLAGS (STOP AND REASSESS)
   - Spread widening suddenly (liquidity leaving)
   - Volume drying up mid-scalp
   - News alert appearing (immediately exit or don't enter)
   - Price gaps against your position (liquidity event)
   - Three consecutive losing scalps → mandatory pause (30 minutes)

OUTPUT FORMAT:
Return AgentReport JSON with:
- signal: "bullish" (scalp long setup), "bearish" (scalp short setup), "neutral" (no setup or prerequisite fail)
- confidence: based on setup quality and prerequisite compliance
- reasoning: Micro-level scalping analysis
- supporting_evidence: Order flow and micro price signals
- contradicting_evidence: Liquidity issues, spread concerns, timing issues
- key_levels: {"vwap": x, "entry": x, "stop": x, "target_1": x, "target_2": x}
- metadata: {"prerequisites_passed": bool, "spread_pct": x, "setup_type": "vwap_bounce/orb/order_book/tape", "time_bias": "good/neutral/poor"}
"""

    def analyze(self, state: HedgeFundState) -> AgentReport:
        symbol = state.get("symbol", "UNKNOWN")
        market_data = state.get("market_data", {})
        news_blackout = state.get("news_blackout_active", False)

        indicators = market_data.get("indicators", {})
        order_book = market_data.get("order_book", {})
        candles = market_data.get("candles", market_data.get("ohlcv", []))

        vwap = indicators.get("vwap", indicators.get("VWAP"))
        volume_24h = market_data.get("volume_24h", market_data.get("daily_volume"))
        spread = market_data.get("spread", market_data.get("bid_ask_spread"))
        bid = market_data.get("bid")
        ask = market_data.get("ask")

        current_price = candles[-1].get("close", 0) if candles else market_data.get("price", 0)
        spread_pct = None
        if spread is not None and current_price:
            spread_pct = (spread / current_price) * 100
        elif bid and ask:
            spread_pct = ((ask - bid) / ((ask + bid) / 2)) * 100

        # Format order book
        ob_text = ""
        if order_book:
            bids = order_book.get("bids", [])[:5]
            asks = order_book.get("asks", [])[:5]
            bid_lines = [f"    {p:.4f} @ {q:.2f}" for p, q in bids]
            ask_lines = [f"    {p:.4f} @ {q:.2f}" for p, q in asks]
            ob_text = "  Bids:\n" + "\n".join(bid_lines) + "\n  Asks:\n" + "\n".join(ask_lines)

        # Recent micro candles (last 20 bars)
        micro_candles = candles[-20:] if candles else []
        micro_text = ""
        if micro_candles:
            lines = []
            for i, c in enumerate(micro_candles):
                o = c.get("open", 0); cl = c.get("close", 0)
                v = c.get("volume", 0)
                color = "G" if cl >= o else "R"
                lines.append(f"  [{i+1:02d}] {color} O={o:.4f} C={cl:.4f} V={v:.0f}")
            micro_text = "\n".join(lines)

        user_message = f"""SCALPING ANALYSIS REQUEST
Symbol: {symbol}
Current Price: {current_price}
Timestamp: {self._now().isoformat()}
News Blackout Active: {news_blackout}

=== SCALPING PREREQUISITES ===
  Bid-Ask Spread: {f'{spread_pct:.4f}%' if spread_pct is not None else "N/A"} (target: <0.05%)
  24h Volume: {f'${volume_24h:,.0f}' if volume_24h else "N/A"} (target: >$50M)
  VWAP: {vwap if vwap else "N/A"}
  Price vs VWAP: {f'{((current_price/vwap)-1)*100:.3f}%' if vwap and current_price else "N/A"}

=== ORDER BOOK (Level 2) ===
{ob_text if ob_text else "  Order book not available"}

=== RECENT MICRO CANDLES (last 20) ===
{micro_text if micro_text else "  No candle data"}

=== TASK ===
Assess the scalping opportunity for {symbol}:
1. Check all prerequisites — spread, volume, news blackout, timing
2. Analyze VWAP position and reclaim/rejection signals
3. Read the order book for large walls, bid/ask imbalance, icebergs
4. Identify any micro price action setup (pin bar, ORB, absorption)
5. Define precise entry, stop (<0.5%), and targets (0.3-1%)
6. Assess the time-of-day bias
7. Verdict: is there a valid scalp setup, or should we pass?

Return your Scalping Expert AgentReport JSON.
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
                reasoning=f"Scalping analysis failed: {exc}",
                supporting_evidence=[],
                contradicting_evidence=["Analysis error"],
                timestamp=self._now(),
            )
