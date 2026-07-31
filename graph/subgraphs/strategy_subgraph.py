"""
graph/subgraphs/strategy_subgraph.py
======================================
Strategy subgraph — 6 strategy agents run in full parallel via the
LangGraph Send API.  Each agent reads the completed analysis_reports from
state and produces a StrategySignal written into state["strategy_signals"].

Flow
----
  dispatcher  ──(Send×6)──>  [strategy agents]  ──>  merger  ──>  END
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from langgraph.graph import StateGraph, END
from langgraph.constants import Send

from graph.state import HedgeFundState, StrategySignal
from agents.registry import AgentRegistry

# ---------------------------------------------------------------------------
# Strategy agent identifiers (must match AgentRegistry keys)
# ---------------------------------------------------------------------------

STRATEGY_AGENTS: list[str] = [
    "momentum_trader",
    "mean_reversion",
    "range_specialist",
    "scalping_expert",
    "swing_specialist",
    "position_expert",
]


# ---------------------------------------------------------------------------
# Adapter: strategy agents return StrategySignal, not AgentReport
# Strategy agents are expected to write into state["strategy_signals"].
# We wrap each registry agent so it appends to the list rather than
# overwriting it.
# ---------------------------------------------------------------------------


class _StrategyAgentNode:
    """
    Thin wrapper that calls the underlying strategy agent's __call__ and
    coerces the result into a strategy_signals list append.

    Strategy agents are expected to return one of:
      - {"strategy_signals": [StrategySignal, ...]}
      - {"analysis_reports": {...}}  (fall-through — ignored for strategy phase)

    If the agent happens to return analysis_reports we still carry those
    forward; if it returns strategy_signals we merge them properly.
    """

    def __init__(self, agent_id: str) -> None:
        self._agent_id = agent_id
        self._agent = AgentRegistry.get(agent_id)

    def __call__(self, state: HedgeFundState) -> dict[str, Any]:
        existing_signals: list[StrategySignal] = list(state.get("strategy_signals", []))
        existing_errors: list[str] = list(state.get("errors", []))

        try:
            result: dict[str, Any] = self._agent(state)

            new_signals: list[StrategySignal] = result.get("strategy_signals", [])
            # Some strategy agents may return a single signal (not a list).
            if isinstance(new_signals, StrategySignal):
                new_signals = [new_signals]

            merged = existing_signals + new_signals

            # Carry forward any errors the agent may have recorded.
            new_errors: list[str] = result.get("errors", [])
            all_errors = existing_errors + new_errors

            update: dict[str, Any] = {"strategy_signals": merged}
            if all_errors:
                update["errors"] = all_errors

            return update

        except Exception as exc:
            error_msg = f"{self._agent_id} strategy error: {exc}"
            return {"errors": [*existing_errors, error_msg]}


# ---------------------------------------------------------------------------
# Node functions
# ---------------------------------------------------------------------------


def _dispatch_strategy(state: HedgeFundState) -> list[Send]:
    """Fan out to every strategy agent in parallel."""
    return [Send(f"strategy_{agent_id}", state) for agent_id in STRATEGY_AGENTS]


def _merge_strategy(state: HedgeFundState) -> dict:
    """
    Barrier node executed after all strategy agents complete.

    De-duplicates signals by strategy_id in case any agent ran twice due
    to LangGraph retry semantics, then updates the current phase.
    """
    signals: list[StrategySignal] = list(state.get("strategy_signals", []))

    # Deduplicate by strategy_id (keep last occurrence)
    seen: dict[str, StrategySignal] = {}
    for sig in signals:
        seen[sig.strategy_id] = sig
    deduped = list(seen.values())

    return {
        "strategy_signals": deduped,
        "current_phase": "strategy_complete",
    }


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


def build_strategy_subgraph():
    """
    Construct and compile the strategy subgraph.

    Returns
    -------
    CompiledGraph
        A compiled LangGraph subgraph ready to be embedded in the master graph.
    """
    builder: StateGraph = StateGraph(HedgeFundState)

    # --- Dispatcher ---
    builder.add_node("dispatcher", lambda s: s)
    builder.set_entry_point("dispatcher")

    # --- One node per strategy agent (prefixed to avoid collision with analysis nodes) ---
    node_names: dict[str, str] = {}
    for agent_id in STRATEGY_AGENTS:
        node_name = f"strategy_{agent_id}"
        node_names[node_name] = node_name
        builder.add_node(node_name, _StrategyAgentNode(agent_id))

    # --- Fan-out: dispatcher -> all 6 strategy agents in parallel ---
    builder.add_conditional_edges(
        "dispatcher",
        _dispatch_strategy,
        node_names,
    )

    # --- Collect barrier ---
    builder.add_node("merger", _merge_strategy)
    for node_name in node_names:
        builder.add_edge(node_name, "merger")

    builder.add_edge("merger", END)

    return builder.compile()
