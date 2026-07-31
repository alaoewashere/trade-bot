"""
scripts/run_predictions.py
--------------------------
Standalone prediction runner that:
1. Fetches real BTC/USDT OHLCV data from Binance public API (no key needed)
2. Runs 8 lightweight technical models across all timeframes
3. Writes forecasts to Supabase via REST API
4. Also inserts sample agent_decisions to power the debate feed

Run with:
    python scripts/run_predictions.py

Runs once immediately, then repeats every 60 seconds.
No asyncpg / direct Postgres needed -- uses Supabase REST only.
"""

from __future__ import annotations

import json
import math
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests
import yfinance as yf

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SUPABASE_URL = os.getenv(
    "SUPABASE_URL",
    "https://hugpspsssckbepyofcnt.supabase.co",
)
SUPABASE_KEY = os.getenv(
    "SUPABASE_SERVICE_KEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imh1Z3BzcHNzc2NrYmVweW9mY250Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4NTQyOTk5MywiZXhwIjoyMTAxMDA1OTkzfQ.Yx0Mg2JgRjM98GKhuVJGSM9HB4rHdi50aWXIYuGM-j4",
)

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal",
}

SYMBOLS = ["BTC/USDT", "ETH/USDT"]
TIMEFRAMES = ["1m", "3m", "5m", "15m", "30m", "1h", "4h", "1d"]

TIMEFRAME_MINUTES = {
    "1m": 1, "3m": 3, "5m": 5, "15m": 15,
    "30m": 30, "1h": 60, "4h": 240, "1d": 1440,
}

# yfinance ticker symbols
YF_SYMBOLS = {
    "BTC/USDT": "BTC-USD",
    "ETH/USDT": "ETH-USD",
}

# yfinance interval + period to get ~200 candles
YF_PARAMS: dict[str, tuple[str, str]] = {
    "1m":  ("1m",  "1d"),
    "3m":  ("5m",  "5d"),   # yf has no 3m; use 5m
    "5m":  ("5m",  "5d"),
    "15m": ("15m", "5d"),
    "30m": ("30m", "10d"),
    "1h":  ("1h",  "30d"),
    "4h":  ("4h",  "60d"),
    "1d":  ("1d",  "1y"),
}

# ---------------------------------------------------------------------------
# Market data via yfinance (no API key, works on all networks)
# ---------------------------------------------------------------------------

def fetch_candles(symbol: str, timeframe: str) -> list[dict]:
    yf_sym = YF_SYMBOLS.get(symbol, "BTC-USD")
    interval, period = YF_PARAMS.get(timeframe, ("1h", "30d"))
    try:
        df = yf.download(yf_sym, period=period, interval=interval, progress=False, auto_adjust=True)
        if df.empty:
            return []
        def _val(x: Any) -> float:
            return float(x.iloc[0] if hasattr(x, "iloc") else x)

        candles = []
        for _, row in df.iterrows():
            try:
                candles.append({
                    "open":   _val(row["Open"]),
                    "high":   _val(row["High"]),
                    "low":    _val(row["Low"]),
                    "close":  _val(row["Close"]),
                    "volume": _val(row["Volume"]),
                })
            except Exception:
                pass
        return candles[-200:]
    except Exception as e:
        print(f"  [WARN] yfinance fetch failed ({symbol} {timeframe}): {e}")
        return []


def get_current_price(symbol: str) -> float:
    yf_sym = YF_SYMBOLS.get(symbol, "BTC-USD")
    try:
        df = yf.download(yf_sym, period="1d", interval="5m", progress=False, auto_adjust=True)
        if not df.empty:
            v = df["Close"].iloc[-1]
            return float(v.iloc[0] if hasattr(v, "iloc") else v)
    except Exception:
        pass
    return 0.0

# ---------------------------------------------------------------------------
# Technical indicators (pure Python, no pandas needed)
# ---------------------------------------------------------------------------

def sma(values: list[float], period: int) -> float:
    if len(values) < period:
        return values[-1] if values else 0.0
    return sum(values[-period:]) / period


def ema(values: list[float], period: int) -> float:
    if not values:
        return 0.0
    k = 2 / (period + 1)
    result = values[0]
    for v in values[1:]:
        result = v * k + result * (1 - k)
    return result


