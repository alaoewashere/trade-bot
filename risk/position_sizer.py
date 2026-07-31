"""
risk/position_sizer.py
======================
Stateless position-sizing utility with three strategies.

All methods are pure static functions — no external I/O, no state.
Each returns a dict with at minimum the keys:
  quantity        — number of units to trade
  risk_usd        — maximum dollar risk for this position
  position_value  — notional USD value at the expected entry price
  method          — name of the sizing strategy used

Additional strategy-specific keys are documented per method.
"""

from __future__ import annotations

import math
import logging

logger = logging.getLogger(__name__)


class PositionSizer:
    """
    Collection of position-sizing algorithms.

    None of these methods send orders or touch broker APIs; they only do
    arithmetic.  The caller is responsible for enforcing hard caps
    (e.g. MAX_POSITION_SIZE_USD) after calling these methods.
    """

    # ------------------------------------------------------------------
    # 1. Fixed fractional
    # ------------------------------------------------------------------

    @staticmethod
    def fixed_fractional(
        account_size: float,
        risk_pct: float,
        entry: float,
        stop_loss: float,
    ) -> dict:
        """
        Size a position by risking a fixed percentage of account equity.

        The number of units is chosen so that if the trade hits the
        stop-loss the total loss equals exactly ``account_size * risk_pct``.

        Parameters
        ----------
        account_size:
            Total account equity in USD.
        risk_pct:
            Fraction of account to risk (e.g. 0.01 = 1 %).
        entry:
            Expected fill price per unit.
        stop_loss:
            Stop-loss price per unit.

        Returns
        -------
        dict with keys:
          quantity        — units to trade (float, truncated to 8 dp)
          risk_usd        — dollar amount at risk
          position_value  — notional value of the position
          stop_distance   — absolute price distance to stop
          method          — "fixed_fractional"

        Raises
        ------
        ValueError
            If entry <= 0 or stop_loss == entry.
        """
        if entry <= 0:
            raise ValueError(f"entry must be positive, got {entry}")
        if math.isclose(entry, stop_loss, rel_tol=1e-9):
            raise ValueError(f"entry and stop_loss are equal ({entry}); cannot size position.")

        risk_usd = account_size * risk_pct
        stop_distance = abs(entry - stop_loss)
        quantity = risk_usd / stop_distance
        position_value = quantity * entry

        logger.debug(
            "fixed_fractional: acct=%.2f risk_pct=%.4f entry=%.4f sl=%.4f "
            "-> qty=%.8f risk_usd=%.2f pos_val=%.2f",
            account_size, risk_pct, entry, stop_loss, quantity, risk_usd, position_value,
        )

        return {
            "quantity": round(quantity, 8),
            "risk_usd": round(risk_usd, 4),
            "position_value": round(position_value, 4),
            "stop_distance": round(stop_distance, 8),
            "method": "fixed_fractional",
        }

    # ------------------------------------------------------------------
    # 2. ATR-based
    # ------------------------------------------------------------------

    @staticmethod
    def atr_based(
        account_size: float,
        risk_pct: float,
        entry: float,
        atr: float,
        atr_multiplier: float = 2.0,
    ) -> dict:
        """
        Size a position using the Average True Range as the stop distance.

        The stop is placed at ``entry ± atr * atr_multiplier``; the
        position size is then computed so that hitting the stop costs
        exactly ``account_size * risk_pct``.

        Parameters
        ----------
        account_size:
            Total account equity in USD.
        risk_pct:
            Fraction of account to risk (e.g. 0.01 = 1 %).
        entry:
            Expected fill price per unit.
        atr:
            Average True Range for the instrument over the chosen lookback.
        atr_multiplier:
            Multiplier applied to ATR to determine stop distance.
            Default is 2.0 (a common volatility-adjusted stop).

        Returns
        -------
        dict with keys:
          quantity        — units to trade
          risk_usd        — dollar amount at risk
          position_value  — notional value of the position
          stop_distance   — ATR-derived stop distance in price units
          atr             — ATR value used
          atr_multiplier  — multiplier used
          method          — "atr_based"

        Raises
        ------
        ValueError
            If atr <= 0 or entry <= 0.
        """
        if entry <= 0:
            raise ValueError(f"entry must be positive, got {entry}")
        if atr <= 0:
            raise ValueError(f"ATR must be positive, got {atr}")
        if atr_multiplier <= 0:
            raise ValueError(f"atr_multiplier must be positive, got {atr_multiplier}")

        stop_distance = atr * atr_multiplier
        risk_usd = account_size * risk_pct
        quantity = risk_usd / stop_distance
        position_value = quantity * entry

        logger.debug(
            "atr_based: acct=%.2f risk_pct=%.4f entry=%.4f atr=%.4f mult=%.2f "
            "-> qty=%.8f risk_usd=%.2f pos_val=%.2f",
            account_size, risk_pct, entry, atr, atr_multiplier,
            quantity, risk_usd, position_value,
        )

        return {
            "quantity": round(quantity, 8),
            "risk_usd": round(risk_usd, 4),
            "position_value": round(position_value, 4),
            "stop_distance": round(stop_distance, 8),
            "atr": atr,
            "atr_multiplier": atr_multiplier,
            "method": "atr_based",
        }

    # ------------------------------------------------------------------
    # 3. Kelly Criterion
    # ------------------------------------------------------------------

    @staticmethod
    def kelly_criterion(
        win_rate: float,
        avg_win: float,
        avg_loss: float,
        account_size: float,
        entry: float,
        max_kelly_fraction: float = 0.25,
    ) -> dict:
        """
        Size a position using a fractional Kelly Criterion.

        The full Kelly fraction is:
            f* = (win_rate / avg_loss) - ((1 - win_rate) / avg_win)

        This implementation caps the fraction at *max_kelly_fraction* to
        reduce volatility (the so-called "fractional Kelly").

        Parameters
        ----------
        win_rate:
            Historical probability of a winning trade (0 < win_rate < 1).
        avg_win:
            Average winning trade magnitude in USD (positive).
        avg_loss:
            Average losing trade magnitude in USD (positive).
        account_size:
            Total account equity in USD.
        entry:
            Expected fill price per unit.
        max_kelly_fraction:
            Upper cap on the Kelly fraction.  0.25 (25 % of equity) is a
            common conservative setting.

        Returns
        -------
        dict with keys:
          quantity          — units to trade
          risk_usd          — USD amount allocated to the position
          position_value    — notional value of the position
          kelly_fraction    — raw (uncapped) Kelly fraction
          applied_fraction  — fraction actually used (capped)
          expected_value    — per-trade expected value in USD
          method            — "kelly_criterion"

        Raises
        ------
        ValueError
            If win_rate is out of (0, 1) range or avg_win / avg_loss <= 0.
        """
        if not (0.0 < win_rate < 1.0):
            raise ValueError(f"win_rate must be in (0, 1), got {win_rate}")
        if avg_win <= 0:
            raise ValueError(f"avg_win must be positive, got {avg_win}")
        if avg_loss <= 0:
            raise ValueError(f"avg_loss must be positive, got {avg_loss}")
        if entry <= 0:
            raise ValueError(f"entry must be positive, got {entry}")
        if max_kelly_fraction <= 0:
            raise ValueError(f"max_kelly_fraction must be positive, got {max_kelly_fraction}")

        lose_rate = 1.0 - win_rate

        # Full Kelly: f* = (p / b) - (q / a)
        # where p = win_rate, q = lose_rate, b = avg_win, a = avg_loss
        kelly_fraction = (win_rate / avg_loss) - (lose_rate / avg_win)

        # Negative Kelly means the edge is negative — do not trade
        if kelly_fraction <= 0:
            logger.warning(
                "kelly_criterion: negative Kelly fraction (%.4f) — "
                "no statistical edge; returning zero-size position.",
                kelly_fraction,
            )
            expected_value = (win_rate * avg_win) - (lose_rate * avg_loss)
            return {
                "quantity": 0.0,
                "risk_usd": 0.0,
                "position_value": 0.0,
                "kelly_fraction": round(kelly_fraction, 6),
                "applied_fraction": 0.0,
                "expected_value": round(expected_value, 4),
                "method": "kelly_criterion",
            }

        # Apply cap
        applied_fraction = min(kelly_fraction, max_kelly_fraction)

        risk_usd = account_size * applied_fraction
        quantity = risk_usd / entry
        position_value = quantity * entry  # same as risk_usd but explicit
        expected_value = (win_rate * avg_win) - (lose_rate * avg_loss)

        logger.debug(
            "kelly_criterion: win_rate=%.3f avg_win=%.2f avg_loss=%.2f "
            "kelly=%.4f applied=%.4f -> qty=%.8f ev=%.2f",
            win_rate, avg_win, avg_loss, kelly_fraction, applied_fraction,
            quantity, expected_value,
        )

        return {
            "quantity": round(quantity, 8),
            "risk_usd": round(risk_usd, 4),
            "position_value": round(position_value, 4),
            "kelly_fraction": round(kelly_fraction, 6),
            "applied_fraction": round(applied_fraction, 6),
            "expected_value": round(expected_value, 4),
            "method": "kelly_criterion",
        }
