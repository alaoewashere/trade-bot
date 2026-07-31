"""
agents/base_agent.py
====================
Abstract base class for every AI agent in the hedge fund system.

All concrete agents inherit from BaseAgent and must implement:
  - agent_id  (class-level str)
  - department (class-level str)
  - get_system_prompt() -> str
  - analyze(state: HedgeFundState) -> AgentReport

The __call__ method provides the LangGraph node interface, wrapping
analyze() in a try/except so that one failing agent never crashes the graph.
"""

from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypeVar

import structlog
import yaml
from pydantic import BaseModel

from config.settings import get_settings
from graph.state import AgentReport, HedgeFundState

logger = structlog.get_logger(__name__)
T = TypeVar("T", bound=BaseModel)


def _get_anthropic_client():
    from anthropic import Anthropic
    settings = get_settings()
    return Anthropic(api_key=settings.anthropic_api_key)


def _get_groq_client():
    from groq import Groq
    settings = get_settings()
    return Groq(api_key=settings.groq_api_key)

# Paths resolved relative to the project root (two levels up from this file)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_CONFIG_PATH = _PROJECT_ROOT / "config" / "agents_config.yaml"
_SKILLS_DIR = _PROJECT_ROOT / "skills"


class BaseAgent(ABC):
    """Abstract base for all hedge fund AI agents."""

    # Subclasses MUST override these
    agent_id: str = ""
    department: str = ""

    # Lazily initialised AI clients
    _client: Any | None = None

    def __init__(self) -> None:
        if not self.agent_id:
            raise ValueError(f"{type(self).__name__} must define a non-empty agent_id class attribute.")

        self.settings = get_settings()
        self._agent_config: dict[str, Any] = {}
        self._skill_registry: dict[str, Path] = {}

        self._load_agent_config()
        self._load_skills()

        logger.debug(
            "agent_initialised",
            agent_id=self.agent_id,
            department=self.department,
            skills=list(self._skill_registry.keys()),
        )

    # ------------------------------------------------------------------
    # Initialisation helpers
    # ------------------------------------------------------------------

    def _load_agent_config(self) -> None:
        """
        Load per-agent configuration from config/agents_config.yaml.

        The YAML file is expected to have a top-level key 'agents' whose
        value is a mapping from agent_id to a configuration dict.
        Falls back to sensible defaults if the file is missing or the
        agent is not listed.
        """
        defaults: dict[str, Any] = {
            "model": "claude-sonnet-4-6",
            "max_tokens": 4096,
            "temperature": 0.3,
            "timeout_seconds": 60,
        }

        if not _CONFIG_PATH.exists():
            logger.warning("agents_config_missing", path=str(_CONFIG_PATH), agent_id=self.agent_id)
            self._agent_config = defaults
            return

        try:
            with _CONFIG_PATH.open("r", encoding="utf-8") as fh:
                full_config: dict = yaml.safe_load(fh) or {}
            agents_section: dict = full_config.get("agents", {})
            agent_specific: dict = agents_section.get(self.agent_id, {})
            self._agent_config = {**defaults, **agent_specific}
        except Exception as exc:
            logger.warning(
                "agents_config_load_error",
                agent_id=self.agent_id,
                error=str(exc),
            )
            self._agent_config = defaults

    def _load_skills(self) -> None:
        """
        Scan the skills/ directory and register available skills.

        A skill is a subdirectory inside skills/ that contains either a
        SKILL.md or a README.md file.  The subdirectory name is used as
        the skill identifier.
        """
        if not _SKILLS_DIR.exists():
            return

        for skill_dir in _SKILLS_DIR.iterdir():
            if not skill_dir.is_dir():
                continue

            skill_doc = skill_dir / "SKILL.md"
            if not skill_doc.exists():
                skill_doc = skill_dir / "README.md"
            if not skill_doc.exists():
                continue

            self._skill_registry[skill_dir.name] = skill_doc

    # ------------------------------------------------------------------
    # Anthropic client (lazy)
    # ------------------------------------------------------------------

    @property
    def client(self) -> Any:
        """Return the AI client for the active provider (Anthropic or Groq)."""
        if self._client is None:
            provider = self.settings.active_provider
            if provider == "groq":
                self._client = _get_groq_client()
            else:
                self._client = _get_anthropic_client()
        return self._client

    def _active_model(self) -> str:
        """Return the model name appropriate for the active provider."""
        provider = self.settings.active_provider
        if provider == "groq":
            cfg_model = self._agent_config.get("model", "")
            # Map Anthropic model names to Groq equivalents
            if "opus" in cfg_model:
                return self.settings.groq_reasoning_model
            return self.settings.groq_default_model
        return self._agent_config.get("model", self.settings.default_model)

    # ------------------------------------------------------------------
    # Core LLM call — works with both Anthropic and Groq
    # ------------------------------------------------------------------

    def _call_claude(
        self,
        system_prompt: str,
        user_message: str,
        response_schema: type[T] | None = None,
    ) -> str | T:
        """
        Send a message to the active AI provider and return the response.
        Works transparently with Anthropic or Groq.
        If response_schema is provided, parses JSON into that Pydantic model.
        """
        model = self._active_model()
        max_tokens: int = int(self._agent_config.get("max_tokens", 4096))
        timeout: float = float(self._agent_config.get("timeout_seconds", 60))
        provider = self.settings.active_provider
        # Groq free tier: cap at 6000 output tokens to avoid 413 errors
        if provider == "groq":
            max_tokens = min(max_tokens, 4096)

        if response_schema:
            schema_json = response_schema.model_json_schema()
            system_prompt += (
                f"\n\nYou MUST respond with ONLY valid JSON matching this schema "
                f"(no markdown, no explanation):\n{json.dumps(schema_json, indent=2)}"
            )

        log = logger.bind(agent_id=self.agent_id, model=model, provider=provider)
        t0 = time.perf_counter()

        try:
            if provider == "groq":
                response = self.client.chat.completions.create(
                    model=model,
                    max_tokens=max_tokens,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message},
                    ],
                    timeout=timeout,
                )
                content = response.choices[0].message.content or ""
            else:
                response = self.client.messages.create(
                    model=model,
                    max_tokens=max_tokens,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_message}],
                    timeout=timeout,
                )
                content = response.content[0].text
        except Exception as exc:
            log.error("ai_api_error", error=str(exc))
            raise

        elapsed = time.perf_counter() - t0
        usage = response.usage
        # Groq uses prompt_tokens/completion_tokens; Anthropic uses input_tokens/output_tokens
        in_tok = getattr(usage, "input_tokens", None) or getattr(usage, "prompt_tokens", 0)
        out_tok = getattr(usage, "output_tokens", None) or getattr(usage, "completion_tokens", 0)
        log.info(
            "ai_response",
            elapsed_s=round(elapsed, 3),
            input_tokens=in_tok,
            output_tokens=out_tok,
        )

        raw: str = content.strip()

        if response_schema is None:
            return raw

        # Strip markdown code fences if present (```json ... ``` or ``` ... ```)
        cleaned = raw
        if cleaned.startswith("```"):
            # Remove opening fence line
            first_newline = cleaned.find("\n")
            if first_newline != -1:
                cleaned = cleaned[first_newline + 1 :]
            # Remove closing fence
            if cleaned.endswith("```"):
                cleaned = cleaned[: cleaned.rfind("```")].rstrip()

        try:
            data = json.loads(cleaned)
            return response_schema.model_validate(data)
        except Exception as exc:
            log.error(
                "response_parse_error",
                schema=response_schema.__name__,
                error=str(exc),
                raw_preview=raw[:300],
            )
            raise ValueError(
                f"[{self.agent_id}] Failed to parse Claude response as "
                f"{response_schema.__name__}: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Skill invocation
    # ------------------------------------------------------------------

    def invoke_skill(self, skill_name: str, context: str) -> str:
        """
        Load a skill's documentation and invoke it via Claude.

        Parameters
        ----------
        skill_name:
            The name of the skill directory under skills/.
        context:
            Contextual information or a question to pass to the skill.

        Returns
        -------
        str
            Claude's response after reading the skill instructions.

        Raises
        ------
        KeyError
            If *skill_name* is not found in the skill registry.
        """
        if skill_name not in self._skill_registry:
            raise KeyError(
                f"[{self.agent_id}] Skill '{skill_name}' not found. "
                f"Available: {list(self._skill_registry.keys())}"
            )

        skill_path = self._skill_registry[skill_name]
        skill_doc = skill_path.read_text(encoding="utf-8")

        system = (
            "You are executing a specialised skill. "
            "Follow the skill instructions exactly.\n\n"
            "=== SKILL INSTRUCTIONS ===\n"
            f"{skill_doc}\n"
            "=== END SKILL INSTRUCTIONS ==="
        )
        user = f"Apply the skill to the following context:\n\n{context}"

        logger.info("invoking_skill", agent_id=self.agent_id, skill=skill_name)
        return self._call_claude(system_prompt=system, user_message=user)  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abstractmethod
    def get_system_prompt(self) -> str:
        """Return the agent's specialised system prompt."""
        ...

    @abstractmethod
    def analyze(self, state: HedgeFundState) -> AgentReport:
        """
        Perform the agent's primary analysis and return an AgentReport.

        Parameters
        ----------
        state:
            Current hedge fund graph state.
        """
        ...

    # ------------------------------------------------------------------
    # LangGraph node interface
    # ------------------------------------------------------------------

    def __call__(self, state: HedgeFundState) -> dict[str, Any]:
        """
        LangGraph node entry point.

        Calls self.analyze(), merges the resulting AgentReport into
        state['analysis_reports'], and returns the partial state update.
        On any exception the error is recorded in state['errors'] and the
        function returns gracefully so that other nodes can continue.
        """
        existing_reports: dict[str, AgentReport] = dict(state.get("analysis_reports", {}))
        existing_errors: list[str] = list(state.get("errors", []))

        try:
            report: AgentReport = self.analyze(state)
            updated_reports = {**existing_reports, self.agent_id: report}
            logger.info(
                "agent_analysis_complete",
                agent_id=self.agent_id,
                symbol=report.symbol,
                signal=report.signal,
                confidence=report.confidence,
            )
            return {"analysis_reports": updated_reports}

        except Exception as exc:
            error_msg = f"{self.agent_id}: {exc}"
            logger.error(
                "agent_analysis_failed",
                agent_id=self.agent_id,
                error=error_msg,
                exc_info=True,
            )
            return {"errors": [*existing_errors, error_msg]}

    # ------------------------------------------------------------------
    # Formatting utilities
    # ------------------------------------------------------------------

    def _format_market_data(self, market_data: dict[str, Any]) -> str:
        """
        Convert the raw market_data dict into a human-readable string
        suitable for inclusion in a Claude prompt.

        Handles both OHLCV candles (list of dicts with open/high/low/close/
        volume keys) and a flat dict of technical indicators.
        """
        sections: list[str] = []

        # --- OHLCV candles ---
        candles: list[dict] | None = market_data.get("candles") or market_data.get("ohlcv")
        if candles:
            latest_n = candles[-10:]  # Show last 10 bars to keep prompt concise
            header = "OHLCV (last {} bars):".format(len(latest_n))
            rows = []
            for c in latest_n:
                ts = c.get("timestamp", c.get("time", ""))
                rows.append(
                    f"  {ts}  O={c.get('open', '?'):.4f}  H={c.get('high', '?'):.4f}"
                    f"  L={c.get('low', '?'):.4f}  C={c.get('close', '?'):.4f}"
                    f"  V={c.get('volume', '?'):.0f}"
                )
            sections.append(header + "\n" + "\n".join(rows))

        # --- Current price ---
        if "price" in market_data or "last_price" in market_data:
            price = market_data.get("price") or market_data.get("last_price")
            sections.append(f"Current Price: {price}")

        # --- Technical indicators ---
        indicators: dict | None = market_data.get("indicators") or market_data.get("technicals")
        if indicators:
            ind_lines = ["Technical Indicators:"]
            for name, value in indicators.items():
                if isinstance(value, float | int):
                    ind_lines.append(f"  {name}: {value:.4f}" if isinstance(value, float) else f"  {name}: {value}")
                elif isinstance(value, dict):
                    inner = ", ".join(f"{k}={v:.4f}" if isinstance(v, float) else f"{k}={v}" for k, v in value.items())
                    ind_lines.append(f"  {name}: {{{inner}}}")
                else:
                    ind_lines.append(f"  {name}: {value}")
            sections.append("\n".join(ind_lines))

        # --- Order book snapshot ---
        order_book: dict | None = market_data.get("order_book")
        if order_book:
            bids = order_book.get("bids", [])[:3]
            asks = order_book.get("asks", [])[:3]
            ob_lines = ["Order Book (top 3):"]
            ob_lines.append("  Bids: " + " | ".join(f"{p:.4f}@{q:.2f}" for p, q in bids))
            ob_lines.append("  Asks: " + " | ".join(f"{p:.4f}@{q:.2f}" for p, q in asks))
            sections.append("\n".join(ob_lines))

        # --- Funding rate (crypto) ---
        if "funding_rate" in market_data:
            sections.append(f"Funding Rate: {market_data['funding_rate']:.4%}")

        # --- Open interest ---
        if "open_interest" in market_data:
            sections.append(f"Open Interest: {market_data['open_interest']:,.0f}")

        # --- Fallback: dump remaining keys ---
        handled_keys = {
            "candles", "ohlcv", "price", "last_price",
            "indicators", "technicals", "order_book",
            "funding_rate", "open_interest",
        }
        remaining = {k: v for k, v in market_data.items() if k not in handled_keys}
        if remaining:
            extra_lines = ["Additional Data:"]
            for k, v in remaining.items():
                extra_lines.append(f"  {k}: {v}")
            sections.append("\n".join(extra_lines))

        return "\n\n".join(sections) if sections else "No market data available."

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def _now(self) -> datetime:
        """Return the current UTC datetime."""
        return datetime.now(timezone.utc)
