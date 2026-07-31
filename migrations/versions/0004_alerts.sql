-- migrations/versions/0004_alerts.sql
-- ---------------------------------------------------------------------------
-- Phase 3 — Alert Center.
--
-- Backs api/routers/alerts.py and alerts/generator.py. A single flat table
-- covers every alert type listed in the Phase 3 spec; alert_type is a free
-- TEXT column (not a Postgres ENUM) so new alert kinds can be added by the
-- generator without a migration, mirroring how risk_events.event_type is
-- modelled in migrations/init.sql.
--
-- Idempotent: safe to run repeatedly / on every startup.
-- ---------------------------------------------------------------------------

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS alerts (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    alert_type     TEXT NOT NULL CHECK (alert_type IN (
                       'high_risk_position', 'stop_loss_hit', 'take_profit_hit',
                       'consensus_changed', 'market_regime_changed', 'whale_alert',
                       'volatility_spike', 'funding_rate_alert', 'large_liquidation',
                       'confidence_dropped'
                   )),
    severity       TEXT NOT NULL DEFAULT 'info' CHECK (severity IN ('info', 'warning', 'critical')),
    symbol         TEXT,
    message        TEXT NOT NULL,
    payload        JSONB NOT NULL DEFAULT '{}',
    acknowledged   BOOLEAN NOT NULL DEFAULT FALSE,
    acknowledged_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_alerts_created_at    ON alerts (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_alert_type     ON alerts (alert_type);
CREATE INDEX IF NOT EXISTS idx_alerts_severity        ON alerts (severity);
CREATE INDEX IF NOT EXISTS idx_alerts_symbol          ON alerts (symbol);
CREATE INDEX IF NOT EXISTS idx_alerts_unacknowledged  ON alerts (acknowledged) WHERE acknowledged = FALSE;
