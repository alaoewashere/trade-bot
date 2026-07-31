"""TechnicalModel — RSI, MACD, Bollinger Bands, EMA stack, ATR-based price range."""
from __future__ import annotations

import numpy as np
import pandas as pd
import structlog
from ta.momentum import RSIIndicator
from ta.trend import MACD, EMAIndicator
from ta.volatility import BollingerBands, AverageTrueRange

from prediction_engine.schemas import ModelOutput

logger = structlog.get_logger(__name__)

MIN_CANDLES = 50


class TechnicalModel:
    """Pure technical analysis model using common indicators."""

    name = "technical"

    def predict(self, market_data: dict) -> ModelOutput:
        symbol: str = market_data.get("symbol", "UNKNOWN")
        timeframe: str = market_data.get("timeframe", "1h")

        closes_raw = market_data.get("closes", [])
        highs_raw = market_data.get("highs", [])
        lows_raw = market_data.get("lows", [])

        def _neutral(reason: str) -> ModelOutput:
            logger.debug("technical_model_neutral", symbol=symbol, reason=reason)
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

        closes = pd.Series(closes_raw, dtype=float)
        highs = pd.Series(highs_raw if len(highs_raw) >= len(closes_raw) else closes_raw, dtype=float)
        lows = pd.Series(lows_raw if len(lows_raw) >= len(closes_raw) else closes_raw, dtype=float)

        bull_signals: list[str] = []
        bear_signals: list[str] = []

        # ------------------------------------------------------------------ RSI
        try:
            rsi_ind = RSIIndicator(close=closes, window=14)
            rsi_series = rsi_ind.rsi()
            rsi_val = float(rsi_series.iloc[-1])
            if not np.isnan(rsi_val):
                if rsi_val < 30:
                    bull_signals.append(f"RSI oversold at {rsi_val:.1f}")
                elif rsi_val > 70:
                    bear_signals.append(f"RSI overbought at {rsi_val:.1f}")
                elif rsi_val < 45:
                    bear_signals.append(f"RSI weak at {rsi_val:.1f}")
                elif rsi_val > 55:
                    bull_signals.append(f"RSI strong at {rsi_val:.1f}")
            else:
                rsi_val = 50.0
        except Exception as exc:
            logger.warning("rsi_calculation_failed", error=str(exc))
            rsi_val = 50.0

        # ------------------------------------------------------------------ MACD
        try:
            macd_ind = MACD(close=closes, window_slow=26, window_fast=12, window_sign=9)
            macd_diff = macd_ind.macd_diff()
            macd_line = macd_ind.macd()
            macd_signal_line = macd_ind.macd_signal()

            diff_now = float(macd_diff.iloc[-1])
            diff_prev = float(macd_diff.iloc[-2]) if len(macd_diff) > 1 else 0.0
            macd_now = float(macd_line.iloc[-1])
            sig_now = float(macd_signal_line.iloc[-1])

            if not any(np.isnan(x) for x in [diff_now, diff_prev, macd_now, sig_now]):
                # Crossover detection
                if diff_prev < 0 and diff_now > 0:
                    bull_signals.append(f"MACD bullish crossover (diff={diff_now:.4f})")
                elif diff_prev > 0 and diff_now < 0:
                    bear_signals.append(f"MACD bearish crossover (diff={diff_now:.4f})")
                elif diff_now > 0:
                    bull_signals.append(f"MACD positive histogram ({diff_now:.4f})")
                elif diff_now < 0:
                    bear_signals.append(f"MACD negative histogram ({diff_now:.4f})")
        except Exception as exc:
            logger.warning("macd_calculation_failed", error=str(exc))

        # ------------------------------------------------------------------ Bollinger Bands
        try:
            bb = BollingerBands(close=closes, window=20, window_dev=2)
            bb_upper = float(bb.bollinger_hband().iloc[-1])
            bb_lower = float(bb.bollinger_lband().iloc[-1])
            bb_mid = float(bb.bollinger_mavg().iloc[-1])
            current_close = float(closes.iloc[-1])

            if not any(np.isnan(x) for x in [bb_upper, bb_lower, bb_mid]):
                bb_width = (bb_upper - bb_lower) / bb_mid if bb_mid != 0 else 0.0
                pct_b = (current_close - bb_lower) / (bb_upper - bb_lower) if (bb_upper - bb_lower) != 0 else 0.5

                if current_close <= bb_lower:
                    bull_signals.append(f"Price at/below lower Bollinger Band (%B={pct_b:.2f})")
                elif current_close >= bb_upper:
                    bear_signals.append(f"Price at/above upper Bollinger Band (%B={pct_b:.2f})")
                elif pct_b > 0.7:
                    bull_signals.append(f"Price in upper Bollinger Band zone (%B={pct_b:.2f})")
                elif pct_b < 0.3:
                    bear_signals.append(f"Price in lower Bollinger Band zone (%B={pct_b:.2f})")

                if bb_width < 0.02:
                    bull_signals.append(f"Bollinger Band squeeze — breakout imminent (width={bb_width:.3f})")
        except Exception as exc:
            logger.warning("bb_calculation_failed", error=str(exc))

        # ------------------------------------------------------------------ EMA Stack
        try:
            ema20_ind = EMAIndicator(close=closes, window=20)
            ema50_ind = EMAIndicator(close=closes, window=50)
            ema20 = float(ema20_ind.ema_indicator().iloc[-1])
            ema50 = float(ema50_ind.ema_indicator().iloc[-1])
            current_close = float(closes.iloc[-1])

            if not any(np.isnan(x) for x in [ema20, ema50]):
                if current_close > ema20 > ema50:
                    bull_signals.append(
                        f"Bullish EMA stack: price({current_close:.2f}) > EMA20({ema20:.2f}) > EMA50({ema50:.2f})"
                    )
                elif current_close < ema20 < ema50:
                    bear_signals.append(
                        f"Bearish EMA stack: price({current_close:.2f}) < EMA20({ema20:.2f}) < EMA50({ema50:.2f})"
                    )
                elif current_close > ema50 and ema20 < ema50:
                    bear_signals.append(f"EMA20({ema20:.2f}) below EMA50({ema50:.2f}) — bearish structure")
                elif current_close < ema50 and ema20 > ema50:
                    bull_signals.append(f"EMA20({ema20:.2f}) above EMA50({ema50:.2f}) — bullish structure")
        except Exception as exc:
            logger.warning("ema_calculation_failed", error=str(exc))
            ema20, ema50 = float(closes.iloc[-1]), float(closes.iloc[-1])

        # ------------------------------------------------------------------ ATR for price range
        predicted_low: float | None = None
        predicted_high: float | None = None
        try:
            atr_ind = AverageTrueRange(high=highs, low=lows, close=closes, window=14)
            atr_series = atr_ind.average_true_range()
            atr_val = float(atr_series.iloc[-1])
            current_close = float(closes.iloc[-1])
            if not np.isnan(atr_val) and atr_val > 0:
                predicted_low = current_close - atr_val
                predicted_high = current_close + atr_val
        except Exception as exc:
            logger.warning("atr_calculation_failed", error=str(exc))
            current_close = float(closes.iloc[-1])
            spread = current_close * 0.01
            predicted_low = current_close - spread
            predicted_high = current_close + spread

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
            predicted_low=predicted_low,
            predicted_high=predicted_high,
            supporting_evidence=bull_signals if direction == "bullish" else bear_signals,
            contradicting_evidence=bear_signals if direction == "bullish" else bull_signals,
            metadata={
                "rsi": round(rsi_val, 2),
                "bull_count": bull_count,
                "bear_count": bear_count,
                "ema20": round(float(closes.iloc[-1]), 4),
            },
        )
