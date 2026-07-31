'use client';

import React from 'react';
import { motion } from 'framer-motion';

const KPIS = [
  { label: 'Win Rate',      value: '67%',    color: '#22C55E' },
  { label: 'Profit Factor', value: '2.1',    color: '#4F7CFF' },
  { label: 'Sharpe Ratio',  value: '1.8',    color: '#4F7CFF' },
  { label: 'Max Drawdown',  value: '-8.2%',  color: '#EF4444' },
  { label: 'Total Trades',  value: '1,247',  color: '#F1F5F9' },
  { label: 'Avg Win',       value: '+$340',  color: '#22C55E' },
  { label: 'Avg Loss',      value: '-$180',  color: '#EF4444' },
  { label: 'Expectancy',    value: '+$164',  color: '#22C55E' },
];

const MONTHS = [
  { m: 'Jan', pnl: 3420, pos: true },
  { m: 'Feb', pnl: -1230, pos: false },
  { m: 'Mar', pnl: 5870, pos: true },
  { m: 'Apr', pnl: 2140, pos: true },
  { m: 'May', pnl: -890,  pos: false },
  { m: 'Jun', pnl: 7830, pos: true },
  { m: 'Jul', pnl: 4210, pos: true },
  { m: 'Aug', pnl: 1560, pos: true },
  { m: 'Sep', pnl: -2400, pos: false },
  { m: 'Oct', pnl: 6700, pos: true },
  { m: 'Nov', pnl: 3100, pos: true },
  { m: 'Dec', pnl: 8420, pos: true },
];

const BEST = [
  { id: '#1247', sym: 'BTC', pnl: '+$2,840', date: '2026-06-15' },
  { id: '#1189', sym: 'ETH', pnl: '+$1,920', date: '2026-05-08' },
  { id: '#1102', sym: 'SOL', pnl: '+$1,640', date: '2026-04-22' },
  { id: '#998',  sym: 'BTC', pnl: '+$1,380', date: '2026-03-11' },
  { id: '#876',  sym: 'BNB', pnl: '+$1,100', date: '2026-02-19' },
];

const WORST = [
  { id: '#1204', sym: 'AVAX', pnl: '-$1,240', date: '2026-07-02' },
  { id: '#1155', sym: 'ETH',  pnl: '-$980',   date: '2026-06-08' },
  { id: '#1072', sym: 'BTC',  pnl: '-$820',   date: '2026-05-14' },
  { id: '#944',  sym: 'SOL',  pnl: '-$640',   date: '2026-04-01' },
  { id: '#812',  sym: 'LINK', pnl: '-$510',   date: '2026-02-28' },
];

const maxPnl = Math.max(...MONTHS.map(m => Math.abs(m.pnl)));

export default function PerformanceView() {
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
      </div>

      {/* KPIs */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14, marginBottom: 24 }}>
        {KPIS.map((k, i) => (
          <motion.div key={k.label}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.04, duration: 0.2 }}
            style={{
              background: '#121826', border: '1px solid rgba(255,255,255,0.06)',
              borderRadius: 12, padding: '16px 18px',
            }}>
            <div style={{ fontSize: 10, color: '#475569', fontWeight: 700, letterSpacing: '0.1em', marginBottom: 6 }}>{k.label.toUpperCase()}</div>
            <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 22, fontWeight: 800, color: k.color }}>{k.value}</div>
          </motion.div>
        ))}
      </div>

      {/* Monthly PnL */}
      <div style={{
        background: '#121826', border: '1px solid rgba(255,255,255,0.06)',
        borderRadius: 12, padding: 20, marginBottom: 24,
      }}>
        <div style={{ fontSize: 14, fontWeight: 700, color: '#E2E8F0', marginBottom: 20 }}>Monthly P&L — 2026</div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(12, 1fr)', gap: 8 }}>
          {MONTHS.map((m) => {
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

      {/* Best and worst */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        {/* Best */}
        <div style={{ background: '#121826', border: '1px solid rgba(255,255,255,0.06)', borderRadius: 12, overflow: 'hidden' }}>
          <div style={{ padding: '14px 20px', borderBottom: '1px solid rgba(255,255,255,0.05)', display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 14, fontWeight: 700, color: '#22C55E' }}>Best Trades</span>
          </div>
          {BEST.map((t, i) => (
            <div key={i} style={{
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              padding: '11px 20px', borderBottom: i < BEST.length - 1 ? '1px solid rgba(255,255,255,0.03)' : 'none',
            }}>
              <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
                <span style={{ fontSize: 11, color: '#475569', fontFamily: "'JetBrains Mono', monospace" }}>{t.id}</span>
                <span style={{ fontWeight: 700, color: '#E2E8F0', fontSize: 13 }}>{t.sym}</span>
              </div>
              <div style={{ textAlign: 'right' }}>
                <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 13, fontWeight: 700, color: '#22C55E' }}>{t.pnl}</div>
                <div style={{ fontSize: 10, color: '#334155', marginTop: 2 }}>{t.date}</div>
              </div>
            </div>
          ))}
        </div>

        {/* Worst */}
        <div style={{ background: '#121826', border: '1px solid rgba(255,255,255,0.06)', borderRadius: 12, overflow: 'hidden' }}>
          <div style={{ padding: '14px 20px', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
            <span style={{ fontSize: 14, fontWeight: 700, color: '#EF4444' }}>Worst Trades</span>
          </div>
          {WORST.map((t, i) => (
            <div key={i} style={{
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              padding: '11px 20px', borderBottom: i < WORST.length - 1 ? '1px solid rgba(255,255,255,0.03)' : 'none',
            }}>
              <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
                <span style={{ fontSize: 11, color: '#475569', fontFamily: "'JetBrains Mono', monospace" }}>{t.id}</span>
                <span style={{ fontWeight: 700, color: '#E2E8F0', fontSize: 13 }}>{t.sym}</span>
              </div>
              <div style={{ textAlign: 'right' }}>
                <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 13, fontWeight: 700, color: '#EF4444' }}>{t.pnl}</div>
                <div style={{ fontSize: 10, color: '#334155', marginTop: 2 }}>{t.date}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </motion.div>
  );
}
