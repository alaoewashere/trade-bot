"""
risk/limits.py
==============
Non-negotiable risk limits for the hedge fund AI system.

These constants mirror the values in risk_config.yaml and are imported
directly by circuit_breakers.py, engine.py, and any other module that
needs hard-coded risk boundaries.  Changing these constants requires a
code review and deployment — they are intentionally NOT read from
environment variables or config files at runtime.
"""

# ---------------------------------------------------------------------------
# Loss limits (USD)
# ---------------------------------------------------------------------------

MAX_DAILY_LOSS_USD: float = 500.0
"""Maximum allowable realised loss within a single calendar day."""

MAX_WEEKLY_LOSS_USD: float = 1_500.0
"""Maximum allowable realised loss within a rolling 7-day window."""

MAX_MONTHLY_DRAWDOWN_USD: float = 5_000.0
"""Maximum allowable peak-to-trough drawdown within a calendar month."""

# ---------------------------------------------------------------------------
# Position sizing
# ---------------------------------------------------------------------------

MAX_POSITION_SIZE_USD: float = 100.0
"""Hard cap on the notional value of any single open position."""

MAX_OPEN_POSITIONS: int = 3
"""Maximum number of concurrent open positions across all instruments."""

MAX_LEVERAGE: float = 1.0
"""Maximum gross leverage (1.0 = no leverage; cash-only trading)."""

# ---------------------------------------------------------------------------
# Portfolio heat / concentration
# ---------------------------------------------------------------------------

MAX_PORTFOLIO_HEAT_PCT: float = 20.0
"""
Maximum percentage of portfolio equity that may be at risk simultaneously
across all open positions (sum of per-position max-loss / equity).
"""

MAX_PORTFOLIO_CORRELATION: float = 0.7
"""
Maximum acceptable Pearson correlation between any new position and the
aggregate existing portfolio returns.  Prevents over-concentration in
correlated instruments.
"""

MAX_SECTOR_EXPOSURE_PCT: float = 30.0
"""
Maximum percentage of portfolio equity allocated to any single market
sector or asset class.
"""

# ---------------------------------------------------------------------------
# Trade quality filters
# ---------------------------------------------------------------------------

MIN_RISK_REWARD: float = 1.5
"""
Minimum acceptable risk-to-reward ratio for any trade signal.
Signals with R:R below this threshold are rejected outright.
"""

MIN_CONFIDENCE_PCT: float = 55.0
"""
Minimum ensemble-model confidence (0–100 %) required before a trade
signal proceeds to the risk engine.
"""

MIN_LIQUIDITY_24H_USD: float = 1_000_000.0
"""
Minimum 24-hour traded volume (in USD) for an instrument to be eligible
for position entry.  Protects against illiquid markets where fills are
unreliable.
"""

# ---------------------------------------------------------------------------
# Consecutive-loss circuit breaker
# ---------------------------------------------------------------------------

MAX_CONSECUTIVE_LOSSES: int = 5
"""
Number of consecutive losing trades that automatically trips the
circuit breaker regardless of the dollar amount lost.
"""

# ---------------------------------------------------------------------------
# Time-based controls
# ---------------------------------------------------------------------------

CIRCUIT_BREAKER_COOLDOWN_MINUTES: int = 60
"""
Mandatory cooldown period after the circuit breaker trips.  The breaker
cannot be reset (even by an operator) until this window has elapsed.
"""

PRE_EVENT_BLACKOUT_MINUTES: int = 30
"""
No new positions may be opened within this many minutes before a
scheduled high-impact macro event (e.g. FOMC, NFP).
"""

POST_EVENT_BLACKOUT_MINUTES: int = 15
"""
No new positions may be opened within this many minutes after a
scheduled high-impact macro event, to allow volatility to settle.
"""
