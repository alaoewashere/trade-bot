"""MacroModel — DXY, yield curve, VIX, Fed rate, inflation macro signals."""
from __future__ import annotations

import structlog

from prediction_engine.schemas import ModelOutput

logger = structlog.get_logger(__name__)

# Asset class classification helpers
_CRYPTO_KEYWORDS = ("USDT", "BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "DOGE", "AVAX", "DOT")
_GOLD_KEYWORDS = ("XAU", "GOLD")
_USD_PAIRS = ("USD",)  # symbol contains USD on the quote side: EUR/USD, GBP/USD
_EQUITY_KEYWORDS = ("SPY", "QQQ", "IWM", "DIA", "SPX", "NDX")


def _classify_asset(symbol: str) -> str:
    """Return broad asset class: 'crypto', 'gold', 'equity', 'forex_usd_quote', 'other'."""
    sym_upper = symbol.upper()
    if any(k in sym_upper for k in _CRYPTO_KEYWORDS):
        return "crypto"
    if any(k in sym_upper for k in _GOLD_KEYWORDS):
        return "gold"
    if any(k in sym_upper for k in _EQUITY_KEYWORDS):
        return "equity"
    # EUR/USD, GBP/USD — USD is the quote (priced in USD)
    parts = sym_upper.split("/")
    if len(parts) == 2 and parts[1] == "USD":
        return "forex_usd_quote"
    return "other"


class MacroModel:
    """Macro-environment model using DXY, yields, VIX, and monetary policy signals."""

    name = "macro"

    def predict(self, market_data: dict) -> ModelOutput:
        symbol: str = market_data.get("symbol", "UNKNOWN")
        timeframe: str = market_data.get("timeframe", "1h")
        macro: dict = market_data.get("macro_data", {})

        def _neutral(reason: str) -> ModelOutput:
            logger.debug("macro_model_neutral", symbol=symbol, reason=reason)
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

        if not macro:
            return _neutral("No macro data available")

        asset_class = _classify_asset(symbol)
        bull_signals: list[str] = []
        bear_signals: list[str] = []

        # ------------------------------------------------------------------ DXY
        dxy_value: float | None = macro.get("dxy_value")
        dxy_trend: str | None = macro.get("dxy_trend")  # "up", "down", "flat"

        if dxy_value is not None and dxy_trend is not None:
            dxy_strong = dxy_trend == "up" and dxy_value > 103
            dxy_weak = dxy_trend == "down" and dxy_value < 101

            if dxy_strong:
                if asset_class in ("crypto", "gold"):
                    bear_signals.append(
                        f"DXY strongly rising ({dxy_value:.1f}, trend=up) — headwind for {asset_class}"
                    )
                elif asset_class == "forex_usd_quote":
                    # e.g. EUR/USD falls when USD strengthens
                    bear_signals.append(
                        f"DXY rising strongly ({dxy_value:.1f}) — bearish for USD-quoted forex pair"
                    )
                elif asset_class == "equity":
                    bear_signals.append(
                        f"DXY rising strongly ({dxy_value:.1f}) — historically a headwind for US equities"
                    )
            elif dxy_weak:
                if asset_class in ("crypto", "gold"):
                    bull_signals.append(
                        f"DXY weakening ({dxy_value:.1f}, trend=down) — tailwind for {asset_class}"
                    )
                elif asset_class == "forex_usd_quote":
                    bull_signals.append(
                        f"DXY weakening ({dxy_value:.1f}) — bullish for USD-quoted forex pair"
                    )
                elif asset_class == "equity":
                    bull_signals.append(
                        f"Weak DXY ({dxy_value:.1f}) — historically supportive of risk assets"
                    )
            elif dxy_trend == "up" and dxy_value <= 103:
                if asset_class in ("crypto", "gold"):
                    bear_signals.append(
                        f"DXY trending up ({dxy_value:.1f}) — mild headwind for {asset_class}"
                    )

        # ------------------------------------------------------------------ Yield Curve
        yield_10y: float | None = macro.get("yield_10y")
        yield_2y: float | None = macro.get("yield_2y")
        yield_spread: float | None = macro.get("yield_spread")

        if yield_spread is None and yield_10y is not None and yield_2y is not None:
            yield_spread = yield_10y - yield_2y

        if yield_spread is not None:
            if yield_spread < 0:
                bear_signals.append(
                    f"Yield curve inverted (10y-2y spread={yield_spread:.2f}%) — recessionary signal"
                )
            elif yield_spread < 0.25:
                bear_signals.append(
                    f"Yield curve near inversion (spread={yield_spread:.2f}%) — macro caution warranted"
                )
            elif yield_spread > 1.0:
                bull_signals.append(
                    f"Healthy yield curve steepness (spread={yield_spread:.2f}%) — growth-positive"
                )

        # ------------------------------------------------------------------ VIX
        vix: float | None = macro.get("vix")
        if vix is not None:
            if vix > 40:
                # Panic zone — contrarian opportunity but also real danger
                if asset_class in ("equity", "crypto"):
                    bull_signals.append(
                        f"VIX at extreme fear level ({vix:.1f}) — contrarian bull signal "
                        f"(historically strong buy signal at extremes)"
                    )
                bear_signals.append(f"VIX={vix:.1f} signals systemic panic — elevated drawdown risk")
            elif vix > 30:
                bear_signals.append(
                    f"Elevated VIX ({vix:.1f}) — high fear, risk-off environment"
                )
            elif vix > 20:
                bear_signals.append(f"VIX above 20 ({vix:.1f}) — rising uncertainty")
            elif vix < 12:
                # Complacency — potential for vol expansion/correction
                bear_signals.append(
                    f"VIX at complacency levels ({vix:.1f}) — potential for vol spike/correction"
                )
            elif vix < 15:
                bull_signals.append(
                    f"Low VIX ({vix:.1f}) — low volatility / risk-on regime"
                )

        # ------------------------------------------------------------------ Fed Rate & Inflation
        fed_rate: float | None = macro.get("fed_rate")
        inflation_rate: float | None = macro.get("inflation_rate")

        if fed_rate is not None and inflation_rate is not None:
            real_rate = fed_rate - inflation_rate
            if real_rate > 2.0:
                if asset_class in ("crypto", "gold", "equity"):
                    bear_signals.append(
                        f"High real interest rate ({real_rate:.2f}% = fed {fed_rate:.2f}% - CPI {inflation_rate:.2f}%) "
                        f"— competes with risk assets"
                    )
            elif real_rate < 0:
                if asset_class in ("crypto", "gold"):
                    bull_signals.append(
                        f"Negative real rate ({real_rate:.2f}%) — tailwind for inflation hedges ({asset_class})"
                    )
                elif asset_class == "equity":
                    bull_signals.append(
                        f"Negative real rate ({real_rate:.2f}%) — TINA effect supportive of equities"
                    )
        elif fed_rate is not None:
            if fed_rate > 5.0:
                if asset_class in ("crypto", "equity"):
                    bear_signals.append(f"Fed rate at restrictive level ({fed_rate:.2f}%) — macro headwind")
            elif fed_rate < 1.0:
                if asset_class in ("crypto", "equity"):
                    bull_signals.append(f"Ultra-low Fed rate ({fed_rate:.2f}%) — accommodative conditions")

        # ------------------------------------------------------------------ Aggregate
        bull_count = len(bull_signals)
        bear_count = len(bear_signals)
        total = bull_count + bear_count

        if total == 0:
            return _neutral("Macro data present but no directional signals generated")

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
            metadata={
                "asset_class": asset_class,
                "dxy_value": dxy_value,
                "dxy_trend": dxy_trend,
                "yield_spread": yield_spread,
                "vix": vix,
                "fed_rate": fed_rate,
                "inflation_rate": inflation_rate,
            },
        )
