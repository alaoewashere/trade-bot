-- migrations/versions/0006_execution_hub.sql
-- ---------------------------------------------------------------------------
-- Phase 7 — Trading Execution hub (Paper Trading wiring) + defensive schema
-- repair for api/routers/trades.py.
--
-- api/routers/trades.py (merged in an earlier phase) already SELECTs columns
-- (trade_id, entry_type, filled_price, take_profit_levels, pnl_usd, pnl_pct,
-- consensus_direction, consensus_confidence_pct, approval_id) and joins
-- tables (trade_events, market_prices, portfolio_equity) that have no
-- corresponding CREATE TABLE / ALTER TABLE anywhere in migrations/ — the
-- base `trades` table in migrations/init.sql only has `id` (not `trade_id`)
-- and lacks the rest. This migration closes that gap idempotently so the
-- existing router (and this phase's new POST /trades/paper/execute) can
-- actually run against a fresh database. Nothing here removes or narrows
-- an existing column.
-- ---------------------------------------------------------------------------

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- `trade_id` is a second, independently-unique identifier alongside the
-- existing `id` PK — trades.py's queries already assume a column with this
-- exact name, and renaming `id` would be destructive to any existing FK
-- (trade_journal.trade_id, trade_legs.trade_id, risk_assessments.proposal_id
-- reference trade_proposals, not trades, so no conflict there).
ALTER TABLE trades ADD COLUMN IF NOT EXISTS trade_id UUID NOT NULL DEFAULT gen_random_uuid();
CREATE UNIQUE INDEX IF NOT EXISTS idx_trades_trade_id_unique ON trades (trade_id);

ALTER TABLE trades ADD COLUMN IF NOT EXISTS entry_type TEXT NOT NULL DEFAULT 'market';
ALTER TABLE trades ADD COLUMN IF NOT EXISTS filled_price DECIMAL(24, 8);
ALTER TABLE trades ADD COLUMN IF NOT EXISTS take_profit_levels DECIMAL(24, 8)[] NOT NULL DEFAULT '{}';
ALTER TABLE trades ADD COLUMN IF NOT EXISTS pnl_usd DECIMAL(24, 8);
ALTER TABLE trades ADD COLUMN IF NOT EXISTS pnl_pct NUMERIC(10, 4);
ALTER TABLE trades ADD COLUMN IF NOT EXISTS consensus_direction TEXT;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS consensus_confidence_pct NUMERIC(5, 2);
ALTER TABLE trades ADD COLUMN IF NOT EXISTS approval_id UUID;

CREATE INDEX IF NOT EXISTS idx_trades_trade_id ON trades (trade_id);

-- ---------------------------------------------------------------------------
-- trade_events — referenced by GET /trades/{id}/timeline and the manual
-- close endpoint, missing from init.sql.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS trade_events (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trade_id     UUID NOT NULL REFERENCES trades (trade_id) ON DELETE CASCADE,
    event_type   TEXT NOT NULL,
    description  TEXT NOT NULL,
    occurred_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata     JSONB NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_trade_events_trade_id ON trade_events (trade_id);
CREATE INDEX IF NOT EXISTS idx_trade_events_occurred_at ON trade_events (occurred_at DESC);

-- ---------------------------------------------------------------------------
-- market_prices — last-known price per symbol, referenced by /trades/open
-- and /trades/stats' unrealised-PnL joins. Kept as a simple upsert table;
-- the live tick pipeline (data/tick_cache.py) is Redis-backed and separate
-- from this Postgres snapshot table.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS market_prices (
    symbol       TEXT PRIMARY KEY,
    last_price   DECIMAL(24, 8) NOT NULL,
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- portfolio_equity — referenced by trades.py's _fetch_equity_usd() as the
-- canonical equity snapshot source (shared with api/routers/portfolio.py).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS portfolio_equity (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    equity_usd   DECIMAL(24, 8) NOT NULL,
    recorded_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_portfolio_equity_recorded_at ON portfolio_equity (recorded_at DESC);
