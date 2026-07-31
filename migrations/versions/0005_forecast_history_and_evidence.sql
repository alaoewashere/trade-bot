-- Phase 4: Data Foundation — prediction history / validation ledger.
--
-- forecasts already has mfe/mae/evaluated/direction_correct/range_hit/absolute_error_pct
-- (see migrations/init.sql), but evaluator.py only ever populated mfe/mae from the
-- *predicted* range as a proxy, not the real price path the market actually took.
-- This migration adds the additive columns needed to record a real win/loss/expired
-- outcome enum, trade duration, the actual high/low touched during the forecast's
-- lifetime, and (when a linked trade_proposal carries risk levels) whether TP/SL were
-- breached before expiry. All columns are nullable/defaulted so existing rows and
-- existing readers of `forecasts` are unaffected.
--
-- Idempotent: safe to run multiple times.

ALTER TABLE forecasts
    ADD COLUMN IF NOT EXISTS outcome              TEXT
        CHECK (outcome IN ('win', 'loss', 'expired', 'pending')) DEFAULT 'pending',
    ADD COLUMN IF NOT EXISTS duration_minutes      INTEGER,
    ADD COLUMN IF NOT EXISTS high_touched          DECIMAL(24, 8),
    ADD COLUMN IF NOT EXISTS low_touched           DECIMAL(24, 8),
    ADD COLUMN IF NOT EXISTS tp_price              DECIMAL(24, 8),
    ADD COLUMN IF NOT EXISTS sl_price              DECIMAL(24, 8),
    ADD COLUMN IF NOT EXISTS tp_hit                BOOLEAN,
    ADD COLUMN IF NOT EXISTS sl_hit                BOOLEAN,
    ADD COLUMN IF NOT EXISTS price_path_source     TEXT,
    ADD COLUMN IF NOT EXISTS price_path_bar_count   INTEGER;

CREATE INDEX IF NOT EXISTS idx_forecasts_outcome ON forecasts (outcome);

-- ---------------------------------------------------------------------------
-- agent_decisions: additive numeric evidence score columns.
--
-- graph/state.py's AgentReport now carries optional supporting_evidence_scored /
-- contradicting_evidence_scored (list[{"label": str, "score": float}]). Persist the
-- net numeric score alongside the existing flat-string evidence so /explain and
-- future chart overlays can read it without re-deriving from JSON blobs each time.
-- ---------------------------------------------------------------------------
ALTER TABLE agent_decisions
    ADD COLUMN IF NOT EXISTS supporting_evidence_scored     JSONB,
    ADD COLUMN IF NOT EXISTS contradicting_evidence_scored  JSONB,
    ADD COLUMN IF NOT EXISTS net_evidence_score             NUMERIC(10, 4);
