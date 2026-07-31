-- Hedge Fund AI - PostgreSQL Initialization
-- Run once on fresh database; all statements are idempotent.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ---------------------------------------------------------------------------
-- trade_proposals
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS trade_proposals (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol            TEXT NOT NULL,
    direction         TEXT NOT NULL CHECK (direction IN ('LONG', 'SHORT', 'FLAT')),
    timeframe         TEXT NOT NULL,
    proposed_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    consensus_score   NUMERIC(5, 4),                 -- 0.0000 – 1.0000
    confidence_pct    NUMERIC(5, 2),                 -- 0.00 – 100.00
    debate_summary    JSONB,
    agent_signals     JSONB,
    risk_assessment   JSONB,
    status            TEXT NOT NULL DEFAULT 'pending'
                          CHECK (status IN ('pending', 'approved', 'rejected', 'expired', 'cancelled')),
    human_decision    TEXT,
    human_reason      TEXT,
    decided_at        TIMESTAMPTZ,
    expires_at        TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_trade_proposals_symbol        ON trade_proposals (symbol);
CREATE INDEX IF NOT EXISTS idx_trade_proposals_status        ON trade_proposals (status);
CREATE INDEX IF NOT EXISTS idx_trade_proposals_proposed_at   ON trade_proposals (proposed_at DESC);
CREATE INDEX IF NOT EXISTS idx_trade_proposals_direction     ON trade_proposals (direction);

-- ---------------------------------------------------------------------------
-- trades
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS trades (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    proposal_id      UUID REFERENCES trade_proposals (id) ON DELETE SET NULL,
    symbol           TEXT NOT NULL,
    direction        TEXT NOT NULL CHECK (direction IN ('LONG', 'SHORT', 'FLAT')),
    quantity         DECIMAL(24, 8) NOT NULL,
    entry_price      DECIMAL(24, 8),
    stop_loss        DECIMAL(24, 8),
    take_profit      DECIMAL(24, 8),
    broker           TEXT NOT NULL,
    broker_order_id  TEXT,
    status           TEXT NOT NULL DEFAULT 'open'
                         CHECK (status IN ('open', 'closed', 'cancelled', 'error')),
    opened_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    closed_at        TIMESTAMPTZ,
    exit_price       DECIMAL(24, 8),
    realized_pnl     DECIMAL(24, 8),
    realized_pnl_pct DECIMAL(10, 6),
    commission       DECIMAL(24, 8) NOT NULL DEFAULT 0,
    slippage         DECIMAL(24, 8) NOT NULL DEFAULT 0,
    exit_reason      TEXT,
    market_regime    TEXT,
    tags             TEXT[],
    notes            TEXT,
    metadata         JSONB
);

CREATE INDEX IF NOT EXISTS idx_trades_symbol       ON trades (symbol);
CREATE INDEX IF NOT EXISTS idx_trades_status       ON trades (status);
CREATE INDEX IF NOT EXISTS idx_trades_opened_at    ON trades (opened_at DESC);
CREATE INDEX IF NOT EXISTS idx_trades_proposal_id  ON trades (proposal_id);
CREATE INDEX IF NOT EXISTS idx_trades_broker       ON trades (broker);

-- ---------------------------------------------------------------------------
-- trade_legs
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS trade_legs (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trade_id         UUID NOT NULL REFERENCES trades (id) ON DELETE CASCADE,
    leg_type         TEXT NOT NULL
                         CHECK (leg_type IN ('entry', 'add', 'partial_exit', 'full_exit',
                                             'stop_loss', 'take_profit')),
    price            DECIMAL(24, 8) NOT NULL,
    quantity         DECIMAL(24, 8) NOT NULL,
    timestamp        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    broker_order_id  TEXT,
    commission       DECIMAL(24, 8) NOT NULL DEFAULT 0,
    notes            TEXT
);

CREATE INDEX IF NOT EXISTS idx_trade_legs_trade_id  ON trade_legs (trade_id);
CREATE INDEX IF NOT EXISTS idx_trade_legs_timestamp ON trade_legs (timestamp DESC);

-- ---------------------------------------------------------------------------
-- portfolio_snapshots
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id           BIGSERIAL PRIMARY KEY,
    snapshot_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    total_equity DECIMAL(24, 8) NOT NULL,
    cash         DECIMAL(24, 8) NOT NULL,
    open_pnl     DECIMAL(24, 8) NOT NULL DEFAULT 0,
    daily_pnl    DECIMAL(24, 8),
    daily_pnl_pct DECIMAL(10, 6),
    weekly_pnl   DECIMAL(24, 8),
    max_drawdown DECIMAL(10, 6),
    positions    JSONB,
    risk_metrics JSONB
);

