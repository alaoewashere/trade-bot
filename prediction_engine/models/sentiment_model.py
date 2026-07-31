"""SentimentModel — Fear & Greed Index (alternative.me) + volume trend analysis."""
from __future__ import annotations

import structlog

from prediction_engine.schemas import ModelOutput

logger = structlog.get_logger(__name__)

_FNG_API_URL = "https://api.alternative.me/fng/?limit=7"

# Fear & Greed classification thresholds
_EXTREME_FEAR_THRESHOLD = 25   # <= 25 → extreme fear → contrarian bull
_FEAR_THRESHOLD = 40           # <= 40 → fear
_GREED_THRESHOLD = 60          # >= 60 → greed
_EXTREME_GREED_THRESHOLD = 75  # >= 75 → extreme greed → contrarian bear


class SentimentModel:
    """
    Crypto market sentiment model.

    Combines:
    1. Fear & Greed Index from alternative.me (7-day data for trend)
    2. Volume trend from market_data["volume_trend"]
    """

    name = "sentiment"

    def predict(self, market_data: dict) -> ModelOutput:
        symbol: str = market_data.get("symbol", "UNKNOWN")
        timeframe: str = market_data.get("timeframe", "1h")

        def _neutral(reason: str) -> ModelOutput:
            logger.debug("sentiment_model_neutral", symbol=symbol, reason=reason)
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

        bull_signals: list[str] = []
        bear_signals: list[str] = []
        metadata: dict = {}

        # ------------------------------------------------------------------ Fear & Greed Index
        fng_data = market_data.get("fng_data")  # pre-fetched by engine; see _fetch_market_data
        if fng_data is None:
            # Attempt live fetch (synchronous fallback — only works in non-async contexts)
            fng_data = self._fetch_fng_sync()

        if fng_data:
            current_value = fng_data.get("value", 50)
            current_label = fng_data.get("value_classification", "Neutral")
            trend_7d = fng_data.get("trend_7d", 0.0)   # average change over 7 days

            metadata["fng_value"] = current_value
            metadata["fng_label"] = current_label
            metadata["fng_trend_7d"] = round(trend_7d, 2)

            if current_value <= _EXTREME_FEAR_THRESHOLD:
                bull_signals.append(
                    f"Extreme Fear & Greed Index reading of {current_value} ({current_label}) — "
                    f"contrarian BULL signal: market is overly fearful"
                )
                if trend_7d < -5:
                    bull_signals.append(
                        f"Fear deepening over 7 days (trend={trend_7d:+.1f}) — "
                        f"capitulation may be near, accumulation opportunity"
                    )
            elif current_value <= _FEAR_THRESHOLD:
                bull_signals.append(
                    f"Fear & Greed Index in fear zone ({current_value}, {current_label}) — "
                    f"mild contrarian bull signal"
                )
                if trend_7d < -3:
                    bull_signals.append(
                        f"Fear increasing (7d trend={trend_7d:+.1f}) — sentiment deteriorating, "
                        f"potential bottom formation"
                    )
                elif trend_7d > 3:
                    bear_signals.append(
                        f"Fear receding (7d trend={trend_7d:+.1f}) but still in fear zone — "
                        f"watch for failed rally"
                    )
            elif current_value >= _EXTREME_GREED_THRESHOLD:
                bear_signals.append(
                    f"Extreme Greed: Fear & Greed Index at {current_value} ({current_label}) — "
                    f"contrarian BEAR signal: market is euphoric"
                )
                if trend_7d > 5:
                    bear_signals.append(
                        f"Greed accelerating (7d trend={trend_7d:+.1f}) — "
                        f"potential blow-off top, distribution risk"
                    )
            elif current_value >= _GREED_THRESHOLD:
                bear_signals.append(
                    f"Fear & Greed Index in greed territory ({current_value}, {current_label}) — "
                    f"mild contrarian bear signal"
                )
                if trend_7d > 3:
                    bear_signals.append(
                        f"Greed increasing (7d trend={trend_7d:+.1f}) — "
                        f"sentiment extended, caution warranted"
                    )
            else:
                # Neutral zone 41-59
                metadata["fng_regime"] = "neutral"
                if trend_7d > 5:
                    bull_signals.append(
                        f"Fear & Greed improving (trend={trend_7d:+.1f}, current={current_value}) "
                        f"— positive momentum in sentiment"
                    )
                elif trend_7d < -5:
                    bear_signals.append(
                        f"Fear & Greed deteriorating (trend={trend_7d:+.1f}, current={current_value}) "
                        f"— negative sentiment momentum"
                    )
        else:
            metadata["fng_status"] = "unavailable"

        # ------------------------------------------------------------------ Volume Trend
        volume_trend: str | float | None = market_data.get("volume_trend")
        volumes_raw = market_data.get("volumes", [])

        if volumes_raw and len(volumes_raw) >= 10:
            try:
                import numpy as np
                volumes = [float(v) for v in volumes_raw]
                recent_vol = float(sum(volumes[-5:]) / 5)
                prev_vol = float(sum(volumes[-10:-5]) / 5)
                vol_ratio = recent_vol / prev_vol if prev_vol > 0 else 1.0
                metadata["volume_ratio_5d"] = round(vol_ratio, 3)

                closes_raw = market_data.get("closes", [])
                if closes_raw and len(closes_raw) >= 2:
                    recent_return = float(closes_raw[-1]) - float(closes_raw[-2])
                    if vol_ratio > 1.5 and recent_return > 0:
                        bull_signals.append(
                            f"Volume surge ({vol_ratio:.2f}x average) with price advance — "
                            f"bullish volume confirmation"
                        )
                    elif vol_ratio > 1.5 and recent_return < 0:
                        bear_signals.append(
                            f"Volume surge ({vol_ratio:.2f}x average) with price decline — "
                            f"bearish capitulation / distribution"
                        )
                    elif vol_ratio < 0.5 and recent_return > 0:
                        bear_signals.append(
                            f"Weak volume ({vol_ratio:.2f}x average) on price advance — "
                            f"low conviction rally, potential fade"
                        )
                    elif vol_ratio < 0.5 and recent_return < 0:
                        bull_signals.append(
                            f"Low volume ({vol_ratio:.2f}x average) on decline — "
                            f"weak selling pressure, potential support"
                        )
                    elif vol_ratio > 1.2:
                        bull_signals.append(
                            f"Above-average volume ({vol_ratio:.2f}x) — increased participation"
                        )
            except Exception as exc:
                logger.warning("volume_trend_calculation_failed", error=str(exc))

        elif isinstance(volume_trend, str):
            metadata["volume_trend_raw"] = volume_trend
            vt_lower = volume_trend.lower()
            if "rising" in vt_lower or "increasing" in vt_lower or "surge" in vt_lower:
                bull_signals.append(f"Rising volume trend ({volume_trend}) — increasing participation")
            elif "falling" in vt_lower or "decreasing" in vt_lower or "declining" in vt_lower:
                bear_signals.append(f"Declining volume trend ({volume_trend}) — waning interest")
        elif isinstance(volume_trend, (int, float)):
            metadata["volume_trend_pct"] = round(float(volume_trend), 2)
            if volume_trend > 20:
                bull_signals.append(f"Volume increasing +{volume_trend:.1f}% — strong participation")
            elif volume_trend < -20:
                bear_signals.append(f"Volume declining {volume_trend:.1f}% — fading interest")

        # ------------------------------------------------------------------ Aggregate
        bull_count = len(bull_signals)
        bear_count = len(bear_signals)
        total = bull_count + bear_count

        if total == 0:
            return _neutral("No sentiment signals generated")

        bull_prob = bull_count / total
        bear_prob = bear_count / total
        imbalance = abs(bull_prob - bear_prob)
        confidence = min(imbalance * 1.3, 1.0)

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
            predicted_low=None,
            predicted_high=None,
            supporting_evidence=bull_signals if direction == "bullish" else bear_signals,
            contradicting_evidence=bear_signals if direction == "bullish" else bull_signals,
            metadata=metadata,
        )

    # ------------------------------------------------------------------
    # Synchronous FNG fetch (fallback when async context not available)
    # ------------------------------------------------------------------

    @staticmethod
    def _fetch_fng_sync() -> dict | None:
        """
        Fetch Fear & Greed data synchronously.
        Used as a fallback if the engine did not pre-fetch it.
        Returns None on any error.
        """
        try:
            import httpx
            response = httpx.get(_FNG_API_URL, timeout=5.0)
            response.raise_for_status()
            payload = response.json()
            return SentimentModel._parse_fng(payload)
        except Exception as exc:
            logger.warning("fng_sync_fetch_failed", error=str(exc))
            return None

    @staticmethod
    def _parse_fng(payload: dict) -> dict | None:
        """Parse alternative.me API response into a simple dict."""
        try:
            data = payload.get("data", [])
            if not data:
                return None

            # Most recent entry
            latest = data[0]
            current_value = int(latest.get("value", 50))
            current_label = latest.get("value_classification", "Neutral")

            # 7-day trend: difference between latest and oldest available
            if len(data) >= 7:
                oldest_value = int(data[-1].get("value", current_value))
                trend_7d = float(current_value - oldest_value) / 7.0
            else:
                trend_7d = 0.0

            return {
                "value": current_value,
                "value_classification": current_label,
                "trend_7d": round(trend_7d, 2),
                "raw_data": data,
            }
        except Exception as exc:
            logger.warning("fng_parse_failed", error=str(exc))
            return None
