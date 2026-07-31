"""
PredictionEngine — orchestrates all 8 models and produces forecasts.

Run as:
    python -m prediction_engine.engine
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

import asyncpg
import redis.asyncio as aioredis
import structlog

from config.settings import get_settings
from prediction_engine.calibration import CalibrationTracker
from prediction_engine.ensemble import EnsembleVoter
from prediction_engine.models.macro_model import MacroModel
from prediction_engine.models.ml_model import MLModel
from prediction_engine.models.onchain_model import OnChainModel
from prediction_engine.models.options_flow_model import OptionsFlowModel
from prediction_engine.models.quant_model import QuantModel
from prediction_engine.models.sentiment_model import SentimentModel, _FNG_API_URL, SentimentModel
from prediction_engine.models.statistical_model import StatisticalModel
from prediction_engine.models.technical_model import TechnicalModel
from prediction_engine.schemas import TIMEFRAME_DURATIONS, Forecast

logger = structlog.get_logger(__name__)

# ccxt timeframe mapping
_CCXT_TIMEFRAMES = {
    "1m": "1m",
    "3m": "3m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1h": "1h",
    "4h": "4h",
    "1d": "1d",
}

# How many candles to fetch per timeframe (enough for ML training + indicators)
_CANDLE_LIMITS = {
    "1m": 300,
    "3m": 300,
    "5m": 300,
    "15m": 300,
    "30m": 300,
    "1h": 300,
    "4h": 300,
    "1d": 365,
}

# Symbols that need on-chain data
_CRYPTO_BASES = {"BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "DOGE", "AVAX", "DOT"}

_INSERT_FORECAST_SQL = """
    INSERT INTO forecasts (
        symbol, timeframe, created_at, expiry_at,
        direction, confidence_pct,
        bull_probability, bear_probability, neutral_probability,
        price_at_creation, predicted_low, predicted_high,
        risk_score, market_regime,
        model_contributions, supporting_evidence, contradicting_evidence,
        evaluated
    ) VALUES (
        $1, $2, $3, $4,
        $5, $6,
        $7, $8, $9,
        $10, $11, $12,
        $13, $14,
        $15::jsonb, $16::jsonb, $17::jsonb,
        FALSE
    )
    RETURNING id