CREATE INDEX IF NOT EXISTS idx_portfolio_snapshots_at ON portfolio_snapshots (snapshot_at DESC);

-- ---------------------------------------------------------------------------
-- forecasts
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS forecasts (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol                  TEXT NOT NULL,
    timeframe               TEXT NOT NULL
                                CHECK (timeframe IN ('1m', '3m', '5m', '15m', '30m', '1h', '4h', '1d')),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expiry_at               TIMESTAMPTZ NOT NULL,
    direction               TEXT NOT NULL CHECK (direction IN ('bullish', 'bearish', 'neutral')),
    confidence_pct          NUMERIC(5, 2),
    bull_probability        NUMERIC(5, 4),
    bear_probability        NUMERIC(5, 4),
    neutral_probability     NUMERIC(5, 4),
    price_at_creation       DECIMAL(24, 8),
    predicted_low           DECIMAL(24, 8),
    predicted_high          DECIMAL(24, 8),
    risk_score              NUMERIC(5, 4),
    market_regime           TEXT,
    model_contributions     JSONB,
    supporting_evidence     JSONB,
    contradicting_evidence  JSONB,
    -- evaluation fields (filled by forecast-evaluator service)
    evaluated               BOOLEAN NOT NULL DEFAULT FALSE,
    actual_price_at_expiry  DECIMAL(24, 8),
    actual_direction        TEXT,
    direction_correct       BOOLEAN,
    range_hit               BOOLEAN,
    absolute_error_pct      DECIMAL(10, 6),
    mfe                     DECIMAL(24, 8),   -- maximum favourable excursion
    mae                     DECIMAL(24, 8)    -- maximum adverse excursion
);

CREATE INDEX IF NOT EXISTS idx_forecasts_symbol      ON forecasts (symbol);
CREATE INDEX IF NOT EXISTS idx_forecasts_timeframe   ON forecasts (timeframe);
CREATE INDEX IF NOT EXISTS idx_forecasts_created_at  ON forecasts (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_forecasts_expiry_at   ON forecasts (expiry_at);
CREATE INDEX IF NOT EXISTS idx_forecasts_evaluated   ON forecasts (evaluated) WHERE NOT evaluated;
CREATE INDEX IF NOT EXISTS idx_forecasts_direction   ON forecasts (direction);

-- ---------------------------------------------------------------------------
-- calibration_stats
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS calibration_stats (
    id              BIGSERIAL PRIMARY KEY,
    symbol          TEXT NOT NULL,
    timeframe       TEXT NOT NULL,
    model_name      TEXT NOT NULL,
    window_size     INTEGER NOT NULL CHECK (window_size IN (100, 500, 1000, 10000)),
    computed_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    accuracy_pct    NUMERIC(6, 4),
    brier_score     NUMERIC(8, 6),
    log_loss        NUMERIC(8, 6),
    avg_confidence  NUMERIC(5, 4),
    overconfidence  NUMERIC(6, 4),
    range_accuracy  NUMERIC(5, 4),
    sample_count    INTEGER NOT NULL DEFAULT 0,
    UNIQUE (symbol, timeframe, model_name, window_size)
);

CREATE INDEX IF NOT EXISTS idx_calibration_stats_symbol     ON calibration_stats (symbol);
CREATE INDEX IF NOT EXISTS idx_calibration_stats_model      ON calibration_stats (model_name);
CREATE INDEX IF NOT EXISTS idx_calibration_stats_computed_at ON calibration_stats (computed_at DESC);

-- ---------------------------------------------------------------------------
-- agent_decisions
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS agent_decisions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id        TEXT NOT NULL,
    symbol          TEXT NOT NULL,
    decided_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    signal          TEXT NOT NULL,
    confidence      NUMERIC(5, 4),
    reasoning       TEXT,
    outcome         TEXT NOT NULL DEFAULT 'pending'
                        CHECK (outcome IN ('correct', 'incorrect', 'neutral', 'pending')),
    pnl_attribution DECIMAL(24, 8)
);

