"""StatisticalModel — linear regression slope, z-score mean reversion, volatility ratio."""
from __future__ import annotations

import numpy as np
import structlog

from prediction_engine.schemas import ModelOutput

logger = structlog.get_logger(__name__)

MIN_CANDLES = 30
REGRESSION_WINDOW = 20
ZSCORE_WINDOW = 20
VOL_SHORT_WINDOW = 10
VOL_LONG_WINDOW = 60


class StatisticalModel:
    """Statistical model using regression, z-score, and volatility regime analysis."""

    name = "statistical"

    def predict(self, market_data: dict) -> ModelOutput:
        symbol: str = market_data.get("symbol", "UNKNOWN")
        timeframe: str = market_data.get("timeframe", "1h")
        closes_raw = market_data.get("closes", [])

        def _neutral(reason: str) -> ModelOutput:
            logger.debug("statistical_model_neutral", symbol=symbol, reason=reason)
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
        current_price = closes[-1]

        bull_signals: list[str] = []
        bear_signals: list[str] = []
        metadata: dict = {}

        # ------------------------------------------------------------------ Linear Regression Slope
        slope = 0.0
        try:
            window_closes = closes[-REGRESSION_WINDOW:]
            x = np.arange(len(window_closes), dtype=float)
            # Normalise x so slope is in price-per-bar units
            coeffs = np.polyfit(x, window_closes, 1)
            slope = float(coeffs[0])
            slope_pct = slope / current_price * 100  # slope as % of price per bar

            metadata["slope"] = round(slope, 6)
            metadata["slope_pct_per_bar"] = round(slope_pct, 6)

            if slope_pct > 0.05:
                bull_signals.append(
                    f"Positive regression slope over {REGRESSION_WINDOW} bars "
                    f"({slope_pct:+.4f}% per bar)"
                )
            elif slope_pct < -0.05:
                bear_signals.append(
                    f"Negative regression slope over {REGRESSION_WINDOW} bars "
                    f"({slope_pct:+.4f}% per bar)"
                )
            # Residual standard deviation as a volatility measure
            predicted = np.polyval(coeffs, x)
            residuals = window_closes - predicted
            residual_std = float(np.std(residuals))
            metadata["residual_std"] = round(residual_std, 6)
        except Exception as exc:
            logger.warning("regression_failed", error=str(exc))

        # ------------------------------------------------------------------ Z-Score (mean reversion)
        z_score = 0.0
        try:
            mean_window = closes[-ZSCORE_WINDOW:]
            mean_val = float(np.mean(mean_window))
            std_val = float(np.std(mean_window))

            if std_val > 0:
                z_score = (current_price - mean_val) / std_val
            else:
                z_score = 0.0

            metadata["z_score"] = round(z_score, 4)
            metadata["mean_20"] = round(mean_val, 4)

            if z_score < -1.5:
                bull_signals.append(
                    f"Mean reversion opportunity: price {z_score:.2f} std devs below 20-period mean "
                    f"(mean={mean_val:.4f})"
                )
            elif z_score < -2.5:
                bull_signals.append(
                    f"Extreme mean reversion: price {z_score:.2f} std devs below mean — strong bull signal"
                )
            elif z_score > 1.5:
                bear_signals.append(
                    f"Mean reversion opportunity: price {z_score:.2f} std devs above 20-period mean "
                    f"(mean={mean_val:.4f})"
                )
            elif z_score > 2.5:
                bear_signals.append(
                    f"Extreme mean reversion: price {z_score:.2f} std devs above mean — strong bear signal"
                )
        except Exception as exc:
            logger.warning("zscore_failed", error=str(exc))

        # ------------------------------------------------------------------ Volatility ratio
        vol_ratio = 1.0
        try:
            if len(closes) >= VOL_LONG_WINDOW + 1:
                returns = np.diff(np.log(closes + 1e-10))
                recent_vol = float(np.std(returns[-VOL_SHORT_WINDOW:]))
                hist_vol = float(np.std(returns[-VOL_LONG_WINDOW:]))
                vol_ratio = (recent_vol / hist_vol) if hist_vol > 0 else 1.0
                metadata["vol_ratio"] = round(vol_ratio, 4)
                metadata["recent_vol_annualised"] = round(recent_vol * (252 ** 0.5), 4)

                if vol_ratio > 2.0:
                    bear_signals.append(
                        f"Volatility spike: recent vol is {vol_ratio:.2f}x historical "
                        f"— elevated risk/uncertainty"
                    )
                elif vol_ratio < 0.5:
                    bull_signals.append(
                        f"Volatility compression ({vol_ratio:.2f}x historical) — low-vol regime, "
                        f"potential trend continuation"
                    )
            else:
                metadata["vol_ratio"] = 1.0
        except Exception as exc:
            logger.warning("vol_ratio_failed", error=str(exc))

        # ------------------------------------------------------------------ Price range estimate
        try:
            recent_range = np.std(closes[-ZSCORE_WINDOW:])
            predicted_low = max(0.0, current_price - recent_range)
            predicted_high = current_price + recent_range
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
