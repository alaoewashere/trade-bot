"""OnChainModel — on-chain metrics for crypto assets (MVRV, exchange flows, funding)."""
from __future__ import annotations

import structlog

from prediction_engine.schemas import ModelOutput

logger = structlog.get_logger(__name__)

# Symbols that qualify for on-chain analysis
_CRYPTO_SUFFIXES = ("/USDT", "/USD", "/BTC", "/ETH", "/BUSD", "/USDC")
_CRYPTO_BASES = ("BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "DOGE", "AVAX", "DOT", "LINK",
                 "MATIC", "LTC", "BCH", "UNI", "ATOM", "FIL", "TRX", "ETC", "XLM", "ALGO")


def _is_crypto(symbol: str) -> bool:
    """Return True if symbol looks like a crypto asset."""
    sym = symbol.upper().replace("-", "/")
    if any(sym.endswith(sfx) for sfx in _CRYPTO_SUFFIXES):
        return True
    base = sym.split("/")[0] if "/" in sym else sym
    return base in _CRYPTO_BASES


class OnChainModel:
    """
    On-chain data model for crypto assets.

    Reads market_data["onchain_data"] which may contain:
        exchange_inflow          float  (coins flowing onto exchanges — sell pressure)
        exchange_outflow         float  (coins leaving exchanges — accumulation)
        mvrv_ratio               float  (Market Value / Realised Value; >3.5 overvalued, <1 undervalued)
        stablecoin_supply_change float  (% change; rising = more dry powder = bullish)
        whale_accumulation       bool   (large wallets net accumulating)
        funding_rate             float  (perpetual futures; positive = longs pay shorts)
    """

    name = "onchain"

    def predict(self, market_data: dict) -> ModelOutput:
        symbol: str = market_data.get("symbol", "UNKNOWN")
        timeframe: str = market_data.get("timeframe", "1h")

        def _neutral(reason: str) -> ModelOutput:
            logger.debug("onchain_model_neutral", symbol=symbol, reason=reason)
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

        # Only analyse crypto symbols
        if not _is_crypto(symbol):
            return _neutral(f"Symbol {symbol} is not a crypto asset — on-chain data not applicable")

        onchain: dict = market_data.get("onchain_data", {})
        if not onchain:
            return _neutral("No on-chain data available")

        bull_signals: list[str] = []
        bear_signals: list[str] = []
        metadata: dict = {"symbol_classified_as": "crypto"}

        # ------------------------------------------------------------------ Exchange Flows
        inflow: float | None = onchain.get("exchange_inflow")
        outflow: float | None = onchain.get("exchange_outflow")

        if inflow is not None and outflow is not None:
            net_flow = outflow - inflow  # positive = net outflow (bullish)
            metadata["net_exchange_flow"] = round(net_flow, 4)
            metadata["exchange_inflow"] = round(inflow, 4)
            metadata["exchange_outflow"] = round(outflow, 4)

            flow_ratio = outflow / inflow if inflow > 0 else 1.0

            if flow_ratio > 1.5:
                bull_signals.append(
                    f"Net exchange outflow (outflow={outflow:.2f} > inflow={inflow:.2f}, ratio={flow_ratio:.2f}) "
                    f"— coins leaving exchanges indicate accumulation / HODLing"
                )
            elif flow_ratio > 1.1:
                bull_signals.append(
                    f"Moderate exchange outflow (ratio={flow_ratio:.2f}) — mild accumulation signal"
                )
            elif flow_ratio < 0.7:
                bear_signals.append(
                    f"Net exchange inflow (inflow={inflow:.2f} > outflow={outflow:.2f}, ratio={flow_ratio:.2f}) "
                    f"— coins flowing to exchanges signal potential sell pressure"
                )
            elif flow_ratio < 0.9:
                bear_signals.append(
                    f"Mild exchange inflow (ratio={flow_ratio:.2f}) — slight sell pressure signal"
                )
        elif inflow is not None:
            metadata["exchange_inflow"] = round(inflow, 4)
            if inflow > 0:
                bear_signals.append(f"Exchange inflow detected ({inflow:.2f}) — potential sell pressure")
        elif outflow is not None:
            metadata["exchange_outflow"] = round(outflow, 4)
            if outflow > 0:
                bull_signals.append(f"Exchange outflow detected ({outflow:.2f}) — accumulation signal")

        # ------------------------------------------------------------------ MVRV Ratio
        mvrv: float | None = onchain.get("mvrv_ratio")
        if mvrv is not None:
            metadata["mvrv_ratio"] = round(mvrv, 3)

            if mvrv > 3.5:
                bear_signals.append(
                    f"MVRV ratio at {mvrv:.2f} — market significantly overvalued vs realised value, "
                    f"historically near cycle tops"
                )
            elif mvrv > 2.5:
                bear_signals.append(
                    f"MVRV ratio elevated ({mvrv:.2f}) — above fair value, caution warranted"
                )
            elif mvrv < 1.0:
                bull_signals.append(
                    f"MVRV ratio below 1.0 ({mvrv:.2f}) — market trading below realised value, "
                    f"historically strong accumulation zone"
                )
            elif mvrv < 1.5:
                bull_signals.append(
                    f"MVRV ratio at {mvrv:.2f} — undervalued relative to realised value, bullish long-term"
                )
            else:
                metadata["mvrv_regime"] = "fair_value"

        # ------------------------------------------------------------------ Stablecoin Supply Change
        stable_change: float | None = onchain.get("stablecoin_supply_change")
        if stable_change is not None:
            metadata["stablecoin_supply_change_pct"] = round(stable_change, 3)

            if stable_change > 5.0:
                bull_signals.append(
                    f"Stablecoin supply growing rapidly (+{stable_change:.1f}%) — "
                    f"significant dry powder entering the ecosystem"
                )
            elif stable_change > 2.0:
                bull_signals.append(
                    f"Stablecoin supply increasing (+{stable_change:.1f}%) — more capital available to deploy"
                )
            elif stable_change < -5.0:
                bear_signals.append(
                    f"Stablecoin supply declining ({stable_change:.1f}%) — capital leaving ecosystem"
                )
            elif stable_change < -2.0:
                bear_signals.append(
                    f"Stablecoin supply shrinking ({stable_change:.1f}%) — mild capital outflow"
                )

        # ------------------------------------------------------------------ Whale Accumulation
        whale_acc: bool | None = onchain.get("whale_accumulation")
        if whale_acc is True:
            bull_signals.append(
                "Whale accumulation detected — large wallet addresses are net buying"
            )
            metadata["whale_accumulation"] = True
        elif whale_acc is False:
            bear_signals.append(
                "Whale distribution detected — large wallet addresses are net selling"
            )
            metadata["whale_accumulation"] = False

        # ------------------------------------------------------------------ Funding Rate
        funding_rate: float | None = onchain.get("funding_rate")
        if funding_rate is not None:
            metadata["funding_rate"] = round(funding_rate, 5)

            if funding_rate > 0.01:
                # >1% per 8h is very high — longs are overleveraged
                bear_signals.append(
                    f"Very high positive funding rate ({funding_rate * 100:.3f}% per 8h) — "
                    f"longs heavily leveraged, squeeze risk / bearish"
                )
            elif funding_rate > 0.005:
                bear_signals.append(
                    f"Elevated positive funding ({funding_rate * 100:.3f}%) — longs paying shorts, "
                    f"market leaning bullish but crowded"
                )
            elif funding_rate < -0.005:
                # Negative funding — shorts paying longs → good short squeeze setup
                bull_signals.append(
                    f"Negative funding rate ({funding_rate * 100:.3f}%) — shorts paying longs, "
                    f"potential short squeeze / contrarian bull"
                )
            elif funding_rate < -0.001:
                bull_signals.append(
                    f"Slightly negative funding ({funding_rate * 100:.3f}%) — mild bear leverage, "
                    f"short squeeze potential"
                )
            else:
                metadata["funding_regime"] = "neutral"

        # ------------------------------------------------------------------ Aggregate
        bull_count = len(bull_signals)
        bear_count = len(bear_signals)
        total = bull_count + bear_count

        if total == 0:
            return _neutral("On-chain data present but no directional signals generated")

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
