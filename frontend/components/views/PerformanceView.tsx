'use client';

import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { api, TradeStats, CalendarDay } from '@/lib/api';

const MONTH_LABELS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

function monthlyFromCalendar(days: CalendarDay[]): { m: string; pnl: number; pos: boolean }[] {
  const byMonth = new Map<number, number>();
  for (const d of days) {
    const month = new Date(d.date).getUTCMonth();
    byMonth.set(month, (byMonth.get(month) || 0) + d.pnl_usd);
  }
  return MONTH_LABELS.map((m, i) => {
    const pnl = byMonth.get(i) || 0;
    return { m, pnl, pos: pnl >= 0 };
  });
}

export default function PerformanceView() {
  const [stats, setStats] = useState<TradeStats | null>(null);
  const [calendar, setCalendar] = useState<CalendarDay[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const yearStart = `${new Date().getUTCFullYear()}-01-01T00:00:00Z`;

    Promise.all([api.trades.stats(), api.trades.calendar({ since: yearStart })])
      .then(([statsRes, calendarRes]) => {
        if (cancelled) return;
        setStats(statsRes);
        setCalendar(calendarRes);
        setError(null);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : 'Failed to load performance data');
      })
      .finally(() => !cancelled && setLoading(false));

    return () => {
      cancelled = true;
    };
  }, []);

  const kpis = stats
    ? [
        { label: 'Win Rate', value: `${stats.win_rate_pct.toFixed(1)}%`, color: '#22C55E' },
        { label: 'Profit Factor', value: Number.isFinite(stats.profit_factor) ? stats.profit_factor.toFixed(2) : '∞', color: '#4F7CFF' },
        { label: 'Sharpe Ratio', value: stats.sharpe_ratio !== null ? stats.sharpe_ratio.toFixed(2) : '—', color: '#4F7CFF' },
        { label: 'Max Drawdown', value: `-${stats.max_drawdown_pct.toFixed(1)}%`, color: '#EF4444' },
        { label: 'Total Trades', value: stats.total_trades.toLocaleString(), color: '#F1F5F9' },
        { label: 'Avg Win', value: `+$${stats.avg_win_usd.toFixed(0)}`, color: '#22C55E' },
        { label: 'Avg Loss', value: `-$${Math.abs(stats.avg_loss_usd).toFixed(0)}`, color: '#EF4444' },
        { label: 'Expectancy', value: `${stats.expectancy_usd >= 0 ? '+' : ''}$${stats.expectancy_usd.toFixed(0)}`, color: stats.expectancy_usd >= 0 ? '#22C55E' : '#EF4444' },
      ]
    : [];

  const months = monthlyFromCalendar(calendar);
  const maxPnl = Math.max(1, ...months.map((m) => Math.abs(m.pnl)));

  const bestDay = stats?.best_day;
  const worstDay = stats?.worst_day;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      style={{ padding: 24, paddingBottom: 48 }}
    >
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 20, fontWeight: 700, color: '#E2E8F0', margin: 0 }}>Performance Analytics</h1>
        <p style={{ fontSize: 13, color: '#475569', marginTop: 4 }}>Comprehensive trading performance metrics and analysis</p>
        {error && (
          <p style={{ fontSize: 12, color: '#EF4444', marginTop: 8 }}>
            Could not load live performance data: {error}
          </p>
        )}
      </div>

      {/* KPIs */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14, marginBottom: 24 }}>
        {(loading ? Array.from({ length: 8 }) : kpis).map((k: any, i) => (
          <motion.div key={k?.label ?? i}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.04, duration: 0.2 }}
            style={{
              background: '#121826', border: '1px solid rgba(255,255,255,0.06)',
              borderRadius: 12, padding: '16px 18px',
            }}>
            <div style={{ fontSize: 10, color: '#475569', fontWeight: 700, letterSpacing: '0.1em', marginBottom: 6 }}>
              {k ? k.label.toUpperCase() : '—'}
            </div>
            <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 22, fontWeight: 800, color: k ? k.color : '#475569' }}>
              {k ? k.value : '—'}
            </div>
          </motion.div>
        ))}
      </div>

      {/* Monthly PnL */}
      <div style={{
        background: '#121826', border: '1px solid rgba(255,255,255,0.06)',
        borderRadius: 12, padding: 20, marginBottom: 24,
      }}>
        <div style={{ fontSize: 14, fontWeight: 700, color: '#E2E8F0', marginBottom: 20 }}>
          Monthly P&L — {new Date().getUTCFullYear()}
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(12, 1fr)', gap: 8 }}>
          {months.map((m) => {
            const barH = (Math.abs(m.pnl) / maxPnl) * 80;
            return (
              <div key={m.m} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6 }}>
                <div style={{
                  fontFamily: "'JetBrains Mono', monospace", fontSize: 10, fontWeight: 700,
                  color: m.pos ? '#22C55E' : '#EF4444',
                }}>
                  {m.pos ? '+' : ''}{(m.pnl / 1000).toFixed(1)}k
                </div>
                <div style={{
                  width: '100%', height: `${barH}px`, minHeight: 4, borderRadius: 4,
                  background: m.pos ? 'rgba(34,197,94,0.4)' : 'rgba(239,68,68,0.4)',
                  border: `1px solid ${m.pos ? 'rgba(34,197,94,0.3)' : 'rgba(239,68,68,0.3)'}`,
                }} />
                <div style={{ fontSize: 10, color: '#475569', fontWeight: 600 }}>{m.m}</div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Best and worst day */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        {/* Best */}
        <div style={{ background: '#121826', border: '1px solid rgba(255,255,255,0.06)', borderRadius: 12, overflow: 'hidden' }}>
          <div style={{ padding: '14px 20px', borderBottom: '1px solid rgba(255,255,255,0.05)', display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 14, fontWeight: 700, color: '#22C55E' }}>Best Day</span>
          </div>
          <div style={{
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            padding: '11px 20px',
          }}>
            <span style={{ fontSize: 12, color: '#475569', fontFamily: "'JetBrains Mono', monospace" }}>
              {bestDay ? bestDay.date : loading ? 'Loading…' : 'No closed trades yet'}
            </span>
            {bestDay && (
              <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 13, fontWeight: 700, color: '#22C55E' }}>
                +${bestDay.pnl_usd.toFixed(0)}
              </div>
            )}
          </div>
        </div>

        {/* Worst */}
        <div style={{ background: '#121826', border: '1px solid rgba(255,255,255,0.06)', borderRadius: 12, overflow: 'hidden' }}>
          <div style={{ padding: '14px 20px', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
            <span style={{ fontSize: 14, fontWeight: 700, color: '#EF4444' }}>Worst Day</span>
          </div>
          <div style={{
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            padding: '11px 20px',
          }}>
            <span style={{ fontSize: 12, color: '#475569', fontFamily: "'JetBrains Mono', monospace" }}>
              {worstDay ? worstDay.date : loading ? 'Loading…' : 'No closed trades yet'}
            </span>
            {worstDay && (
              <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 13, fontWeight: 700, color: '#EF4444' }}>
                {worstDay.pnl_usd < 0 ? '-' : ''}${Math.abs(worstDay.pnl_usd).toFixed(0)}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Additional real metrics row */}
      {stats && (
        <div style={{
          background: '#121826', border: '1px solid rgba(255,255,255,0.06)',
          borderRadius: 12, padding: 20, marginTop: 16,
          display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16,
        }}>
          <div>
            <div style={{ fontSize: 10, color: '#475569', fontWeight: 700, letterSpacing: '0.1em', marginBottom: 6 }}>EQUITY</div>
            <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 16, fontWeight: 700, color: '#E2E8F0' }}>
              ${stats.equity_usd.toLocaleString(undefined, { maximumFractionDigits: 0 })}
            </div>
          </div>
          <div>
            <div style={{ fontSize: 10, color: '#475569', fontWeight: 700, letterSpacing: '0.1em', marginBottom: 6 }}>UNREALIZED PNL</div>
            <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 16, fontWeight: 700, color: stats.unrealized_pnl_usd >= 0 ? '#22C55E' : '#EF4444' }}>
              {stats.unrealized_pnl_usd >= 0 ? '+' : ''}${stats.unrealized_pnl_usd.toFixed(0)}
            </div>
          </div>
          <div>
            <div style={{ fontSize: 10, color: '#475569', fontWeight: 700, letterSpacing: '0.1em', marginBottom: 6 }}>SORTINO</div>
            <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 16, fontWeight: 700, color: '#E2E8F0' }}>
              {stats.sortino_ratio !== null ? stats.sortino_ratio.toFixed(2) : '—'}
            </div>
          </div>
          <div>
            <div style={{ fontSize: 10, color: '#475569', fontWeight: 700, letterSpacing: '0.1em', marginBottom: 6 }}>CALMAR</div>
            <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 16, fontWeight: 700, color: '#E2E8F0' }}>
              {stats.calmar_ratio !== null ? stats.calmar_ratio.toFixed(2) : '—'}
            </div>
          </div>
        </div>
      )}
    </motion.div>
  );
}