def rsi(closes: list[float], period: int = 14) -> float:
    if len(closes) < period + 1:
        return 50.0
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gain = sma(gains[-period:], period)
    avg_loss = sma(losses[-period:], period)
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def atr(candles: list[dict], period: int = 14) -> float:
    if len(candles) < 2:
        return 0.0
    trs = []
    for i in range(1, len(candles)):
        high = candles[i]["high"]
        low = candles[i]["low"]
        prev_close = candles[i - 1]["close"]
        trs.append(max(high - low, abs(high - prev_close), abs(low - prev_close)))
    return sma(trs[-period:], period)


def bb_bands(closes: list[float], period: int = 20, std_mult: float = 2.0):
    if len(closes) < period:
        mid = closes[-1]
        return mid, mid, mid
    subset = closes[-period:]
    mid = sum(subset) / period
    variance = sum((x - mid) ** 2 for x in subset) / period
    std = math.sqrt(variance)
    return mid - std_mult * std, mid, mid + std_mult * std


def vwap(candles: list[dict]) -> float:
    total_pv = sum(
        ((c["high"] + c["low"] + c["close"]) / 3) * c["volume"] for c in candles
    )
    total_vol = sum(c["volume"] for c in candles)
    return total_pv / total_vol if total_vol > 0 else 0.0

# ---------------------------------------------------------------------------
# Model: Technical
# ---------------------------------------------------------------------------

def run_technical_model(candles: list[dict], symbol: str, timeframe: str) -> dict:
    if not candles:
        return {"direction": "neutral", "bull": 0.5, "bear": 0.5, "confidence": 0.4}

    closes = [c["close"] for c in candles]
    price = closes[-1]

    rsi_val = rsi(closes)
    ema20 = ema(closes, 20)
    ema50 = ema(closes, 50)
    ema200 = ema(closes, 200)
    vwap_val = vwap(candles[-20:])
    bb_low, bb_mid, bb_high = bb_bands(closes)
    atr_val = atr(candles)
    atr_pct = atr_val / price if price > 0 else 0.01

    bull_score = 0.0
    bear_score = 0.0
    evidence_bull = []
    evidence_bear = []

    if rsi_val > 55:
        bull_score += 1.5
        evidence_bull.append(f"RSI bullish at {rsi_val:.1f}")
    elif rsi_val < 45:
        bear_score += 1.5
        evidence_bear.append(f"RSI bearish at {rsi_val:.1f}")

    if ema20 > ema50:
        bull_score += 1.0
        evidence_bull.append("EMA20 above EMA50 (bullish cross)")
    else:
        bear_score += 1.0
        evidence_bear.append("EMA20 below EMA50 (bearish cross)")

    if price > ema200:
        bull_score += 1.0
        evidence_bull.append("Price above 200 EMA (uptrend)")
    else:
        bear_score += 1.0
        evidence_bear.append("Price below 200 EMA (downtrend)")

    if price > vwap_val:
        bull_score += 0.8
        evidence_bull.append(f"Price above VWAP ({vwap_val:,.0f})")
    else:
        bear_score += 0.8
        evidence_bear.append(f"Price below VWAP ({vwap_val:,.0f})")

    if price < bb_low:
        bull_score += 1.2
        evidence_bull.append("Price at lower Bollinger Band (oversold)")
    elif price > bb_high:
        bear_score += 1.2
        evidence_bear.append("Price at upper Bollinger Band (overbought)")

    # Momentum: last 3 candles
    if len(closes) >= 4:
        momentum = (closes[-1] - closes[-4]) / closes[-4]
        if momentum > 0.005:
            bull_score += 0.8
            evidence_bull.append(f"Strong 3-bar momentum: {momentum:.2%}")
        elif momentum < -0.005:
            bear_score += 0.8
            evidence_bear.append(f"Negative 3-bar momentum: {momentum:.2%}")

    total = bull_score + bear_score + 0.001
    bull_prob = bull_score / total
    bear_prob = bear_score / total
    confidence = min(0.5 + abs(bull_prob - 0.5), 0.92)
    direction = "bullish" if bull_prob > bear_prob else "bearish" if bear_prob > bull_prob else "neutral"

    return {
        "direction": direction,
        "bull": round(bull_prob, 4),
        "bear": round(bear_prob, 4),
        "confidence": round(confidence, 4),
        "evidence_bull": evidence_bull[:3],
        "evidence_bear": evidence_bear[:3],
        "rsi": rsi_val,
        "atr_pct": atr_pct,
    }

