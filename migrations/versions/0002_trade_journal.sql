-- migrations/versions/0002_trade_journal.sql
-- ---------------------------------------------------------------------------
-- Phase 1 — Trade Journal.
--
-- Backs api/routers/journal.py. Entries are created either manually via
-- POST /journal or auto-populated when a trade closes (see
-- api/routers/trades.py's close_position), reusing the consensus /
-- agent_signals / risk_assessment JSONB already stored on trade_proposals
-- rather than re-deriving them.
--
-- Idempotent: safe to run repeatedly / on every startup.
-- ---------------------------------------------------------------------------

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS trade_journal (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trade_id                UUID REFERENCES trades (id) ON DELETE SET NULL,
    symbol                  TEXT NOT NULL,
    direction               TEXT NOT NULL CHECK (direction IN ('LONG', 'SHORT', 'FLAT')),
    entry_price             DECIMAL(24, 8),
    exit_price              DECIMAL(24, 8),
    opened_at               TIMESTAMPTZ,
    closed_at               TIMESTAMPTZ,
    outcome                 TEXT CHECK (outcome IN ('WIN', 'LOSS', 'BE')),
    pnl_usd                 DECIMAL(24, 8),
    ai_consensus_direction  TEXT,
    ai_confidence_pct       NUMERIC(5, 2),
    agent_opinions          JSONB NOT NULL DEFAULT '[]',
    market_regime           TEXT,
    risk_score              NUMERIC(5, 2),
    emotional_notes         TEXT,
    execution_notes         TEXT,
    lessons_learned         TEXT,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_trade_journal_trade_id   ON trade_journal (trade_id);
CREATE INDEX IF NOT EXISTS idx_trade_journal_symbol     ON trade_journal (symbol);
CREATE INDEX IF NOT EXISTS idx_trade_journal_outcome    ON trade_journal (outcome);
CREATE INDEX IF NOT EXISTS idx_trade_journal_closed_at  ON trade_journal (closed_at DESC);
CREATE INDEX IF NOT EXISTS idx_trade_journal_created_at ON trade_journal (created_at DESC);

-- Free-text search across the three notes fields, used by GET /journal's
-- `search` query param.
CREATE INDEX IF NOT EXISTS idx_trade_journal_notes_fts ON trade_journal
    USING GIN (
        to_tsvector(
            'english',
            COALESCE(emotional_notes, '') || ' ' ||
            COALESCE(execution_notes, '') || ' ' ||
            COALESCE(lessons_learned, '')
        )
    );
