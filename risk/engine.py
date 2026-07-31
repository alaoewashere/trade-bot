"""
risk/engine.py
==============
RiskEngine — evaluates proposed trade signals against the fund's risk rules
and returns a RiskAssessment detailing approval status, position sizing,
and all intermediate checks.

Design principles
-----------------
* Pure function semantics: RiskEngine.evaluate() is stateless (no Redis, no
  side-effects).  It reads config from settings and limits from limits.py.
* Parametric VaR at 95 % confidence is computed using numpy's percentile on
  a simulated return distribution derived from the signal's stop-loss width.
* All monetary figures are in USD.
"""

from __future__ import annotations

import logging
import math
from typing import Any

import numpy as np

from graph.state import ConsensusResult, RiskAssessment, StrategySignal
from risk.limits import (
    MAX_CONSECUTIVE_LOSSES,
    MAX_OPEN_POSITIONS,
    MAX_PORTFOLIO_CORRELATION,
    MAX_PORTFOLIO_HEAT_PCT,
    MAX_POSITION_SIZE_USD,
    MIN_CONFIDENCE_PCT,
    MIN_LIQUIDITY_24H_USD,
    MIN_RISK_REWARD,
)

logger = logging.getLogger(__name__)

# Fraction of account equity risked per trade (fixed-fractional baseline)
_DEFAULT_RISK_PCT: float = 0.01  # 1 %

# Number of Monte Carlo samples for parametric VaR estimation
_VAR_SAMPLES: int = 10_000

# Random seed for reproducibility
_RNG_SEED: int = 42


