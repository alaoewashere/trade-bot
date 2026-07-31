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
                   created_at, expiry_at, model_contributions
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
                created_at: datetime = row["created_at"]
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
                expiry_at: datetime = row["expiry_at"]
                if expiry_at.tzinfo is None:
                    expiry_at = expiry_at.replace(tzinfo=timezone.utc)

                creation_price = float(row["price_at_creation"])
                predicted_low = float(row["predicted_low"])
                predicted_high = float(row["predicted_high"])
                direction = row["direction"]

                # Full price path over the forecast's lifetime, not just the price
                # at expiry — needed to derive real MFE/MAE and TP/SL breaches
                # rather than approximating them from the predicted range.
                path = await self._get_price_path(symbol, created_at, expiry_at)

                if not path:
                    # Fall back to a single point-in-time price so evaluation can
                    # still proceed (e.g. very short forecast windows where a full
                    # series isn't meaningfully different from a point lookup).
                    point_price = await self._get_actual_price(symbol, expiry_at)
                    if point_price is None:
                        logger.debug(
                            "actual_price_unavailable",
                            symbol=symbol,
                            expiry_at=expiry_at.isoformat(),
                            detail="Will retry next cycle.",
                        )
                        continue
                    path = [{"high": point_price, "low": point_price, "close": point_price, "ts": expiry_at.timestamp() * 1000}]

                actual_price = float(path[-1]["close"])
                high_touched = max(float(b["high"]) for b in path)
                low_touched = min(float(b["low"]) for b in path)

                actual_direction = "bullish" if actual_price > creation_price else "bearish"
                direction_correct = actual_direction == direction
                range_hit = predicted_low <= actual_price <= predicted_high

                abs_error = (
                    abs(actual_price - creation_price) / creation_price * 100
                    if creation_price > 0
                    else 0.0
                )

                mfe, mae = self._compute_mfe_mae(direction, creation_price, high_touched, low_touched)

                # TP/SL: pulled from the nearest trade_proposal's risk_assessment
                # JSONB in the same window (same join pattern used by
                # api/routers/forecasts.py's /explain endpoint), since forecasts
                # themselves don't carry explicit TP/SL levels.
                tp_price, sl_price = await self._lookup_tp_sl(symbol, created_at)
                tp_hit, sl_hit = self._compute_tp_sl_hits(direction, path, tp_price, sl_price)

                duration_minutes = int((expiry_at - created_at).total_seconds() / 60)

                if direction == "neutral":
                    outcome = "expired"
                elif direction_correct:
                    outcome = "win"
                else:
                    outcome = "loss"

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
                        mae                    = $8,
                        outcome                = $9,
                        duration_minutes       = $10,
                        high_touched           = $11,
                        low_touched            = $12,
                        tp_price               = $13,
                        sl_price               = $14,
                        tp_hit                 = $15,
                        sl_hit                 = $16,
                        price_path_source      = $17,
                        price_path_bar_count   = $18
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
                    outcome,
                    duration_minutes,
                    high_touched,
                    low_touched,
                    tp_price,
                    sl_price,
                    tp_hit,
                    sl_hit,
                    "ccxt" if self._is_crypto(symbol) else "alpaca",
                    len(path),
                )

                logger.debug(
                    "forecast_evaluated",
                    forecast_id=str(row["id"]),
                    symbol=symbol,
                    direction_correct=direction_correct,
                    range_hit=range_hit,
                    outcome=outcome,
                    mfe=mfe,
                    mae=mae,
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
    # MFE / MAE / TP-SL helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_mfe_mae(
        direction: str, creation_price: float, high_touched: float, low_touched: float
    ) -> tuple[float, float]:
        """
        Maximum Favourable/Adverse Excursion, in percent, derived from the real
        high/low touched during the forecast's lifetime (not the predicted range).

        - bullish forecast: favourable = upside (high_touched), adverse = downside (low_touched)
        - bearish forecast: favourable = downside (low_touched), adverse = upside (high_touched)
        - neutral forecast: no directional bet — MFE/MAE both measured as the
          largest move away from creation price in either direction, reported
          as favourable=smaller move / adverse=larger move so at least the
          magnitude of drift is captured.
        """
        if creation_price <= 0:
            return 0.0, 0.0

        up_pct = (high_touched - creation_price) / creation_price * 100
        down_pct = (creation_price - low_touched) / creation_price * 100

        if direction == "bullish":
            mfe, mae = max(0.0, up_pct), max(0.0, down_pct)
        elif direction == "bearish":
            mfe, mae = max(0.0, down_pct), max(0.0, up_pct)
        else:
            moves = sorted([max(0.0, up_pct), max(0.0, down_pct)])
            mfe, mae = moves[0], moves[1]

        return round(mfe, 6), round(mae, 6)

    @staticmethod
    def _compute_tp_sl_hits(
        direction: str,
        path: list[dict[str, Any]],
        tp_price: float | None,
        sl_price: float | None,
    ) -> tuple[bool | None, bool | None]:
        """Whether TP/SL levels (if known) were breached at any point in the price path."""
        if tp_price is None and sl_price is None:
            return None, None

        tp_hit = False
        sl_hit = False
        for bar in path:
            high = float(bar["high"])
            low = float(bar["low"])
            if tp_price is not None:
                if direction == "bearish":
                    tp_hit = tp_hit or low <= tp_price
                else:
                    tp_hit = tp_hit or high >= tp_price
            if sl_price is not None:
                if direction == "bearish":
                    sl_hit = sl_hit or high >= sl_price
                else:
                    sl_hit = sl_hit or low <= sl_price

        return (tp_hit if tp_price is not None else None), (sl_hit if sl_price is not None else None)

    async def _lookup_tp_sl(self, symbol: str, created_at: datetime) -> tuple[float | None, float | None]:
        """
        Best-effort lookup of TP/SL levels from the nearest trade_proposal's
        risk_assessment JSONB (mirrors the join used by /forecasts/{id}/explain).
        Returns (None, None) if no proposal is close enough or fields are absent.
        """
        try:
            row = await self.db.fetchrow(
                """
                SELECT risk_assessment
                FROM trade_proposals
                WHERE symbol = $1
                ORDER BY ABS(EXTRACT(EPOCH FROM (proposed_at - $2::TIMESTAMPTZ)))
                LIMIT 1
                """,
                symbol,
                created_at,
            )
        except Exception:
            return None, None

        if not row or not row["risk_assessment"]:
            return None, None

        ra = row["risk_assessment"]
        if isinstance(ra, str):
            try:
                ra = json.loads(ra)
            except Exception:
                return None, None
        if not isinstance(ra, dict):
            return None, None

        tp = ra.get("take_profit")
        if tp is None:
            levels = ra.get("take_profit_levels")
            if isinstance(levels, list) and levels:
                tp = levels[0]
        sl = ra.get("stop_loss")

        try:
            tp_f = float(tp) if tp is not None else None
        except (TypeError, ValueError):
            tp_f = None
        try:
            sl_f = float(sl) if sl is not None else None
        except (TypeError, ValueError):
            sl_f = None

        return tp_f, sl_f

    @staticmethod
    def _is_crypto(symbol: str) -> bool:
        sym_upper = symbol.upper()
        return any(
            sym_upper.endswith(sfx)
            for sfx in ("/USDT", "/USD", "/BTC", "/ETH", "/BUSD", "/USDC")
        ) or any(
            sym_upper.startswith(base) and "/" in sym_upper
            for base in ("BTC", "ETH", "SOL", "BNB", "XRP", "ADA")
        )

    async def _get_price_path(
        self, symbol: str, start_time: datetime, end_time: datetime
    ) -> list[dict[str, Any]]:
        """
        Fetch the full OHLCV series between start_time and end_time (inclusive),
        choosing a bar timeframe that keeps the request to a reasonable size —
        we only need the high/low envelope and closing price, not every tick.
        Returns a list of {"ts": ms, "open", "high", "low", "close"} dicts in
        chronological order, or [] if unavailable (caller falls back to a
        single point-in-time lookup).
        """
        span_minutes = max(1.0, (end_time - start_time).total_seconds() / 60.0)
        if span_minutes <= 1000:
            bar_tf = "1m"
        elif span_minutes <= 1000 * 15:
            bar_tf = "15m"
        else:
            bar_tf = "1h"

        if self._is_crypto(symbol):
            return await self._get_crypto_price_path(symbol, start_time, end_time, bar_tf)
        return await self._get_equity_price_path(symbol, start_time, end_time, bar_tf)

    async def _get_crypto_price_path(
        self, symbol: str, start_time: datetime, end_time: datetime, bar_tf: str
    ) -> list[dict[str, Any]]:
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

            since_ms = int(start_time.timestamp() * 1000)
            until_ms = int(end_time.timestamp() * 1000)
            bars: list[dict[str, Any]] = []
            cursor = since_ms
            # ccxt caps limit per call; page through until we pass until_ms or
            # hit a sane bar cap to avoid unbounded requests for very old/long forecasts.
            max_bars = 1500
            while cursor <= until_ms and len(bars) < max_bars:
                ohlcv = await exchange.fetch_ohlcv(symbol, bar_tf, since=cursor, limit=500)
                if not ohlcv:
                    break
                for bar in ohlcv:
                    if bar[0] > until_ms:
                        break
                    bars.append(
                        {"ts": bar[0], "open": bar[1], "high": bar[2], "low": bar[3], "close": bar[4]}
                    )
                last_ts = ohlcv[-1][0]
                if last_ts <= cursor:
                    break
                cursor = last_ts + 1
                if ohlcv[-1][0] > until_ms:
                    break

            return bars

        except Exception as exc:
            logger.warning("ccxt_price_path_fetch_failed", symbol=symbol, error=str(exc))
            return []

    async def _get_equity_price_path(
        self, symbol: str, start_time: datetime, end_time: datetime, bar_tf: str
    ) -> list[dict[str, Any]]:
        try:
            if self._httpx_client is None:
                import httpx
                self._httpx_client = httpx.AsyncClient(timeout=10.0)

            base_url = "https://data.alpaca.markets/v2"
            headers = {
                "APCA-API-KEY-ID": self.settings.alpaca_api_key,
                "APCA-API-SECRET-KEY": self.settings.alpaca_secret_key,
            }
            alpaca_symbol = symbol.replace("/", "")
            alpaca_tf = {"1m": "1Min", "15m": "15Min", "1h": "1Hour"}.get(bar_tf, "1Min")

            params = {
                "symbols": alpaca_symbol,
                "timeframe": alpaca_tf,
                "start": start_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "end": end_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "limit": 1500,
                "feed": "iex",
                "sort": "asc",
            }

            response = await self._httpx_client.get(
                f"{base_url}/stocks/bars", headers=headers, params=params
            )
            response.raise_for_status()
            data = response.json()
            bars_raw = data.get("bars", {}).get(alpaca_symbol, [])

            return [
                {
                    "ts": b.get("t"),
                    "open": float(b["o"]),
                    "high": float(b["h"]),
                    "low": float(b["l"]),
                    "close": float(b["c"]),
                }
                for b in bars_raw
            ]

        except Exception as exc:
            logger.warning("alpaca_price_path_fetch_failed", symbol=symbol, error=str(exc))
            return []

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
