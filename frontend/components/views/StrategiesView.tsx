'use client';

import React, { useState } from 'react';
import { motion } from 'framer-motion';

const STRATEGIES = [
  {
    id: 1,
    name: 'Momentum Breakout',
    desc: 'Identifies breakout patterns above resistance with volume confirmation and trend continuation.',
    status: 'ACTIVE',
    winRate: '64%',
    pnl: '+$12,400',
    trades: 142,
    drawdown: '-5.2%',
    enabled: true,
  },
  {
    id: 2,
    name: 'Mean Reversion',
    desc: 'Fades extreme moves using Bollinger Bands and RSI divergence signals on 1h timeframe.',
    status: 'PAUSED',
    winRate: '58%',
    pnl: '+$6,200',
    trades: 89,
    drawdown: '-7.8%',
    enabled: false,
  },
  {
    id: 3,
    name: 'Trend Following',
    desc: 'Multi-timeframe trend alignment using EMA crossovers with ATR-based position sizing.',
    status: 'ACTIVE',
    winRate: '71%',
    pnl: '+$28,900',
    trades: 314,
    drawdown: '-3.4%',
    enabled: true,
  },
  {
    id: 4,
    name: 'Volatility Arbitrage',
    desc: 'Exploits implied vs realized volatility spreads across correlated crypto pairs.',
    status: 'BACKTESTING',
    winRate: 'N/A',
    pnl: 'N/A',
    trades: 0,
    drawdown: 'N/A',
    enabled: false,
  },
];

const STATUS_STYLES: Record<string, { bg: string; text: string }> = {
  ACTIVE:      { bg: 'rgba(34,197,94,0.12)',  text: '#22C55E' },
  PAUSED:      { bg: 'rgba(245,158,11,0.12)', text: '#F59E0B' },
  BACKTESTING: { bg: 'rgba(79,124,255,0.12)', text: '#4F7CFF' },
};

function Toggle({ on }: { on: boolean }) {
  return (
    <div style={{
      width: 44, height: 24, borderRadius: 12,
      background: on ? 'rgba(34,197,94,0.3)' : 'rgba(255,255,255,0.08)',
      border: `1px solid ${on ? 'rgba(34,197,94,0.5)' : 'rgba(255,255,255,0.1)'}`,
      position: 'relative', cursor: 'pointer', transition: 'all 0.2s',
      flexShrink: 0,
    }}>
      <div style={{
        position: 'absolute', top: 3, left: on ? 21 : 3,
        width: 16, height: 16, borderRadius: '50%',
        background: on ? '#22C55E' : '#475569',
        transition: 'all 0.2s', boxShadow: on ? '0 0 8px rgba(34,197,94,0.6)' : 'none',
      }} />
    </div>
  );
}

export default function StrategiesView() {
  const [toggles, setToggles] = useState<Record<number, boolean>>(
    Object.fromEntries(STRATEGIES.map(s => [s.id, s.enabled]))
  );

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      style={{ padding: 24, paddingBottom: 48 }}
    >
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 20, fontWeight: 700, color: '#E2E8F0', margin: 0 }}>Trading Strategies</h1>
        <p style={{ fontSize: 13, color: '#475569', marginTop: 4 }}>Manage and monitor algorithmic trading strategies</p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        {STRATEGIES.map((s, i) => {
          const sc = STATUS_STYLES[s.status];
          return (
            <motion.div key={s.id}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.07, duration: 0.2 }}
              style={{
                background: '#121826',
                border: '1px solid rgba(255,255,255,0.06)',
                borderRadius: 12, padding: 20,
              }}
            >
              {/* Header */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
                <div>
                  <div style={{ fontSize: 15, fontWeight: 700, color: '#E2E8F0', marginBottom: 4 }}>{s.name}</div>
                  <span style={{
                    padding: '2px 9px', borderRadius: 6, fontSize: 10, fontWeight: 700,
                    background: sc.bg, color: sc.text,
                  }}>{s.status}</span>
                </div>
                <div onClick={() => setToggles(prev => ({ ...prev, [s.id]: !prev[s.id] }))}>
                  <Toggle on={toggles[s.id]} />
                </div>
              </div>

              {/* Description */}
              <p style={{ fontSize: 12.5, color: '#64748B', lineHeight: 1.55, margin: '0 0 16px' }}>{s.desc}</p>

              {/* Metrics */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8 }}>
                {[
                  { label: 'Win Rate', value: s.winRate, color: s.winRate !== 'N/A' ? '#22C55E' : '#475569' },
                  { label: 'P&L',      value: s.pnl,     color: s.pnl.startsWith('+') ? '#22C55E' : s.pnl === 'N/A' ? '#475569' : '#EF4444' },
                  { label: 'Trades',   value: String(s.trades), color: '#4F7CFF' },
                  { label: 'Drawdown', value: s.drawdown, color: s.drawdown !== 'N/A' ? '#EF4444' : '#475569' },
                ].map(m => (
                  <div key={m.label} style={{
                    background: 'rgba(255,255,255,0.03)', borderRadius: 8, padding: '8px 10px',
                    border: '1px solid rgba(255,255,255,0.04)',
                  }}>
                    <div style={{ fontSize: 9, color: '#475569', fontWeight: 700, letterSpacing: '0.1em', marginBottom: 4 }}>{m.label}</div>
                    <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 13, fontWeight: 700, color: m.color }}>{m.value}</div>
                  </div>
                ))}
              </div>
            </motion.div>
          );
        })}
      </div>
    </motion.div>
  );
}