"""


class PredictionEngine:
    """
    Orchestrates all 8 prediction models for every configured symbol × timeframe.

    Architecture:
    - Models run synchronously (CPU-bound) inside asyncio.to_thread for safety.
    - Market data is fetched via ccxt (crypto) or Alpaca (equities).
    - Forecasts are persisted to PostgreSQL and cached in Redis.
    - The engine loops every 60 seconds; longer timeframes are naturally
      overwritten in Redis by the next 1m-aligned cycle.
    """

    TIMEFRAMES = list(TIMEFRAME_DURATIONS.keys())

    def __init__(
        self,
        db_pool: asyncpg.Pool,
        redis_client: aioredis.Redis,
        calibration_tracker: CalibrationTracker,
    ) -> None:
        self.db = db_pool
        self.redis = redis_client
        self.calibration = calibration_tracker
        self.voter = EnsembleVoter(calibration_tracker)
        self.models = [
            TechnicalModel(),
            MacroModel(),
            QuantModel(),
            MLModel(),
            StatisticalModel(),
            SentimentModel(),
            OptionsFlowModel(),
            OnChainModel(),
        ]
        self._ccxt_exchanges: dict[str, Any] = {}
        self._httpx_client: Any = None
        self._fng_cache: dict | None = None          # shared Fear & Greed cache
        self._fng_cache_ts: float = 0.0              # epoch seconds of last fetch
        self._fng_cache_ttl: float = 300.0           # 5 minutes

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def startup(self) -> None:
        """Initialise HTTP client and warm calibration cache."""
        import httpx
        self._httpx_client = httpx.AsyncClient(timeout=15.0)

        settings = get_settings()
        for symbol in settings.prediction_symbols:
            for tf in self.TIMEFRAMES:
                await self.calibration.warm_cache(symbol, tf)

        logger.info("prediction_engine_startup_complete")

    async def shutdown(self) -> None:
        """Cleanly close all network resources."""
        for exchange in self._ccxt_exchanges.values():
            try:
                await exchange.close()
            except Exception:
                pass
        if self._httpx_client is not None:
            try:
                await self._httpx_client.aclose()
            except Exception:
                pass
        logger.info("prediction_engine_shutdown_complete")

    # ------------------------------------------------------------------
    # Main run loop
    # ------------------------------------------------------------------

    async def run_forever(self) -> None:
        """Run forecast cycles for all symbols on a 60-second cadence."""
        settings = get_settings()
        await self.startup()
        logger.info("prediction_engine_started", symbols=settings.prediction_symbols)

        while True:
            cycle_start = asyncio.get_event_loop().time()

            tasks = [
                self.run_forecast_cycle(symbol, timeframe)
                for symbol in settings.prediction_symbols
                for timeframe in self.TIMEFRAMES
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            errors = [r for r in results if isinstance(r, Exception)]
            successes = len(results) - len(errors)
            for err in errors:
                logger.error("forecast_cycle_error", error=str(err))

            logger.info(
                "forecast_batch_complete",
                successes=successes,
                errors=len(errors),
                symbols=len(settings.prediction_symbols),
                timeframes=len(self.TIMEFRAMES),
            )

            elapsed = asyncio.get_event_loop().time() - cycle_start
            sleep_time = max(0.0, 60.0 - elapsed)
            await asyncio.sleep(sleep_time)

    # ------------------------------------------------------------------
    # Forecast cycle
    # ------------------------------------------------------------------

    async def run_forecast_cycle(self, symbol: str, timeframe: str) -> Forecast:
        """
        Run all 8 models for one symbol × timeframe combination, ensemble the
        results, persist to DB and Redis, and return the Forecast.
        """
        market_data = await self._fetch_market_data(symbol, timeframe)

        # Run models in a thread pool (they are CPU-bound / synchronous)
        def _run_models() -> list:
            outputs = []
            for model in self.models:
                try:
                    out = model.predict(market_data)
                    outputs.append(out)
                except Exception as exc:
                    logger.warning(
                        "model_predict_error",
                        model=model.name,
                        symbol=symbol,
                        timeframe=timeframe,
                        error=str(exc),
                    )
            return outputs

        outputs = await asyncio.to_thread(_run_models)

        ensemble_result = self.voter.vote(outputs, symbol, timeframe)
        current_price = float(market_data.get("current_price", 0.0))

        # If ensemble returned 0/0 price range, fill from current price + ATR proxy
        if ensemble_result.predicted_low == 0.0 and ensemble_result.predicted_high == 0.0:
            closes = market_data.get("closes", [])
            if closes and len(closes) >= 2:
                import numpy as np
                recent_std = float(np.std(closes[-20:])) if len(closes) >= 20 else current_price * 0.01
                ensemble_result = ensemble_result.model_copy(
                    update={
                        "predicted_low": max(0.0, current_price - recent_std),
                        "predicted_high": current_price + recent_std,
                    }
                )

        forecast = Forecast.from_ensemble(ensemble_result, current_price)
        await self._save_forecast(forecast)
        await self._cache_forecast(forecast)

        logger.info(
            "forecast_produced",
            symbol=symbol,
            timeframe=timeframe,
            direction=forecast.direction,
            confidence_pct=forecast.confidence_pct,
            risk_score=forecast.risk_score,
        )
        return forecast

    # ------------------------------------------------------------------
    # Market data fetching
    # ------------------------------------------------------------------

    async def _fetch_market_data(self, symbol: str, timeframe: str) -> dict:
        """
        Fetch OHLCV + auxiliary data for a symbol/timeframe.

        Routing:
        - Crypto (/USDT, /BTC, /ETH, /USD with crypto base): ccxt Binance
        - Equities (SPY, QQQ, AAPL, …): Alpaca REST API
        - Forex (EUR/USD, GBP/USD, XAU/USD): Alpaca REST API (forex data feed)
        """
        sym_upper = symbol.upper()
        is_crypto = self._classify_as_crypto(sym_upper)

        if is_crypto:
            ohlcv_data = await self._fetch_ccxt_ohlcv(symbol, timeframe)
        else:
            ohlcv_data = await self._fetch_alpaca_bars(symbol, timeframe)

        # Shared supplementary data
        fng_data = await self._fetch_fng()
        macro_data = await self._fetch_macro_data()

        # Crypto-specific supplementary data
        onchain_data: dict = {}
        options_data: dict = {}
        if is_crypto:
            onchain_data = await self._fetch_onchain_data(symbol)
        else:
            options_data = await self._fetch_options_data(symbol)

        market_data = {
            "symbol": symbol,
            "timeframe": timeframe,
            **ohlcv_data,
            "macro_data": macro_data,
            "onchain_data": onchain_data,
            "options_data": options_data,
            "fng_data": fng_data,
        }
        return market_data

    @staticmethod
    def _classify_as_crypto(sym_upper: str) -> bool:
        """Return True if the symbol represents a crypto asset."""
        crypto_suffixes = ("/USDT", "/BTC", "/ETH", "/BUSD", "/USDC")
        if any(sym_upper.endswith(sfx) for sfx in crypto_suffixes):
            return True
        parts = sym_upper.split("/")
        if len(parts) == 2 and parts[0] in _CRYPTO_BASES:
            return True
        return False

    async def _fetch_ccxt_ohlcv(self, symbol: str, timeframe: str) -> dict:
        """Fetch OHLCV data from Binance via ccxt."""
        try:
            import ccxt.async_support as ccxt

            exchange = self._ccxt_exchanges.get("binance")
            if exchange is None:
                settings = get_settings()
                exchange = ccxt.binance(
                    {
                        "apiKey": settings.binance_api_key,
                        "secret": settings.binance_secret_key,
                        "enableRateLimit": True,
                    }
                )
                self._ccxt_exchanges["binance"] = exchange

            limit = _CANDLE_LIMITS.get(timeframe, 300)
            ccxt_tf = _CCXT_TIMEFRAMES.get(timeframe, "1h")
            ohlcv = await exchange.fetch_ohlcv(symbol, ccxt_tf, limit=limit)

            if not ohlcv:
                return self._empty_ohlcv(symbol)

            timestamps = [bar[0] for bar in ohlcv]
            opens = [float(bar[1]) for bar in ohlcv]
            highs = [float(bar[2]) for bar in ohlcv]
            lows = [float(bar[3]) for bar in ohlcv]
            closes = [float(bar[4]) for bar in ohlcv]
            volumes = [float(bar[5]) for bar in ohlcv]

            current_price = closes[-1] if closes else 0.0

            # Volume trend: % change recent 5 bars vs previous 5
            volume_trend = 0.0
            if len(volumes) >= 10:
                recent_avg = sum(volumes[-5:]) / 5
                prev_avg = sum(volumes[-10:-5]) / 5
                volume_trend = (recent_avg - prev_avg) / prev_avg * 100 if prev_avg > 0 else 0.0

            return {
                "timestamps": timestamps,
                "opens": opens,
                "highs": highs,
                "lows": lows,
                "closes": closes,
                "volumes": volumes,
                "current_price": current_price,
                "volume_trend": round(volume_trend, 2),
                "data_source": "binance_ccxt",
            }

        except Exception as exc:
            logger.warning(
                "ccxt_ohlcv_fetch_failed",
                symbol=symbol,
                timeframe=timeframe,
                error=str(exc),
            )
            return self._empty_ohlcv(symbol)

    async def _fetch_alpaca_bars(self, symbol: str, timeframe: str) -> dict:
        """Fetch OHLCV data from Alpaca for equities and forex."""
        try:
            if self._httpx_client is None:
                import httpx
                self._httpx_client = httpx.AsyncClient(timeout=15.0)

            settings = get_settings()
            headers = {
                "APCA-API-KEY-ID": settings.alpaca_api_key,
                "APCA-API-SECRET-KEY": settings.alpaca_secret_key,
            }

            # Alpaca timeframe format
            alpaca_tf_map = {
                "1m": "1Min", "3m": "3Min", "5m": "5Min", "15m": "15Min",
                "30m": "30Min", "1h": "1Hour", "4h": "4Hour", "1d": "1Day",
            }
            alpaca_tf = alpaca_tf_map.get(timeframe, "1Hour")

            # Detect if forex (XAU/USD, EUR/USD) vs equity
            sym_upper = symbol.upper()
            is_forex = "/" in sym_upper and not self._classify_as_crypto(sym_upper)
            alpaca_symbol = sym_upper.replace("/", "")

            limit = _CANDLE_LIMITS.get(timeframe, 300)

            if is_forex:
                # Alpaca forex feed
                url = "https://data.alpaca.markets/v1beta3/forex/bars"
                params = {
                    "symbols": alpaca_symbol,
                    "timeframe": alpaca_tf,
                    "limit": limit,
                    "sort": "asc",
                }
            else:
                # Equity bars
                url = "https://data.alpaca.markets/v2/stocks/bars"
                params = {
                    "symbols": alpaca_symbol,
                    "timeframe": alpaca_tf,
                    "limit": limit,
                    "feed": "iex",
                    "sort": "asc",
                }

            response = await self._httpx_client.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()

            bars = data.get("bars", {}).get(alpaca_symbol, [])
            if not bars:
                logger.debug("alpaca_no_bars", symbol=symbol, timeframe=timeframe)
                return self._empty_ohlcv(symbol)

            timestamps = [bar.get("t", "") for bar in bars]
            opens = [float(bar["o"]) for bar in bars]
            highs = [float(bar["h"]) for bar in bars]
            lows = [float(bar["l"]) for bar in bars]
            closes = [float(bar["c"]) for bar in bars]
            volumes = [float(bar.get("v", 0)) for bar in bars]

            current_price = closes[-1] if closes else 0.0

            volume_trend = 0.0
            if len(volumes) >= 10:
                recent_avg = sum(volumes[-5:]) / 5
                prev_avg = sum(volumes[-10:-5]) / 5
                volume_trend = (recent_avg - prev_avg) / prev_avg * 100 if prev_avg > 0 else 0.0

            return {
                "timestamps": timestamps,
                "opens": opens,
                "highs": highs,
                "lows": lows,
                "closes": closes,
                "volumes": volumes,
                "current_price": current_price,
                "volume_trend": round(volume_trend, 2),
                "data_source": "alpaca",
            }

        except Exception as exc:
            logger.warning(
                "alpaca_bars_fetch_failed",
                symbol=symbol,
                timeframe=timeframe,
                error=str(exc),
            )
            return self._empty_ohlcv(symbol)

    async def _fetch_fng(self) -> dict | None:
        """
        Fetch Fear & Greed index from alternative.me with a 5-minute cache.
        Returns None if unavailable.
        """
        import time

        now = time.monotonic()
        if self._fng_cache is not None and (now - self._fng_cache_ts) < self._fng_cache_ttl:
            return self._fng_cache

        try:
            if self._httpx_client is None:
                import httpx
                self._httpx_client = httpx.AsyncClient(timeout=10.0)

            response = await self._httpx_client.get(_FNG_API_URL, timeout=5.0)
            response.raise_for_status()
            payload = response.json()
            parsed = SentimentModel._parse_fng(payload)
            self._fng_cache = parsed
            self._fng_cache_ts = now
            return parsed

        except Exception as exc:
            logger.debug("fng_fetch_failed", error=str(exc))
            return self._fng_cache  # Return stale cache if available

    async def _fetch_macro_data(self) -> dict:
        """
        Fetch macro indicators.

        In production these would come from a Bloomberg/Refinitiv feed or
        dedicated macro data provider. Here we return a best-effort dict
        populated from free public sources where possible.
        """
        macro: dict = {}

        # Attempt to fetch VIX from CBOE via Yahoo Finance-compatible endpoint
        try:
            if self._httpx_client is None:
                import httpx
                self._httpx_client = httpx.AsyncClient(timeout=10.0)

            # Yahoo Finance v8 quote for VIX — no auth required
            response = await self._httpx_client.get(
                "https://query1.finance.yahoo.com/v8/finance/chart/%5EVIX",
                params={"interval": "1d", "range": "1d"},
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=5.0,
            )
            response.raise_for_status()
            data = response.json()
            price_data = (
                data.get("chart", {})
                .get("result", [{}])[0]
                .get("meta", {})
            )
            vix_price = price_data.get("regularMarketPrice")
            if vix_price:
                macro["vix"] = float(vix_price)
        except Exception as exc:
            logger.debug("vix_fetch_failed", error=str(exc))

        # DXY — Yahoo Finance
        try:
            response = await self._httpx_client.get(
                "https://query1.finance.yahoo.com/v8/finance/chart/DX-Y.NYB",
                params={"interval": "1d", "range": "5d"},
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=5.0,
            )
            response.raise_for_status()
            data = response.json()
            results = data.get("chart", {}).get("result", [{}])[0]
            closes_list = results.get("indicators", {}).get("quote", [{}])[0].get("close", [])
            closes_list = [c for c in closes_list if c is not None]
            if len(closes_list) >= 2:
                macro["dxy_value"] = float(closes_list[-1])
                dxy_change = closes_list[-1] - closes_list[-5] if len(closes_list) >= 5 else closes_list[-1] - closes_list[0]
                macro["dxy_trend"] = "up" if dxy_change > 0.3 else ("down" if dxy_change < -0.3 else "flat")
        except Exception as exc:
            logger.debug("dxy_fetch_failed", error=str(exc))

        # US 10Y and 2Y yields — Yahoo Finance
        try:
            for key, ticker in [("yield_10y", "%5ETNX"), ("yield_2y", "%5ETWOYEAR")]:
                response = await self._httpx_client.get(
                    f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}",
                    params={"interval": "1d", "range": "1d"},
                    headers={"User-Agent": "Mozilla/5.0"},
                    timeout=5.0,
                )
                response.raise_for_status()
                data = response.json()
                price = (
                    data.get("chart", {})
                    .get("result", [{}])[0]
                    .get("meta", {})
                    .get("regularMarketPrice")
                )
                if price:
                    macro[key] = float(price)

            if "yield_10y" in macro and "yield_2y" in macro:
                macro["yield_spread"] = macro["yield_10y"] - macro["yield_2y"]
        except Exception as exc:
            logger.debug("yields_fetch_failed", error=str(exc))

        return macro

    async def _fetch_onchain_data(self, symbol: str) -> dict:
        """
        Fetch on-chain data for crypto symbols.

        In production this would call Glassnode / CryptoQuant APIs.
        Returns an empty dict if API keys are not configured.
        """
        settings = get_settings()

        if not settings.glassnode_api_key and not settings.cryptoquant_api_key:
            logger.debug("onchain_data_no_api_keys", symbol=symbol)
            return {}

        onchain: dict = {}

        if settings.glassnode_api_key:
            try:
                base = symbol.split("/")[0].lower()  # e.g. "btc"

                # Example Glassnode endpoints (would need account with appropriate tier)
                # Funding rate from Glassnode (if available in tier)
                response = await self._httpx_client.get(
                    "https://api.glassnode.com/v1/metrics/derivatives/futures_funding_rate_perpetual",
                    params={"a": base, "api_key": settings.glassnode_api_key, "i": "24h"},
                    timeout=10.0,
                )
                if response.status_code == 200:
                    data = response.json()
                    if data:
                        latest = data[-1]
                        onchain["funding_rate"] = float(latest.get("v", 0.0))

                # Exchange net position change
                response = await self._httpx_client.get(
                    "https://api.glassnode.com/v1/metrics/transactions/transfers_volume_from_exchanges_sum",
                    params={"a": base, "api_key": settings.glassnode_api_key, "i": "24h"},
                    timeout=10.0,
                )
                if response.status_code == 200:
                    data = response.json()
                    if len(data) >= 2:
                        onchain["exchange_outflow"] = float(data[-1].get("v", 0))

                response = await self._httpx_client.get(
                    "https://api.glassnode.com/v1/metrics/transactions/transfers_volume_to_exchanges_sum",
                    params={"a": base, "api_key": settings.glassnode_api_key, "i": "24h"},
                    timeout=10.0,
                )
                if response.status_code == 200:
                    data = response.json()
                    if data:
                        onchain["exchange_inflow"] = float(data[-1].get("v", 0))

                # MVRV ratio
                response = await self._httpx_client.get(
                    "https://api.glassnode.com/v1/metrics/market/mvrv",
                    params={"a": base, "api_key": settings.glassnode_api_key, "i": "24h"},
                    timeout=10.0,
                )
                if response.status_code == 200:
                    data = response.json()
                    if data:
                        onchain["mvrv_ratio"] = float(data[-1].get("v", 0))

            except Exception as exc:
                logger.debug("glassnode_fetch_failed", symbol=symbol, error=str(exc))

        return onchain

    async def _fetch_options_data(self, symbol: str) -> dict:
        """
        Fetch options market data for equity symbols.

        In production this would call CBOE DataShop, Unusual Whales, or similar.
        Returns an empty dict if the data source is not configured.
        """
        # Options data requires a paid data feed; we return empty dict here.
        # Populated by a dedicated options_data_fetcher service in full production.
        logger.debug("options_data_not_configured", symbol=symbol)
        return {}

    @staticmethod
    def _empty_ohlcv(symbol: str) -> dict:
        """Return an empty market data dict when fetching fails."""
        return {
            "timestamps": [],
            "opens": [],
            "highs": [],
            "lows": [],
            "closes": [],
            "volumes": [],
            "current_price": 0.0,
            "volume_trend": 0.0,
            "data_source": "unavailable",
        }

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    async def _save_forecast(self, forecast: Forecast) -> None:
        """Insert forecast into PostgreSQL forecasts table."""
        try:
            row_id = await self.db.fetchval(
                _INSERT_FORECAST_SQL,
                forecast.symbol,
                forecast.timeframe,
                forecast.created_at,
                forecast.expiry_at,
                forecast.direction,
                forecast.confidence_pct,
                forecast.bull_probability,
                forecast.bear_probability,
                forecast.neutral_probability,
                forecast.price_at_creation,
                forecast.predicted_low,
                forecast.predicted_high,
                forecast.risk_score,
                forecast.market_regime,
                json.dumps(forecast.model_contributions),
                json.dumps(forecast.supporting_evidence),
                json.dumps(forecast.contradicting_evidence),
            )
            # Attach DB-generated ID to the forecast object (in-memory only)
            object.__setattr__(forecast, "id", str(row_id))
            logger.debug(
                "forecast_saved",
                forecast_id=str(row_id),
                symbol=forecast.symbol,
                timeframe=forecast.timeframe,
            )
        except asyncpg.exceptions.UndefinedTableError:
            logger.error(
                "forecasts_table_missing",
                detail="Run database migrations: CREATE TABLE forecasts ...",
            )
        except Exception as exc:
            logger.error(
                "forecast_save_failed",
                symbol=forecast.symbol,
                timeframe=forecast.timeframe,
                error=str(exc),
            )

    async def _cache_forecast(self, forecast: Forecast) -> None:
        """
        Cache the latest forecast in Redis.

        Key:   prediction:{symbol}:{timeframe}:latest
        Value: JSON-serialised Forecast
        TTL:   Same as the timeframe duration (in seconds)
        """
        try:
            redis_key = f"prediction:{forecast.symbol}:{forecast.timeframe}:latest"
            duration = TIMEFRAME_DURATIONS.get(forecast.timeframe)
            ttl_seconds = int(duration.total_seconds()) if duration else 3600

            payload = forecast.model_dump_json()
            await self.redis.set(redis_key, payload, ex=ttl_seconds)
            logger.debug(
                "forecast_cached",
                key=redis_key,
                ttl_seconds=ttl_seconds,
            )
        except Exception as exc:
            logger.warning(
                "forecast_cache_failed",
                symbol=forecast.symbol,
                timeframe=forecast.timeframe,
                error=str(exc),
            )


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------

async def main() -> None:
    settings = get_settings()
    db_pool = await asyncpg.create_pool(
        settings.database_url,
        min_size=2,
        max_size=10,
        command_timeout=30,
    )
    redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)
    calibration = await CalibrationTracker.create(settings.database_url)

    engine = PredictionEngine(db_pool, redis_client, calibration)
    try:
        await engine.run_forever()
    finally:
        await engine.shutdown()
        await db_pool.close()
        await redis_client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
