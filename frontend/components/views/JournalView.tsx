'use client';

import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { api, JournalEntry } from '@/lib/api';

const OUTCOME_COLORS: Record<string, { bg: string; text: string }> = {
  WIN:  { bg: 'rgba(34,197,94,0.12)',  text: '#22C55E' },
  LOSS: { bg: 'rgba(239,68,68,0.12)', text: '#EF4444' },
  BE:   { bg: 'rgba(245,158,11,0.12)', text: '#F59E0B' },
};

const inputStyle: React.CSSProperties = {
  padding: '8px 12px', borderRadius: 8, fontSize: 12.5,
  background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)',
  color: '#E2E8F0',
};

function formatDate(iso: string | null): string {
  if (!iso) return '—';
  return iso.slice(0, 10);
}

function formatPnl(pnl: number | null): string {
  if (pnl == null) return '—';
  const sign = pnl >= 0 ? '+' : '';
  return `${sign}$${pnl.toFixed(2)}`;
}

export default function JournalView() {
  const [entries, setEntries] = useState<JournalEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [outcomeFilter, setOutcomeFilter] = useState<string>('');
  const [search, setSearch] = useState('');
  const [since, setSince] = useState('');
  const [until, setUntil] = useState('');

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api.journal
      .list({
        outcome: outcomeFilter || undefined,
        search: search || undefined,
        since: since || undefined,
        until: until || undefined,
        limit: 50,
      })
      .then(data => { if (!cancelled) setEntries(data); })
      .catch(e => { if (!cancelled) setError(e instanceof Error ? e.message : 'Failed to load journal'); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [outcomeFilter, search, since, until]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      style={{ padding: 24, paddingBottom: 48 }}
    >
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 20, fontWeight: 700, color: '#E2E8F0', margin: 0 }}>Trade Journal</h1>
        <p style={{ fontSize: 13, color: '#475569', marginTop: 4 }}>Document your trades, lessons, and insights</p>
      </div>

      {/* Filters */}
      <div style={{
        background: '#121826',
        border: '1px solid rgba(255,255,255,0.06)',
        borderRadius: 12, padding: 16, marginBottom: 24,
        display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center',
      }}>
        <input
          style={{ ...inputStyle, flex: '1 1 220px' }}
          placeholder="Search notes and lessons..."
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
        <select style={inputStyle} value={outcomeFilter} onChange={e => setOutcomeFilter(e.target.value)}>
          <option value="">All outcomes</option>
          <option value="WIN">Win</option>
          <option value="LOSS">Loss</option>
          <option value="BE">Break-even</option>
        </select>
        <input style={inputStyle} type="date" value={since} onChange={e => setSince(e.target.value)} />
        <span style={{ color: '#475569', fontSize: 12 }}>to</span>
        <input style={inputStyle} type="date" value={until} onChange={e => setUntil(e.target.value)} />
      </div>

      {error && (
        <div style={{
          background: '#121826', border: '1px solid rgba(239,68,68,0.3)', borderRadius: 12,
          padding: 16, marginBottom: 24, color: '#F87171', fontSize: 13,
        }}>
          Could not load journal entries ({error}).
        </div>
      )}

      {/* Journal entries */}
      <div style={{
        background: '#121826',
        border: '1px solid rgba(255,255,255,0.06)',
        borderRadius: 12, overflow: 'hidden',
      }}>
        <div style={{ padding: '14px 20px', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
          <span style={{ fontSize: 14, fontWeight: 700, color: '#E2E8F0' }}>
            {loading ? 'Loading entries...' : `Journal Entries (${entries.length})`}
          </span>
        </div>
        {!loading && entries.length === 0 && (
          <div style={{ padding: 24, fontSize: 13, color: '#475569' }}>No journal entries match these filters.</div>
        )}
        {entries.map((e, i) => {
          const oc = OUTCOME_COLORS[e.outcome ?? ''] ?? { bg: 'rgba(148,163,184,0.1)', text: '#94A3B8' };
          const preview = e.lessons_learned || e.execution_notes || e.emotional_notes || 'No notes recorded for this trade.';
          return (
            <div key={e.id} style={{
              padding: '16px 20px',
              borderBottom: i < entries.length - 1 ? '1px solid rgba(255,255,255,0.04)' : 'none',
              cursor: 'pointer',
              transition: 'background 0.12s',
            }}
              onMouseEnter={ev => (ev.currentTarget.style.background = 'rgba(255,255,255,0.02)')}
              onMouseLeave={ev => (ev.currentTarget.style.background = 'transparent')}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: '#475569' }}>{formatDate(e.closed_at)}</span>
                  <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: '#4F7CFF', fontWeight: 600 }}>{e.symbol}</span>
                  <span style={{ fontSize: 11, color: '#64748B' }}>{e.direction}</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 12, fontWeight: 700, color: (e.pnl_usd ?? 0) >= 0 ? '#22C55E' : '#EF4444' }}>{formatPnl(e.pnl_usd)}</span>
                  {e.outcome && (
                    <span style={{ padding: '2px 8px', borderRadius: 5, fontSize: 10, fontWeight: 700, background: oc.bg, color: oc.text }}>{e.outcome}</span>
                  )}
                </div>
              </div>
              <p style={{ fontSize: 12.5, color: '#64748B', lineHeight: 1.55, margin: 0 }}>{preview}</p>
              {e.ai_consensus_direction && (
                <div style={{ fontSize: 11, color: '#334155', marginTop: 6 }}>
                  AI consensus: {e.ai_consensus_direction} @ {e.ai_confidence_pct != null ? `${e.ai_confidence_pct.toFixed(0)}%` : '—'} confidence
                  {e.market_regime ? ` · Regime: ${e.market_regime}` : ''}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </motion.div>
  );
}
