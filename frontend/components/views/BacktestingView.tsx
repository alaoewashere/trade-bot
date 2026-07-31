'use client';

import React, { useState } from 'react';
import { motion } from 'framer-motion';

const SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT'];
const STRATEGIES = ['Momentum Breakout', 'Mean Reversion', 'Trend Following', 'Volatility Arbitrage'];

const KPIS = [
  { label: 'Total Return', value: '+42.8%',  color: '#22C55E' },
  { label: 'Win Rate',     value: '71.4%',   color: '#22C55E' },
  { label: 'Max Drawdown', value: '-12.4%',  color: '#EF4444' },
  { label: 'Total Trades', value: '384',     color: '#4F7CFF' },
];

const TRADES = Array.from({ length: 10 }, (_, i) => {
  const pos = Math.random() > 0.3;
  const pnl = pos ? `+$${(Math.random() * 500 + 50).toFixed(0)}` : `-$${(Math.random() * 300 + 30).toFixed(0)}`;
  const syms = ['BTC', 'ETH', 'SOL', 'BNB'];
  const sym = syms[i % syms.length];
  return {
    id: `#${1000 + i}`,
    date: `2026-0${Math.floor(i / 3) + 1}-${10 + i}`,
    sym,
    dir: Math.random() > 0.5 ? 'LONG' : 'SHORT',
    entry: `$${(60000 + Math.random() * 8000).toFixed(0)}`,
    exit:  `$${(60000 + Math.random() * 8000).toFixed(0)}`,
    pnl,
    pos,
  };
});

function StyledSelect({ options, value, onChange }: { options: string[]; value: string; onChange: (v: string) => void }) {
  return (
    <select
      value={value}
      onChange={e => onChange(e.target.value)}
      style={{
        background: '#1a2235', border: '1px solid rgba(255,255,255,0.1)',
        borderRadius: 8, padding: '8px 12px', fontSize: 13, color: '#E2E8F0',
        cursor: 'pointer', outline: 'none', minWidth: 160,
      }}
    >
      {options.map(o => <option key={o} value={o}>{o}</option>)}
    </select>
  );
}

function StyledInput({ type = 'text', value, label }: { type?: string; value: string; label: string }) {
  return (
    <div>
      <div style={{ fontSize: 10, color: '#475569', fontWeight: 700, marginBottom: 6, letterSpacing: '0.1em' }}>{label}</div>
      <input
        type={type}
        defaultValue={value}
        style={{
          background: '#1a2235', border: '1px solid rgba(255,255,255,0.1)',
          borderRadius: 8, padding: '8px 12px', fontSize: 13, color: '#E2E8F0',
          outline: 'none', width: '100%',
        }}
      />
    </div>
  );
}

export default function BacktestingView() {
  const [symbol, setSymbol] = useState(SYMBOLS[0]);
  const [strategy, setStrategy] = useState(STRATEGIES[0]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      style={{ padding: 24, paddingBottom: 48 }}
    >
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 20, fontWeight: 700, color: '#E2E8F0', margin: 0 }}>Strategy Backtesting</h1>
        <p style={{ fontSize: 13, color: '#475569', marginTop: 4 }}>Test strategies against historical data with AI optimization</p>
      </div>

      {/* Config panel */}
      <div style={{
        background: '#121826', border: '1px solid rgba(255,255,255,0.06)',
        borderRadius: 12, padding: 20, marginBottom: 20,
      }}>
        <div style={{ fontSize: 14, fontWeight: 700, color: '#E2E8F0', marginBottom: 16 }}>Configuration</div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 16 }}>
          <div>
            <div style={{ fontSize: 10, color: '#475569', fontWeight: 700, marginBottom: 6, letterSpacing: '0.1em' }}>SYMBOL</div>
            <StyledSelect options={SYMBOLS} value={symbol} onChange={setSymbol} />
          </div>
          <div>
            <div style={{ fontSize: 10, color: '#475569', fontWeight: 700, marginBottom: 6, letterSpacing: '0.1em' }}>STRATEGY</div>
            <StyledSelect options={STRATEGIES} value={strategy} onChange={setStrategy} />
          </div>
          <StyledInput label="START DATE" value="2026-01-01" type="date" />
          <StyledInput label="END DATE" value="2026-07-31" type="date" />
        </div>
        <button style={{
          padding: '10px 24px', borderRadius: 8, fontSize: 13, fontWeight: 700, cursor: 'pointer',
          background: 'linear-gradient(135deg,#4F7CFF,#818CF8)',
          border: 'none', color: '#fff',
          boxShadow: '0 4px 16px rgba(79,124,255,0.4)',
        }}>Run Backtest</button>
      </div>

      {/* Results KPIs */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14, marginBottom: 20 }}>
        {KPIS.map((k, i) => (
          <motion.div key={k.label}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.05, duration: 0.2 }}
            style={{
              background: '#121826', border: '1px solid rgba(255,255,255,0.06)',
              borderRadius: 12, padding: '16px 18px',
            }}>
            <div style={{ fontSize: 10, color: '#475569', fontWeight: 700, letterSpacing: '0.1em', marginBottom: 6 }}>{k.label.toUpperCase()}</div>
            <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 24, fontWeight: 800, color: k.color }}>{k.value}</div>
          </motion.div>
        ))}
      </div>

      {/* Trade list */}
      <div style={{
        background: '#121826', border: '1px solid rgba(255,255,255,0.06)',
        borderRadius: 12, overflow: 'hidden',
      }}>
        <div style={{ padding: '14px 20px', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
          <span style={{ fontSize: 14, fontWeight: 700, color: '#E2E8F0' }}>Backtest Trades</span>
        </div>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ background: 'rgba(255,255,255,0.02)' }}>
              {['#', 'Date', 'Symbol', 'Dir', 'Entry', 'Exit', 'P&L'].map(h => (
                <th key={h} style={{ padding: '9px 16px', textAlign: 'left', fontSize: 10, fontWeight: 700, color: '#475569', letterSpacing: '0.1em', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {TRADES.map((t, i) => (
              <tr key={i} style={{ background: i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.015)' }}>
                <td style={{ padding: '10px 16px', fontSize: 11, color: '#475569', fontFamily: "'JetBrains Mono', monospace" }}>{t.id}</td>
                <td style={{ padding: '10px 16px', fontSize: 11, color: '#475569', fontFamily: "'JetBrains Mono', monospace" }}>{t.date}</td>
                <td style={{ padding: '10px 16px', fontWeight: 700, color: '#E2E8F0', fontSize: 13 }}>{t.sym}</td>
                <td style={{ padding: '10px 16px' }}>
                  <span style={{ padding: '2px 7px', borderRadius: 5, fontSize: 10, fontWeight: 700, background: t.dir === 'LONG' ? 'rgba(34,197,94,0.12)' : 'rgba(239,68,68,0.12)', color: t.dir === 'LONG' ? '#22C55E' : '#EF4444' }}>{t.dir}</span>
                </td>
                <td style={{ padding: '10px 16px', fontSize: 11, color: '#94A3B8', fontFamily: "'JetBrains Mono', monospace" }}>{t.entry}</td>
                <td style={{ padding: '10px 16px', fontSize: 11, color: '#94A3B8', fontFamily: "'JetBrains Mono', monospace" }}>{t.exit}</td>
                <td style={{ padding: '10px 16px', fontSize: 12, fontFamily: "'JetBrains Mono', monospace", fontWeight: 700, color: t.pos ? '#22C55E' : '#EF4444' }}>{t.pnl}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </motion.div>
  );
}