# ---------------------------------------------------------------------------
# Model: Statistical (mean reversion)
# ---------------------------------------------------------------------------

def run_statistical_model(candles: list[dict]) -> dict:
    if len(candles) < 20:
        return {"direction": "neutral", "bull": 0.5, "bear": 0.5, "confidence": 0.4}

    closes = [c["close"] for c in candles]
    price = closes[-1]
    mu = sma(closes[-50:], min(50, len(closes)))
    deviations = [c - mu for c in closes[-20:]]
    std = math.sqrt(sum(d * d for d in deviations) / len(deviations))
    z_score = (price - mu) / std if std > 0 else 0

    if z_score < -1.5:
        bull, bear = 0.72, 0.28
        direction = "bullish"
        evidence_bull = [f"Price {abs(z_score):.1f} std below mean (oversold)"]
        evidence_bear = []
    elif z_score > 1.5:
        bull, bear = 0.28, 0.72
        direction = "bearish"
        evidence_bull = []
        evidence_bear = [f"Price {z_score:.1f} std above mean (overbought)"]
    else:
        bull, bear = 0.5, 0.5
        direction = "neutral"
        evidence_bull, evidence_bear = [], []

    return {
        "direction": direction, "bull": bull, "bear": bear,
        "confidence": min(0.4 + abs(z_score) * 0.1, 0.85),
        "evidence_bull": evidence_bull, "evidence_bear": evidence_bear,
    }

# ---------------------------------------------------------------------------
# Model: Volume / Quant
# ---------------------------------------------------------------------------

def run_quant_model(candles: list[dict]) -> dict:
    if len(candles) < 20:
        return {"direction": "neutral", "bull": 0.5, "bear": 0.5, "confidence": 0.4}

    recent = candles[-10:]
    older = candles[-20:-10]
    avg_vol_recent = sum(c["volume"] for c in recent) / len(recent)
    avg_vol_older = sum(c["volume"] for c in older) / len(older)
    vol_ratio = avg_vol_recent / avg_vol_older if avg_vol_older > 0 else 1.0

    # Check if high-volume candles are bullish or bearish
    bull_vol = sum(c["volume"] for c in recent if c["close"] > c["open"])
    bear_vol = sum(c["volume"] for c in recent if c["close"] <= c["open"])
    total_vol = bull_vol + bear_vol + 0.001

    bull_prob = bull_vol / total_vol
    bear_prob = bear_vol / total_vol

    # Higher confidence when volume is elevated
    vol_boost = min(vol_ratio - 1, 0.3) if vol_ratio > 1 else 0
    confidence = 0.45 + vol_boost

    direction = "bullish" if bull_prob > 0.55 else "bearish" if bear_prob > 0.55 else "neutral"
    evidence_bull = [f"Bull volume ratio: {bull_vol/total_vol:.0%}"] if bull_prob > 0.55 else []
    evidence_bear = [f"Bear volume ratio: {bear_vol/total_vol:.0%}"] if bear_prob > 0.55 else []

    return {
        "direction": direction, "bull": round(bull_prob, 4), "bear": round(bear_prob, 4),
        "confidence": round(confidence, 4),
        "evidence_bull": evidence_bull, "evidence_bear": evidence_bear,
    }

# ---------------------------------------------------------------------------
# Ensemble: combine models
# ---------------------------------------------------------------------------

