"""Pydantic models for the Ultra Short-Term Prediction Engine."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Literal
from pydantic import BaseModel, Field

TIMEFRAME_DURATIONS = {
    "1m": timedelta(minutes=1),
    "3m": timedelta(minutes=3),
    "5m": timedelta(minutes=5),
    "15m": timedelta(minutes=15),
    "30m": timedelta(minutes=30),
    "1h": timedelta(hours=1),
    "4h": timedelta(hours=4),
    "1d": timedelta(days=1),
}

class ModelOutput(BaseModel):
    model_name: str
    symbol: str
    timeframe: str
    direction: Literal["bullish", "bearish", "neutral"]
    bull_probability: float = Field(ge=0.0, le=1.0)
    bear_probability: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    predicted_low: float | None = None
    predicted_high: float | None = None
    supporting_evidence: list[str] = []
    contradicting_evidence: list[str] = []
    metadata: dict = {}

class EnsembleResult(BaseModel):
    symbol: str
    timeframe: str
    direction: Literal["bullish", "bearish", "neutral"]
    bull_probability: float
    bear_probability: float
    neutral_probability: float
    confidence_pct: float
    predicted_low: float
    predicted_high: float
    risk_score: float
    market_regime: str
    model_contributions: dict[str, float]
    supporting_evidence: list[str]
    contradicting_evidence: list[str]

class Forecast(BaseModel):
    id: str | None = None
    symbol: str
    timeframe: str
    created_at: datetime
    expiry_at: datetime
    direction: Literal["bullish", "bearish", "neutral"]
    confidence_pct: float
    bull_probability: float
    bear_probability: float
    neutral_probability: float
    price_at_creation: float
    predicted_low: float
    predicted_high: float
    risk_score: float
    market_regime: str
    model_contributions: dict[str, float]
    supporting_evidence: list[str]
    contradicting_evidence: list[str]

    @classmethod
    def from_ensemble(cls, result: EnsembleResult, current_price: float) -> "Forecast":
        now = datetime.now(timezone.utc)
        duration = TIMEFRAME_DURATIONS.get(result.timeframe, timedelta(hours=1))
        return cls(
            symbol=result.symbol, timeframe=result.timeframe,
            created_at=now, expiry_at=now + duration,
            direction=result.direction,
            confidence_pct=result.confidence_pct,
            bull_probability=result.bull_probability,
            bear_probability=result.bear_probability,
            neutral_probability=result.neutral_probability,
            price_at_creation=current_price,
            predicted_low=result.predicted_low,
            predicted_high=result.predicted_high,
            risk_score=result.risk_score,
            market_regime=result.market_regime,
            model_contributions=result.model_contributions,
            supporting_evidence=result.supporting_evidence,
            contradicting_evidence=result.contradicting_evidence,
        )

class CalibrationStats(BaseModel):
    symbol: str
    timeframe: str
    model_name: str
    window_size: int
    computed_at: datetime
    accuracy_pct: float
    brier_score: float
    avg_confidence: float
    overconfidence: float
    range_accuracy: float
    sample_count: int