class RiskEngine:
    """
    Evaluates a StrategySignal + ConsensusResult against all risk rules.

    Parameters
    ----------
    account_equity_usd:
        Current total account equity in USD.  Used to compute position
        size, portfolio heat, and VaR as fractions of the account.
    """

    def __init__(self, account_equity_usd: float = 10_000.0) -> None:
        self.account_equity_usd = account_equity_usd

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate(
        self,
        strategy_signal: StrategySignal,
        consensus: ConsensusResult,
        current_portfolio: dict[str, Any],
        market_data: dict[str, Any],
    ) -> RiskAssessment:
        """
        Run the full risk-check pipeline and return a RiskAssessment.

        Parameters
        ----------
        strategy_signal:
            The trade signal to evaluate.
        consensus:
            The multi-agent consensus result (used for confidence gating).
        current_portfolio:
            Dict describing current open positions.  Expected keys:
              open_positions: list[dict] — each with 'symbol', 'side',
                  'size_usd', 'entry', 'stop_loss', 'returns' (list[float])
              total_heat_pct: float — existing portfolio heat percentage
        market_data:
            Raw market data dict.  Expected keys (best-effort):
              volume_24h_usd: float
              price: float (or last_price)

        Returns
        -------
        RiskAssessment
            Fully populated model.  If ``approved=False``, all monetary
            fields are set to 0 and ``rejection_reasons`` lists the causes.
        """
        rejection_reasons: list[str] = []

        # ----------------------------------------------------------------
        # 1. Derive entry price
        # ----------------------------------------------------------------
        entry_price = self._resolve_entry_price(strategy_signal, market_data)

        # ----------------------------------------------------------------
        # 2. Confidence gate
        # ----------------------------------------------------------------
        confidence_pct = consensus.confidence_pct
        if confidence_pct < MIN_CONFIDENCE_PCT:
            rejection_reasons.append(
                f"Confidence {confidence_pct:.1f}% is below minimum {MIN_CONFIDENCE_PCT:.1f}%."
            )

        # ----------------------------------------------------------------
        # 3. Risk-reward check
        # ----------------------------------------------------------------
        rr = self._compute_risk_reward(strategy_signal, entry_price)
        if rr < MIN_RISK_REWARD:
            rejection_reasons.append(
                f"Risk-reward {rr:.2f} is below minimum {MIN_RISK_REWARD:.2f}."
            )

        # ----------------------------------------------------------------
        # 4. Position sizing (fixed fractional, confidence-scaled)
        # ----------------------------------------------------------------
        # Reduce effective risk fraction as confidence falls from 100% to 55%
        confidence_scalar = (confidence_pct - MIN_CONFIDENCE_PCT) / (100.0 - MIN_CONFIDENCE_PCT)
        confidence_scalar = max(0.0, min(1.0, confidence_scalar))
        effective_risk_pct = _DEFAULT_RISK_PCT * (0.5 + 0.5 * confidence_scalar)

        max_risk_usd = self.account_equity_usd * effective_risk_pct
        max_risk_usd = min(max_risk_usd, MAX_POSITION_SIZE_USD)

        stop_distance = abs(entry_price - strategy_signal.stop_loss)
        if stop_distance <= 0:
            rejection_reasons.append("Stop-loss distance is zero; cannot size position.")
            stop_distance = entry_price * 0.01  # fallback to 1% for downstream calcs

        position_size_units = max_risk_usd / stop_distance
        position_size_usd = position_size_units * entry_price

        # Hard cap
        if position_size_usd > MAX_POSITION_SIZE_USD:
            position_size_usd = MAX_POSITION_SIZE_USD
            position_size_units = position_size_usd / entry_price

        # ----------------------------------------------------------------
        # 5. Portfolio heat check
        # ----------------------------------------------------------------
        existing_heat_pct: float = float(current_portfolio.get("total_heat_pct", 0.0))
        new_heat_pct = (max_risk_usd / self.account_equity_usd) * 100.0
        total_heat_pct = existing_heat_pct + new_heat_pct

        if total_heat_pct > MAX_PORTFOLIO_HEAT_PCT:
            rejection_reasons.append(
                f"Portfolio heat {total_heat_pct:.1f}% would exceed limit "
                f"{MAX_PORTFOLIO_HEAT_PCT:.1f}%."
            )

        # ----------------------------------------------------------------
        # 6. Open-positions count check
        # ----------------------------------------------------------------
        open_positions: list[dict] = current_portfolio.get("open_positions", [])
        open_count = len(open_positions)
        if open_count >= MAX_OPEN_POSITIONS:
            rejection_reasons.append(
                f"Open positions ({open_count}) at or above limit ({MAX_OPEN_POSITIONS})."
            )

        # ----------------------------------------------------------------
        # 7. Parametric VaR at 95 %
        # ----------------------------------------------------------------
        var_95 = self._compute_var_95(
            position_size_usd=position_size_usd,
            entry_price=entry_price,
            stop_loss=strategy_signal.stop_loss,
        )
        cvar_95 = self._compute_cvar_95(
            position_size_usd=position_size_usd,
            entry_price=entry_price,
            stop_loss=strategy_signal.stop_loss,
        )

        # Win probability from consensus, directionally matched to the trade
        if strategy_signal.direction == "LONG":
            win_prob = consensus.bull_probability
        elif strategy_signal.direction == "SHORT":
            win_prob = consensus.bear_probability
        else:
            win_prob = confidence_pct / 100.0

        kelly_fraction = self._compute_kelly_fraction(win_prob, rr)

        max_profit_usd = max_risk_usd * rr
        expected_value_usd = self._compute_expected_value_usd(
            win_prob=win_prob,
            max_profit_usd=max_profit_usd,
            max_loss_usd=max_risk_usd,
        )

        var_95_pct_of_equity = (
            (var_95 / self.account_equity_usd) * 100.0 if self.account_equity_usd > 0 else 0.0
        )
        risk_category = self._classify_risk_category(
            risk_score=consensus.risk_score,
            portfolio_heat_pct=total_heat_pct,
            var_95_pct_of_equity=var_95_pct_of_equity,
        )

        # ----------------------------------------------------------------
        # 8. Correlation check
        # ----------------------------------------------------------------
        correlation_ok = self._check_correlation(
            strategy_signal.symbol,
            open_positions,
            market_data,
        )
        if not correlation_ok:
            rejection_reasons.append(
                f"New position correlation with portfolio exceeds limit "
                f"({MAX_PORTFOLIO_CORRELATION:.2f})."
            )

        # ----------------------------------------------------------------
        # 9. Liquidity check (24h volume >= $1M)
        # ----------------------------------------------------------------
        volume_24h = self._resolve_volume_24h(market_data)
        liquidity_ok = volume_24h >= MIN_LIQUIDITY_24H_USD
        if not liquidity_ok:
            rejection_reasons.append(
                f"24h volume ${volume_24h:,.0f} is below minimum "
                f"${MIN_LIQUIDITY_24H_USD:,.0f}."
            )

        # ----------------------------------------------------------------
        # 10. Build RiskAssessment
        # ----------------------------------------------------------------
        approved = len(rejection_reasons) == 0

        if not approved:
            logger.warning(
                "risk_engine_rejected symbol=%s reasons=%s",
                strategy_signal.symbol,
                rejection_reasons,
            )
            return RiskAssessment(
                approved=False,
                position_size_usd=0.0,
                position_size_units=0.0,
                entry_price=entry_price,
                stop_loss=strategy_signal.stop_loss,
                take_profit=strategy_signal.take_profit,
                risk_reward=rr,
                max_risk_usd=0.0,
                portfolio_heat_pct=existing_heat_pct,
                var_95=var_95,
                correlation_check=correlation_ok,
                liquidity_check=liquidity_ok,
                rejection_reasons=rejection_reasons,
                cvar_95=cvar_95,
                kelly_fraction=0.0,
                expected_value_usd=0.0,
                risk_category=risk_category,
            )

        logger.info(
            "risk_engine_approved symbol=%s size_usd=%.2f rr=%.2f heat=%.1f%%",
            strategy_signal.symbol,
            position_size_usd,
            rr,
            total_heat_pct,
        )

        return RiskAssessment(
            approved=True,
            position_size_usd=round(position_size_usd, 4),
            position_size_units=round(position_size_units, 8),
            entry_price=entry_price,
            stop_loss=strategy_signal.stop_loss,
            take_profit=strategy_signal.take_profit,
            risk_reward=round(rr, 3),
            max_risk_usd=round(max_risk_usd, 4),
            portfolio_heat_pct=round(total_heat_pct, 2),
            var_95=round(var_95, 4),
            correlation_check=correlation_ok,
            liquidity_check=liquidity_ok,
            rejection_reasons=[],
            cvar_95=round(cvar_95, 4),
            kelly_fraction=round(kelly_fraction, 4),
            expected_value_usd=round(expected_value_usd, 4),
            risk_category=risk_category,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_entry_price(
        self,
        signal: StrategySignal,
        market_data: dict[str, Any],
    ) -> float:
        """
        Determine the expected entry price.

        Uses the midpoint of the signal's entry zone; falls back to the
        current market price from market_data if the zone is degenerate.
        """
        mid = (signal.entry_zone_low + signal.entry_zone_high) / 2.0
        if mid > 0:
            return mid

        market_price = market_data.get("price") or market_data.get("last_price") or 0.0
        return float(market_price)

    def _compute_risk_reward(self, signal: StrategySignal, entry_price: float) -> float:
        """
        Calculate the actual risk-to-reward ratio from the signal parameters.

        R:R = |take_profit - entry| / |entry - stop_loss|
        """
        reward = abs(signal.take_profit - entry_price)
        risk = abs(entry_price - signal.stop_loss)

        if risk == 0:
            return 0.0

        return reward / risk

    def _compute_var_95(
        self,
        position_size_usd: float,
        entry_price: float,
        stop_loss: float,
    ) -> float:
        """
        Estimate the 95th-percentile Value at Risk using parametric simulation.

        Models daily P&L as normally distributed with:
          - mean = 0 (conservative assumption)
          - std  = position_size_usd * (stop_distance / entry_price)

        VaR is reported as a positive dollar figure representing the loss
        that will not be exceeded 95% of the time.

        Parameters
        ----------
        position_size_usd:
            Notional USD value of the position.
        entry_price:
            Expected fill price.
        stop_loss:
            Stop-loss price level.
        """
        if entry_price <= 0:
            return 0.0

        stop_pct = abs(entry_price - stop_loss) / entry_price
        daily_vol_usd = position_size_usd * stop_pct

        rng = np.random.default_rng(_RNG_SEED)
        simulated_pnl = rng.normal(loc=0.0, scale=daily_vol_usd, size=_VAR_SAMPLES)

        # VaR = negative 5th percentile (loss at 95% confidence)
        var_95 = float(-np.percentile(simulated_pnl, 5))
        return max(var_95, 0.0)

    def _compute_cvar_95(
        self,
        position_size_usd: float,
        entry_price: float,
        stop_loss: float,
    ) -> float:
        """
        Estimate Expected Shortfall (CVaR) at 95% confidence.

        Uses the same Monte Carlo return distribution as _compute_var_95
        (same seed/samples for consistency) and averages the tail beyond
        the 5th percentile rather than taking the single cutoff point,
        which is why CVaR is always >= VaR for the same distribution.
        """
        if entry_price <= 0:
            return 0.0

        stop_pct = abs(entry_price - stop_loss) / entry_price
        daily_vol_usd = position_size_usd * stop_pct

        rng = np.random.default_rng(_RNG_SEED)
        simulated_pnl = rng.normal(loc=0.0, scale=daily_vol_usd, size=_VAR_SAMPLES)

        cutoff = np.percentile(simulated_pnl, 5)
        tail_losses = simulated_pnl[simulated_pnl <= cutoff]
        if tail_losses.size == 0:
            return 0.0

        cvar_95 = float(-np.mean(tail_losses))
        return max(cvar_95, 0.0)

    def _compute_kelly_fraction(self, win_prob: float, risk_reward: float) -> float:
        """
        Kelly Criterion: f* = p - (1-p)/RR.

        Clamped to [0, 0.25] — full/half Kelly is well known to be too
        aggressive for a system with model-estimated (not exact) win
        probabilities, so we cap the "suggested" fraction at 25% of equity
        even when the raw Kelly value is higher.
        """
        if risk_reward <= 0:
            return 0.0
        kelly = win_prob - (1.0 - win_prob) / risk_reward
        return max(0.0, min(kelly, 0.25))

    def _compute_expected_value_usd(
        self,
        win_prob: float,
        max_profit_usd: float,
        max_loss_usd: float,
    ) -> float:
        """EV = P(win)*max_profit - P(loss)*max_loss, in USD."""
        return win_prob * max_profit_usd - (1.0 - win_prob) * max_loss_usd

    def _classify_risk_category(
        self,
        risk_score: float,
        portfolio_heat_pct: float,
        var_95_pct_of_equity: float,
    ) -> str:
        """
        Composite risk_category from three independent signals.

        Thresholds (chosen to be conservative for a fund capped at 20%
        total portfolio heat and a 0-10 risk_score scale):
          - very_low : risk_score < 2  and heat < 5%  and VaR < 2% of equity
          - low      : risk_score < 4  and heat < 10% and VaR < 5% of equity
          - medium   : risk_score < 6  and heat < 15% and VaR < 10% of equity
          - high     : risk_score < 8  and heat < 20% and VaR < 15% of equity
          - extreme  : anything at or above the "high" bounds

        We take the *worst* (highest) category implied by any single
        input so that one bad dimension (e.g. VaR spike) can't be masked
        by two good ones.
        """
        buckets = ["very_low", "low", "medium", "high", "extreme"]

        def _bucket_for(value: float, cutoffs: list[float]) -> int:
            for i, cutoff in enumerate(cutoffs):
                if value < cutoff:
                    return i
            return len(cutoffs)

        score_idx = _bucket_for(risk_score, [2, 4, 6, 8])
        heat_idx = _bucket_for(portfolio_heat_pct, [5, 10, 15, 20])
        var_idx = _bucket_for(var_95_pct_of_equity, [2, 5, 10, 15])

        worst_idx = max(score_idx, heat_idx, var_idx)
        return buckets[min(worst_idx, len(buckets) - 1)]

    def _check_correlation(
        self,
        symbol: str,
        open_positions: list[dict[str, Any]],
        market_data: dict[str, Any],
    ) -> bool:
        """
        Check whether the new position's returns are too correlated with
        the existing portfolio.

        Uses the 'returns' list from each open position to build a
        portfolio returns series, then correlates with the new position's
        recent returns (from market_data).

        Returns True (correlation acceptable) when:
          * There are no existing positions (no correlation risk), OR
          * The computed Pearson r < MAX_PORTFOLIO_CORRELATION, OR
          * Insufficient data to compute correlation (safe pass-through).
        """
        if not open_positions:
            return True  # No existing positions — no correlation to check

        # Collect existing portfolio returns
        portfolio_returns_list: list[list[float]] = []
        for pos in open_positions:
            if pos.get("symbol") == symbol:
                # Same instrument already open — treat as max correlation
                logger.warning(
                    "correlation_check: same symbol %s already in portfolio", symbol
                )
                return False
            pos_returns = pos.get("returns", [])
            if len(pos_returns) >= 10:
                portfolio_returns_list.append(pos_returns)

        if not portfolio_returns_list:
            return True  # No return history — pass through

        # Build equal-weight portfolio returns series
        min_len = min(len(r) for r in portfolio_returns_list)
        if min_len < 10:
            return True  # Too little data

        portfolio_returns = np.mean(
            [r[-min_len:] for r in portfolio_returns_list], axis=0
        )

        # New instrument's recent returns from market_data
        new_returns_raw = (
            market_data.get("returns")
            or market_data.get("daily_returns")
            or []
        )
        if len(new_returns_raw) < 10:
            return True  # Cannot compute — pass through

        new_returns = np.array(new_returns_raw[-min_len:], dtype=float)

        if len(new_returns) != len(portfolio_returns):
            shared = min(len(new_returns), len(portfolio_returns))
            new_returns = new_returns[-shared:]
            portfolio_returns = portfolio_returns[-shared:]

        try:
            corr_matrix = np.corrcoef(new_returns, portfolio_returns)
            pearson_r = float(corr_matrix[0, 1])
        except Exception:
            return True  # Computation failed — pass through conservatively

        if math.isnan(pearson_r):
            return True

        logger.debug("correlation_check symbol=%s pearson_r=%.3f", symbol, pearson_r)
        return abs(pearson_r) < MAX_PORTFOLIO_CORRELATION

    def _resolve_volume_24h(self, market_data: dict[str, Any]) -> float:
        """Extract 24-hour volume in USD from market_data."""
        candidates = [
            "volume_24h_usd",
            "volume_24h",
            "vol_24h_usd",
            "quoteVolume",
            "quote_volume",
        ]
        for key in candidates:
            val = market_data.get(key)
            if val is not None:
                return float(val)

        # Fallback: derive from OHLCV if available
        candles: list[dict] = market_data.get("candles") or market_data.get("ohlcv") or []
        if candles:
            # Use the last candle's volume × close as a rough USD proxy
            last = candles[-1]
            vol = float(last.get("volume", 0))
            close = float(last.get("close", 1))
            return vol * close

        return 0.0
