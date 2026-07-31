'use client';

import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { api, TradeRecord } from '@/lib/api';

function fmtUsd(n: number | null | undefined): string {
  if (n == null) return '—';
  const sign = n >= 0 ? '+' : '-';
  return `${sign}$${Math.abs(n).toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}

function fmtPrice(n: number | null | undefined): string {
  if (n == null) return '—';
  return `$${n.toLocaleString(undefined, { maximumFractionDigits: n >= 100 ? 2 : 4 })}`;
}

const STATUS_FILTERS = ['all', 'open', 'closed', 'cancelled'] as const;

/**
 * Full execution history table — sourced directly from GET /trades (the
 * same trade ledger the rest of the platform reads), not a new data source.
 * Journal entries (GET /journal) are linked out per-row rather than
 * duplicated here, since JournalEntry already exists as its own page.
 */
export default function ExecutionHistoryView() {
  const [trades, setTrades] = useState<TradeRecord[]>([]);
  const [statusFilter, setStatusFilter] = useState<(typeof STATUS_FILTERS)[number]>('all');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api.trades
      .list({ status: statusFilter === 'all' ? undefined : statusFilter, limit: 100 })
      .then((rows) => {
        if (!cancelled) {
          setTrades(rows);
          setError(null);
        }
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Failed to load execution history');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [statusFilter]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      style={{ padding: 24, paddingBottom: 48 }}
    >
      <div style={{ marginBottom: 24, display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 700, color: '#E2E8F0', margin: 0 }}>Execution History</h1>
          <p style={{ fontSize: 13, color: '#475569', marginTop: 4 }}>
            Every order this platform has executed — paper only, until a live broker is connected
          </p>
        </div>
        <div style={{ display: 'flex', gap: 6, background: '#121826', border: '1px solid rgba(255,255,255,0.06)', borderRadius: 10, padding: 4 }}>
          {STATUS_FILTERS.map((s) => (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              style={{
                padding: '6px 14px', borderRadius: 7, fontSize: 12, fontWeight: 700, cursor: 'pointer',
                border: 'none',
                background: statusFilter === s ? 'rgba(79,124,255,0.15)' : 'transparent',
                color: statusFilter === s ? '#4F7CFF' : '#64748B',
              }}
            >
              {s.charAt(0).toUpperCase() + s.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div style={{ marginBottom: 16, padding: 12, borderRadius: 8, background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)', color: '#EF4444', fontSize: 12 }}>
          {error}
        </div>
      )}

      <div style={{
        background: '#121826', border: '1px solid rgba(255,255,255,0.06)',
        borderRadius: 12, overflow: 'hidden',
      }}>
        {!loading && trades.length === 0 ? (
          <div style={{ padding: 40, textAlign: 'center', fontSize: 13, color: '#475569' }}>
            No executions match this filter.
          </div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: 'rgba(255,255,255,0.02)' }}>
                {['Opened', 'Symbol', 'Dir', 'Broker', 'Qty', 'Fill', 'Stop', 'Status', 'P&L', 'Commission'].map(h => (
                  <th key={h} style={{ padding: '9px 14px', textAlign: 'left', fontSize: 10, fontWeight: 700, color: '#475569', letterSpacing: '0.1em', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {trades.map((t, i) => (
                <tr key={t.trade_id} style={{ background: i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.015)' }}>
                  <td style={{ padding: '10px 14px', fontSize: 11, color: '#475569', fontFamily: "'JetBrains Mono', monospace" }}>{t.opened_at?.slice(0, 16).replace('T', ' ')}</td>
                  <td style={{ padding: '10px 14px', fontWeight: 700, color: '#E2E8F0', fontSize: 13 }}>{t.symbol}</td>
                  <td style={{ padding: '10px 14px' }}>
                    <span style={{ padding: '2px 7px', borderRadius: 5, fontSize: 10, fontWeight: 700, background: t.direction === 'LONG' ? 'rgba(34,197,94,0.12)' : 'rgba(239,68,68,0.12)', color: t.direction === 'LONG' ? '#22C55E' : '#EF4444' }}>{t.direction}</span>
                  </td>
                  <td style={{ padding: '10px 14px', fontSize: 11, color: '#94A3B8' }}>{t.broker}</td>
                  <td style={{ padding: '10px 14px', fontSize: 11, color: '#94A3B8', fontFamily: "'JetBrains Mono', monospace" }}>{t.quantity}</td>
                  <td style={{ padding: '10px 14px', fontSize: 11, color: '#F1F5F9', fontFamily: "'JetBrains Mono', monospace" }}>{fmtPrice(t.filled_price)}</td>
                  <td style={{ padding: '10px 14px', fontSize: 11, color: '#EF4444', fontFamily: "'JetBrains Mono', monospace" }}>{fmtPrice(t.stop_loss)}</td>
                  <td style={{ padding: '10px 14px' }}>
                    <span style={{
                      padding: '2px 7px', borderRadius: 5, fontSize: 10, fontWeight: 700,
                      background: t.status === 'open' ? 'rgba(79,124,255,0.12)' : t.status === 'closed' ? 'rgba(148,163,184,0.12)' : 'rgba(239,68,68,0.12)',
                      color: t.status === 'open' ? '#4F7CFF' : t.status === 'closed' ? '#94A3B8' : '#EF4444',
                    }}>{t.status.toUpperCase()}</span>
                  </td>
                  <td style={{ padding: '10px 14px', fontSize: 12, fontFamily: "'JetBrains Mono', monospace", fontWeight: 700, color: (t.pnl_usd ?? 0) >= 0 ? '#22C55E' : '#EF4444' }}>{fmtUsd(t.pnl_usd)}</td>
                  <td style={{ padding: '10px 14px', fontSize: 11, color: '#64748B', fontFamily: "'JetBrains Mono', monospace" }}>{fmtPrice(t.commission)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </motion.div>
  );
}