CREATE INDEX IF NOT EXISTS idx_agent_decisions_agent_id   ON agent_decisions (agent_id);
CREATE INDEX IF NOT EXISTS idx_agent_decisions_symbol     ON agent_decisions (symbol);
CREATE INDEX IF NOT EXISTS idx_agent_decisions_decided_at ON agent_decisions (decided_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_decisions_outcome    ON agent_decisions (outcome);

-- ---------------------------------------------------------------------------
-- market_regimes
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS market_regimes (
    id          BIGSERIAL PRIMARY KEY,
    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    symbol      TEXT NOT NULL,
    regime      TEXT NOT NULL
                    CHECK (regime IN ('trending_up', 'trending_down', 'ranging', 'volatile',
                                      'accumulation', 'distribution', 'low_volatility')),
    confidence  NUMERIC(5, 4),
    features    JSONB
);

CREATE INDEX IF NOT EXISTS idx_market_regimes_symbol      ON market_regimes (symbol);
CREATE INDEX IF NOT EXISTS idx_market_regimes_detected_at ON market_regimes (detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_market_regimes_regime      ON market_regimes (regime);

-- ---------------------------------------------------------------------------
-- risk_events
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS risk_events (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type   TEXT NOT NULL,
    triggered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    severity     TEXT NOT NULL CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    details      JSONB,
    resolved_at  TIMESTAMPTZ,
    resolved_by  TEXT
);

CREATE INDEX IF NOT EXISTS idx_risk_events_triggered_at ON risk_events (triggered_at DESC);
CREATE INDEX IF NOT EXISTS idx_risk_events_severity     ON risk_events (severity);
CREATE INDEX IF NOT EXISTS idx_risk_events_event_type   ON risk_events (event_type);
CREATE INDEX IF NOT EXISTS idx_risk_events_unresolved   ON risk_events (resolved_at) WHERE resolved_at IS NULL;

-- ---------------------------------------------------------------------------
-- news_blackout_windows
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS news_blackout_windows (
    id             BIGSERIAL PRIMARY KEY,
    event_name     TEXT NOT NULL,
    symbol         TEXT,                             -- NULL means all symbols
    blackout_start TIMESTAMPTZ NOT NULL,
    blackout_end   TIMESTAMPTZ NOT NULL,
    source         TEXT NOT NULL DEFAULT 'economic_calendar',
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_blackout_symbol        ON news_blackout_windows (symbol);
CREATE INDEX IF NOT EXISTS idx_blackout_start         ON news_blackout_windows (blackout_start);
CREATE INDEX IF NOT EXISTS idx_blackout_end           ON news_blackout_windows (blackout_end);
CREATE INDEX IF NOT EXISTS idx_blackout_active        ON news_blackout_windows (blackout_start, blackout_end);

-- ---------------------------------------------------------------------------
-- strategy_performance
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS strategy_performance (
    id              BIGSERIAL PRIMARY KEY,
    strategy_name   TEXT NOT NULL,
    symbol          TEXT NOT NULL,
    market_regime   TEXT,
    period_start    TIMESTAMPTZ NOT NULL,
    period_end      TIMESTAMPTZ NOT NULL,
    trade_count     INTEGER NOT NULL DEFAULT 0,
    win_count       INTEGER NOT NULL DEFAULT 0,
    win_rate        NUMERIC(5, 4),
    total_pnl       DECIMAL(24, 8),
    avg_pnl         DECIMAL(24, 8),
    sharpe_ratio    NUMERIC(8, 4),
    max_drawdown    NUMERIC(6, 4),
    profit_factor   NUMERIC(8, 4),
    computed_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_strategy_perf_name         ON strategy_performance (strategy_name);
CREATE INDEX IF NOT EXISTS idx_strategy_perf_symbol       ON strategy_performance (symbol);
CREATE INDEX IF NOT EXISTS idx_strategy_perf_regime       ON strategy_performance (market_regime);
CREATE INDEX IF NOT EXISTS idx_strategy_perf_computed_at  ON strategy_performance (computed_at DESC);
CREATE INDEX IF NOT EXISTS idx_strategy_perf_period       ON strategy_performance (period_start, period_end);
