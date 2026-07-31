"""
agents/security/emergency_bot.py
===================================
Emergency Bot Agent.

Can initiate kill switch activation, close all positions, and notify operators.
Monitors for anomalous behavior from state errors/warnings.
"""

from __future__ import annotations

from agents.base_agent import BaseAgent
from graph.state import AgentReport, HedgeFundState

# Emergency trigger thresholds
_MAX_DAILY_LOSS_PCT = 5.0       # Close all if daily P&L < -5%
_MAX_SINGLE_LOSS_PCT = 10.0    # Emergency alert if single position loss > 10%
_MAX_ERRORS_BEFORE_HALT = 5    # Halt after 5 system errors
_MAX_DRAWDOWN_PCT = 20.0       # Kill switch if drawdown exceeds 20%


class EmergencyBotAgent(BaseAgent):
    agent_id = "emergency_bot"
    department = "security"

    def get_system_prompt(self) -> str:
        return """You are the Emergency Bot for a quantitative hedge fund.

YOUR ROLE:
You are the fund's emergency response system. You monitor for catastrophic conditions
and have the authority to initiate emergency procedures: kill switch activation,
position closure, and operator notification. You are always running in the background,
scanning for conditions that require immediate action.

You operate on the principle: "When in doubt, protect capital first, ask questions later."

YOUR EMERGENCY MONITORING FRAMEWORK:

1. PORTFOLIO-LEVEL EMERGENCIES
   Trigger emergency close-all when:
   - Daily P&L < -5% of portfolio equity (catastrophic daily loss)
   - Total drawdown > 20% from peak (unacceptable drawdown)
   - Portfolio heat > 8% (excessive combined risk exposure)
   - Margin call warning from broker
   - Net liquidation value declining faster than expected

2. POSITION-LEVEL EMERGENCIES
   Trigger individual position emergency exit when:
   - Single position loss > 10% of portfolio equity
   - Position moving against thesis at 3× expected velocity
   - Position size has grown to >30% of portfolio (concentration risk)
   - Counter-party risk detected (broker issue, exchange hack)

3. SYSTEM-LEVEL EMERGENCIES
   Trigger system halt when:
   - 5 or more errors in state["errors"] list (system malfunction)
   - API connectivity issues (broker unreachable)
   - Database corruption or state inconsistency
   - Anomalous agent behavior (infinite loops, extreme values)
   - Security breach detected (unauthorized API calls)

4. MARKET-LEVEL EMERGENCIES
   Trigger precautionary risk reduction when:
   - VIX spike > 50% in a single day
   - Circuit breaker triggered on major exchange
   - Black swan news event (war declaration, major country default, bank run)
   - Exchange outage or liquidity crisis
   - Flash crash detected (price move > 10% in < 5 minutes)

5. ANOMALY DETECTION
   Flag anomalous behavior for review:
   - Price data showing impossible values (negative prices, zero prices)
   - Volume data showing 100× normal (data error?)
   - Agents returning contradictory signals with very high confidence simultaneously
   - Order fills at prices far from expected (slippage anomaly)
   - Duplicate order IDs or order book anomalies

6. EMERGENCY PROCEDURE HIERARCHY
   Level 1 — Alert Only (neutral signal):
   - System warning, no immediate action
   - Notify operator via logging
   - Flag in state["warnings"]

   Level 2 — Risk Reduction (neutral to bearish signal):
   - Reduce position sizes by 50%
   - Tighten all stop losses
   - No new positions until cleared

   Level 3 — Halt New Trades (bearish signal):
   - No new positions
   - Existing positions: tighten stops, prepare to exit
   - Notify operator immediately

   Level 4 — Close All Positions (strong bearish signal):
   - Exit all positions at market
   - Cancel all pending orders
   - Notify operator and await instructions

   Level 5 — Kill Switch (strongest bearish):
   - Everything in Level 4 PLUS:
   - Activate kill_switch in state
   - Revoke API keys
   - Emergency shutdown

7. RECOVERY CRITERIA
   Before clearing the emergency:
   - Root cause of emergency identified and documented
   - Risk parameters reviewed and updated if needed
   - Manual review and approval from senior trader/risk officer
   - System health check passed
   - Paper trading mode suggested for first day of recovery

OUTPUT FORMAT:
Return AgentReport JSON with:
- signal: "bullish" (all clear, no emergency), "neutral" (monitoring warnings, alert only), "bearish" (emergency active)
- confidence: 1.0 (emergency conditions are objective, not probabilistic)
- reasoning: Emergency assessment narrative identifying all monitored conditions
- supporting_evidence: Conditions that are normal/safe
- contradicting_evidence: Emergency conditions triggered
- key_levels: {"daily_pnl_pct": x, "max_drawdown_pct": x, "portfolio_heat_pct": x, "error_count": x}
- metadata: {"emergency_level": 0-5, "action_required": "none/alert/reduce/halt/close_all/kill_switch", "trigger_conditions": [...], "kill_switch_recommendation": bool}
"""

    def analyze(self, state: HedgeFundState) -> AgentReport:
        symbol = state.get("symbol", "UNKNOWN")
        market_data = state.get("market_data", {})
        errors = state.get("errors", [])
        warnings = state.get("warnings", [])
        kill_switch = state.get("kill_switch_active", False)
        circuit_breaker = state.get("circuit_breaker_tripped", False)

        # Portfolio data
        portfolio = market_data.get("portfolio", {})
        daily_pnl_pct = portfolio.get("daily_pnl_pct", portfolio.get("daily_return_pct", 0))
        current_drawdown = portfolio.get("current_drawdown_pct", 0)
        portfolio_heat = portfolio.get("portfolio_heat_pct", 0)
        total_equity = portfolio.get("total_equity_usd", 0)

        # Market conditions
        indicators = market_data.get("indicators", {})
        vix = market_data.get("vix", indicators.get("vix", indicators.get("VIX", 0)))
        vix_change_pct = market_data.get("vix_change_pct", 0)

        emergency_triggers = []
        warnings_list = []
        emergency_level = 0

        # Check 1: Daily loss limit
        if daily_pnl_pct <= -_MAX_DAILY_LOSS_PCT:
            emergency_triggers.append(f"DAILY_LOSS_LIMIT: {daily_pnl_pct:.2f}% (limit: -{_MAX_DAILY_LOSS_PCT}%)")
            emergency_level = max(emergency_level, 4)
        elif daily_pnl_pct <= -3.0:
            warnings_list.append(f"Daily loss approaching limit: {daily_pnl_pct:.2f}%")
            emergency_level = max(emergency_level, 2)

        # Check 2: Max drawdown
        if current_drawdown >= _MAX_DRAWDOWN_PCT:
            emergency_triggers.append(f"MAX_DRAWDOWN_EXCEEDED: {current_drawdown:.2f}% (limit: {_MAX_DRAWDOWN_PCT}%)")
            emergency_level = max(emergency_level, 5)  # Kill switch level
        elif current_drawdown >= 15.0:
            warnings_list.append(f"Drawdown elevated: {current_drawdown:.2f}%")
            emergency_level = max(emergency_level, 2)

        # Check 3: Portfolio heat
        if portfolio_heat >= 8.0:
            emergency_triggers.append(f"PORTFOLIO_HEAT_CRITICAL: {portfolio_heat:.2f}% (limit: 8%)")
            emergency_level = max(emergency_level, 3)
        elif portfolio_heat >= 6.0:
            warnings_list.append(f"Portfolio heat elevated: {portfolio_heat:.2f}%")
            emergency_level = max(emergency_level, 1)

        # Check 4: System errors
        error_count = len(errors)
        if error_count >= _MAX_ERRORS_BEFORE_HALT:
            emergency_triggers.append(f"SYSTEM_ERRORS: {error_count} errors (limit: {_MAX_ERRORS_BEFORE_HALT})")
            emergency_level = max(emergency_level, 3)
        elif error_count >= 3:
            warnings_list.append(f"Multiple system errors: {error_count}")
            emergency_level = max(emergency_level, 1)

        # Check 5: Kill switch already active
        if kill_switch:
            emergency_triggers.append("KILL_SWITCH_ACTIVE: System already in emergency halt")
            emergency_level = max(emergency_level, 5)

        # Check 6: Circuit breaker
        if circuit_breaker:
            emergency_triggers.append("CIRCUIT_BREAKER_TRIPPED: Market circuit breaker active")
            emergency_level = max(emergency_level, 3)

        # Check 7: VIX spike
        if vix_change_pct >= 50:
            emergency_triggers.append(f"VIX_SPIKE: +{vix_change_pct:.1f}% today (extreme fear)")
            emergency_level = max(emergency_level, 2)
        elif vix and vix >= 50:
            emergency_triggers.append(f"VIX_EXTREME: VIX={vix:.1f} (panic territory)")
            emergency_level = max(emergency_level, 2)

        # Determine action and signal
        action_map = {
            0: "none",
            1: "alert",
            2: "reduce_risk",
            3: "halt_new_trades",
            4: "close_all",
            5: "kill_switch",
        }
        action = action_map.get(emergency_level, "none")
        kill_switch_recommendation = emergency_level >= 5

        if emergency_level == 0:
            signal = "bullish"
            confidence = 1.0
            reasoning = (
                f"ALL CLEAR: No emergency conditions detected for {symbol}. "
                f"Daily P&L: {daily_pnl_pct:.2f}%, Drawdown: {current_drawdown:.2f}%, "
                f"Portfolio Heat: {portfolio_heat:.2f}%, System Errors: {error_count}. "
                f"System operating normally."
            )
        elif emergency_level <= 2:
            signal = "neutral"
            confidence = 1.0
            reasoning = (
                f"WARNING LEVEL {emergency_level}: Non-critical alerts detected. "
                f"Warnings: {warnings_list}. "
                f"Action: {action}. Monitor closely."
            )
        else:
            signal = "bearish"
            confidence = 1.0
            triggers_str = "; ".join(emergency_triggers)
            reasoning = (
                f"EMERGENCY LEVEL {emergency_level} TRIGGERED for system. "
                f"Triggers: {triggers_str}. "
                f"Required action: {action.upper()}. "
                f"Kill switch recommendation: {kill_switch_recommendation}."
            )

        return AgentReport(
            agent_id=self.agent_id,
            symbol=symbol,
            signal=signal,
            confidence=confidence,
            reasoning=reasoning,
            supporting_evidence=[
                f"Daily P&L: {daily_pnl_pct:.2f}% (within limit)",
                f"Drawdown: {current_drawdown:.2f}% (within limit)",
                f"Portfolio heat: {portfolio_heat:.2f}%",
            ] if emergency_level == 0 else [],
            contradicting_evidence=[f"TRIGGER: {t}" for t in emergency_triggers] + [f"WARNING: {w}" for w in warnings_list],
            key_levels={
                "daily_pnl_pct": daily_pnl_pct,
                "max_drawdown_pct": current_drawdown,
                "portfolio_heat_pct": portfolio_heat,
                "error_count": float(error_count),
            },
            timestamp=self._now(),
            metadata={
                "emergency_level": emergency_level,
                "action_required": action,
                "trigger_conditions": emergency_triggers,
                "warnings": warnings_list,
                "kill_switch_recommendation": kill_switch_recommendation,
            },
        )
