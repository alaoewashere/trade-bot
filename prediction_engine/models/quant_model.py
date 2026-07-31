"""QuantModel — autocorrelation, Hurst exponent, historical volatility rank."""
from __future__ import annotations

import numpy as np
import structlog

from prediction_engine.schemas import ModelOutput

logger = structlog.get_logger(__name__)

MIN_CANDLES = 50
HURST_WINDOW = 50    # minimum candles needed for Hurst estimate
HV_LONG_WINDOW = 252  # trading days for HV rank


class QuantModel:
    """Quantitative factor model: momentum/mean-reversion regime via Hurst + autocorrelation."""

    name = "quant"

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def predict(self, market_data: dict) -> ModelOutput:
        symbol: str = market_data.get("symbol", "UNKNOWN")
        timeframe: str = market_data.get("timeframe", "1h")
        closes_raw = market_data.get("closes", [])

        def _neutral(reason: str) -> ModelOutput:
            logger.debug("quant_model_neutral", symbol=symbol, reason=reason)
            return ModelOutput(
                model_name=self.name,
                symbol=symbol,
                timeframe=timeframe,
                direction="neutral",
                bull_probability=0.5,
                bear_probability=0.5,
                confidence=0.0,
                supporting_evidence=[reason],
                contradicting_evidence=[],
                metadata={},
            )

        if len(closes_raw) < MIN_CANDLES:
            return _neutral(f"Insufficient data: {len(closes_raw)} candles (need {MIN_CANDLES})")

        closes = np.array(closes_raw, dtype=float)
        returns = np.diff(np.log(closes + 1e-12))  # log-returns

        bull_signals: list[str] = []
        bear_signals: list[str] = []
        metadata: dict = {}

        current_price = float(closes[-1])

        # ------------------------------------------------------------------ Autocorrelation of returns
        try:
            lag1_autocorr = self._autocorrelation(returns, lag=1)
            lag5_autocorr = self._autocorrelation(returns, lag=5)
            metadata["autocorr_lag1"] = round(lag1_autocorr, 4)
            metadata["autocorr_lag5"] = round(lag5_autocorr, 4)

            # Positive autocorrelation at lag-1 → momentum (trend-following signal)
            if lag1_autocorr > 0.10:
                recent_return = float(returns[-1])
                if recent_return > 0:
                    bull_signals.append(
                        f"Positive return autocorrelation (lag-1={lag1_autocorr:.3f}) "
                        f"with positive last return — momentum bull"
                    )
                elif recent_return < 0:
                    bear_signals.append(
                        f"Positive return autocorrelation (lag-1={lag1_autocorr:.3f}) "
                        f"with negative last return — momentum bear"
                    )
            elif lag1_autocorr < -0.10:
                # Negative autocorrelation → mean reversion tendency
                recent_return = float(returns[-1])
                if recent_return < 0:
                    bull_signals.append(
                        f"Negative autocorrelation (lag-1={lag1_autocorr:.3f}) with down move "
                        f"— mean reversion bull"
                    )
                elif recent_return > 0:
                    bear_signals.append(
                        f"Negative autocorrelation (lag-1={lag1_autocorr:.3f}) with up move "
                        f"— mean reversion bear"
                    )
        except Exception as exc:
            logger.warning("autocorr_failed", error=str(exc))

        # ------------------------------------------------------------------ Hurst Exponent
        try:
            hurst = self._hurst_exponent(closes[-HURST_WINDOW:])
            metadata["hurst_exponent"] = round(hurst, 4)

            if hurst > 0.60:
                # Strong trending regime
                recent_trend = float(np.mean(returns[-10:]))
                if recent_trend > 0:
                    bull_signals.append(
                        f"Hurst exponent {hurst:.3f} > 0.6 — trending regime with bullish recent momentum"
                    )
                elif recent_trend < 0:
                    bear_signals.append(
                        f"Hurst exponent {hurst:.3f} > 0.6 — trending regime with bearish recent momentum"
                    )
            elif hurst < 0.40:
                # Mean-reverting regime
                recent_return = float(returns[-1])
                if recent_return < -0.001:
                    bull_signals.append(
                        f"Hurst exponent {hurst:.3f} < 0.4 — mean-reverting regime, "
                        f"fade recent down move (bull)"
                    )
                elif recent_return > 0.001:
                    bear_signals.append(
                        f"Hurst exponent {hurst:.3f} < 0.4 — mean-reverting regime, "
                        f"fade recent up move (bear)"
                    )
            else:
                metadata["regime"] = "random_walk"
        except Exception as exc:
            logger.warning("hurst_failed", error=str(exc))
            hurst = 0.5

        # ------------------------------------------------------------------ Historical Volatility Rank
        try:
            hv_rank, current_hv, hv_pct = self._hv_rank(returns)
            metadata["hv_rank_pct"] = round(hv_rank, 2)
            metadata["current_hv_annualised"] = round(current_hv, 4)

            if hv_rank > 80:
                bear_signals.append(
                    f"HV rank at {hv_rank:.0f}th percentile — historically high vol, "
                    f"elevated risk of continued dislocation"
                )
            elif hv_rank < 20:
                bull_signals.append(
                    f"HV rank at {hv_rank:.0f}th percentile — vol compression, "
                    f"potential for breakout or trend continuation"
                )
            elif hv_rank > 60:
                bear_signals.append(
                    f"HV rank elevated ({hv_rank:.0f}th pct) — above-average volatility environment"
                )
        except Exception as exc:
            logger.warning("hv_rank_failed", error=str(exc))

        # ------------------------------------------------------------------ Price range estimate
        try:
            recent_std = float(np.std(returns[-20:])) * current_price
            predicted_low = max(0.0, current_price - recent_std * 1.5)
            predicted_high = current_price + recent_std * 1.5
        except Exception:
            spread = current_price * 0.01
            predicted_low = current_price - spread
            predicted_high = current_price + spread

        # ------------------------------------------------------------------ Aggregate
        bull_count = len(bull_signals)
        bear_count = len(bear_signals)
        total = bull_count + bear_count

        if total == 0:
            bull_prob = 0.5
            bear_prob = 0.5
            direction = "neutral"
            confidence = 0.0
        else:
            bull_prob = bull_count / total
            bear_prob = bear_count / total
            imbalance = abs(bull_prob - bear_prob)
            confidence = min(imbalance * 1.5, 1.0)

            if bull_prob > 0.55:
                direction = "bullish"
            elif bear_prob > 0.55:
                direction = "bearish"
            else:
                direction = "neutral"

        return ModelOutput(
            model_name=self.name,
            symbol=symbol,
            timeframe=timeframe,
            direction=direction,
            bull_probability=round(bull_prob, 4),
            bear_probability=round(bear_prob, 4),
            confidence=round(confidence, 4),
            predicted_low=round(predicted_low, 6),
            predicted_high=round(predicted_high, 6),
            supporting_evidence=bull_signals if direction in ("bullish", "neutral") else bear_signals,
            contradicting_evidence=bear_signals if direction in ("bullish", "neutral") else bull_signals,
            metadata=metadata,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _autocorrelation(series: np.ndarray, lag: int = 1) -> float:
        """Pearson autocorrelation at a given lag."""
        if len(series) <= lag + 1:
            return 0.0
        x = series[:-lag]
        y = series[lag:]
        if np.std(x) == 0 or np.std(y) == 0:
            return 0.0
        corr = float(np.corrcoef(x, y)[0, 1])
        return corr if not np.isnan(corr) else 0.0

    @staticmethod
    def _hurst_exponent(prices: np.ndarray) -> float:
        """
        Estimate Hurst exponent via R/S analysis.
        H > 0.5 → trending (persistence)
        H < 0.5 → mean-reverting (anti-persistence)
        H = 0.5 → random walk
        """
        n = len(prices)
        if n < 20:
            return 0.5

        lags = []
        rs_values = []

        for lag in range(10, n // 2, max(1, (n // 2 - 10) // 8)):
            sub = prices[:lag]
            mean_sub = np.mean(sub)
            deviations = np.cumsum(sub - mean_sub)
            r = float(np.max(deviations) - np.min(deviations))
            s = float(np.std(sub, ddof=1))
            if s > 0:
                lags.append(np.log(lag))
                rs_values.append(np.log(r / s))

        if len(lags) < 2:
            return 0.5

        try:
            coeffs = np.polyfit(lags, rs_values, 1)
            hurst = float(coeffs[0])
            # Clamp to sensible range
            return float(np.clip(hurst, 0.0, 1.0))
        except Exception:
            return 0.5

    @staticmethod
    def _hv_rank(returns: np.ndarray) -> tuple[float, float, float]:
        """
        Returns (rank_percentile, current_hv_annualised, historical_hv_annualised).
        Uses rolling 20-bar HV windows over the full return series.
        """
        window = 20
        annual_factor = 252 ** 0.5

        if len(returns) < window + 1:
            current_hv = float(np.std(returns)) * annual_factor
            return 50.0, current_hv, current_hv

        rolling_hvs = [
            float(np.std(returns[i: i + window])) * annual_factor
            for i in range(len(returns) - window + 1)
        ]
        current_hv = rolling_hvs[-1]
        all_hvs = np.array(rolling_hvs)
        rank_pct = float(np.sum(all_hvs <= current_hv) / len(all_hvs) * 100)
        hist_hv = float(np.mean(all_hvs))
        return rank_pct, current_hv, hist_hv
