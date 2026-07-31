"""
agents/registry.py
==================
Singleton registry for all 40 hedge fund AI agents.

Usage
-----
    from agents.registry import AgentRegistry

    # Load a single agent by its ID
    cio = AgentRegistry.get("cio_agent")

    # Load every registered agent
    all_agents = AgentRegistry.get_all()

Agents are loaded lazily: the import only happens on first access and
the resulting instance is cached for the lifetime of the process.
"""

from __future__ import annotations

import importlib
import threading
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from agents.base_agent import BaseAgent

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Registry map
# Format: "agent_id" -> "module.path.ClassName"
# ---------------------------------------------------------------------------

AGENT_REGISTRY_MAP: dict[str, str] = {
    # Executive
    "cio_agent": "agents.executive.cio_agent.CIOAgent",
    "cro_agent": "agents.executive.cro_agent.CROAgent",
    "portfolio_manager": "agents.executive.portfolio_manager.PortfolioManagerAgent",
    # Market Intelligence
    "macro_economist": "agents.market_intelligence.macro_economist.MacroEconomistAgent",
    "news_analyst": "agents.market_intelligence.news_analyst.NewsAnalystAgent",
    "sentiment_analyst": "agents.market_intelligence.sentiment_analyst.SentimentAnalystAgent",
    "regulation_analyst": "agents.market_intelligence.regulation_analyst.RegulationAnalystAgent",
    # Technical
    "trend_analyst": "agents.technical.trend_analyst.TrendAnalystAgent",
    "price_action": "agents.technical.price_action.PriceActionAgent",
    "smc_expert": "agents.technical.smc_expert.SMCExpertAgent",
    "wyckoff_analyst": "agents.technical.wyckoff_analyst.WyckoffAnalystAgent",
    "elliott_wave": "agents.technical.elliott_wave.ElliottWaveAgent",
    "volume_profile": "agents.technical.volume_profile.VolumeProfileAgent",
    "market_structure": "agents.technical.market_structure.MarketStructureAgent",
    # Quantitative
    "quant_researcher": "agents.quantitative.quant_researcher.QuantResearcherAgent",
    "probability_analyst": "agents.quantitative.probability_analyst.ProbabilityAnalystAgent",
    "ml_researcher": "agents.quantitative.ml_researcher.MLResearcherAgent",
    "backtesting_expert": "agents.quantitative.backtesting_expert.BacktestingExpertAgent",
    "hf_pattern_detector": "agents.quantitative.hf_pattern_detector.HFPatternDetectorAgent",
    # Options
    "options_flow_analyst": "agents.options.options_flow_analyst.OptionsFlowAnalystAgent",
    "volatility_analyst": "agents.options.volatility_analyst.VolatilityAnalystAgent",
    # Crypto
    "onchain_analyst": "agents.crypto.onchain_analyst.OnChainAnalystAgent",
    "funding_rate_analyst": "agents.crypto.funding_rate_analyst.FundingRateAnalystAgent",
    # Strategy
    "momentum_trader": "agents.strategy.momentum_trader.MomentumTraderAgent",
    "mean_reversion": "agents.strategy.mean_reversion.MeanReversionAgent",
    "range_specialist": "agents.strategy.range_specialist.RangeSpecialistAgent",
    "scalping_expert": "agents.strategy.scalping_expert.ScalpingExpertAgent",
    "swing_specialist": "agents.strategy.swing_specialist.SwingSpecialistAgent",
    "position_expert": "agents.strategy.position_expert.PositionExpertAgent",
    # Execution
    "trade_planner": "agents.execution.trade_planner.TradePlannerAgent",
    "execution_bot": "agents.execution.execution_bot.ExecutionBotAgent",
    "liquidity_analyst": "agents.execution.liquidity_analyst.LiquidityAnalystAgent",
    "exit_manager": "agents.execution.exit_manager.ExitManagerAgent",
    # Monitoring
    "performance_analyst": "agents.monitoring.performance_analyst.PerformanceAnalystAgent",
    "journal_ai": "agents.monitoring.journal_ai.JournalAIAgent",
    "learning_agent": "agents.monitoring.learning_agent.LearningAgent",
    # Security
    "security_bot": "agents.security.security_bot.SecurityBotAgent",
    "emergency_bot": "agents.security.emergency_bot.EmergencyBotAgent",
    # Coordination
    "debate_moderator": "agents.coordination.debate_moderator.DebateModeratorAgent",
    "consensus_engine": "agents.coordination.consensus_engine.ConsensusEngineAgent",
}


