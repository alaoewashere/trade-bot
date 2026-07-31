"""
graph/main_graph.py
====================
Master LangGraph StateGraph for the Hedge Fund AI system.

Topology
--------

  security_check
      │
      ├─(kill_switch)──────────────────────────────► emergency_bot ──► monitoring_subgraph
      ├─(circuit_breaker | news_blackout)──────────► monitoring_subgraph
      └─(clear)────────────────────────────────────► prediction_engine_node
                                                          │
                                                     analysis_subgraph
                                                          │
                                                     strategy_subgraph
                                                          │
                                                      debate_subgraph
                                                          │
                                          ┌─(no consensus / low conf)──► monitoring_subgraph
                                          └─(consensus ≥55%)──────────► risk_gate_node
                                                                             │
                                                     ┌─(risk rejected)───────┘
                                                     │
                                                     └─(risk approved)──► human_approval_node
                                                                               │
                                                      ┌─(rejected/expired)────┘
                                                      │
                                                      └─(approved)──► execution_subgraph
                                                                           │
                                                                      monitoring_subgraph
                                                                           │
                                                                          END

Run as a script for smoke-testing:
    python -m graph.main_graph
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from langgraph.graph import StateGraph, END

from agents.registry import AgentRegistry
from config.settings import get_settings
from graph.conditional_edges import EdgeRouter
from graph.state import HedgeFundState, RiskAssessment
from graph.subgraphs.analysis_subgraph import build_analysis_subgraph
from graph.subgraphs.debate_subgraph import build_debate_subgraph
from graph.subgraphs.execution_subgraph import build_execution_subgraph
from graph.subgraphs.monitoring_subgraph import build_monitoring_subgraph
from graph.subgraphs.strategy_subgraph import build_strategy_subgraph
from risk.engine import RiskEngine

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Standalone node: security_check
# ---------------------------------------------------------------------------


def security_check_node(state: HedgeFundState) -> dict[str, Any]:
    """
    Run the security_bot agent and check Redis-backed circuit breakers.

    Also performs a fast synchronous news-blackout check against cached
    events loaded by the prediction engine.

    Returns
    -------
    Partial state update containing safety flags.
    """
    settings = get_settings()
    existing_errors: list[str] = list(state.get("errors", []))

    # Default safety flags — preserved if checks cannot run
    update: dict[str, Any] = {
        "current_phase": "security_checked",
        "kill_switch_active": state.get("kill_switch_active", False),
        "circuit_breaker_tripped": state.get("circuit_breaker_tripped", False),
        "news_blackout_active": state.get("news_blackout_active", False),
    }

    try:
        agent = AgentRegistry.get("security_bot")
        result: dict[str, Any] = agent(state)

        # security_bot may directly set safety flags in its return dict
        for flag in ("kill_switch_active", "circuit_breaker_tripped", "news_blackout_active"):
            if flag in result:
                update[flag] = result[flag]

        new_errors = result.get("errors", [])
        if new_errors:
            update["errors"] = existing_errors + new_errors

        new_warnings = result.get("warnings", [])
        if new_warnings:
            update["warnings"] = list(state.get("warnings", [])) + new_warnings

    except Exception as exc:
        error_msg = f"security_check error: {exc}"
        logger.error(error_msg, exc_info=True)
        update["errors"] = [*existing_errors, error_msg]

    return update


# ---------------------------------------------------------------------------
# Standalone node: prediction_engine_node
# ---------------------------------------------------------------------------


def prediction_engine_node(state: HedgeFundState) -> dict[str, Any]:
    """
    Retrieve the latest cached forecasts from Redis (fast path).

    In production the prediction engine runs as a separate background
    service that writes forecasts to Redis.  This node reads those
    cached values for the requested symbol × timeframe combination.

    Falls back gracefully when Redis is unavailable or no forecast exists.
    """
    symbol = state.get("symbol", "UNKNOWN")
    timeframe = state.get("timeframe", "1h")
    existing_forecasts: dict = dict(state.get("forecasts", {}))
    existing_errors: list[str] = list(state.get("errors", []))

    update: dict[str, Any] = {
        "current_phase": "forecasts_loaded",
        "forecasts": existing_forecasts,
    }

    try:
        import redis as sync_redis  # type: ignore[import]
        from config.settings import get_settings as _settings

        settings = _settings()
        r = sync_redis.from_url(settings.redis_url, decode_responses=True)

        # Timeframes the prediction engine publishes
        timeframes = ["1m", "5m", "15m", "1h", "4h", "1d", "1w", "1M"]
        loaded: dict = {}

        for tf in timeframes:
            key = f"forecast:{symbol}:{tf}"
            raw = r.get(key)
            if raw:
                try:
                    from graph.state import Forecast
                    data = json.loads(raw)
                    loaded[tf] = Forecast.model_validate(data)
                except Exception as parse_exc:
                    logger.warning(
                        "prediction_engine: failed to parse forecast for %s:%s — %s",
                        symbol, tf, parse_exc,
                    )

        r.close()

        # Merge with any forecasts already in state
        merged = {**existing_forecasts, **loaded}
        update["forecasts"] = merged

        if loaded:
            # Use the first loaded forecast's market_regime for routing
            first = next(iter(loaded.values()), None)
            if first is not None:
                update["market_regime"] = first.market_regime

        logger.info(
            "prediction_engine: loaded %d forecasts for %s", len(loaded), symbol
        )

    except Exception as exc:
        warning_msg = f"prediction_engine: Redis unavailable — using empty forecasts ({exc})"
        logger.warning(warning_msg)
        update["warnings"] = list(state.get("warnings", [])) + [warning_msg]

    return update


# ---------------------------------------------------------------------------
# Standalone node: risk_gate_node
# ---------------------------------------------------------------------------


def risk_gate_node(state: HedgeFundState) -> dict[str, Any]:
    """
    Run the CRO agent followed by the RiskEngine to produce a RiskAssessment.

    The CRO agent may veto the trade based on qualitative factors (news,
    regulatory risk, unusual market conditions).  If it passes, the
    RiskEngine applies quantitative checks: position sizing, portfolio heat,
    VaR, liquidity.
    """
    existing_errors: list[str] = list(state.get("errors", []))

    update: dict[str, Any] = {
        "current_phase": "risk_gate_evaluated",
        "risk_assessment": None,
    }

    # --- CRO agent (qualitative veto layer) ---
    try:
        cro = AgentRegistry.get("cro_agent")
        cro_result: dict[str, Any] = cro(state)

        new_errors = cro_result.get("errors", [])
        if new_errors:
            update["errors"] = existing_errors + new_errors
            existing_errors = existing_errors + new_errors

        # CRO agent may set a veto flag
        if cro_result.get("kill_switch_active") or cro_result.get("circuit_breaker_tripped"):
            for flag in ("kill_switch_active", "circuit_breaker_tripped"):
                if flag in cro_result:
                    update[flag] = cro_result[flag]
            update["risk_assessment"] = RiskAssessment(
                approved=False,
                position_size_usd=0.0,
                position_size_units=0.0,
                entry_price=0.0,
                stop_loss=0.0,
                take_profit=0.0,
                risk_reward=0.0,
                max_risk_usd=0.0,
                portfolio_heat_pct=0.0,
                var_95=0.0,
                correlation_check=False,
                liquidity_check=False,
                rejection_reasons=["CRO agent vetoed the trade."],
            )
            return update

    except Exception as exc:
        error_msg = f"cro_agent error: {exc}"
        logger.error(error_msg, exc_info=True)
        existing_errors = [*existing_errors, error_msg]
        update["errors"] = existing_errors

    # --- RiskEngine (quantitative layer) ---
    try:
        consensus = state.get("consensus")
        strategy_signals = state.get("strategy_signals", [])

        if consensus is None or not strategy_signals:
            update["risk_assessment"] = RiskAssessment(
                approved=False,
                position_size_usd=0.0,
                position_size_units=0.0,
                entry_price=0.0,
                stop_loss=0.0,
                take_profit=0.0,
                risk_reward=0.0,
                max_risk_usd=0.0,
                portfolio_heat_pct=0.0,
                var_95=0.0,
                correlation_check=False,
                liquidity_check=False,
                rejection_reasons=["No consensus or strategy signals available for risk evaluation."],
            )
            return update

        # Use the first strategy signal (highest confidence signal)
        sorted_signals = sorted(strategy_signals, key=lambda s: s.confidence, reverse=True)
        primary_signal = sorted_signals[0]

        engine = RiskEngine(account_equity_usd=10_000.0)
        risk_assessment = engine.evaluate(
            strategy_signal=primary_signal,
            consensus=consensus,
            current_portfolio={"open_positions": [], "total_heat_pct": 0.0},
            market_data=state.get("market_data", {}),
        )

        update["risk_assessment"] = risk_assessment
        logger.info(
            "risk_gate: approved=%s size_usd=%.2f rr=%.2f",
            risk_assessment.approved,
            risk_assessment.position_size_usd,
            risk_assessment.risk_reward,
        )

    except Exception as exc:
        error_msg = f"risk_engine error: {exc}"
        logger.error(error_msg, exc_info=True)
        update["errors"] = [*existing_errors, error_msg]
        update["risk_assessment"] = RiskAssessment(
            approved=False,
            position_size_usd=0.0,
            position_size_units=0.0,
            entry_price=0.0,
            stop_loss=0.0,
            take_profit=0.0,
            risk_reward=0.0,
            max_risk_usd=0.0,
            portfolio_heat_pct=0.0,
            var_95=0.0,
            correlation_check=False,
            liquidity_check=False,
            rejection_reasons=[f"RiskEngine raised an exception: {exc}"],
        )

    return update


# ---------------------------------------------------------------------------
# Standalone node: human_approval_node
# ---------------------------------------------------------------------------


def human_approval_node(state: HedgeFundState) -> dict[str, Any]:
    """
    Create a human approval request and suspend the graph.

    In production this node uses LangGraph's interrupt() mechanism to pause
    graph execution.  The FastAPI /approvals/{id}/approve endpoint writes
    the decision to Redis, and the graph resumes from this checkpoint.

    For development / paper-trading environments the node can be configured
    to auto-approve (settings.environment == "paper").

    Returns
    -------
    Partial state update with approval_id, approval_deadline, and
    human_approval_status set to "pending".
    """
    from datetime import timedelta
    settings = get_settings()

    approval_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    deadline = now + timedelta(minutes=settings.approval_timeout_minutes)

    consensus = state.get("consensus")
    risk = state.get("risk_assessment")
    symbol = state.get("symbol", "UNKNOWN")

    approval_payload: dict[str, Any] = {
        "approval_id": approval_id,
        "symbol": symbol,
        "direction": consensus.direction if consensus else "UNKNOWN",
        "confidence_pct": consensus.confidence_pct if consensus else 0.0,
        "final_thesis": consensus.final_thesis if consensus else "",
        "risk_assessment": risk.model_dump() if risk else {},
        "debate_excerpt": _excerpt_debate(state),
        "created_at": now.isoformat(),
        "expires_at": deadline.isoformat(),
        "status": "pending",
    }

    # Write approval request to Redis (non-blocking; best-effort)
    try:
        import redis as sync_redis  # type: ignore[import]
        r = sync_redis.from_url(settings.redis_url, decode_responses=True)
        score = deadline.timestamp()

        pipe = r.pipeline(transaction=True)
        pipe.set(
            f"approval:{approval_id}",
            json.dumps(approval_payload),
            ex=int(settings.approval_timeout_minutes * 60) + 60,
        )
        pipe.zadd("approval:pending", {approval_id: score})
        pipe.execute()
        r.close()

        logger.info(
            "human_approval: created approval_id=%s symbol=%s expires=%s",
            approval_id, symbol, deadline.isoformat(),
        )

    except Exception as exc:
        logger.warning("human_approval: Redis write failed — %s", exc)

    # In paper mode, auto-approve immediately so the full graph can run
    if settings.is_paper:
        logger.info("human_approval: paper mode — auto-approving %s", approval_id)
        return {
            "approval_id": approval_id,
            "approval_deadline": deadline,
            "human_approval_status": "approved",
            "current_phase": "auto_approved",
        }

    # Live mode: use LangGraph interrupt to suspend the graph.
    # The graph will be resumed by the FastAPI approval endpoint.
    try:
        from langgraph.types import interrupt  # type: ignore[import]
        interrupt(
            {
                "type": "human_approval",
                "approval_id": approval_id,
                "message": (
                    f"Approval required for {symbol} {consensus.direction if consensus else 'UNKNOWN'} "
                    f"trade. Confidence: {consensus.confidence_pct if consensus else 0:.1f}%. "
                    f"Expires: {deadline.isoformat()}."
                ),
            }
        )
    except ImportError:
        # langgraph.types.interrupt not available in this version — fall back
        # to polling loop via Redis (graph will re-check on next invocation)
        logger.warning(
            "human_approval: langgraph.types.interrupt not available — "
            "falling back to status=pending (manual resume required)"
        )

    return {
        "approval_id": approval_id,
        "approval_deadline": deadline,
        "human_approval_status": "pending",
        "current_phase": "awaiting_human_approval",
    }


def _excerpt_debate(state: HedgeFundState) -> str:
    """Return the last 3 debate messages as a readable excerpt."""
    transcript = state.get("debate_transcript", [])
    if not transcript:
        return "No debate transcript available."
    recent = transcript[-3:]
    lines = [
        f"[Round {m.round_number}] {m.agent_id} ({m.position}): {m.argument[:200]}"
        for m in recent
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Master graph builder
# ---------------------------------------------------------------------------


def build_graph():
    """
    Assemble and compile the master hedge fund AI graph.

    Returns
    -------
    CompiledGraph
        A compiled LangGraph StateGraph ready for invocation.
    """
    builder = StateGraph(HedgeFundState)

    # --- Standalone nodes ---
    builder.add_node("security_check", security_check_node)
    builder.add_node("prediction_engine_node", prediction_engine_node)
    builder.add_node("risk_gate_node", risk_gate_node)
    builder.add_node("human_approval_node", human_approval_node)
    builder.add_node("emergency_bot", AgentRegistry.get("emergency_bot"))

    # --- Subgraph nodes ---
    builder.add_node("analysis_subgraph", build_analysis_subgraph())
    builder.add_node("strategy_subgraph", build_strategy_subgraph())
    builder.add_node("debate_subgraph", build_debate_subgraph())
    builder.add_node("execution_subgraph", build_execution_subgraph())
    builder.add_node("monitoring_subgraph", build_monitoring_subgraph())

    # --- Entry point ---
    builder.set_entry_point("security_check")

    # --- Edge routing ---
    builder.add_conditional_edges(
        "security_check",
        EdgeRouter.after_security_check,
        {
            "emergency_bot": "emergency_bot",
            "monitoring_subgraph": "monitoring_subgraph",
            "prediction_engine_node": "prediction_engine_node",
        },
    )

    builder.add_edge("prediction_engine_node", "analysis_subgraph")
    builder.add_edge("analysis_subgraph", "strategy_subgraph")
    builder.add_edge("strategy_subgraph", "debate_subgraph")

    builder.add_conditional_edges(
        "debate_subgraph",
        EdgeRouter.after_consensus,
        {
            "monitoring_subgraph": "monitoring_subgraph",
            "risk_gate_node": "risk_gate_node",
        },
    )

    builder.add_conditional_edges(
        "risk_gate_node",
        EdgeRouter.after_risk_gate,
        {
            "monitoring_subgraph": "monitoring_subgraph",
            "human_approval_node": "human_approval_node",
        },
    )

    builder.add_conditional_edges(
        "human_approval_node",
        EdgeRouter.after_human_approval,
        {
            "execution_subgraph": "execution_subgraph",
            "monitoring_subgraph": "monitoring_subgraph",
        },
    )

    builder.add_edge("execution_subgraph", "monitoring_subgraph")
    builder.add_edge("monitoring_subgraph", END)

    builder.add_conditional_edges(
        "emergency_bot",
        EdgeRouter.after_emergency,
        {"monitoring_subgraph": "monitoring_subgraph"},
    )

    return builder.compile()


# ---------------------------------------------------------------------------
# Script entry point
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    import structlog

    import logging as _logging

    _logging.basicConfig(level=_logging.INFO, format="%(message)s")
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.dev.ConsoleRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
    )

    settings = get_settings()
    graph = build_graph()

    print("=" * 70)
    print("Hedge Fund AI — Agent Orchestrator")
    print(f"Environment : {settings.environment.upper()}")
    print(f"Started at  : {datetime.now(timezone.utc).isoformat()}")
    print("=" * 70)

    test_symbols = [
        ("BTC/USDT", "1h"),
        ("SPY", "4h"),
        ("EUR/USD", "15m"),
    ]

    for symbol, timeframe in test_symbols:
        print(f"\n{'─'*60}")
        print(f"Running graph for {symbol} ({timeframe}) …")

        initial_state: HedgeFundState = {
            "symbol": symbol,
            "timeframe": timeframe,
            "market_data": {},
            "timestamp": datetime.now(timezone.utc),
            "current_phase": "init",
            "iteration_count": 0,
            "analysis_reports": {},
            "strategy_signals": [],
            "debate_transcript": [],
            "consensus": None,
            "risk_assessment": None,
            "human_approval_required": True,
            "human_approval_status": None,
            "approval_id": None,
            "approval_deadline": None,
            "trade_plan": None,
            "order_ids": [],
            "execution_report": None,
            "forecasts": {},
            "market_regime": None,
            "circuit_breaker_tripped": False,
            "kill_switch_active": False,
            "news_blackout_active": False,
            "errors": [],
            "warnings": [],
        }

        try:
            result = graph.invoke(initial_state)

            consensus = result.get("consensus")
            exec_report = result.get("execution_report")
            errors = result.get("errors", [])

            print(f"  Phase     : {result.get('current_phase', 'unknown')}")
            print(
                f"  Consensus : {consensus.direction if consensus else 'None'} "
                f"({consensus.confidence_pct:.1f}% conf)" if consensus else "  Consensus : None"
            )
            print(
                f"  Execution : {'SUCCESS' if exec_report and exec_report.success else 'NOT EXECUTED'}"
            )
            if errors:
                print(f"  Errors    : {len(errors)}")
                for e in errors[:3]:
                    print(f"    - {e[:120]}")

        except Exception as exc:
            print(f"  GRAPH ERROR: {exc}")

    print(f"\n{'='*70}")
    print("Graph run complete.")