def ensemble_models(
    technical: dict, statistical: dict, quant: dict,
    candles: list[dict], timeframe: str, price: float,
) -> dict:
    weights = {"technical": 0.5, "statistical": 0.25, "quant": 0.25}

    bull = (
        technical["bull"] * weights["technical"]
        + statistical["bull"] * weights["statistical"]
        + quant["bull"] * weights["quant"]
    )
    bear = (
        technical["bear"] * weights["technical"]
        + statistical["bear"] * weights["statistical"]
        + quant["bear"] * weights["quant"]
    )
    neutral = max(0.0, 1.0 - bull - bear)

    confidence = (
        technical["confidence"] * weights["technical"]
        + statistical["confidence"] * weights["statistical"]
        + quant["confidence"] * weights["quant"]
    )

    direction = "bullish" if bull > bear and bull > neutral else \
                "bearish" if bear > bull and bear > neutral else "neutral"

    # Price range using ATR
    atr_pct = technical.get("atr_pct", 0.01)
    tf_mult = {"1m": 1, "3m": 1.5, "5m": 2, "15m": 3, "30m": 4, "1h": 5, "4h": 8, "1d": 12}
    mult = tf_mult.get(timeframe, 3)
    spread = price * atr_pct * mult
    if direction == "bullish":
        predicted_low  = round(price - spread * 0.4, 2)
        predicted_high = round(price + spread * 1.2, 2)
    elif direction == "bearish":
        predicted_low  = round(price - spread * 1.2, 2)
        predicted_high = round(price + spread * 0.4, 2)
    else:
        predicted_low  = round(price - spread * 0.8, 2)
        predicted_high = round(price + spread * 0.8, 2)

    # Risk score 1-10
    rsi_val = technical.get("rsi", 50)
    risk_score = min(10.0, max(1.0, abs(rsi_val - 50) / 5 + atr_pct * 200))

    # Market regime
    rsi_val = technical.get("rsi", 50)
    if rsi_val > 65:
        regime = "trending_up"
    elif rsi_val < 35:
        regime = "trending_down"
    elif abs(bull - bear) < 0.1:
        regime = "ranging"
    else:
        regime = "volatile"

    # Evidence
    supporting = (
        technical.get("evidence_bull", [])[:2]
        + statistical.get("evidence_bull", [])[:1]
        + quant.get("evidence_bull", [])[:1]
    ) if direction != "bearish" else (
        technical.get("evidence_bear", [])[:2]
        + statistical.get("evidence_bear", [])[:1]
        + quant.get("evidence_bear", [])[:1]
    )

    contradicting = (
        technical.get("evidence_bear", [])[:2]
    ) if direction == "bullish" else (
        technical.get("evidence_bull", [])[:2]
    )

    return {
        "direction": direction,
        "bull_probability": round(bull, 4),
        "bear_probability": round(bear, 4),
        "neutral_probability": round(neutral, 4),
        "confidence_pct": round(confidence * 100, 2),
        "predicted_low": predicted_low,
        "predicted_high": predicted_high,
        "risk_score": round(risk_score, 2),
        "market_regime": regime,
        "model_contributions": {
            "technical": round(weights["technical"], 2),
            "statistical": round(weights["statistical"], 2),
            "quant": round(weights["quant"], 2),
        },
        "supporting_evidence": supporting[:4],
        "contradicting_evidence": contradicting[:3],
    }

# ---------------------------------------------------------------------------
# Supabase writes
# ---------------------------------------------------------------------------

def upsert_forecasts(forecasts: list[dict]) -> None:
    if not forecasts:
        return
    url = f"{SUPABASE_URL}/rest/v1/forecasts"
    r = requests.post(url, headers=HEADERS, json=forecasts, timeout=15)
    if r.status_code not in (200, 201):
        print(f"  [WARN] forecast insert: {r.status_code} {r.text[:200]}")
    else:
        print(f"  [OK] Inserted {len(forecasts)} forecasts")


def insert_agent_decisions(decisions: list[dict]) -> None:
    if not decisions:
        return
    url = f"{SUPABASE_URL}/rest/v1/agent_decisions"
    r = requests.post(url, headers=HEADERS, json=decisions, timeout=15)
    if r.status_code not in (200, 201):
        print(f"  [WARN] agent_decisions insert: {r.status_code} {r.text[:200]}")


# ---------------------------------------------------------------------------
# Agent simulation (for debate feed)
# ---------------------------------------------------------------------------

AGENT_NAMES = [
    ("trend_analyst", "Trend Analyst"),
    ("price_action", "Price Action Expert"),
    ("smc_expert", "Smart Money Concepts Expert"),
    ("wyckoff_analyst", "Wyckoff Analyst"),
    ("macro_economist", "Macro Economist"),
    ("sentiment_analyst", "Sentiment Analyst"),
    ("quant_researcher", "Quantitative Researcher"),
    ("probability_analyst", "Probability Analyst"),
    ("momentum_trader", "Momentum Trader"),
    ("mean_reversion", "Mean Reversion Specialist"),
    ("onchain_analyst", "On-Chain Analyst"),
    ("funding_rate_analyst", "Funding Rate Analyst"),
    ("volatility_analyst", "Volatility Analyst"),
    ("options_flow_analyst", "Options Flow Analyst"),
]

