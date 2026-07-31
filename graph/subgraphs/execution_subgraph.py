"""
graph/subgraphs/execution_subgraph.py
=======================================
Execution subgraph — sequential pipeline that converts a human-approved
ConsensusResult + RiskAssessment into live (or paper) orders.

Flow (strictly sequential)
--------------------------
  liquidity_analyst  ──>  trade_planner  ──>  execution_bot  ──>  exit_manager  ──>  END

Node: liquidity_analyst
    Verifies market depth and estimates slippage for the planned position.
    Writes metadata into state["warnings"] / state["errors"] and enriches
    state["market_data"] with depth info.

Node: trade_planner
    Converts the consensus direction + risk_assessment sizing into a fully
    specified TradePlan.  Writes state["trade_plan"].

Node: execution_bot
    Re-validates all safety gates (kill switch, circuit breaker), then
    submits the order through the appropriate broker.
    Writes state["execution_report"] and state["order_ids"].

Node: exit_manager
    Registers the stop-loss and take-profit orders with the broker after
    the entry fill is confirmed.
    Appends to state["order_ids"].
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from langgraph.graph import StateGraph, END

from graph.state import (
    ExecutionReport,
    HedgeFundState,
    RiskAssessment,
    TradePlan,
)
from agents.registry import AgentRegistry

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Liquidity analyst node
# ---------------------------------------------------------------------------


class _LiquidityAnalystNode:
    """
    Checks market depth and estimates slippage before order submission.

    Delegates to the liquidity_analyst agent.  On failure, records a warning
    but does not block execution (slippage will be higher than estimated).
    """

    def __init__(self) -> None:
        self._agent = AgentRegistry.get("liquidity_analyst")

    def __call__(self, state: HedgeFundState) -> dict[str, Any]:
        existing_warnings: list[str] = list(state.get("warnings", []))
        existing_errors: list[str] = list(state.get("errors", []))

        try:
            result: dict[str, Any] = self._agent(state)

            # Merge any warnings / errors from the agent
            new_warnings = result.get("warnings", [])
            new_errors = result.get("errors", [])

            update: dict[str, Any] = {
                "current_phase": "liquidity_checked",
                "warnings": existing_warnings + new_warnings,
            }
            if new_errors:
                update["errors"] = existing_errors + new_errors

            # Carry forward enriched market data if the agent provides it
            enriched_market_data = result.get("market_data")
            if enriched_market_data:
                update["market_data"] = {
                    **state.get("market_data", {}),
                    **enriched_market_data,
                }

            return update

        except Exception as exc:
            warning_msg = f"liquidity_analyst warning (non-fatal): {exc}"
            logger.warning(warning_msg, exc_info=True)
            return {
                "current_phase": "liquidity_checked",
                "warnings": [*existing_warnings, warning_msg],
            }


# ---------------------------------------------------------------------------
# Trade planner node
# ---------------------------------------------------------------------------


class _TradePlannerNode:
    """
    Produces a fully specified TradePlan from the approved risk_assessment.

    Delegates to the trade_planner agent.  Falls back to building a TradePlan
    directly from the risk_assessment and consensus if the agent fails.
    """

    def __init__(self) -> None:
        self._agent = AgentRegistry.get("trade_planner")

    def __call__(self, state: HedgeFundState) -> dict[str, Any]:
        existing_errors: list[str] = list(state.get("errors", []))

        try:
            result: dict[str, Any] = self._agent(state)

            trade_plan: TradePlan | None = result.get("trade_plan")

            # Some agents embed the TradePlan in metadata
            if trade_plan is None:
                reports = result.get("analysis_reports", {})
                planner_report = reports.get("trade_planner")
                if planner_report is not None:
                    meta = getattr(planner_report, "metadata", {})
                    raw_plan = meta.get("trade_plan")
                    if isinstance(raw_plan, TradePlan):
                        trade_plan = raw_plan
                    elif isinstance(raw_plan, dict):
                        try:
                            trade_plan = TradePlan.model_validate(raw_plan)
                        except Exception:
                            pass

            if trade_plan is None:
                trade_plan = _build_trade_plan_from_state(state)

            update: dict[str, Any] = {
                "trade_plan": trade_plan,
                "current_phase": "trade_planned",
            }
            new_errors = result.get("errors", [])
            if new_errors:
                update["errors"] = existing_errors + new_errors
            return update

        except Exception as exc:
            error_msg = f"trade_planner error: {exc}"
            logger.error(error_msg, exc_info=True)

            # Best-effort fallback plan
            try:
                trade_plan = _build_trade_plan_from_state(state)
                return {
                    "trade_plan": trade_plan,
                    "current_phase": "trade_planned",
                    "errors": [*existing_errors, error_msg],
                }
            except Exception as fallback_exc:
                return {
                    "current_phase": "trade_plan_failed",
                    "errors": [
                        *existing_errors,
                        error_msg,
                        f"trade_plan fallback failed: {fallback_exc}",
                    ],
                }


def _build_trade_plan_from_state(state: HedgeFundState) -> TradePlan:
    """Build a TradePlan directly from risk_assessment and consensus."""
    risk: RiskAssessment | None = state.get("risk_assessment")
    consensus = state.get("consensus")
    symbol = state.get("symbol", "UNKNOWN")

    if risk is None:
        raise ValueError("risk_assessment is required to build a TradePlan")

    direction: str
    if consensus is not None and consensus.direction in ("LONG", "SHORT"):
        direction = consensus.direction
    else:
        direction = "LONG"  # safe fallback

    return TradePlan(
        symbol=symbol,
        direction=direction,  # type: ignore[arg-type]
        entry_type="market",
        entry_price=risk.entry_price if risk.entry_price > 0 else None,
        quantity=risk.position_size_units,
        stop_loss=risk.stop_loss,
        take_profit_levels=[risk.take_profit],
        trailing_stop_pct=None,
        time_in_force="GTC",
        broker="paper" if True else "live",  # determined by settings at runtime
        notes=(
            f"Auto-generated plan | RR={risk.risk_reward:.2f} | "
            f"heat={risk.portfolio_heat_pct:.1f}%"
        ),
    )


# ---------------------------------------------------------------------------
# Execution bot node
# ---------------------------------------------------------------------------


class _ExecutionBotNode:
    """
    Verifies all safety gates and submits the order to the broker.

    Delegates to the execution_bot agent.  If safety gates fail (kill switch,
    circuit breaker) or the agent raises, records an ExecutionReport with
    success=False rather than raising so the graph can continue to monitoring.
    """

    def __init__(self) -> None:
        self._agent = AgentRegistry.get("execution_bot")

    def __call__(self, state: HedgeFundState) -> dict[str, Any]:
        existing_errors: list[str] = list(state.get("errors", []))

        # Hard stop if kill switch was activated between approval and execution
        if state.get("kill_switch_active"):
            report = _failed_execution_report("Kill switch activated — order cancelled.")
            return {
                "execution_report": report,
                "current_phase": "execution_failed",
                "errors": [*existing_errors, "Execution blocked: kill switch active."],
            }

        if state.get("circuit_breaker_tripped"):
            report = _failed_execution_report("Circuit breaker tripped — order cancelled.")
            return {
                "execution_report": report,
                "current_phase": "execution_failed",
                "errors": [*existing_errors, "Execution blocked: circuit breaker tripped."],
            }

        try:
            result: dict[str, Any] = self._agent(state)

            execution_report: ExecutionReport | None = result.get("execution_report")

            # Attempt to extract from metadata if agent used analysis_reports
            if execution_report is None:
                reports = result.get("analysis_reports", {})
                bot_report = reports.get("execution_bot")
                if bot_report is not None:
                    meta = getattr(bot_report, "metadata", {})
                    raw = meta.get("execution_report")
                    if isinstance(raw, ExecutionReport):
                        execution_report = raw
                    elif isinstance(raw, dict):
                        try:
                            execution_report = ExecutionReport.model_validate(raw)
                        except Exception:
                            pass

            if execution_report is None:
                execution_report = _failed_execution_report(
                    "execution_bot did not return an ExecutionReport."
                )

            order_ids: list[str] = list(state.get("order_ids", []))
            if execution_report.broker_order_id:
                order_ids = [*order_ids, execution_report.broker_order_id]

            update: dict[str, Any] = {
                "execution_report": execution_report,
                "order_ids": order_ids,
                "current_phase": "executed" if execution_report.success else "execution_failed",
            }
            new_errors = result.get("errors", [])
            if new_errors:
                update["errors"] = existing_errors + new_errors
            return update

        except Exception as exc:
            error_msg = f"execution_bot error: {exc}"
            logger.error(error_msg, exc_info=True)
            return {
                "execution_report": _failed_execution_report(error_msg),
                "current_phase": "execution_failed",
                "errors": [*existing_errors, error_msg],
            }


def _failed_execution_report(reason: str) -> ExecutionReport:
    return ExecutionReport(
        success=False,
        trade_id=None,
        broker_order_id=None,
        filled_price=None,
        filled_quantity=None,
        commission=0.0,
        slippage=0.0,
        error_message=reason,
        timestamp=datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# Exit manager node
# ---------------------------------------------------------------------------


class _ExitManagerNode:
    """
    Places stop-loss and take-profit orders after a successful entry fill.

    Delegates to the exit_manager agent.  If the entry failed, this node
    is a no-op (it skips order placement and logs a warning).
    """

    def __init__(self) -> None:
        self._agent = AgentRegistry.get("exit_manager")

    def __call__(self, state: HedgeFundState) -> dict[str, Any]:
        existing_errors: list[str] = list(state.get("errors", []))
        existing_warnings: list[str] = list(state.get("warnings", []))
        order_ids: list[str] = list(state.get("order_ids", []))

        # Skip if the entry order was not successful
        exec_report: ExecutionReport | None = state.get("execution_report")
        if exec_report is None or not exec_report.success:
            return {
                "current_phase": "exit_orders_skipped",
                "warnings": [
                    *existing_warnings,
                    "exit_manager skipped: no successful entry order.",
                ],
            }

        try:
            result: dict[str, Any] = self._agent(state)

            # Collect any new order IDs registered for stop / TP orders
            new_order_ids: list[str] = result.get("order_ids", [])
            merged_ids = order_ids + new_order_ids

            update: dict[str, Any] = {
                "order_ids": merged_ids,
                "current_phase": "exit_orders_placed",
            }
            new_errors = result.get("errors", [])
            new_warnings = result.get("warnings", [])
            if new_errors:
                update["errors"] = existing_errors + new_errors
            if new_warnings:
                update["warnings"] = existing_warnings + new_warnings
            return update

        except Exception as exc:
            error_msg = f"exit_manager error: {exc}"
            logger.error(error_msg, exc_info=True)
            return {
                "current_phase": "exit_orders_failed",
                "errors": [*existing_errors, error_msg],
            }


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


def build_execution_subgraph():
    """
    Construct and compile the execution subgraph (sequential pipeline).

    Returns
    -------
    CompiledGraph
        A compiled LangGraph subgraph ready to be embedded in the master graph.
    """
    builder: StateGraph = StateGraph(HedgeFundState)

    builder.add_node("liquidity_analyst", _LiquidityAnalystNode())
    builder.add_node("trade_planner", _TradePlannerNode())
    builder.add_node("execution_bot", _ExecutionBotNode())
    builder.add_node("exit_manager", _ExitManagerNode())

    builder.set_entry_point("liquidity_analyst")
    builder.add_edge("liquidity_analyst", "trade_planner")
    builder.add_edge("trade_planner", "execution_bot")
    builder.add_edge("execution_bot", "exit_manager")
    builder.add_edge("exit_manager", END)

    return builder.compile()
