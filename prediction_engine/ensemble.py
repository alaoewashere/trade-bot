"""EnsembleVoter — combines all 8 model predictions with calibration-adjusted weights."""
from __future__ import annotations

import numpy as np
import structlog

from prediction_engine.schemas import EnsembleResult, ModelOutput

logger = structlog.get_logger(__name__)

BASE_WEIGHTS = {
    "technical": 0.20,
    "macro": 0.10,
    "quant": 0.15,
    "ml": 0.20,
    "statistical": 0.10,
    "sentiment": 0.10,
    "options_flow": 0.10,
    "onchain": 0.05,
}

# Minimum weight factor — even a poorly-calibrated model keeps 10% of its base weight
_MIN_WEIGHT_FACTOR = 0.10
# Maximum evidence items collected per direction
_MAX_EVIDENCE_ITEMS = 6


class EnsembleVoter:
    """
    Weighted ensemble voter that combines ModelOutput predictions into a single EnsembleResult.

    Calibration-adjusted weights are derived from historical accuracy stored in the
    CalibrationTracker. Models without calibration data fall back to BASE_WEIGHTS.
    """

    def __init__(self, calibration_tracker=None) -> None:
        self._calibration_tracker = calibration_tracker

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def vote(
        self,
        outputs: list[ModelOutput],
        symbol: str,
        timeframe: str,
    ) -> EnsembleResult:
        """
        Combine model outputs via calibration-adjusted weighted voting.

        Steps:
        1. Get calibration-adjusted, normalised weights.
        2. Compute weighted bull_prob and bear_prob across all models.
        3. Determine direction by plurality of weighted probability.
        4. Confidence = |bull_prob - bear_prob| * 100, capped at 95.
        5. Predicted range: 25th percentile of lows, 75th percentile of highs.
        6. Risk score = model disagreement (0–10 scale).
        7. Collect top evidence from winning-direction models.
        8. Detect market regime from technical model metadata.
        """
        if not outputs:
            logger.warning("ensemble_voter_no_outputs", symbol=symbol, timeframe=timeframe)
            return self._fallback_result(symbol, timeframe)

        # Step 1: weights
        weights = self._get_adjusted_weights(outputs, symbol, timeframe)

        # Step 2: weighted probabilities
        weighted_bull = 0.0
        weighted_bear = 0.0
        model_contributions: dict[str, float] = {}

        for output in outputs:
            w = weights.get(output.model_name, 0.0)
            weighted_bull += w * output.bull_probability
            weighted_bear += w * output.bear_probability
            model_contributions[output.model_name] = round(w, 4)

        # Ensure they sum to ~1.0 (they should if bear+bull≈1 per model)
        total_prob = weighted_bull + weighted_bear
        if total_prob > 0:
            weighted_bull /= total_prob
            weighted_bear /= total_prob

        weighted_neutral = max(0.0, 1.0 - weighted_bull - weighted_bear)

        # Step 3: direction
        if weighted_bull > 0.50:
            direction = "bullish"
        elif weighted_bear > 0.50:
            direction = "bearish"
        else:
            direction = "neutral"

        # Step 4: confidence
        raw_diff = abs(weighted_bull - weighted_bear)
        confidence_pct = min(raw_diff * 100.0, 95.0)

        # Step 5: predicted price range
        predicted_low, predicted_high = self._aggregate_price_range(outputs)

        # Step 6: risk score
        risk_score = self._compute_risk_score(outputs)

        # Step 7: evidence
        supporting_evidence, contradicting_evidence = self._collect_evidence(outputs, direction)

        # Step 8: regime
        market_regime = self._detect_regime(outputs)

        logger.info(
            "ensemble_vote_complete",
            symbol=symbol,
            timeframe=timeframe,
            direction=direction,
            confidence_pct=round(confidence_pct, 2),
            bull_prob=round(weighted_bull, 4),
            bear_prob=round(weighted_bear, 4),
            risk_score=round(risk_score, 2),
            regime=market_regime,
        )

        return EnsembleResult(
            symbol=symbol,
            timeframe=timeframe,
            direction=direction,
            bull_probability=round(weighted_bull, 4),
            bear_probability=round(weighted_bear, 4),
            neutral_probability=round(weighted_neutral, 4),
            confidence_pct=round(confidence_pct, 2),
            predicted_low=round(predicted_low, 6),
            predicted_high=round(predicted_high, 6),
            risk_score=round(risk_score, 2),
            market_regime=market_regime,
            model_contributions=model_contributions,
            supporting_evidence=supporting_evidence,
            contradicting_evidence=contradicting_evidence,
        )

    # ------------------------------------------------------------------
    # Weight computation
    # ------------------------------------------------------------------

    def _get_adjusted_weights(
        self,
        outputs: list[ModelOutput],
        symbol: str,
        timeframe: str,
    ) -> dict[str, float]:
        """
        Return calibration-adjusted, normalised weights.

        For each model:
          raw_weight = base_weight * max(_MIN_WEIGHT_FACTOR, accuracy_pct / 50.0)

        If accuracy_pct is unavailable the base weight is used unchanged.
        All weights are normalised to sum to 1.0.
        """
        output_names = {o.model_name for o in outputs}
        raw_weights: dict[str, float] = {}

        for output in outputs:
            name = output.model_name
            base_w = BASE_WEIGHTS.get(name, 0.05)

            accuracy: float | None = None
            if self._calibration_tracker is not None:
                try:
                    accuracy = self._calibration_tracker.get_accuracy_sync(
                        symbol, timeframe, name
                    )
                except AttributeError:
                    # CalibrationTracker may only expose async interface;
                    # fall back to cached accuracies if available.
                    try:
                        accuracy = self._calibration_tracker._cache.get(
                            (symbol, timeframe, name)
                        )
                    except Exception:
                        accuracy = None

            if accuracy is not None and accuracy > 0:
                # Scale: 50% accuracy → factor 1.0; 100% → factor 2.0; 25% → factor 0.5 (floored)
                scale = max(_MIN_WEIGHT_FACTOR, accuracy / 50.0)
                raw_weights[name] = base_w * scale
            else:
                raw_weights[name] = base_w

        # Normalise across models actually present in outputs
        total = sum(raw_weights[n] for n in output_names if n in raw_weights)
        if total <= 0:
            # Fallback: equal weights
            eq = 1.0 / len(outputs)
            return {o.model_name: eq for o in outputs}

        return {
            name: raw_weights[name] / total
            for name in output_names
            if name in raw_weights
        }

    # ------------------------------------------------------------------
    # Regime detection
    # ------------------------------------------------------------------

    def _detect_regime(self, outputs: list[ModelOutput]) -> str:
        """
        Derive the current market regime.

        Priority:
        1. Use RSI from the technical model's metadata.
        2. Fall back to a vote-based regime label.
        """
        # Try technical model metadata first
        for output in outputs:
            if output.model_name == "technical":
                rsi = output.metadata.get("rsi")
                if rsi is not None:
                    rsi = float(rsi)
                    if rsi < 30:
                        return "oversold"
                    elif rsi > 70:
                        return "overbought"
                    elif rsi < 45:
                        return "bearish_momentum"
                    elif rsi > 55:
                        return "bullish_momentum"
                    else:
                        return "ranging"

        # Vote-based fallback
        bull_votes = sum(1 for o in outputs if o.direction == "bullish")
        bear_votes = sum(1 for o in outputs if o.direction == "bearish")
        total_votes = len(outputs)

        if total_votes == 0:
            return "unknown"

        bull_frac = bull_votes / total_votes
        bear_frac = bear_votes / total_votes

        if bull_frac >= 0.6:
            return "bullish_trend"
        elif bear_frac >= 0.6:
            return "bearish_trend"
        elif bull_frac >= 0.4 and bear_frac >= 0.4:
            return "mixed"
        else:
            return "neutral"

    # ------------------------------------------------------------------
    # Risk score
    # ------------------------------------------------------------------

    def _compute_risk_score(self, outputs: list[ModelOutput]) -> float:
        """
        Measure disagreement between models on a 0–10 scale.

        Methodology:
          1. Compute the standard deviation of bull_probability across all models.
          2. Scale: std_dev of 0.0 → score 0; std_dev of 0.5 → score 10.
          3. Also add a bonus for models with contradicting evidence.
        """
        if not outputs:
            return 5.0

        bull_probs = np.array([o.bull_probability for o in outputs])
        std_dev = float(np.std(bull_probs))

        # Base disagreement score (0–10 scale; std_dev ranges 0 to 0.5 theoretically)
        base_score = min(std_dev * 20.0, 10.0)

        # Contradicting evidence bonus
        has_contradiction = sum(1 for o in outputs if len(o.contradicting_evidence) > 0)
        contradiction_ratio = has_contradiction / len(outputs)
        bonus = contradiction_ratio * 2.0  # up to +2 points

        return min(base_score + bonus, 10.0)

    # ------------------------------------------------------------------
    # Price range aggregation
    # ------------------------------------------------------------------

    def _aggregate_price_range(
        self, outputs: list[ModelOutput]
    ) -> tuple[float, float]:
        """
        Aggregate predicted price ranges from individual models.

        Returns (predicted_low, predicted_high) using:
        - 25th percentile of all model predicted_lows
        - 75th percentile of all model predicted_highs

        Falls back to the mean ± small spread if no model provides a range.
        """
        lows = [o.predicted_low for o in outputs if o.predicted_low is not None]
        highs = [o.predicted_high for o in outputs if o.predicted_high is not None]

        if lows and highs:
            predicted_low = float(np.percentile(lows, 25))
            predicted_high = float(np.percentile(highs, 75))
        elif lows:
            predicted_low = float(np.percentile(lows, 25))
            predicted_high = predicted_low * 1.02
        elif highs:
            predicted_high = float(np.percentile(highs, 75))
            predicted_low = predicted_high * 0.98
        else:
            # Derive from weighted mean bull_prob as a signal strength proxy
            bull_probs = [o.bull_probability for o in outputs]
            avg_signal = float(np.mean(bull_probs)) if bull_probs else 0.5
            # No price data — return 0/0 sentinel; engine will fill from current_price
            predicted_low = 0.0
            predicted_high = 0.0

        # Sanity check
        if predicted_low > predicted_high:
            predicted_low, predicted_high = predicted_high, predicted_low

        return predicted_low, predicted_high

    # ------------------------------------------------------------------
    # Evidence collection
    # ------------------------------------------------------------------

    def _collect_evidence(
        self,
        outputs: list[ModelOutput],
        direction: str,
    ) -> tuple[list[str], list[str]]:
        """
        Collect top supporting and contradicting evidence strings.

        For the winning direction: gather evidence from models that agree,
        prioritising high-confidence models.
        """
        agreeing = [o for o in outputs if o.direction == direction]
        disagreeing = [o for o in outputs if o.direction != direction and o.direction != "neutral"]

        # Sort agreeing models by confidence descending
        agreeing.sort(key=lambda o: o.confidence, reverse=True)
        disagreeing.sort(key=lambda o: o.confidence, reverse=True)

        supporting: list[str] = []
        for model in agreeing:
            for item in model.supporting_evidence:
                if item and item not in supporting:
                    supporting.append(f"[{model.model_name}] {item}")
                if len(supporting) >= _MAX_EVIDENCE_ITEMS:
                    break
            if len(supporting) >= _MAX_EVIDENCE_ITEMS:
                break

        contradicting: list[str] = []
        for model in disagreeing:
            for item in model.supporting_evidence:
                if item and item not in contradicting:
                    contradicting.append(f"[{model.model_name}] {item}")
                if len(contradicting) >= _MAX_EVIDENCE_ITEMS:
                    break
            if len(contradicting) >= _MAX_EVIDENCE_ITEMS:
                break

        return supporting, contradicting

    # ------------------------------------------------------------------
    # Fallback
    # ------------------------------------------------------------------

    @staticmethod
    def _fallback_result(symbol: str, timeframe: str) -> EnsembleResult:
        """Return a safe neutral result when no model outputs are available."""
        return EnsembleResult(
            symbol=symbol,
            timeframe=timeframe,
            direction="neutral",
            bull_probability=0.5,
            bear_probability=0.5,
            neutral_probability=0.0,
            confidence_pct=0.0,
            predicted_low=0.0,
            predicted_high=0.0,
            risk_score=5.0,
            market_regime="unknown",
            model_contributions={},
            supporting_evidence=["No model outputs available"],
            contradicting_evidence=[],
        )
