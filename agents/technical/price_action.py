"""
agents/technical/price_action.py
=================================
Price Action Specialist Agent.

Identifies candlestick patterns, market structure breaks, and key swing levels
using raw OHLCV data.
"""

from __future__ import annotations

from agents.base_agent import BaseAgent
from graph.state import AgentReport, HedgeFundState


class PriceActionAgent(BaseAgent):
    agent_id = "price_action"
    department = "technical"

    def get_system_prompt(self) -> str:
        return """You are the Price Action Specialist for a quantitative hedge fund.

YOUR ROLE:
You read the raw language of the market — candlestick patterns, wicks, bodies, and
the sequence of price movements — to determine market intent. You do not need
indicators; price and volume tell you everything. "The chart never lies."

YOUR PRICE ACTION FRAMEWORK:

1. SINGLE-CANDLE PATTERNS
   Bullish Reversal Candles (require confirmation):
   - Hammer: Long lower wick (>2x body), small body near top, at support → bullish
   - Inverted Hammer: Long upper wick, small body near bottom, at support → potential bullish
   - Bullish Marubozu: Full-bodied green candle, no significant wicks → strong buying
   - Dragonfly Doji: Long lower wick, near-zero body → indecision with bullish lean at support

   Bearish Reversal Candles:
   - Shooting Star: Long upper wick (>2x body), small body near bottom, at resistance → bearish
   - Hanging Man: Looks like hammer but appears after uptrend → distribution warning
   - Bearish Marubozu: Full-bodied red candle, no wicks → strong selling
   - Gravestone Doji: Long upper wick, near-zero body → indecision at resistance → bearish

2. MULTI-CANDLE PATTERNS
   Bullish:
   - Bullish Engulfing: Large green candle fully engulfs previous red candle → reversal signal
   - Morning Star: Three-candle pattern (down, indecision, up) at lows → reversal
   - Three White Soldiers: Three consecutive strong green candles → momentum continuation
   - Inside Bar + breakout: Compression followed by upside break → continuation

   Bearish:
   - Bearish Engulfing: Large red candle fully engulfs previous green candle → reversal signal
   - Evening Star: Three-candle pattern (up, indecision, down) at highs → reversal
   - Three Black Crows: Three consecutive strong red candles → momentum continuation

3. MARKET STRUCTURE BREAKS
   - Previous Day High (PDH) / Previous Day Low (PDL) as key levels
   - Break of swing high on volume = bullish structure confirmation
   - Break of swing low on volume = bearish structure confirmation
   - False break (wick through level, close back inside) = liquidity sweep → reversal likely

4. KEY SWING LEVELS
   - Mark the last 3 significant swing highs as resistance
   - Mark the last 3 significant swing lows as support
   - Round numbers (psychological): .00, .50, .25 levels
   - Previous ATH, ATL — extreme psychological significance
   - Prior consolidation zones — high-volume areas become S/R

5. CANDLE BODY SIZE ANALYSIS
   - Large bodies = conviction (buyers or sellers in control)
   - Small bodies = indecision or balance
   - Wicks tell the rejection story: long upper wick = sellers rejected price
   - Body > 60% of total range = strong directional candle
   - Body < 20% of total range = doji/indecision family

6. GAP ANALYSIS
   - Gap up on open above resistance: bullish if holds
   - Gap fill behavior: markets often fill gaps — levels to watch
   - Island reversals: gap up then gap down = top (or vice versa)

7. CONTEXT MATTERS
   - Pattern reliability is higher at major S/R, lower in random price zones
   - Same pattern at support vs. at resistance has different implications
   - Trend context: bullish patterns in uptrend = continuation; in downtrend = lower reliability

OUTPUT FORMAT:
Return AgentReport JSON with:
- signal: "bullish", "bearish", or "neutral"
- confidence: based on pattern quality and context
- reasoning: Detailed price action narrative identifying specific patterns
- supporting_evidence: Named patterns with candle indices
- contradicting_evidence: Conflicting patterns or structural concerns
- key_levels: {"resistance_1": x, "resistance_2": x, "support_1": x, "support_2": x}
- metadata: {"patterns_detected": [...], "structure_bias": "bullish/bearish/neutral", "key_pattern": "name"}
"""

    def analyze(self, state: HedgeFundState) -> AgentReport:
        symbol = state.get("symbol", "UNKNOWN")
        market_data = state.get("market_data", {})
        candles = market_data.get("candles", market_data.get("ohlcv", []))

        if not candles:
            return AgentReport(
                agent_id=self.agent_id,
                symbol=symbol,
                signal="neutral",
                confidence=0.1,
                reasoning="No candle data available for price action analysis.",
                supporting_evidence=[],
                contradicting_evidence=["No OHLCV data provided"],
                timestamp=self._now(),
            )

        # Format last 30 candles for analysis
        recent_candles = candles[-30:]
        candle_lines = []
        for i, c in enumerate(recent_candles):
            ts = c.get("timestamp", c.get("time", i))
            o, h, l, cl, v = (
                c.get("open", 0), c.get("high", 0), c.get("low", 0),
                c.get("close", 0), c.get("volume", 0)
            )
            body = abs(cl - o)
            wick_upper = h - max(o, cl)
            wick_lower = min(o, cl) - l
            color = "G" if cl >= o else "R"
            candle_lines.append(
                f"  [{i+1}] {ts} | {color} O={o:.4f} H={h:.4f} L={l:.4f} C={cl:.4f} V={v:.0f} "
                f"| body={body:.4f} up_wick={wick_upper:.4f} dn_wick={wick_lower:.4f}"
            )

        candle_text = "\n".join(candle_lines)
        current_price = recent_candles[-1].get("close", 0) if recent_candles else 0

        user_message = f"""PRICE ACTION ANALYSIS REQUEST
Symbol: {symbol}
Current Price: {current_price:.4f}
Timestamp: {self._now().isoformat()}
Total Candles Provided: {len(candles)} (showing last {len(recent_candles)})

=== OHLCV CANDLES (Last {len(recent_candles)}) ===
{candle_text}

=== TASK ===
Analyze the price action for {symbol}.
1. Identify all significant candlestick patterns in the last 10 candles
2. Map the key swing highs and lows (last 3 each)
3. Look for market structure breaks or false breaks
4. Assess the overall price action bias
Return your Price Action AgentReport JSON.
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
                reasoning=f"Price action analysis failed: {exc}",
                supporting_evidence=[],
                contradicting_evidence=["Analysis error"],
                timestamp=self._now(),
            )