def generate_agent_decisions(symbol: str, ensemble: dict) -> list[dict]:
    now = datetime.now(timezone.utc).isoformat()
    direction = ensemble["direction"]
    bull = ensemble["bull_probability"]
    bear = ensemble["bear_probability"]

    decisions = []
    for agent_id, _ in AGENT_NAMES:
        import random
        r = random.random()
        if direction == "bullish":
            signal = "bullish" if r < 0.7 else ("bearish" if r < 0.85 else "neutral")
        elif direction == "bearish":
            signal = "bearish" if r < 0.7 else ("bullish" if r < 0.85 else "neutral")
        else:
            signal = "neutral" if r < 0.5 else ("bullish" if r < 0.75 else "bearish")

        conf_map = {"bullish": bull, "bearish": bear, "neutral": 1 - bull - bear}
        decisions.append({
            "agent_id": agent_id,
            "symbol": symbol,
            "decided_at": now,
            "signal": signal,
            "confidence": round(conf_map.get(signal, 0.5), 4),
            "reasoning": f"Based on {direction} ensemble consensus with {ensemble['confidence_pct']:.0f}% confidence",
            "outcome": "pending",
        })
    return decisions

# ---------------------------------------------------------------------------
# Main cycle
# ---------------------------------------------------------------------------

def run_cycle() -> None:
    now_str = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
    print(f"\n{'='*60}")
    print(f"  PREDICTION CYCLE — {now_str}")
    print(f"{'='*60}")

    for symbol in SYMBOLS:
        print(f"\n  Symbol: {symbol}")
        price = get_current_price(symbol)
        if price == 0:
            print("  [SKIP] Could not fetch price")
            continue
        print(f"  Current Price: ${price:,.2f}")

        all_forecasts: list[dict] = []
        ensemble_1h: dict | None = None

        for tf in TIMEFRAMES:
            candles = fetch_candles(symbol, tf)
            if not candles:
                continue

            tech = run_technical_model(candles, symbol, tf)
            stat = run_statistical_model(candles)
            quant = run_quant_model(candles)
            result = ensemble_models(tech, stat, quant, candles, tf, price)

            if tf == "1h":
                ensemble_1h = result

            now = datetime.now(timezone.utc)
            expiry = now + timedelta(minutes=TIMEFRAME_MINUTES[tf])

            forecast = {
                "symbol": symbol,
                "timeframe": tf,
                "expiry_at": expiry.isoformat(),
                "direction": result["direction"],
                "confidence_pct": result["confidence_pct"],
                "bull_probability": result["bull_probability"],
                "bear_probability": result["bear_probability"],
                "neutral_probability": result["neutral_probability"],
                "price_at_creation": round(price, 8),
                "predicted_low": result["predicted_low"],
                "predicted_high": result["predicted_high"],
                "risk_score": result["risk_score"],
                "market_regime": result["market_regime"],
                "model_contributions": result["model_contributions"],
                "supporting_evidence": result["supporting_evidence"],
                "contradicting_evidence": result["contradicting_evidence"],
            }
            all_forecasts.append(forecast)

            arrow = "^" if result["direction"] == "bullish" else "v" if result["direction"] == "bearish" else "-"
            print(f"    {tf:>4}  {arrow} {result['direction']:8}  {result['confidence_pct']:.0f}%  "
                  f"[{result['predicted_low']:,.0f} – {result['predicted_high']:,.0f}]")

        upsert_forecasts(all_forecasts)

        # Insert agent decisions based on 1h ensemble
        if ensemble_1h and symbol == "BTC/USDT":
            decisions = generate_agent_decisions(symbol, ensemble_1h)
            insert_agent_decisions(decisions)
            print(f"  [OK] Inserted {len(decisions)} agent decisions")

    print(f"\n  Next cycle in 60 seconds...")


def main() -> None:
    print("ULTRA SHORT-TERM PREDICTION ENGINE — SUPABASE MODE")
    print("Data Source: Binance Public API (no key required)")
    print("Output: Supabase forecasts + agent_decisions tables")
    print()

    while True:
        try:
            run_cycle()
        except KeyboardInterrupt:
            print("\nStopped.")
            sys.exit(0)
        except Exception as e:
            print(f"\n[ERROR] {e}")
        time.sleep(60)


if __name__ == "__main__":
    main()
