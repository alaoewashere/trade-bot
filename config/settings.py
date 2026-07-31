"""
config/settings.py
------------------
Centralised application settings loaded from environment variables / .env file.

Usage:
    from config.settings import get_settings
    settings = get_settings()
    print(settings.anthropic_api_key)
"""

from __future__ import annotations

import functools
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All application configuration — read from env vars or .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ------------------------------------------------------------------
    # Application
    # ------------------------------------------------------------------
    environment: Literal["paper", "live"] = Field(
        default="paper",
        description="Trading environment: 'paper' for simulation, 'live' for real money.",
    )

    # ------------------------------------------------------------------
    # Infrastructure
    # ------------------------------------------------------------------
    database_url: str = Field(
        default="postgresql://postgres:eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imh1Z3BzcHNzc2NrYmVweW9mY250Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4NTQyOTk5MywiZXhwIjoyMTAxMDA1OTkzfQ.Yx0Mg2JgRjM98GKhuVJGSM9HB4rHdi50aWXIYuGM-j4@db.hugpspsssckbepyofcnt.supabase.co:5432/postgres",
        description="Async-compatible PostgreSQL connection string (Supabase).",
    )
    supabase_url: str = Field(
        default="https://hugpspsssckbepyofcnt.supabase.co",
        description="Supabase project URL.",
    )
    supabase_anon_key: str = Field(
        default="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imh1Z3BzcHNzc2NrYmVweW9mY250Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODU0Mjk5OTMsImV4cCI6MjEwMTAwNTk5M30.DF3DCBllgTpQ9XCy4V_N0UiTljq-GDaJkoyu0TEsUhY",
        description="Supabase anonymous (public) API key.",
    )
    supabase_service_key: str = Field(
        default="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imh1Z3BzcHNzc2NrYmVweW9mY250Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4NTQyOTk5MywiZXhwIjoyMTAxMDA1OTkzfQ.Yx0Mg2JgRjM98GKhuVJGSM9HB4rHdi50aWXIYuGM-j4",
        description="Supabase service role key (full DB access — backend only).",
    )
    redis_url: str = Field(
        default="redis://localhost:6379",
        description="Redis connection string.",
    )
    qdrant_url: str = Field(
        default="http://localhost:6333",
        description="Qdrant vector-store base URL.",
    )

    # ------------------------------------------------------------------
    # AI providers — Anthropic (primary) or Groq (fallback / free tier)
    # ------------------------------------------------------------------
    anthropic_api_key: str = Field(
        default="",
        description="Anthropic API key for Claude model calls.",
    )
    groq_api_key: str = Field(
        default="",
        description="Groq API key — used when Anthropic credits are unavailable.",
    )
    ai_provider: str = Field(
        default="auto",
        description="AI provider: 'anthropic', 'groq', or 'auto' (uses Groq if Anthropic key missing).",
    )
    default_model: str = Field(
        default="claude-sonnet-4-6",
        description="Default Claude model ID for most agents (Anthropic).",
    )
    groq_default_model: str = Field(
        default="llama-3.3-70b-versatile",
        description="Default Groq model for fast inference.",
    )
    groq_reasoning_model: str = Field(
        default="llama-3.3-70b-versatile",
        description="Groq model for deep reasoning tasks.",
    )
    reasoning_model: str = Field(
        default="claude-opus-4-7",
        description="High-capability Claude model for complex reasoning tasks.",
    )

    @property
    def active_provider(self) -> str:
        """Returns the actual provider to use based on available keys."""
        if self.ai_provider == "groq":
            return "groq"
        if self.ai_provider == "anthropic":
            return "anthropic"
        # auto: use Anthropic if key present, else Groq
        if self.anthropic_api_key:
            return "anthropic"
        if self.groq_api_key:
            return "groq"
        return "anthropic"  # will fail at runtime with clear error

    # ------------------------------------------------------------------
    # Alpaca (equities / paper trading)
    # ------------------------------------------------------------------
    alpaca_api_key: str = Field(default="", description="Alpaca Markets API key.")
    alpaca_secret_key: str = Field(default="", description="Alpaca Markets secret key.")
    alpaca_base_url: str = Field(
        default="https://paper-api.alpaca.markets",
        description="Alpaca REST API base URL (paper or live).",
    )

    # ------------------------------------------------------------------
    # Binance (crypto)
    # ------------------------------------------------------------------
    binance_api_key: str = Field(default="", description="Binance API key.")
    binance_secret_key: str = Field(default="", description="Binance secret key.")

    # ------------------------------------------------------------------
    # Bybit (crypto)
    # ------------------------------------------------------------------
    bybit_api_key: str = Field(default="", description="Bybit API key.")
    bybit_secret_key: str = Field(default="", description="Bybit secret key.")

    # ------------------------------------------------------------------
    # On-chain data providers (optional)
    # ------------------------------------------------------------------
    glassnode_api_key: str = Field(default="", description="Glassnode API key.")
    cryptoquant_api_key: str = Field(default="", description="CryptoQuant API key.")

    # ------------------------------------------------------------------
    # Risk limits (USD)
    # ------------------------------------------------------------------
    max_daily_loss: float = Field(
        default=500.0,
        ge=0,
        description="Maximum allowed realised loss in a single calendar day (USD).",
    )
    max_weekly_loss: float = Field(
        default=1500.0,
        ge=0,
        description="Maximum allowed realised loss in a rolling 7-day window (USD).",
    )
    max_monthly_drawdown: float = Field(
        default=5000.0,
        ge=0,
        description="Maximum allowed drawdown from the monthly equity peak (USD).",
    )
    max_position_size_usd: float = Field(
        default=100.0,
        ge=0,
        description="Maximum notional size for any single position (USD).",
    )
    max_leverage: float = Field(
        default=1.0,
        ge=0,
        description="Maximum allowable leverage ratio (1.0 = no leverage).",
    )

    # ------------------------------------------------------------------
    # Agent / orchestration
    # ------------------------------------------------------------------
    agent_timeout_seconds: int = Field(
        default=120,
        ge=10,
        description="Maximum wall-clock seconds any individual agent may run before timing out.",
    )
    approval_timeout_minutes: int = Field(
        default=5,
        ge=1,
        description="Minutes to wait for human approval of a trade proposal before it expires.",
    )

    # ------------------------------------------------------------------
    # Prediction engine
    # ------------------------------------------------------------------
    prediction_symbols: list[str] = Field(
        default=["BTC/USDT", "ETH/USDT", "SPY", "QQQ", "EUR/USD", "XAU/USD"],
        description="Symbols monitored by the prediction engine.",
    )

    # ------------------------------------------------------------------
    # Validators
    # ------------------------------------------------------------------
    @field_validator("prediction_symbols", mode="before")
    @classmethod
    def parse_symbols_from_string(cls, v: object) -> list[str]:
        """Allow comma-separated string from env var, e.g. PREDICTION_SYMBOLS=BTC/USDT,ETH/USDT"""
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return v  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------
    @property
    def is_live(self) -> bool:
        return self.environment == "live"

    @property
    def is_paper(self) -> bool:
        return self.environment == "paper"


@functools.lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Return a cached singleton Settings instance.

    Call ``get_settings.cache_clear()`` in tests to force re-initialisation
    with different environment variables.
    """
    return Settings()
