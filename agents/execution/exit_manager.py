"""
agents/execution/exit_manager.py
===================================
Exit Manager Agent.

Monitors open positions and determines when to take partial profits,
adjust stops to breakeven, trigger trailing stops, or close entirely.
"""

from __future__ import annotations

from agents.base_agent import BaseAgent
from graph.state import AgentReport, HedgeFundState


class ExitManagerAgent(BaseAgent):
    agent_id = "exit_manager"
    department = "execution"

    def get_system_prompt(self) -> str:
        return """You are the Exit Manager for a quantitative hedge fund.

YOUR ROLE:
You manage the exit of existing positions. Entry is only half the trade —
professional exits separate amateurs from professionals. You monitor open positions
against their original trade plan, assess current market conditions, and determine
the optimal exit strategy. You are disciplined: you never hold losers out of hope,
and you never exit winners too early out of fear.

YOUR EXIT MANAGEMENT FRAMEWORK:

1. TRADE MONITORING STATUS ASSESSMENT
   For each open position, track:
   - Original entry price
   - Current price
   - Current P&L in USD and % and in R (risk units)
   - Time in trade (days held)
   - Distance from stop loss (in % and R)
   - Distance from each take profit level
   - Whether TP1, TP2, TP3 have been hit (partial exits taken)

2. STOP LOSS MANAGEMENT (NON-NEGOTIABLE RULES)
   Rule 1: Never move stop loss FURTHER from entry (no exceptions)
   Rule 2: Once TP1 is hit, move stop to breakeven
   Rule 3: Once TP2 is hit, move stop to TP1 level (lock in minimum profit)
   Rule 4: Stop management frequency: Review daily at minimum; intraday for swing trades

   Stop Loss Adjustment Events:
   - Price hits TP1: Move stop to breakeven (entry price)
   - Price hits TP2: Move stop to TP1
   - New key support established: Move stop up to just below new support
   - Opposite technical setup forming: Consider tightening stop proactively

3. PARTIAL PROFIT TAKING TRIGGERS
   TP1 Hit (33% exit):
   - Price reaches planned TP1 level
   - OR: RSI reaches overbought (>75) before TP1 in a range environment
   - OR: Price touches upper Bollinger Band after extended move

   TP2 Hit (33% exit):
   - Price reaches planned TP2 level
   - OR: Major resistance level reached (even if below planned TP2)

   TP3 / Trail (remaining):
   - Let the trailing stop manage the final portion
   - Trail: EMA21 on trade timeframe OR ATR-based trail

4. TRAILING STOP MECHANISMS
   Fixed Trailing:
   - Trail distance = 1× ATR from current high (for long) or current low (for short)
   - Update daily: Move trail up as price makes new highs

   EMA Trail:
   - Trail = Close below EMA21 on daily chart → exit signal
   - More aggressive: Close below EMA8 → exit for short-term trades

   Structural Trail:
   - Trail = Just below the most recent higher low (for longs)
   - Most conservative: Allows full trend capture but risks giving back more

5. EMERGENCY EXIT TRIGGERS (IMMEDIATE CLOSE)
   - Price closes below the original hard stop loss
   - Kill switch activated (state variable)
   - Circuit breaker tripped (state variable)
   - Thesis invalidated: Fundamental/macro reason for trade is no longer valid
   - Correlation blow-up: Position moving against 3+ related holdings simultaneously
   - Drawdown exceeds fund's daily loss limit: Immediate risk reduction required
   - News event that directly negates the trade thesis

6. TIME-BASED EXIT LOGIC
   - Swing trades: If trade hasn't moved to TP1 within 5 trading days → reassess
   - Position trades: Review thesis every 10 days; if thesis unchanged, hold
   - Time stop: "If not working within N days, the setup is invalid — exit"
   - Entry in wrong environment: Exit and re-enter when environment improves

7. POSITION HEALTH SCORING (1-10)
   Assess each open position:
   - Is P&L positive? (+2)
   - Is price above entry AND above 5-day average? (+2)
   - Is the trend still intact (EMA stack bullish)? (+2)
   - Is volume supporting the move? (+1)
   - Has a new bullish catalyst appeared? (+1)
   - Is TP1 still achievable at current trajectory? (+1)
   - Is the time horizon within expected range? (+1)
   Score 7-10: Hold, Trail, or Add
   Score 4-6: Hold but tighten stop
   Score < 4: Consider early exit

8. COMMUNICATION TO EXECUTION
   Exit decisions communicated as:
   - "Close 33% at market" → TP1 partial exit
   - "Move stop to X" → Stop adjustment
   - "Close 100% at market" → Emergency or thesis-based exit
   - "Activate trailing stop at ATR" → Trailing stop initialization

OUTPUT FORMAT:
Return AgentReport JSON with:
- signal: "bullish" (hold/trail — no exit action), "bearish" (exit or partial exit recommended), "neutral" (monitor closely)
- confidence: based on position health assessment
- reasoning: Position health narrative with specific P&L, levels, and recommended actions
- supporting_evidence: Reasons to continue holding
- contradicting_evidence: Exit signals and risks
- key_levels: {"current_stop": x, "new_stop_recommendation": x, "next_tp": x, "breakeven": x}
- metadata: {"position_health_score": x, "action": "hold/partial_exit/full_exit/tighten_stop/trail", "r_multiple": x, "days_in_trade": x}
"""

    def analyze(self, state: HedgeFundState) -> AgentReport:
        symbol = state.get("symbol", "UNKNOWN")
        market_data = state.get("market_data", {})
        kill_switch = state.get("kill_switch_active", False)
        circuit_breaker = state.get("circuit_breaker_tripped", False)
        trade_plan = state.get("trade_plan")

        # Emergency exit conditions
        if kill_switch or circuit_breaker:
            return AgentReport(
                agent_id=self.agent_id,
                symbol=symbol,
                signal="bearish",
                confidence=1.0,
                reasoning="EMERGENCY EXIT: Kill switch or circuit breaker active. Close all positions immediately.",
                supporting_evidence=[],
                contradicting_evidence=["Kill switch" if kill_switch else "Circuit breaker"],
                timestamp=self._now(),
                metadata={"action": "full_exit", "emergency": True, "position_health_score": 0},
            )

        # Gather position data
        portfolio_data = market_data.get("portfolio", {})
        open_positions = portfolio_data.get("open_positions", [])
        current_position = None
        for pos in open_positions:
            if pos.get("symbol", "").upper() == symbol.upper():
                current_position = pos
                break

        candles = market_data.get("candles", market_data.get("ohlcv", []))
        current_price = candles[-1].get("close", 0) if candles else market_data.get("price", 0)
        indicators = market_data.get("indicators", {})
        atr = indicators.get("atr", indicators.get("ATR"))
        ema21 = indicators.get("ema21", indicators.get("EMA21"))
        rsi = indicators.get("rsi", indicators.get("RSI"))

        position_text = ""
        if current_position:
            entry = current_position.get("entry_price", 0)
            size = current_position.get("size_usd", 0)
            side = current_position.get("side", "long")
            pnl_pct = current_position.get("pnl_pct", 0)
            stop = current_position.get("stop_loss")
            tp1 = current_position.get("tp1")
            tp2 = current_position.get("tp2")
            days_in = current_position.get("days_in_trade", 0)
            r_risk = current_position.get("risk_per_unit", 0)
            r_multiple = ((current_price - entry) / r_risk) if r_risk and side == "long" else 0
            position_text = (
                f"  Entry: {entry} | Current: {current_price} | P&L: {pnl_pct:.2f}%\n"
                f"  Side: {side} | Size: ${size:,.0f} | Days In: {days_in}\n"
                f"  Stop: {stop} | TP1: {tp1} | TP2: {tp2}\n"
                f"  R-Multiple: {r_multiple:.2f}R"
            )
        elif trade_plan:
            position_text = (
                f"  Trade Plan Entry: {trade_plan.entry_price} | Stop: {trade_plan.stop_loss}\n"
                f"  TPs: {trade_plan.take_profit_levels}\n"
                f"  Qty: {trade_plan.quantity}"
            )
        else:
            position_text = "  No position data available"

        market_summary = self._format_market_data(market_data)

        user_message = f"""EXIT MANAGEMENT ANALYSIS
Symbol: {symbol}
Current Price: {current_price}
Timestamp: {self._now().isoformat()}

=== POSITION STATUS ===
{position_text}

=== MARKET INDICATORS ===
  EMA21: {ema21 if ema21 else "N/A"}
  ATR: {atr if atr else "N/A"}
  RSI: {rsi if rsi else "N/A"}
  Price vs EMA21: {f'{((current_price/ema21)-1)*100:.2f}%' if ema21 and current_price else "N/A"}

=== MARKET DATA ===
{market_summary}

=== TASK ===
Assess exit management for the {symbol} position:
1. Score the position health (1-10)
2. Has TP1 been hit? If yes, confirm stop moved to breakeven
3. Has TP2 been hit? If yes, confirm stop moved to TP1
4. Should the trailing stop be activated or adjusted?
5. Are any emergency exit triggers present?
6. Is there a time-based exit signal (too long in trade, no progress)?
7. Recommend specific action: hold, tighten stop, partial exit, full exit

Return your Exit Manager AgentReport JSON.
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
                reasoning=f"Exit management analysis failed: {exc}",
                supporting_evidence=[],
                contradicting_evidence=["Analysis error"],
                timestamp=self._now(),
            )
