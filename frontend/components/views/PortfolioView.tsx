'use client';

import React from 'react';
import { motion } from 'framer-motion';
import { api, PortfolioSnapshot, AllocationBreakdown, OpenPosition, TradeRecord } from '@/lib/api';

const ALLOC_COLORS = ['#F59E0B', '#818CF8', '#22C55E', '#EF4444', '#4F7CFF', '#EC4899', '#475569'];

function fmtUsd(n: number | null | undefined): string {
  if (n === null || n === undefined || Number.isNaN(n)) return '$0';
  const sign = n >= 0 ? '+' : '-';
  return `${sign}$${Math.abs(n).toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}

function fmtPlain(n: number | null | undefined): string {
  if (n === null || n === undefined || Number.isNaN(n)) return '$0';
  return `$${n.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}

function fmtPct(n: number | null | undefined): string {
  if (n === null || n === undefined || Number.isNaN(n)) return '0.0%';
  return `${n >= 0 ? '+' : ''}${n.toFixed(1)}%`;
}

function DonutChart({ alloc }: { alloc: { label: string; pct: number; color: string }[] }) {
  let cumulative = 0;
  const total = alloc.reduce((s, a) => s + a.pct, 0) || 1;
  const r = 60;
  const circumference = 2 * Math.PI * r;
  const cx = 80, cy = 80;

  const arcs = alloc.map(a => {
    const strokeDash = (a.pct / total) * circumference;
    const startOffset = (cumulative / total) * circumference;
    cumulative += a.pct;
    return { ...a, startOffset, strokeDash };
  });

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 24 }}>
      <svg width={160} height={160} viewBox="0 0 160 160">
        <circle cx={cx} cy={cy} r={r} fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth={20} />
        {arcs.map((a, i) => (
          <circle key={i} cx={cx} cy={cy} r={r} fill="none"
            stroke={a.color} strokeWidth={20}
            strokeDasharray={`${a.strokeDash} ${circumference}`}
            strokeDashoffset={-(a.startOffset)}
            style={{ transformOrigin: `${cx}px ${cy}px`, transform: 'rotate(-90deg)' }}
          />
        ))}
        <text x={cx} y={cy - 5} textAnchor="middle" fill="#E2E8F0" fontSize={13} fontWeight="700">Portfolio</text>
        <text x={cx} y={cy + 12} textAnchor="middle" fill="#475569" fontSize={10}>Allocation</text>
      </svg>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {alloc.map(a => (
          <div key={a.label} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{ width: 10, height: 10, borderRadius: 3, background: a.color, flexShrink: 0 }} />
            <span style={{ fontSize: 12, color: '#94A3B8', minWidth: 40 }}>{a.label}</span>
            <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 12, fontWeight: 700, color: '#E2E8F0' }}>{a.pct.toFixed(1)}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function PortfolioView() {
  const [snapshot, setSnapshot] = React.useState<PortfolioSnapshot | null>(null);
  const [allocation, setAllocation] = React.useState<AllocationBreakdown | null>(null);
  const [openPositions, setOpenPositions] = React.useState<OpenPosition[]>([]);
  const [recentTrades, setRecentTrades] = React.useState<TradeRecord[]>([]);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [snap, alloc, positions, trades] = await Promise.all([
          api.portfolio.getSnapshot(),
          api.portfolio.getAllocation(),
          api.trades.listOpen(),
          api.trades.list({ status: 'closed', limit: 8 }),
        ]);
        if (cancelled) return;
        setSnapshot(snap);
        setAllocation(alloc);
        setOpenPositions(positions);
        setRecentTrades(trades);
        setError(null);
      } catch (e) {
        if (!cancelled) setError('Backend unavailable — showing empty state.');
      }
    }
    load();
    const interval = setInterval(load, 15000);
    return () => { cancelled = true; clearInterval(interval); };
  }, []);

  const stats = [
    { label: 'Total Value', value: fmtPlain(snapshot?.equity_usd), sub: `${fmtUsd(snapshot?.daily_pnl_usd)} today`, color: '#4F7CFF' },
    { label: "Today's P&L", value: fmtUsd(snapshot?.daily_pnl_usd), sub: fmtPct(snapshot ? (snapshot.daily_pnl_usd / (snapshot.equity_usd || 1)) * 100 : 0), color: (snapshot?.daily_pnl_usd ?? 0) >= 0 ? '#22C55E' : '#EF4444' },
    { label: 'Week P&L', value: fmtUsd(snapshot?.weekly_pnl_usd), sub: `${fmtPct(snapshot ? (snapshot.weekly_pnl_usd / (snapshot.equity_usd || 1)) * 100 : 0)} this week`, color: (snapshot?.weekly_pnl_usd ?? 0) >= 0 ? '#22C55E' : '#EF4444' },
    { label: 'Total Return', value: fmtPct(snapshot?.total_pnl_pct), sub: 'Since inception', color: (snapshot?.total_pnl_pct ?? 0) >= 0 ? '#22C55E' : '#EF4444' },
  ];

  const allocEntries = allocation
    ? Object.entries(allocation.by_symbol).map(([label, val], i) => {
        const total = Object.values(allocation.by_symbol).reduce((s, v) => s + v, 0) || 1;
        return { label, pct: (val / total) * 100, color: ALLOC_COLORS[i % ALLOC_COLORS.length] };
      })
    : [];

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      style={{ padding: 24, paddingBottom: 48 }}
    >
      <div style={{ marginBottom: 24, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end' }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 700, color: '#E2E8F0', margin: 0 }}>Portfolio Overview</h1>
          <p style={{ fontSize: 13, color: '#475569', marginTop: 4 }}>Real-time portfolio tracking and position management</p>
        </div>
        {allocation && (
          <div style={{ fontSize: 11, color: '#475569' }}>
            Diversification score: <span style={{ color: '#E2E8F0', fontWeight: 700 }}>{allocation.diversification_score.toFixed(2)}</span>
          </div>
        )}
        {error && <div style={{ fontSize: 11, color: '#F59E0B' }}>{error}</div>}
      </div>

      {/* Stats */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 24 }}>
        {stats.map((s, i) => (
          <motion.div key={s.label}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.06, duration: 0.2 }}
            style={{
              background: '#121826', border: '1px solid rgba(255,255,255,0.06)',
              borderRadius: 12, padding: '18px 20px',
            }}>
            <div style={{ fontSize: 11, color: '#475569', fontWeight: 700, letterSpacing: '0.1em', marginBottom: 6 }}>{s.label.toUpperCase()}</div>
            <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 22, fontWeight: 800, color: s.color }}>{s.value}</div>
            <div style={{ fontSize: 11, color: '#475569', marginTop: 4 }}>{s.sub}</div>
          </motion.div>
        ))}
      </div>

      {/* Two columns */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 320px', gap: 16, marginBottom: 24 }}>
        {/* Positions table */}
        <div style={{ background: '#121826', border: '1px solid rgba(255,255,255,0.06)', borderRadius: 12, overflow: 'hidden' }}>
          <div style={{ padding: '14px 20px', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
            <span style={{ fontSize: 14, fontWeight: 700, color: '#E2E8F0' }}>Open Positions</span>
          </div>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: 'rgba(255,255,255,0.02)' }}>
                {['Symbol', 'Dir', 'Size', 'Entry', 'Current', 'P&L', '%'].map(h => (
                  <th key={h} style={{ padding: '9px 14px', textAlign: 'left', fontSize: 10, fontWeight: 700, color: '#475569', letterSpacing: '0.1em', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {openPositions.length === 0 && (
                <tr><td colSpan={7} style={{ padding: '20px 14px', fontSize: 12, color: '#475569', textAlign: 'center' }}>No open positions</td></tr>
              )}
              {openPositions.map((p, i) => {
                const pos = (p.unrealised_pnl_usd ?? 0) >= 0;
                return (
                  <tr key={p.trade_id} style={{ background: i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.015)' }}>
                    <td style={{ padding: '10px 14px', fontWeight: 700, color: '#E2E8F0', fontSize: 13 }}>{p.symbol}</td>
                    <td style={{ padding: '10px 14px' }}>
                      <span style={{ padding: '2px 7px', borderRadius: 5, fontSize: 10, fontWeight: 700, background: p.direction === 'LONG' ? 'rgba(34,197,94,0.12)' : 'rgba(239,68,68,0.12)', color: p.direction === 'LONG' ? '#22C55E' : '#EF4444' }}>{p.direction}</span>
                    </td>
                    <td style={{ padding: '10px 14px', fontSize: 11, color: '#94A3B8', fontFamily: "'JetBrains Mono', monospace" }}>{p.quantity}</td>
                    <td style={{ padding: '10px 14px', fontSize: 11, color: '#94A3B8', fontFamily: "'JetBrains Mono', monospace" }}>{fmtPlain(p.entry_price)}</td>
                    <td style={{ padding: '10px 14px', fontSize: 11, color: '#F1F5F9', fontFamily: "'JetBrains Mono', monospace" }}>{fmtPlain(p.current_price)}</td>
                    <td style={{ padding: '10px 14px', fontSize: 11, fontFamily: "'JetBrains Mono', monospace", fontWeight: 700, color: pos ? '#22C55E' : '#EF4444' }}>{fmtUsd(p.unrealised_pnl_usd)}</td>
                    <td style={{ padding: '10px 14px', fontSize: 11, fontFamily: "'JetBrains Mono', monospace", fontWeight: 700, color: pos ? '#22C55E' : '#EF4444' }}>{fmtPct(p.unrealised_pnl_pct)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* Donut */}
        <div style={{ background: '#121826', border: '1px solid rgba(255,255,255,0.06)', borderRadius: 12, padding: 20 }}>
          <div style={{ fontSize: 14, fontWeight: 700, color: '#E2E8F0', marginBottom: 20 }}>Allocation</div>
          {allocEntries.length > 0 ? <DonutChart alloc={allocEntries} /> : <div style={{ fontSize: 12, color: '#475569' }}>No allocation data</div>}
        </div>
      </div>

      {/* Recent trades */}
      <div style={{ background: '#121826', border: '1px solid rgba(255,255,255,0.06)', borderRadius: 12, overflow: 'hidden' }}>
        <div style={{ padding: '14px 20px', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
          <span style={{ fontSize: 14, fontWeight: 700, color: '#E2E8F0' }}>Recent Trades</span>
        </div>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ background: 'rgba(255,255,255,0.02)' }}>
              {['Date', 'Symbol', 'Direction', 'Size', 'Entry', 'Exit', 'P&L'].map(h => (
                <th key={h} style={{ padding: '9px 14px', textAlign: 'left', fontSize: 10, fontWeight: 700, color: '#475569', letterSpacing: '0.1em', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {recentTrades.length === 0 && (
              <tr><td colSpan={7} style={{ padding: '20px 14px', fontSize: 12, color: '#475569', textAlign: 'center' }}>No closed trades yet</td></tr>
            )}
            {recentTrades.map((t, i) => {
              const pos = (t.pnl_usd ?? 0) >= 0;
              return (
                <tr key={t.trade_id} style={{ background: i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.015)' }}>
                  <td style={{ padding: '10px 14px', fontSize: 11, color: '#475569', fontFamily: "'JetBrains Mono', monospace" }}>{t.closed_at ? new Date(t.closed_at).toLocaleDateString() : '—'}</td>
                  <td style={{ padding: '10px 14px', fontWeight: 700, color: '#E2E8F0', fontSize: 13 }}>{t.symbol}</td>
                  <td style={{ padding: '10px 14px' }}>
                    <span style={{ padding: '2px 7px', borderRadius: 5, fontSize: 10, fontWeight: 700, background: t.direction === 'LONG' ? 'rgba(34,197,94,0.12)' : 'rgba(239,68,68,0.12)', color: t.direction === 'LONG' ? '#22C55E' : '#EF4444' }}>{t.direction}</span>
                  </td>
                  <td style={{ padding: '10px 14px', fontSize: 11, color: '#94A3B8', fontFamily: "'JetBrains Mono', monospace" }}>{t.quantity}</td>
                  <td style={{ padding: '10px 14px', fontSize: 11, color: '#94A3B8', fontFamily: "'JetBrains Mono', monospace" }}>{fmtPlain(t.entry_price)}</td>
                  <td style={{ padding: '10px 14px', fontSize: 11, color: '#94A3B8', fontFamily: "'JetBrains Mono', monospace" }}>{fmtPlain(t.filled_price)}</td>
                  <td style={{ padding: '10px 14px', fontSize: 11, fontFamily: "'JetBrains Mono', monospace", fontWeight: 700, color: pos ? '#22C55E' : '#EF4444' }}>{fmtUsd(t.pnl_usd)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </motion.div>
  );
}
