-- migrations/versions/0003_backtest_runs.sql
-- ---------------------------------------------------------------------------
-- Phase 2 — Backtesting System.
--
-- Backs api/routers/backtest.py. A backtest run replays historical
-- `forecasts` rows (already scored against actual outcomes by
-- prediction_engine/evaluator.py) over a symbol/timeframe/date-range window
-- and stores the aggregated report as JSONB in `results` — this is a
-- research tool, not a production job system, so runs execute synchronously
-- and there is no separate queue/worker table.
--
-- `strategy_name` is stored as a label only. The forecasts table has no
-- strategy taxonomy (it is symbol/timeframe based, keyed by an ensemble of
-- models in `model_contributions`), so we do not fabricate per-strategy
-- performance — see api/routers/backtest.py module docstring for details.
--
-- Idempotent: safe to run repeatedly / on every startup.
-- ---------------------------------------------------------------------------

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS backtest_runs (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    symbol             TEXT NOT NULL,
    timeframe          TEXT NOT NULL,
    strategy_name      TEXT,
    date_range_start   TIMESTAMPTZ NOT NULL,
    date_range_end     TIMESTAMPTZ NOT NULL,
    status             TEXT NOT NULL DEFAULT 'pending'
                           CHECK (status IN ('pending', 'running', 'completed', 'failed')),
    results            JSONB NOT NULL DEFAULT '{}',
    error_message      TEXT,
    created_by         TEXT,
    notes              TEXT
);

CREATE INDEX IF NOT EXISTS idx_backtest_runs_symbol      ON backtest_runs (symbol);
CREATE INDEX IF NOT EXISTS idx_backtest_runs_created_at  ON backtest_runs (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_backtest_runs_status      ON backtest_runs (status);
