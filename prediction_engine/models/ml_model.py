"""MLModel — in-process scikit-learn classifier trained on recent candle features."""
from __future__ import annotations

import warnings
from typing import Literal

import numpy as np
import structlog

from prediction_engine.schemas import ModelOutput

logger = structlog.get_logger(__name__)

MIN_CANDLES_TRAIN = 100  # minimum candles to train
MIN_CANDLES_FEATURES = 15  # need at least this many for feature calculation


class MLModel:
    """
    In-process ML model using scikit-learn RandomForestClassifier.

    Features per candle:
        [return_1, return_5, return_10, rsi_norm, vol_ratio, z_score]

    Target: direction of the NEXT candle (1 = up, 0 = down).

    In production this would load a pre-trained model from MLflow registry;
    here we train on the provided data at inference time (last N candles).
    """

    name = "ml"

    def predict(self, market_data: dict) -> ModelOutput:
        symbol: str = market_data.get("symbol", "UNKNOWN")
        timeframe: str = market_data.get("timeframe", "1h")
        closes_raw = market_data.get("closes", [])

        def _neutral(reason: str) -> ModelOutput:
            logger.debug("ml_model_neutral", symbol=symbol, reason=reason)
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

        if len(closes_raw) < MIN_CANDLES_TRAIN:
            return _neutral(
                f"Insufficient data for ML training: {len(closes_raw)} candles "
                f"(minimum {MIN_CANDLES_TRAIN} required)"
            )

        closes = np.array(closes_raw, dtype=float)

        # ------------------------------------------------------------------ Build features & labels
        try:
            X, y = self._build_dataset(closes)
        except Exception as exc:
            logger.warning("ml_feature_build_failed", error=str(exc))
            return _neutral(f"Feature extraction failed: {exc}")

        if len(X) < 20:
            return _neutral(f"Only {len(X)} training samples after feature extraction (need ≥20)")

        # ------------------------------------------------------------------ Train classifier
        try:
            from sklearn.ensemble import RandomForestClassifier
            from sklearn.preprocessing import StandardScaler

            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X)

            # Use last row as the "live" prediction point, train on the rest
            X_train = X_scaled[:-1]
            y_train = y[:-1]
            X_live = X_scaled[-1].reshape(1, -1)

            # Balance classes using class_weight; n_estimators intentionally small for speed
            clf = RandomForestClassifier(
                n_estimators=50,
                max_depth=5,
                class_weight="balanced",
                random_state=42,
                n_jobs=1,
            )

            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                clf.fit(X_train, y_train)

            proba = clf.predict_proba(X_live)[0]
            classes = list(clf.classes_)

            # Map class indices to probabilities
            prob_up = float(proba[classes.index(1)]) if 1 in classes else 0.5
            prob_down = float(proba[classes.index(0)]) if 0 in classes else 0.5

            # Feature importances
            feature_names = ["return_1", "return_5", "return_10", "rsi_norm", "vol_ratio", "z_score"]
            importances = {
                name: round(float(imp), 4)
                for name, imp in zip(feature_names, clf.feature_importances_)
            }

        except ImportError:
            return _neutral("scikit-learn not installed — ML model unavailable")
        except Exception as exc:
            logger.warning("ml_training_failed", error=str(exc))
            return _neutral(f"Model training failed: {exc}")

        # ------------------------------------------------------------------ Determine direction
        imbalance = abs(prob_up - prob_down)
        confidence = min(imbalance * 2.0, 1.0)

        if prob_up > 0.55:
            direction: Literal["bullish", "bearish", "neutral"] = "bullish"
            supporting = [
                f"RandomForest classifier predicts up with {prob_up * 100:.1f}% probability",
                f"Top features: {', '.join(k for k, v in sorted(importances.items(), key=lambda x: -x[1])[:3])}",
            ]
            contradicting = [f"Down probability: {prob_down * 100:.1f}%"]
        elif prob_down > 0.55:
            direction = "bearish"
            supporting = [
                f"RandomForest classifier predicts down with {prob_down * 100:.1f}% probability",
                f"Top features: {', '.join(k for k, v in sorted(importances.items(), key=lambda x: -x[1])[:3])}",
            ]
            contradicting = [f"Up probability: {prob_up * 100:.1f}%"]
        else:
            direction = "neutral"
            supporting = [f"Model uncertain — up={prob_up * 100:.1f}%, down={prob_down * 100:.1f}%"]
            contradicting = []

        # ------------------------------------------------------------------ Price range
        current_price = float(closes[-1])
        recent_std = float(np.std(closes[-20:])) if len(closes) >= 20 else current_price * 0.01
        predicted_low = max(0.0, current_price - recent_std)
        predicted_high = current_price + recent_std

        return ModelOutput(
            model_name=self.name,
            symbol=symbol,
            timeframe=timeframe,
            direction=direction,
            bull_probability=round(prob_up, 4),
            bear_probability=round(prob_down, 4),
            confidence=round(confidence, 4),
            predicted_low=round(predicted_low, 6),
            predicted_high=round(predicted_high, 6),
            supporting_evidence=supporting,
            contradicting_evidence=contradicting,
            metadata={
                "n_training_samples": len(X_train),
                "feature_importances": importances,
                "model": "RandomForestClassifier(n_estimators=50, max_depth=5)",
            },
        )

    # ------------------------------------------------------------------
    # Feature engineering
    # ------------------------------------------------------------------

    def _build_dataset(self, closes: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """
        Build supervised dataset from closing prices.

        Returns X (n_samples, 6) and y (n_samples,) where y[i] is the
        direction of closes[i+1] relative to closes[i]: 1=up, 0=down.
        """
        n = len(closes)
        features = []
        labels = []

        # We need at least 10 historical bars per sample plus a next bar
        for i in range(10, n - 1):
            window = closes[: i + 1]
            feat = self._extract_features(window)
            if feat is None:
                continue
            label = 1 if closes[i + 1] > closes[i] else 0
            features.append(feat)
            labels.append(label)

        # Also build the "live" feature row (last available window, no future label)
        live_feat = self._extract_features(closes)
        if live_feat is not None:
            features.append(live_feat)
            labels.append(0)  # dummy label — never used for training

        return np.array(features, dtype=float), np.array(labels, dtype=int)

    @staticmethod
    def _extract_features(closes: np.ndarray) -> list[float] | None:
        """
        Extract 6 features from a window of closing prices.
        Returns None if window is too short.
        """
        if len(closes) < 11:
            return None

        current = closes[-1]

        # -- Short-term returns
        return_1 = float((current - closes[-2]) / closes[-2]) if closes[-2] != 0 else 0.0
        return_5 = float((current - closes[-6]) / closes[-6]) if len(closes) >= 6 and closes[-6] != 0 else 0.0
        return_10 = float((current - closes[-11]) / closes[-11]) if len(closes) >= 11 and closes[-11] != 0 else 0.0

        # -- RSI (normalised 0-1) — simple rolling calculation
        window14 = closes[-15:] if len(closes) >= 15 else closes
        if len(window14) >= 2:
            deltas = np.diff(window14.astype(float))
            gains = deltas[deltas > 0]
            losses = -deltas[deltas < 0]
            avg_gain = float(np.mean(gains)) if len(gains) > 0 else 0.0
            avg_loss = float(np.mean(losses)) if len(losses) > 0 else 0.0
            rsi_raw = 100 - (100 / (1 + avg_gain / avg_loss)) if avg_loss != 0 else 100.0
            rsi_norm = rsi_raw / 100.0
        else:
            rsi_norm = 0.5

        # -- Volatility ratio (recent 5 / historical 20)
        if len(closes) >= 21:
            returns = np.diff(np.log(closes[-21:] + 1e-10))
            recent_vol = float(np.std(returns[-5:]))
            hist_vol = float(np.std(returns))
            vol_ratio = (recent_vol / hist_vol) if hist_vol > 0 else 1.0
        else:
            vol_ratio = 1.0

        # -- Z-score
        if len(closes) >= 20:
            window20 = closes[-20:]
            mean20 = float(np.mean(window20))
            std20 = float(np.std(window20))
            z_score = float((current - mean20) / std20) if std20 > 0 else 0.0
        else:
            z_score = 0.0

        return [return_1, return_5, return_10, rsi_norm, vol_ratio, z_score]
