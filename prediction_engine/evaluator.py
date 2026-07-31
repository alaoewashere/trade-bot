"""
ForecastEvaluator — daemon that evaluates expired forecasts and recomputes calibration stats.

Run as:
    python -m prediction_engine.evaluator
"""
from __future__ import annotations

import asyncio
import json
import math
from datetime import datetime, timezone
from typing import Any

import asyncpg
import structlog

from config.settings import get_settings

logger = structlog.get_logger(__name__)

_CALIBRATION_WINDOWS = [100, 500, 1000, 10_000]

_UPSERT_CALIBRATION_SQL = """
    INSERT INTO calibration_stats (
        symbol, timeframe, model_name, window_size,
        computed_at, accuracy_pct, brier_score, avg_confidence,
        overconfidence, range_accuracy, sample_count
    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
    ON CONFLICT (symbol, timeframe, model_name, window_size)
    DO UPDATE SET
        computed_at   = EXCLUDED.computed_at,
        accuracy_pct  = EXCLUDED.accuracy_pct,
        brier_score   = EXCLUDED.brier_score,
        avg_confidence = EXCLUDED.avg_confidence,
        overconfidence = EXCLUDED.overconfidence,
        range_accuracy = EXCLUDED.range_accuracy,
        sample_count   = EXCLUDED.sample_count
"""


