-- migrations/versions/0001_risk_assessments_and_extensions.sql
-- ---------------------------------------------------------------------------
-- Phase 1 — Risk Management Center.
--
-- risk_assessments was already queried by api/routers/risk.py but had no
-- corresponding CREATE TABLE in migrations/init.sql. This migration creates
-- it (idempotently) with the full column set the router expects, plus the
-- Phase 1 additions (cvar_95, kelly_fraction, expected_value_usd,
-- risk_category) computed by risk/engine.py's RiskEngine.evaluate().
--
-- All statements are idempotent: safe to run repeatedly / on every startup.
-- ---------------------------------------------------------------------------

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS risk_assessments (
    assessment_id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    proposal_id                UUID REFERENCES trade_proposals (id) ON DELETE SET NULL,
    symbol                     TEXT NOT NULL,
    direction                  TEXT NOT NULL DEFAULT '',
    approved                   BOOLEAN NOT NULL DEFAULT FALSE,
    position_size_usd          DECIMAL(24, 8) NOT NULL DEFAULT 0,
    position_size_units        DECIMAL(24, 8) NOT NULL DEFAULT 0,
    entry_price                DECIMAL(24, 8) NOT NULL DEFAULT 0,
    stop_loss                  DECIMAL(24, 8) NOT NULL DEFAULT 0,
    take_profit                DECIMAL(24, 8) NOT NULL DEFAULT 0,
    risk_reward                NUMERIC(10, 4) NOT NULL DEFAULT 0,
    max_risk_usd                DECIMAL(24, 8) NOT NULL DEFAULT 0,
    portfolio_heat_pct         NUMERIC(6, 2) NOT NULL DEFAULT 0,
    var_95                      DECIMAL(24, 8) NOT NULL DEFAULT 0,
    correlation_check          BOOLEAN NOT NULL DEFAULT TRUE,
    liquidity_check            BOOLEAN NOT NULL DEFAULT TRUE,
    rejection_reasons          JSONB NOT NULL DEFAULT '[]',
    consensus_confidence_pct   NUMERIC(5, 2),
    created_at                 TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Phase 1 additions
    cvar_95                    DECIMAL(24, 8) NOT NULL DEFAULT 0,
    kelly_fraction              NUMERIC(6, 4) NOT NULL DEFAULT 0,
    expected_value_usd          DECIMAL(24, 8) NOT NULL DEFAULT 0,
    risk_category               TEXT NOT NULL DEFAULT 'medium'
                                    CHECK (risk_category IN ('very_low', 'low', 'medium', 'high', 'extreme'))
);

-- Defensive ADD COLUMN IF NOT EXISTS for the case where risk_assessments
-- already existed in a deployed DB without the Phase 1 columns.
ALTER TABLE risk_assessments ADD COLUMN IF NOT EXISTS cvar_95 DECIMAL(24, 8) NOT NULL DEFAULT 0;
ALTER TABLE risk_assessments ADD COLUMN IF NOT EXISTS kelly_fraction NUMERIC(6, 4) NOT NULL DEFAULT 0;
ALTER TABLE risk_assessments ADD COLUMN IF NOT EXISTS expected_value_usd DECIMAL(24, 8) NOT NULL DEFAULT 0;
ALTER TABLE risk_assessments ADD COLUMN IF NOT EXISTS risk_category TEXT NOT NULL DEFAULT 'medium';

CREATE INDEX IF NOT EXISTS idx_risk_assessments_symbol      ON risk_assessments (symbol);
CREATE INDEX IF NOT EXISTS idx_risk_assessments_created_at  ON risk_assessments (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_risk_assessments_approved    ON risk_assessments (approved);
CREATE INDEX IF NOT EXISTS idx_risk_assessments_category    ON risk_assessments (risk_category);

-- ---------------------------------------------------------------------------
-- risk_limit_overrides — referenced by POST /risk/limits, missing from init.sql
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS risk_limit_overrides (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    override_data  JSONB NOT NULL,
    applied_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    operator       TEXT
);

CREATE INDEX IF NOT EXISTS idx_risk_limit_overrides_applied_at ON risk_limit_overrides (applied_at DESC);

-- ---------------------------------------------------------------------------
-- risk_violations — referenced by GET /risk/violations, missing from init.sql
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS risk_violations (
    violation_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    violation_type   TEXT NOT NULL,
    symbol           TEXT NOT NULL,
    direction        TEXT,
    severity         TEXT NOT NULL CHECK (severity IN ('warning', 'error', 'critical')),
    message          TEXT NOT NULL,
    context          JSONB NOT NULL DEFAULT '{}',
    occurred_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_risk_violations_occurred_at ON risk_violations (occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_risk_violations_severity    ON risk_violations (severity);
