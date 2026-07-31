"""
graph/subgraphs/monitoring_subgraph.py
========================================
Monitoring subgraph — runs at the end of every cycle regardless of whether
a trade was executed.  Updates metrics, writes a trade journal entry,
triggers learning, and rebalances the portfolio view.

Flow (sequential)
-----------------
  performance_analyst  ──>  journal_ai  ──>  learning_agent  ──>  portfolio_manager  ──>  END

Node: performance_analyst
    Updates cumulative performance metrics (Sharpe, drawdown, win-rate, etc.)
    based on any execution_report in state.

Node: journal_ai
    Writes a human-readable narrative of the cycle.  Only generates a trade
    narrative if an ExecutionReport with success=True is present; otherwise
    writes a "no-trade" analysis log.

Node: learning_agent
    Analyses patterns across recent cycles, updates agent confidence weights
    stored in memory, and flags any systematic biases.

Node: portfolio_manager
    Recomputes the current portfolio view (exposure, heat, open PnL) and
    updates state for the next cycle.
"""
from __future__ import annotations

import logging
from typing import Any

from langgraph.graph import StateGraph, END

from graph.state import HedgeFundState, ExecutionReport
from agents.registry import AgentRegistry

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper: safe agent call
# ---------------------------------------------------------------------------


def _safe_call(
    agent_id: str,
    state: HedgeFundState,
    existing_errors: list[str],
    phase_name: str,
) -> dict[str, Any]:
    """
    Invoke an agent by ID and return a partial state update.

    On any exception, records the error but does not propagate it so
    that monitoring never blocks the graph from completing.
    """
    try:
        agent = AgentRegistry.get(agent_id)
        result: dict[str, Any] = agent(state)
        update: dict[str, Any] = {"current_phase": phase_name}

        for key in ("warnings", "errors"):
            new_vals = result.get(key, [])
            if new_vals:
                existing = list(state.get(key, []))
                update[key] = existing + new_vals

        # Carry forward any explicit state keys the agent may return
        for key in (
            "market_regime",
            "analysis_reports",
        ):
            if key in result:
                update[key] = result[key]

        return update

    except Exception as exc:
        error_msg = f"{agent_id} monitoring error (non-fatal): {exc}"
        logger.error(error_msg, exc_info=True)
        return {
            "current_phase": phase_name,
            "errors": [*existing_errors, error_msg],
        }


# ---------------------------------------------------------------------------
# Node functions
# ---------------------------------------------------------------------------


def _performance_analyst_node(state: HedgeFundState) -> dict[str, Any]:
    """
    Update performance metrics based on the completed cycle.

    Always runs; uses execution_report.success to decide whether a trade
    outcome should be recorded.
    """
    return _safe_call(
        "performance_analyst",
        state,
        list(state.get("errors", [])),
        "performance_updated",
    )


def _journal_ai_node(state: HedgeFundState) -> dict[str, Any]:
    """
    Write trade journal narrative.

    Generates a trade narrative if execution_report.success is True,
    otherwise writes a "no-trade" analysis summary.
    """
    exec_report: ExecutionReport | None = state.get("execution_report")
    trade_executed = exec_report is not None and exec_report.success

    # Enrich state with a flag the journal_ai agent can read
    enriched_state = dict(state)
    enriched_state["_journal_trade_executed"] = trade_executed  # type: ignore[typeddict-unknown-key]

    return _safe_call(
        "journal_ai",
        enriched_state,  # type: ignore[arg-type]
        list(state.get("errors", [])),
        "journal_written",
    )


def _learning_agent_node(state: HedgeFundState) -> dict[str, Any]:
    """
    Analyse patterns from the completed cycle and update agent weights.

    The learning_agent reads debate_transcript, analysis_reports,
    consensus, execution_report, and any warnings to identify systematic
    biases and update its memory store.
    """
    return _safe_call(
        "learning_agent",
        state,
        list(state.get("errors", [])),
        "learning_complete",
    )


def _portfolio_manager_node(state: HedgeFundState) -> dict[str, Any]:
    """
    Recompute the portfolio view for the next cycle.

    Reads execution_report and order_ids to determine whether exposure
    changed, then updates the portfolio snapshot in Redis via the agent.
    """
    result = _safe_call(
        "portfolio_manager",
        state,
        list(state.get("errors", [])),
        "portfolio_updated",
    )

    # Always mark the final phase as "cycle_complete" regardless of
    # which intermediate phase name portfolio_manager wrote.
    result["current_phase"] = "cycle_complete"
    # Increment the iteration counter for telemetry
    result["iteration_count"] = int(state.get("iteration_count", 0)) + 1

    return result


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


def build_monitoring_subgraph():
    """
    Construct and compile the monitoring subgraph (sequential pipeline).

    Returns
    -------
    CompiledGraph
        A compiled LangGraph subgraph ready to be embedded in the master graph.
    """
    builder: StateGraph = StateGraph(HedgeFundState)

    builder.add_node("performance_analyst", _performance_analyst_node)
    builder.add_node("journal_ai", _journal_ai_node)
    builder.add_node("learning_agent", _learning_agent_node)
    builder.add_node("portfolio_manager", _portfolio_manager_node)

    builder.set_entry_point("performance_analyst")
    builder.add_edge("performance_analyst", "journal_ai")
    builder.add_edge("journal_ai", "learning_agent")
    builder.add_edge("learning_agent", "portfolio_manager")
    builder.add_edge("portfolio_manager", END)

    return builder.compile()
