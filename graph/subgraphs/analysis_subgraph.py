"""
graph/subgraphs/analysis_subgraph.py
=====================================
Analysis subgraph — 20 specialist agents run in full parallel via the
LangGraph Send API.  Each agent receives the complete HedgeFundState and
writes its AgentReport into state["analysis_reports"].

Flow
----
  dispatcher  ──(Send×20)──>  [agent_0 … agent_19]  ──>  merger  ──>  END
"""
from __future__ import annotations

from langgraph.graph import StateGraph, END
from langgraph.constants import Send

from graph.state import HedgeFundState
from agents.registry import AgentRegistry

# ---------------------------------------------------------------------------
# Analysis agent identifiers (must match AgentRegistry keys)
# ---------------------------------------------------------------------------

ANALYSIS_AGENTS: list[str] = [
    "macro_economist",
    "news_analyst",
    "sentiment_analyst",
    "regulation_analyst",
    "trend_analyst",
    "price_action",
    "smc_expert",
    "wyckoff_analyst",
    "elliott_wave",
    "volume_profile",
    "market_structure",
    "quant_researcher",
    "probability_analyst",
    "ml_researcher",
    "backtesting_expert",
    "hf_pattern_detector",
    "options_flow_analyst",
    "volatility_analyst",
    "onchain_analyst",
    "funding_rate_analyst",
]


# ---------------------------------------------------------------------------
# Node functions
# ---------------------------------------------------------------------------


def _dispatch_analysis(state: HedgeFundState) -> list[Send]:
    """
    Fan out to every analysis agent in parallel.

    LangGraph collects all partial state updates produced by the agents
    and merges them before continuing to the merger node.
    """
    return [Send(agent_id, state) for agent_id in ANALYSIS_AGENTS]


def _merge_analysis(state: HedgeFundState) -> dict:
    """
    Collect barrier after all parallel agents complete.

    LangGraph has already merged all ``analysis_reports`` dict updates by
    the time this node runs — nothing to do here except update the phase.
    """
    return {"current_phase": "analysis_complete"}


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


def build_analysis_subgraph():
    """
    Construct and compile the analysis subgraph.

    Returns
    -------
    CompiledGraph
        A compiled LangGraph subgraph ready to be embedded in the master graph
        via ``builder.add_node("analysis_subgraph", build_analysis_subgraph())``.
    """
    registry = AgentRegistry
    builder: StateGraph = StateGraph(HedgeFundState)

    # --- Dispatcher (fan-out entry point) ---
    builder.add_node("dispatcher", lambda s: s)
    builder.set_entry_point("dispatcher")

    # --- One node per analysis agent ---
    for agent_id in ANALYSIS_AGENTS:
        agent = registry.get(agent_id)
        builder.add_node(agent_id, agent)

    # --- Fan-out edges: dispatcher -> all 20 agents in parallel ---
    builder.add_conditional_edges(
        "dispatcher",
        _dispatch_analysis,
        # Destinations are the agent_id strings returned by Send()
        {agent_id: agent_id for agent_id in ANALYSIS_AGENTS},
    )

    # --- Collect barrier: all agents -> merger ---
    builder.add_node("merger", _merge_analysis)
    for agent_id in ANALYSIS_AGENTS:
        builder.add_edge(agent_id, "merger")

    builder.add_edge("merger", END)

    return builder.compile()
