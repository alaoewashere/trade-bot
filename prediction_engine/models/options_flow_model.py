"""OptionsFlowModel — put/call ratio, gamma exposure, IV percentile, open interest."""
from __future__ import annotations

import structlog

from prediction_engine.schemas import ModelOutput

logger = structlog.get_logger(__name__)


class OptionsFlowModel:
    """
    Options market sentiment model.

    Reads market_data["options_data"] which may contain:
        put_call_ratio          float   (>1 heavy puts, <1 heavy calls)
        gamma_exposure          float   (positive = MM long gamma = stabilising)
        iv_percentile           float   (0-100, percentile of current IV vs history)
        unusual_activity        bool    (unusual options flow detected by screener)
        open_interest_change_pct float  (% change in total OI — rising OI = conviction)
    """

    name = "options_flow"

    def predict(self, market_data: dict) -> ModelOutput:
        symbol: str = market_data.get("symbol", "UNKNOWN")
        timeframe: str = market_data.get("timeframe", "1h")
        options: dict = market_data.get("options_data", {})

        def _neutral(reason: str) -> ModelOutput:
            logger.debug("options_flow_model_neutral", symbol=symbol, reason=reason)
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

        if not options:
            return _neutral("No options data available")

        bull_signals: list[str] = []
        bear_signals: list[str] = []
        metadata: dict = {}

        # ------------------------------------------------------------------ Put/Call Ratio
        pcr: float | None = options.get("put_call_ratio")
        if pcr is not None:
            metadata["put_call_ratio"] = round(pcr, 3)

            if pcr > 1.5:
                # Extreme put buying → contrarian bullish (market too fearful)
                bull_signals.append(
                    f"Extreme put/call ratio ({pcr:.2f}) — panic put buying, contrarian BULL signal "
                    f"(market overly hedged)"
                )
                # Also acknowledge the face-value bearish interpretation
                bear_signals.append(
                    f"Heavy put buying (PCR={pcr:.2f}) — participants positioning for downside"
                )
            elif pcr > 1.2:
                # Heavy put buying — slight bearish tilt, mild contrarian bull
                bear_signals.append(
                    f"Elevated put/call ratio ({pcr:.2f}) — bearish options positioning"
                )
                bull_signals.append(
                    f"PCR={pcr:.2f} approaching contrarian bull territory"
                )
            elif pcr < 0.5:
                # Extreme call buying → contrarian bearish (market too complacent)
                bear_signals.append(
                    f"Extreme call buying (PCR={pcr:.2f}) — euphoric positioning, contrarian BEAR signal"
                )
                bull_signals.append(
                    f"Heavy call buying (PCR={pcr:.2f}) — speculative demand for upside"
                )
            elif pcr < 0.7:
                # Heavy call buying — slight bullish tilt
                bull_signals.append(
                    f"Low put/call ratio ({pcr:.2f}) — bullish options positioning"
                )
                bear_signals.append(
                    f"PCR={pcr:.2f} approaching contrarian bear territory (complacency)"
                )
            else:
                # Neutral zone 0.7 – 1.2
                metadata["pcr_regime"] = "neutral"

        # ------------------------------------------------------------------ Gamma Exposure (GEX)
        gex: float | None = options.get("gamma_exposure")
        if gex is not None:
            metadata["gamma_exposure"] = gex

            if gex > 0:
                # Positive GEX: market makers are long gamma → they sell rallies, buy dips → mean reversion
                bull_signals.append(
                    f"Positive gamma exposure ({gex:+.2f}) — market makers hedging creates price stability / "
                    f"mean reversion support"
                )
            elif gex < 0:
                # Negative GEX: market makers short gamma → they buy rallies, sell dips → trend amplification
                bear_signals.append(
                    f"Negative gamma exposure ({gex:+.2f}) — market makers short gamma, "
                    f"price moves may be amplified (vol risk)"
                )

        # ------------------------------------------------------------------ IV Percentile
        iv_pct: float | None = options.get("iv_percentile")
        if iv_pct is not None:
            metadata["iv_percentile"] = round(iv_pct, 1)

            if iv_pct > 80:
                # Options are expensive → vol likely to compress → underlying may stabilise / mean-revert
                bull_signals.append(
                    f"IV percentile at {iv_pct:.0f}% — options expensive, potential vol crush, "
                    f"mean reversion favoured for premium sellers"
                )
                bear_signals.append(
                    f"High IV ({iv_pct:.0f}th pct) reflects elevated uncertainty / fear in market"
                )
            elif iv_pct > 60:
                bear_signals.append(
                    f"Above-average IV ({iv_pct:.0f}th pct) — elevated uncertainty"
                )
            elif iv_pct < 20:
                # Options are cheap → potential for vol expansion / breakout
                bear_signals.append(
                    f"IV percentile at {iv_pct:.0f}% — options cheap, potential for vol expansion / breakout "
                    f"in either direction (complacency)"
                )
            elif iv_pct < 40:
                bull_signals.append(
                    f"Low IV ({iv_pct:.0f}th pct) — calm market, low risk premium"
                )

        # ------------------------------------------------------------------ Unusual Activity
        unusual: bool | None = options.get("unusual_activity")
        if unusual:
            # Unusual activity is generally directionally ambiguous without knowing call vs put
            # We lean bullish (unusual call activity is more common for known catalysts)
            bull_signals.append(
                "Unusual options activity detected — potential informed buying / catalyst positioning"
            )
            metadata["unusual_activity"] = True

        # ------------------------------------------------------------------ Open Interest Change
        oi_change_pct: float | None = options.get("open_interest_change_pct")
        if oi_change_pct is not None:
            metadata["oi_change_pct"] = round(oi_change_pct, 2)

            if oi_change_pct > 20:
                bull_signals.append(
                    f"OI growing rapidly (+{oi_change_pct:.1f}%) — strong conviction / new money entering"
                )
            elif oi_change_pct > 10:
                bull_signals.append(f"Open interest expanding (+{oi_change_pct:.1f}%) — increasing participation")
            elif oi_change_pct < -20:
                bear_signals.append(
                    f"OI collapsing ({oi_change_pct:.1f}%) — positions being closed / unwound, potential reversal"
                )
            elif oi_change_pct < -10:
                bear_signals.append(f"Open interest declining ({oi_change_pct:.1f}%) — decreasing conviction")

        # ------------------------------------------------------------------ Aggregate
        bull_count = len(bull_signals)
        bear_count = len(bear_signals)
        total = bull_count + bear_count

        if total == 0:
            return _neutral("Options data present but no directional signals")

        bull_prob = bull_count / total
        bear_prob = bear_count / total
        imbalance = abs(bull_prob - bear_prob)
        confidence = min(imbalance * 1.2, 1.0)

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