class _AgentRegistrySingleton:
    """
    Thread-safe singleton that lazily loads and caches agent instances.

    Never instantiate this class directly; use the module-level
    ``AgentRegistry`` object instead.
    """

    def __init__(self) -> None:
        self._cache: dict[str, "BaseAgent"] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, agent_id: str) -> "BaseAgent":
        """
        Return an agent instance for *agent_id*, loading it if necessary.

        Parameters
        ----------
        agent_id:
            One of the keys in AGENT_REGISTRY_MAP.

        Returns
        -------
        BaseAgent
            Cached or newly created agent instance.

        Raises
        ------
        KeyError
            If *agent_id* is not in the registry map.
        ImportError
            If the agent module cannot be imported.
        AttributeError
            If the class is not found in the module.
        """
        if agent_id not in AGENT_REGISTRY_MAP:
            raise KeyError(
                f"Agent '{agent_id}' is not registered. "
                f"Valid IDs: {sorted(AGENT_REGISTRY_MAP.keys())}"
            )

        # Fast path — already cached (no lock needed for reads in CPython)
        if agent_id in self._cache:
            return self._cache[agent_id]

        with self._lock:
            # Double-checked locking
            if agent_id in self._cache:
                return self._cache[agent_id]

            instance = self._load(agent_id, AGENT_REGISTRY_MAP[agent_id])
            self._cache[agent_id] = instance
            return instance

    def get_all(self) -> dict[str, "BaseAgent"]:
        """
        Load and return all 40 registered agents.

        Agents that fail to load are logged and skipped; they will NOT be
        present in the returned dict.  This allows the system to start even
        if optional agents (e.g. crypto-specific ones) have missing deps.

        Returns
        -------
        dict[str, BaseAgent]
            Mapping of agent_id -> agent instance.
        """
        result: dict[str, "BaseAgent"] = {}
        for agent_id in AGENT_REGISTRY_MAP:
            try:
                result[agent_id] = self.get(agent_id)
            except Exception as exc:
                logger.error(
                    "agent_load_failed",
                    agent_id=agent_id,
                    error=str(exc),
                    exc_info=True,
                )
        return result

    def is_registered(self, agent_id: str) -> bool:
        """Return True if *agent_id* is in the registry map."""
        return agent_id in AGENT_REGISTRY_MAP

    def registered_ids(self) -> list[str]:
        """Return a sorted list of all registered agent IDs."""
        return sorted(AGENT_REGISTRY_MAP.keys())

    def clear_cache(self) -> None:
        """
        Evict all cached agent instances.

        Primarily useful in tests where a fresh instance is needed.
        """
        with self._lock:
            self._cache.clear()
        logger.info("agent_registry_cache_cleared")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load(self, agent_id: str, dotted_path: str) -> "BaseAgent":
        """
        Dynamically import the module and instantiate the agent class.

        Parameters
        ----------
        agent_id:
            Human-readable identifier (used only for logging).
        dotted_path:
            Full dotted path of the form ``"package.module.ClassName"``.
        """
        module_path, class_name = dotted_path.rsplit(".", 1)

        logger.debug("loading_agent", agent_id=agent_id, module=module_path, cls=class_name)

        try:
            module = importlib.import_module(module_path)
        except ModuleNotFoundError as exc:
            raise ImportError(
                f"Cannot import module '{module_path}' for agent '{agent_id}': {exc}"
            ) from exc

        try:
            cls = getattr(module, class_name)
        except AttributeError as exc:
            raise AttributeError(
                f"Class '{class_name}' not found in module '{module_path}' "
                f"for agent '{agent_id}': {exc}"
            ) from exc

        instance: "BaseAgent" = cls()
        logger.info("agent_loaded", agent_id=agent_id, cls=dotted_path)
        return instance


# ---------------------------------------------------------------------------
# Module-level singleton — import this from everywhere
# ---------------------------------------------------------------------------

AgentRegistry = _AgentRegistrySingleton()
