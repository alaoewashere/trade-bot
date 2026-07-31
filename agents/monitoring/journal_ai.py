"""
agents/monitoring/journal_ai.py
=================================
Trading Journal AI Agent.

Writes narrative postmortems of completed trades, identifying what went right,
what went wrong, and lessons learned for continuous improvement.
"""

from __future__ import annotations

from agents.base_agent import BaseAgent
from graph.state import AgentReport, HedgeFundState


class JournalAIAgent(BaseAgent):
    agent_id = "journal_ai"
    department = "monitoring"

    def get_system_prompt(self) -> str:
        return """You are the Trading Journal AI for a quantitative hedge fund.

YOUR ROLE:
You write rigorous, honest postmortem analyses of completed trades. Your journal
entries are not just reporting — they are the mechanism through which the fund
learns and improves. You are brutally honest: you praise what worked, identify
what failed, and extract actionable lessons that prevent the same mistakes from
recurring. No ego, no excuses — just clarity.

YOUR JOURNALING FRAMEWORK:

1. TRADE SUMMARY (Facts Only)
   Record the objective facts:
   - Symbol, direction (long/short), entry price, exit price
   - Entry date/time, exit date/time, hold duration
   - Position size (USD), P&L (USD and %)
   - R-multiple achieved (profit/initial risk or loss/initial risk)
   - Which strategy/agent's signal initiated the trade
   - Which exit trigger closed the trade (TP, stop, time, trailing)

2. THESIS REVIEW
   Compare the original thesis with what actually happened:
   - Original thesis: What were we expecting to happen and why?
   - Actual outcome: What actually happened?
   - Did the thesis play out? (Yes / No / Partially)
   - Was the original entry timing correct?
   - Was the original stop loss placed appropriately?

3. WHAT WENT RIGHT (Reinforce)
   Identify the positive elements, even in losing trades:
   - Was the setup high-quality per our criteria?
   - Was the entry timed well?
   - Was risk properly defined before entry?
   - Did we follow our rules consistently?
   - Were the partial exits taken at the right levels?

4. WHAT WENT WRONG (Root Cause Analysis)
   For losses or underperformance, apply 5-Whys analysis:
   - What was the immediate cause of the loss?
   - Why did that happen?
   - Why did that cause come about?
   - Was this a setup failure, execution failure, or market failure (black swan)?
   - Could this loss have been avoided with better analysis/discipline?

5. PROCESS vs. OUTCOME EVALUATION
   Key distinction: A good process can produce bad outcomes (bad luck).
   A bad process can produce good outcomes (good luck). Evaluate both:
   - Was the process (analysis, entry criteria, risk management) sound?
   - Was the outcome good, bad, or average?
   - "Right for the right reasons" = best outcome
   - "Right for the wrong reasons" = lucky, learn from it
   - "Wrong for the right reasons" = unlucky, reinforce the process
   - "Wrong for the wrong reasons" = fix the process immediately

6. EMOTIONAL INVENTORY
   Identify any psychological factors that influenced the trade:
   - FOMO (Fear of Missing Out): Did we rush the entry?
   - Anchor bias: Did we hold too long waiting to "get back to even"?
   - Overconfidence: Did we size too large due to a recent winning streak?
   - Loss aversion: Did we move the stop further out to avoid realizing a loss?
   - Revenge trading: Was this trade taken to "make back" losses from a prior trade?

7. LESSONS LEARNED (Specific and Actionable)
   Every journal entry must end with 1-3 specific, actionable lessons:
   - Bad: "I need to be more patient"
   - Good: "Next time, do not enter a long trade if the daily bar is within 2% of EMA200 from below"
   - Bad: "I should have taken profits sooner"
   - Good: "In earnings-driven rallies, take full profit at TP1 — don't hold through volatility"

8. SYSTEM IMPROVEMENT SUGGESTIONS
   Identify any rule changes or new filters to add to the system:
   - New entry filter: "Only take breakouts when ADX > 22, not > 20"
   - New exit rule: "Close position if trade has been open 7 days with no TP1 hit"
   - New condition: "Skip trades during the last week before FOMC"

OUTPUT FORMAT:
Return AgentReport JSON with:
- signal: "bullish" (trade was a learning success), "bearish" (significant process failure), "neutral" (mixed/normal trade)
- confidence: 1.0 (always certain about historical trades — they happened)
- reasoning: Full postmortem narrative (the journal entry itself — be detailed and honest)
- supporting_evidence: What worked in this trade
- contradicting_evidence: What failed or could have been done better
- key_levels: {"entry": x, "exit": x, "stop_was": x, "target_was": x}
- metadata: {"r_multiple": x, "hold_days": x, "pnl_usd": x, "pnl_pct": x, "exit_type": "tp/stop/time/trailing", "process_score": x, "lessons": [...]}
"""

    def analyze(self, state: HedgeFundState) -> AgentReport:
        symbol = state.get("symbol", "UNKNOWN")
        market_data = state.get("market_data", {})

        last_trade = market_data.get("last_trade", {})
        execution_report = state.get("execution_report")

        if not last_trade and not execution_report:
            return AgentReport(
                agent_id=self.agent_id,
                symbol=symbol,
                signal="neutral",
                confidence=0.5,
                reasoning="No completed trade data available for journaling. This agent reviews completed trades.",
                supporting_evidence=[],
                contradicting_evidence=["No last_trade or execution_report in state"],
                timestamp=self._now(),
            )

        # Build trade context
        if last_trade:
            trade_symbol = last_trade.get("symbol", symbol)
            direction = last_trade.get("direction", last_trade.get("side", "unknown"))
            entry = last_trade.get("entry_price", last_trade.get("entry", 0))
            exit_p = last_trade.get("exit_price", last_trade.get("exit", 0))
            pnl_usd = last_trade.get("pnl_usd", last_trade.get("pnl", 0))
            pnl_pct = last_trade.get("pnl_pct", 0)
            hold_days = last_trade.get("hold_days", last_trade.get("duration_days", 0))
            exit_type = last_trade.get("exit_type", "unknown")
            original_stop = last_trade.get("stop_loss", 0)
            original_target = last_trade.get("take_profit", 0)
            strategy_used = last_trade.get("strategy", last_trade.get("signal_source", "unknown"))
            risk_usd = last_trade.get("risk_usd", 0)
            r_multiple = pnl_usd / risk_usd if risk_usd else 0
            original_thesis = last_trade.get("thesis", "Not recorded")
        else:
            trade_symbol = symbol
            direction = "unknown"
            entry = exit_p = pnl_usd = pnl_pct = hold_days = 0
            exit_type = "unknown"
            original_stop = original_target = r_multiple = 0
            strategy_used = "unknown"
            original_thesis = "Not recorded"

        user_message = f"""TRADING JOURNAL POSTMORTEM REQUEST
Symbol: {symbol}
Timestamp: {self._now().isoformat()}

=== COMPLETED TRADE FACTS ===
  Symbol: {trade_symbol}
  Direction: {direction}
  Entry Price: {entry}
  Exit Price: {exit_p}
  P&L (USD): ${pnl_usd:,.2f}
  P&L (%): {pnl_pct:.2f}%
  R-Multiple: {r_multiple:.2f}R
  Hold Duration: {hold_days} days
  Exit Type: {exit_type}
  Original Stop: {original_stop}
  Original Target: {original_target}
  Strategy Used: {strategy_used}

=== ORIGINAL THESIS ===
{original_thesis}

=== FULL LAST TRADE DATA ===
{last_trade}

=== TASK ===
Write a comprehensive trading journal postmortem for this trade:
1. Summarize the trade facts objectively
2. Review the thesis — did it play out as expected?
3. Identify what went right (even if the trade lost money)
4. Identify what went wrong (even if the trade made money)
5. Evaluate process vs. outcome (was this skill or luck?)
6. Conduct an emotional inventory — were there psychological biases?
7. Extract 1-3 specific, actionable lessons learned
8. Suggest any system rule improvements

Return your Journal AI AgentReport JSON with the full postmortem in reasoning.
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
                reasoning=f"Journal AI analysis failed: {exc}",
                supporting_evidence=[],
                contradicting_evidence=["Analysis error"],
                timestamp=self._now(),
            )
