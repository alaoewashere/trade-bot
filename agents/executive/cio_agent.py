"""
agents/executive/cio_agent.py
=============================
Chief Investment Officer Agent.

Reviews ALL agent reports and makes the final strategic direction call.
Uses claude-opus-4-7 for the highest-quality synthesis across macro,
technical, and quantitative signals.
"""

from __future__ import annotations

import json
from typing import Any

from agents.base_agent import BaseAgent
from graph.state import AgentReport, HedgeFundState


class CIOAgent(BaseAgent):
    agent_id = "cio_agent"
    department = "executive"

    def __init__(self) -> None:
        super().__init__()
        # Override model to opus for executive-level synthesis
        self._agent_config["model"] = "claude-opus-4-7"
        self._agent_config["max_tokens"] = 8192

    def get_system_prompt(self) -> str:
        return """You are the Chief Investment Officer (CIO) of a quantitative hedge fund.
Your role is the highest-level synthesis and final strategic direction authority.

YOUR MANDATE:
You review the complete body of evidence from all departments — macro, technical, quantitative,
sentiment, options flow, on-chain, and risk — and determine whether a compelling, high-probability
trade opportunity exists. You are NOT a rubber stamp. You are the senior decision-maker who asks:
"What is the actual edge here?"

YOUR ANALYTICAL FRAMEWORK:

1. SIGNAL QUALITY ASSESSMENT
   - Count bullish vs bearish vs neutral agent signals
   - Weight by department: quant/statistical signals > technical signals > sentiment signals
   - Reject any setup where quant and macro contradict each other sharply
   - Require at least 3 independent confirming signals across different departments
   - Single-department consensus is insufficient — you need convergence

2. EDGE IDENTIFICATION
   - Ask explicitly: "What is the statistical or structural edge?"
   - Is this setup driven by a temporary inefficiency, a regime shift, or a structural factor?
   - What is the probability-weighted expected value of the trade?
   - Is the reward-to-risk ratio justified given the quality of the evidence?

3. MACRO ALIGNMENT
   - No trade opposes the dominant macro regime without exceptional justification
   - Rate environment, DXY trend, yield curve shape must be considered for any multi-day hold
   - Central bank stance is a veto-level factor for directional trades

4. RISK-REWARD DISCIPLINE
   - Minimum 2:1 RRR required for directional trades
   - Confidence must reflect both signal quality AND regime certainty
   - Acknowledge what would need to be true for this trade to fail

5. BEHAVIORAL SAFEGUARDS
   - You are never emotional, never anchored to prior positions
   - You do not chase trades after the entry window has passed
   - FOMO is not a signal. Regret is not a signal.
   - If signals are mixed or weak, the correct answer is NEUTRAL / NO_TRADE
   - "When in doubt, stay out" — capital preservation is paramount

OUTPUT FORMAT:
Return a JSON object matching the AgentReport schema with:
- signal: "bullish", "bearish", or "neutral"
- confidence: 0.0–1.0 (only above 0.7 if exceptional convergence)
- reasoning: A multi-paragraph CIO memo summarizing the investment thesis
- supporting_evidence: List of specific signals supporting the direction
- contradicting_evidence: List of signals arguing against, and why you discounted them
- key_levels: {"entry": x, "stop": x, "target": x}
- metadata: {"edge_description": "...", "signal_convergence_score": 0-10, "macro_aligned": bool}
"""

    def analyze(self, state: HedgeFundState) -> AgentReport:
        symbol = state.get("symbol", "UNKNOWN")
        market_data = state.get("market_data", {})
        analysis_reports = state.get("analysis_reports", {})
        timeframe = state.get("timeframe", "unknown")

        # Summarize all agent reports
        report_summaries = []
        bull_count = 0
        bear_count = 0
        neutral_count = 0
        for aid, report in analysis_reports.items():
            report_summaries.append(
                f"[{aid}] signal={report.signal} confidence={report.confidence:.2f} | {report.reasoning[:200]}"
            )
            if report.signal == "bullish":
                bull_count += 1
            elif report.signal == "bearish":
                bear_count += 1
            else:
                neutral_count += 1

        market_summary = self._format_market_data(market_data)
        reports_text = "\n".join(report_summaries) if report_summaries else "No agent reports yet."

        user_message = f"""CIO INVESTMENT COMMITTEE REVIEW
Symbol: {symbol}
Timeframe: {timeframe}
Timestamp: {self._now().isoformat()}

=== AGENT SIGNAL TALLY ===
Bullish: {bull_count} | Bearish: {bear_count} | Neutral: {neutral_count}

=== ALL AGENT REPORTS ===
{reports_text}

=== MARKET DATA SUMMARY ===
{market_summary}

=== YOUR TASK ===
As CIO, synthesize ALL the above. Identify the edge. Make the call.
Return your AgentReport JSON with your final investment thesis and direction.
Be rigorous. If you don't have high conviction, say NEUTRAL with low confidence.
"""

        try:
            result = self._call_claude(self.get_system_prompt(), user_message, AgentReport)
            # Ensure agent_id and timestamp are correct
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
                metadata={
                    **result.metadata,
                    "bull_count": bull_count,
                    "bear_count": bear_count,
                    "neutral_count": neutral_count,
                },
            )
        except Exception as exc:
            return AgentReport(
                agent_id=self.agent_id,
                symbol=symbol,
                signal="neutral",
                confidence=0.0,
                reasoning=f"CIO analysis failed: {exc}",
                supporting_evidence=[],
                contradicting_evidence=["Analysis error — defaulting to no position"],
                timestamp=self._now(),
            )
