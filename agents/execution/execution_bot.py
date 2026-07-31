"""
agents/execution/execution_bot.py
====================================
Execution Bot Agent.

The ONLY agent that interfaces with broker APIs (via the brokers/ module).
Will NOT signal unless ALL safety gates are passed:
  1. human_approval_status == "approved"
  2. Kill switch is clear
  3. Circuit breaker is clear
"""

from __future__ import annotations

from agents.base_agent import BaseAgent
from graph.state import AgentReport, HedgeFundState


class ExecutionBotAgent(BaseAgent):
    agent_id = "execution_bot"
    department = "execution"

    def get_system_prompt(self) -> str:
        return """You are the Execution Bot for a quantitative hedge fund.

YOUR ROLE:
You are the final gate before any real money is deployed. You review the complete
trade plan and verify that all safety conditions are met before signaling that
execution can proceed. You are not an analyst — you are a gate-keeper and
a quality-control agent for the execution process.

CRITICAL SAFETY REQUIREMENTS (ALL MUST PASS):
1. Human approval status MUST be "approved" — no exceptions
2. Kill switch MUST be inactive (kill_switch_active = False)
3. Circuit breaker MUST be clear (circuit_breaker_tripped = False)
4. News blackout MUST be inactive (news_blackout_active = False) — if trade is news-sensitive
5. CRO signal MUST be bullish (risk approved)
6. Trade plan MUST be present and complete
7. Security bot MUST have cleared the trade (no flags)

YOUR EXECUTION REVIEW FRAMEWORK:

1. GATE VERIFICATION (Sequential)
   Gate 1 — Human Approval: Is human_approval_status == "approved"?
     → If "pending": Return neutral, wait
     → If "rejected" or "expired": Return bearish, abort
     → If "approved": Proceed to Gate 2

   Gate 2 — Kill Switch: Is kill_switch_active == True?
     → If True: Return bearish, STOP (kill switch overrides everything)
     → If False: Proceed to Gate 3

   Gate 3 — Circuit Breaker: Is circuit_breaker_tripped == True?
     → If True: Return bearish, HALT (circuit breaker triggered)
     → If False: Proceed to Gate 4

   Gate 4 — News Blackout: Is news_blackout_active == True?
     → If True: Return neutral (wait for blackout to clear)
     → If False: Proceed to Gate 5

   Gate 5 — CRO Approval: Did CRO agent return bullish signal?
     → If not bullish: Return bearish (risk rejected)
     → If bullish: Proceed to Gate 6

   Gate 6 — Trade Plan Complete: Is trade_plan populated?
     → If missing: Return neutral (cannot execute without plan)
     → If present: Proceed to Gate 7

   Gate 7 — Security Clearance: Did security_bot return bullish?
     → If not: Return bearish (security block)
     → If bullish: ALL GATES PASSED → Return bullish

2. TRADE PLAN COMPLETENESS VERIFICATION
   Before executing, verify the trade plan contains:
   - Symbol (matches current symbol)
   - Direction (LONG or SHORT)
   - Entry type (market/limit/stop_limit)
   - Quantity (units, not just USD)
   - Stop loss price
   - At least one take profit level
   - Broker specified
   These fields must all be non-None.

3. ORDER VALIDATION
   Review the trade plan for sanity:
   - Is the symbol on the approved trading whitelist? (check security_bot report)
   - Is the position size within limits? (check CRO report)
   - Is the stop loss in the correct direction? (long: stop below entry; short: stop above)
   - Is the take profit in the correct direction? (long: target above entry; short: below)
   - Is the RRR at least 1.5:1? (minimum acceptable)

4. EXECUTION TIMING ASSESSMENT
   - Is the current time appropriate for execution?
   - Is there a pending news event within 30 minutes?
   - Is the market open and liquid?
   - Is the spread currently acceptable?

5. BROKER API HANDOFF
   When all gates are passed:
   - Signal: "bullish" (execution approved, broker module will handle the actual order)
   - The ACTUAL ORDER PLACEMENT is done by the execution subgraph using brokers/ module
   - This agent only returns the approval signal — it does NOT call broker APIs directly
   - The execution report will be populated by the execution subgraph

OUTPUT FORMAT:
Return AgentReport JSON with:
- signal: "bullish" (all gates passed, execute), "bearish" (blocked — do not execute), "neutral" (pending approval or incomplete plan)
- confidence: 1.0 if gates clearly pass/fail; lower if ambiguous
- reasoning: Gate-by-gate verification narrative
- supporting_evidence: Gates that passed
- contradicting_evidence: Gates that failed (blocking reasons)
- key_levels: {} (execution bot doesn't set price levels — they come from trade plan)
- metadata: {"gates_passed": [...], "gates_failed": [...], "human_approval": "...", "kill_switch": bool, "circuit_breaker": bool, "execution_ready": bool}
"""

    def analyze(self, state: HedgeFundState) -> AgentReport:
        symbol = state.get("symbol", "UNKNOWN")
        human_approval = state.get("human_approval_status")
        kill_switch = state.get("kill_switch_active", False)
        circuit_breaker = state.get("circuit_breaker_tripped", False)
        news_blackout = state.get("news_blackout_active", False)
        trade_plan = state.get("trade_plan")
        analysis_reports = state.get("analysis_reports", {})

        gates_passed = []
        gates_failed = []

        # Gate 1 — Human Approval
        if human_approval == "approved":
            gates_passed.append("human_approval")
        elif human_approval == "pending":
            return AgentReport(
                agent_id=self.agent_id,
                symbol=symbol,
                signal="neutral",
                confidence=0.9,
                reasoning="WAITING: Human approval is pending. No execution until approved.",
                supporting_evidence=[],
                contradicting_evidence=["Human approval pending"],
                timestamp=self._now(),
                metadata={"gates_passed": [], "gates_failed": ["human_approval_pending"], "execution_ready": False},
            )
        else:
            gates_failed.append(f"human_approval ({human_approval})")

        # Gate 2 — Kill Switch
        if kill_switch:
            gates_failed.append("kill_switch_active")
        else:
            gates_passed.append("kill_switch_clear")

        # Gate 3 — Circuit Breaker
        if circuit_breaker:
            gates_failed.append("circuit_breaker_tripped")
        else:
            gates_passed.append("circuit_breaker_clear")

        # Gate 4 — News Blackout
        if news_blackout:
            gates_failed.append("news_blackout_active")
        else:
            gates_passed.append("news_blackout_clear")

        # Gate 5 — CRO Approval
        cro_approved = False
        if "cro_agent" in analysis_reports:
            cro_report = analysis_reports["cro_agent"]
            if cro_report.signal == "bullish":
                gates_passed.append("cro_approved")
                cro_approved = True
            else:
                gates_failed.append(f"cro_rejected ({cro_report.signal})")
        else:
            gates_failed.append("cro_not_run")

        # Gate 6 — Trade Plan Present
        if trade_plan is not None:
            gates_passed.append("trade_plan_present")
        else:
            gates_failed.append("trade_plan_missing")

        # Gate 7 — Security Bot
        security_cleared = False
        if "security_bot" in analysis_reports:
            sec_report = analysis_reports["security_bot"]
            if sec_report.signal == "bullish":
                gates_passed.append("security_cleared")
                security_cleared = True
            else:
                gates_failed.append("security_blocked")
        else:
            gates_failed.append("security_bot_not_run")

        # Final determination
        execution_ready = len(gates_failed) == 0

        if execution_ready:
            return AgentReport(
                agent_id=self.agent_id,
                symbol=symbol,
                signal="bullish",
                confidence=1.0,
                reasoning=(
                    f"ALL EXECUTION GATES PASSED for {symbol}. "
                    f"Human approved, kill switch clear, circuit breaker clear, "
                    f"news blackout clear, CRO approved, trade plan present, security cleared. "
                    f"Execution subgraph is authorized to proceed with broker order placement."
                ),
                supporting_evidence=[f"Gate passed: {g}" for g in gates_passed],
                contradicting_evidence=[],
                timestamp=self._now(),
                metadata={
                    "gates_passed": gates_passed,
                    "gates_failed": [],
                    "human_approval": human_approval,
                    "kill_switch": kill_switch,
                    "circuit_breaker": circuit_breaker,
                    "execution_ready": True,
                },
            )
        else:
            failed_summary = "; ".join(gates_failed)
            return AgentReport(
                agent_id=self.agent_id,
                symbol=symbol,
                signal="bearish",
                confidence=1.0,
                reasoning=(
                    f"EXECUTION BLOCKED for {symbol}. "
                    f"Failed gates: {failed_summary}. "
                    f"No order will be placed until all gates pass."
                ),
                supporting_evidence=[f"Gate passed: {g}" for g in gates_passed],
                contradicting_evidence=[f"Gate FAILED: {g}" for g in gates_failed],
                timestamp=self._now(),
                metadata={
                    "gates_passed": gates_passed,
                    "gates_failed": gates_failed,
                    "human_approval": human_approval,
                    "kill_switch": kill_switch,
                    "circuit_breaker": circuit_breaker,
                    "execution_ready": False,
                },
            )