class ForecastEvaluator:
    """
    Daemon that:
    1. Polls the forecasts table every 60 seconds for expired, un-evaluated rows.
    2. Fetches the actual price at expiry (via ccxt for crypto, Alpaca for equities).
    3. Marks each forecast as evaluated with accuracy metrics.
    4. Recomputes calibration_stats for all model x symbol x timeframe combinations.
    """

    def __init__(self, db_pool: asyncpg.Pool) -> None:
        self.db = db_pool
        self.settings = get_settings()
        self._ccxt_exchanges: dict[str, Any] = {}  # symbol → ccxt exchange instance
        self._httpx_client: Any = None              # lazy httpx.AsyncClient

    # ------------------------------------------------------------------
    # Main daemon loop
    # ------------------------------------------------------------------

    async def run_forever(self) -> None:
        """Main daemon loop — runs every 60 seconds."""
        logger.info("forecast_evaluator_started")
        try:
            await self._init_clients()
            while True:
                try:
                    count = await self.evaluate_expired()
                    if count > 0:
                        await self.recompute_calibration_stats()
                        logger.info("evaluation_cycle_complete", evaluated=count)
                    else:
                        logger.debug("evaluation_cycle_no_expired_forecasts")
                except asyncpg.exceptions.UndefinedTableError as exc:
                    logger.error(
                        "evaluation_table_missing",
                        error=str(exc),
                        detail="Run database migrations first.",
                    )
                except Exception as exc:
                    logger.error("evaluation_error", error=str(exc), exc_info=True)
                await asyncio.sleep(60)
        finally:
            await self._close_clients()

    # ------------------------------------------------------------------
    # Core evaluation
    # ------------------------------------------------------------------

    async def evaluate_expired(self) -> int:
        """
        Fetch and evaluate up to 100 expired, un-evaluated forecasts.
        Returns the count of successfully evaluated forecasts.
        """
        rows = await self.db.fetch(
            """
            SELECT id, symbol, timeframe, direction, confidence_pct,
                   bull_probability, price_at_creation, predicted_low, predicted_high,
                   expiry_at, model_contributions
            FROM forecasts
            WHERE evaluated = FALSE
              AND expiry_at < NOW()
            ORDER BY expiry_at ASC
            LIMIT 100
            """
        )

        if not rows:
            return 0

        evaluated = 0
        for row in rows:
            try:
                symbol = row["symbol"]
                expiry_at: datetime = row["expiry_at"]
                if expiry_at.tzinfo is None:
                    expiry_at = expiry_at.replace(tzinfo=timezone.utc)

                actual_price = await self._get_actual_price(symbol, expiry_at)
                if actual_price is None:
                    logger.debug(
                        "actual_price_unavailable",
                        symbol=symbol,
                        expiry_at=expiry_at.isoformat(),
                        detail="Will retry next cycle.",
                    )
                    continue

                creation_price = float(row["price_at_creation"])
                actual_direction = "bullish" if actual_price > creation_price else "bearish"
                direction_correct = actual_direction == row["direction"]
                predicted_low = float(row["predicted_low"])
                predicted_high = float(row["predicted_high"])
                range_hit = predicted_low <= actual_price <= predicted_high

                # Percentage move
                abs_error = (
                    abs(actual_price - creation_price) / creation_price * 100
                    if creation_price > 0
                    else 0.0
                )

                # MFE / MAE (simplified via predicted range as proxy for intra-period extremes)
                mfe = max(
                    0.0,
                    (predicted_high - creation_price) / creation_price * 100
                    if creation_price > 0
                    else 0.0,
                )
                mae = max(
                    0.0,
                    (creation_price - predicted_low) / creation_price * 100
                    if creation_price > 0
                    else 0.0,
                )

                await self.db.execute(
                    """
                    UPDATE forecasts SET
                        evaluated              = TRUE,
                        actual_price_at_expiry = $2,
                        actual_direction       = $3,
                        direction_correct      = $4,
                        range_hit              = $5,
                        absolute_error_pct     = $6,
                        mfe                    = $7,
                        mae                    = $8
                    WHERE id = $1
                    """,
                    row["id"],
                    actual_price,
                    actual_direction,
                    direction_correct,
                    range_hit,
                    abs_error,
                    mfe,
                    mae,
                )

                logger.debug(
                    "forecast_evaluated",
                    forecast_id=str(row["id"]),
                    symbol=symbol,
                    direction_correct=direction_correct,
                    range_hit=range_hit,
                )
                evaluated += 1

            except Exception as exc:
                logger.warning(
                    "forecast_evaluation_row_error",
                    forecast_id=str(row.get("id")),
                    error=str(exc),
                )

        return evaluated

    # ------------------------------------------------------------------
    # Actual price fetching
    # ------------------------------------------------------------------

    async def _get_actual_price(self, symbol: str, at_time: datetime) -> float | None:
        """
        Get the actual closing price of 'symbol' at (or near) 'at_time'.

        Strategy:
        - Crypto symbols (contain /USDT, /USD, /BTC, /ETH): use ccxt Binance
          to fetch the 1m OHLCV bar that contains at_time.
        - Equity symbols (SPY, QQQ, AAPL, etc.): use Alpaca historical bars API.
        - Forex / other: attempt Alpaca first; fall back to None.

        Returns None if the price cannot be retrieved so the forecast is
        retried on the next evaluation cycle.
        """
        sym_upper = symbol.upper()
        is_crypto = any(
            sym_upper.endswith(sfx)
            for sfx in ("/USDT", "/USD", "/BTC", "/ETH", "/BUSD", "/USDC")
        ) or any(
            sym_upper.startswith(base) and "/" in sym_upper
            for base in ("BTC", "ETH", "SOL", "BNB", "XRP", "ADA")
        )

        if is_crypto:
            return await self._get_crypto_price(symbol, at_time)
        else:
            return await self._get_equity_price(symbol, at_time)

    async def _get_crypto_price(self, symbol: str, at_time: datetime) -> float | None:
        """Fetch crypto price at at_time using ccxt Binance."""
        try:
            import ccxt.async_support as ccxt

            exchange = self._ccxt_exchanges.get("binance")
            if exchange is None:
                exchange = ccxt.binance(
                    {
                        "apiKey": self.settings.binance_api_key,
                        "secret": self.settings.binance_secret_key,
                        "enableRateLimit": True,
                    }
                )
                self._ccxt_exchanges["binance"] = exchange

            since_ms = int(at_time.timestamp() * 1000) - 60_000  # 1 min before
            ohlcv = await exchange.fetch_ohlcv(symbol, "1m", since=since_ms, limit=3)

            if not ohlcv:
                logger.debug("ccxt_no_ohlcv", symbol=symbol, at_time=at_time.isoformat())
                return None

            # Find the bar closest to at_time
            at_ts = at_time.timestamp() * 1000
            closest = min(ohlcv, key=lambda bar: abs(bar[0] - at_ts))
            close_price = float(closest[4])  # index 4 = close
            logger.debug(
                "ccxt_price_fetched",
                symbol=symbol,
                bar_ts=closest[0],
                close=close_price,
            )
            return close_price

        except Exception as exc:
            logger.warning(
                "ccxt_price_fetch_failed",
                symbol=symbol,
                at_time=at_time.isoformat(),
                error=str(exc),
            )
            return None

    async def _get_equity_price(self, symbol: str, at_time: datetime) -> float | None:
        """Fetch equity price at at_time using Alpaca historical bars API."""
        try:
            if self._httpx_client is None:
                import httpx
                self._httpx_client = httpx.AsyncClient(timeout=10.0)

            # Alpaca historical bars endpoint
            base_url = "https://data.alpaca.markets/v2"
            headers = {
                "APCA-API-KEY-ID": self.settings.alpaca_api_key,
                "APCA-API-SECRET-KEY": self.settings.alpaca_secret_key,
            }

            # Request a 1-minute bar window around at_time
            start = at_time.strftime("%Y-%m-%dT%H:%M:%SZ")
            # Convert symbol format (e.g. SPY → SPY, BTC/USD → skip)
            alpaca_symbol = symbol.replace("/", "")

            params = {
                "symbols": alpaca_symbol,
                "timeframe": "1Min",
                "start": start,
                "limit": 3,
                "feed": "iex",  # use IEX for wider coverage
                "sort": "asc",
            }

            response = await self._httpx_client.get(
                f"{base_url}/stocks/bars",
                headers=headers,
                params=params,
            )
            response.raise_for_status()
            data = response.json()

            bars = data.get("bars", {}).get(alpaca_symbol, [])
            if not bars:
                logger.debug(
                    "alpaca_no_bars",
                    symbol=symbol,
                    at_time=at_time.isoformat(),
                )
                return None

            # Use the first bar's close (closest to at_time)
            close_price = float(bars[0]["c"])
            logger.debug(
                "alpaca_price_fetched",
                symbol=symbol,
                bar_time=bars[0].get("t"),
                close=close_price,
            )
            return close_price

        except Exception as exc:
            logger.warning(
                "alpaca_price_fetch_failed",
                symbol=symbol,
                at_time=at_time.isoformat(),
                error=str(exc),
            )
            return None

    # ------------------------------------------------------------------
    # Calibration stats recomputation
    # ------------------------------------------------------------------

    async def recompute_calibration_stats(self) -> None:
        """
        Recompute calibration_stats for all model × symbol × timeframe × window combos.

        For each combination:
        - Fetch the last N evaluated forecasts.
        - Compute accuracy_pct, brier_score, avg_confidence, overconfidence, range_accuracy.
        - Upsert into calibration_stats.
        """
        # Get all distinct (symbol, timeframe, model_name) combos from recent forecasts
        combos = await self.db.fetch(
            """
            SELECT DISTINCT symbol, timeframe, key AS model_name
            FROM forecasts,
                 jsonb_object_keys(model_contributions::jsonb) AS key
            WHERE evaluated = TRUE
            ORDER BY symbol, timeframe, model_name
            """
        )

        if not combos:
            logger.debug("calibration_recompute_no_combos")
            return

        now = datetime.now(timezone.utc)
        recomputed = 0

        for combo in combos:
            symbol = combo["symbol"]
            timeframe = combo["timeframe"]
            model_name = combo["model_name"]

            for window in _CALIBRATION_WINDOWS:
                try:
                    rows = await self.db.fetch(
                        """
                        SELECT direction, direction_correct, range_hit,
                               bull_probability, confidence_pct
                        FROM forecasts
                        WHERE symbol = $1
                          AND timeframe = $2
                          AND evaluated = TRUE
                        ORDER BY expiry_at DESC
                        LIMIT $3
                        """,
                        symbol,
                        timeframe,
                        window,
                    )

                    if len(rows) < 10:
                        # Not enough data for meaningful calibration
                        continue

                    forecasts_list = [dict(r) for r in rows]
                    accuracy_pct = self._compute_accuracy(forecasts_list)
                    brier_score = await self._compute_brier_score(forecasts_list)
                    avg_confidence = sum(
                        float(r["confidence_pct"]) for r in forecasts_list
                    ) / len(forecasts_list)
                    range_accuracy = (
                        sum(1 for r in forecasts_list if r["range_hit"]) / len(forecasts_list) * 100
                    )
                    overconfidence = avg_confidence - accuracy_pct

                    await self.db.execute(
                        _UPSERT_CALIBRATION_SQL,
                        symbol,
                        timeframe,
                        model_name,
                        window,
                        now,
                        round(accuracy_pct, 4),
                        round(brier_score, 6),
                        round(avg_confidence, 4),
                        round(overconfidence, 4),
                        round(range_accuracy, 4),
                        len(forecasts_list),
                    )
                    recomputed += 1

                except Exception as exc:
                    logger.warning(
                        "calibration_recompute_error",
                        symbol=symbol,
                        timeframe=timeframe,
                        model=model_name,
                        window=window,
                        error=str(exc),
                    )

        logger.info(
            "calibration_recomputed",
            total_upserts=recomputed,
            combos=len(combos),
        )

    # ------------------------------------------------------------------
    # Metric helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_accuracy(forecasts: list[dict]) -> float:
        """Direction accuracy as a percentage (0–100)."""
        if not forecasts:
            return 0.0
        correct = sum(1 for f in forecasts if f.get("direction_correct"))
        return correct / len(forecasts) * 100.0

    async def _compute_brier_score(self, forecasts: list[dict]) -> float:
        """
        Brier score: mean((probability - outcome)²).

        For binary direction:
        - outcome = 1.0 if actual_direction == "bullish" else 0.0
        - probability = bull_probability from forecast
        Lower is better; 0.25 is the score of a random guesser.
        """
        if not forecasts:
            return 0.25

        total = 0.0
        count = 0
        for f in forecasts:
            bull_prob = float(f.get("bull_probability", 0.5))
            # Reconstruct actual outcome: direction_correct XOR (direction == "bearish")
            # We stored direction_correct=True if predicted matches actual.
            # We need to infer actual_direction from what we stored.
            # Since actual_direction is stored in the DB but not fetched here, use proxy:
            # If direction_correct is True: actual == predicted direction
            # If direction_correct is False: actual != predicted direction
            predicted_bull = f.get("direction") == "bullish"
            direction_correct = bool(f.get("direction_correct"))

            actual_bull = predicted_bull if direction_correct else (not predicted_bull)
            outcome = 1.0 if actual_bull else 0.0

            total += (bull_prob - outcome) ** 2
            count += 1

        return total / count if count > 0 else 0.25

    # ------------------------------------------------------------------
    # Client lifecycle
    # ------------------------------------------------------------------

    async def _init_clients(self) -> None:
        """Initialise HTTP client."""
        try:
            import httpx
            self._httpx_client = httpx.AsyncClient(timeout=10.0)
        except ImportError:
            logger.warning("httpx_not_installed", detail="Equity price fetching will be unavailable.")

    async def _close_clients(self) -> None:
        """Cleanly close all network clients."""
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


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------

async def main() -> None:
    settings = get_settings()
    pool = await asyncpg.create_pool(
        settings.database_url,
        min_size=2,
        max_size=10,
        command_timeout=30,
    )
    evaluator = ForecastEvaluator(pool)
    await evaluator.run_forever()


if __name__ == "__main__":
    asyncio.run(main())
