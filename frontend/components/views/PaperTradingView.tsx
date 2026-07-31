'use client';

import React from 'react';
import { motion } from 'framer-motion';

const ACCOUNT = [
  { label: 'Balance',    value: '$100,000', color: '#F1F5F9' },
  { label: 'Used Margin', value: '$14,320',  color: '#F59E0B' },
  { label: 'Available',  value: '$85,680',  color: '#22C55E' },
  { label: "Today's P&L", value: '+$4,830', color: '#22C55E' },
];

const OPEN = [
  { sym: 'BTC', dir: 'LONG',  size: '0.1 BTC', entry: '$64,200', cur: '$67,428', pnl: '+$322.8', pct: '+5.0%', pos: true,  stop: '$62,000', target: '$71,000' },
  { sym: 'ETH', dir: 'LONG',  size: '0.8 ETH', entry: '$3,500',  cur: '$3,842',  pnl: '+$273.6', pct: '+9.8%', pos: true,  stop: '$3,200',  target: '$4,200' },
  { sym: 'SOL', dir: 'SHORT', size: '5 SOL',   entry: '$195',    cur: '$185',    pnl: '+$50.0',  pct: '+5.1%', pos: true,  stop: '$205',    target: '$170' },
  { sym: 'BNB', dir: 'LONG',  size: '2 BNB',   entry: '$630',    cur: '$612',    pnl: '-$36.0',  pct: '-2.9%', pos: false, stop: '$590',    target: '$680' },
  { sym: 'ADA', dir: 'LONG',  size: '200 ADA', entry: '$0.460',  cur: '$0.478',  pnl: '+$3.6',   pct: '+3.9%', pos: true,  stop: '$0.420',  target: '$0.550' },
];

const HISTORY = [
  { date: '2026-07-30 14:32', sym: 'LINK', dir: 'LONG',  size: '20',  entry: '$13.40', exit: '$14.80', pnl: '+$28.0',  pos: true },
  { date: '2026-07-30 11:15', sym: 'BTC',  dir: 'SHORT', size: '0.05', entry: '$68,200', exit: '$66,800', pnl: '+$70.0', pos: true },
  { date: '2026-07-29 16:44', sym: 'ETH',  dir: 'LONG',  size: '0.5', entry: '$3,400',  exit: '$3,580',  pnl: '+$90.0', pos: true },
  { date: '2026-07-29 09:20', sym: 'AVAX', dir: 'LONG',  size: '10',  entry: '$40.00',  exit: '$37.50',  pnl: '-$25.0', pos: false },
  { date: '2026-07-28 15:10', sym: 'SOL',  dir: 'LONG',  size: '3',   entry: '$180',    exit: '$192',    pnl: '+$36.0', pos: true },
  { date: '2026-07-28 10:05', sym: 'BNB',  dir: 'SHORT', size: '1',   entry: '$640',    exit: '$618',    pnl: '+$22.0', pos: true },
  { date: '2026-07-27 14:30', sym: 'BTC',  dir: 'LONG',  size: '0.08', entry: '$65,000', exit: '$67,200', pnl: '+$176', pos: true },
  { date: '2026-07-27 08:55', sym: 'ETH',  dir: 'SHORT', size: '0.4', entry: '$3,720',  exit: '$3,810',  pnl: '-$36.0', pos: false },
];

export default function PaperTradingView() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      style={{ padding: 24, paddingBottom: 48 }}
    >
      <div style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <h1 style={{ fontSize: 20, fontWeight: 700, color: '#E2E8F0', margin: 0 }}>Paper Trading</h1>
          <span style={{
            padding: '3px 10px', borderRadius: 6, fontSize: 10, fontWeight: 800,
            background: 'rgba(34,197,94,0.12)', color: '#22C55E',
            letterSpacing: '0.1em', border: '1px solid rgba(34,197,94,0.2)',
          }}>SIMULATION</span>
        </div>
        <p style={{ fontSize: 13, color: '#475569', marginTop: 4 }}>Risk-free trading simulation with real market data</p>
      </div>

      {/* Account summary */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14, marginBottom: 24 }}>
        {ACCOUNT.map((a, i) => (
          <motion.div key={a.label}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.05, duration: 0.2 }}
            style={{
              background: '#121826', border: '1px solid rgba(255,255,255,0.06)',
              borderRadius: 12, padding: '16px 18px',
            }}>
            <div style={{ fontSize: 10, color: '#475569', fontWeight: 700, letterSpacing: '0.1em', marginBottom: 6 }}>{a.label.toUpperCase()}</div>
            <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 22, fontWeight: 800, color: a.color }}>{a.value}</div>
          </motion.div>
        ))}
      </div>

      {/* Open trades */}
      <div style={{
        background: '#121826', border: '1px solid rgba(255,255,255,0.06)',
        borderRadius: 12, overflow: 'hidden', marginBottom: 20,
      }}>
        <div style={{ padding: '14px 20px', borderBottom: '1px solid rgba(255,255,255,0.05)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontSize: 14, fontWeight: 700, color: '#E2E8F0' }}>Open Paper Trades</span>
          <button style={{
            padding: '6px 14px', borderRadius: 8, fontSize: 12, fontWeight: 600, cursor: 'pointer',
            background: 'rgba(79,124,255,0.1)', border: '1px solid rgba(79,124,255,0.25)', color: '#4F7CFF',
          }}>+ New Trade</button>
        </div>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ background: 'rgba(255,255,255,0.02)' }}>
              {['Symbol', 'Dir', 'Size', 'Entry', 'Current', 'Stop', 'Target', 'P&L', '%'].map(h => (
                <th key={h} style={{ padding: '9px 14px', textAlign: 'left', fontSize: 10, fontWeight: 700, color: '#475569', letterSpacing: '0.1em', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {OPEN.map((t, i) => (
              <tr key={i} style={{ background: i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.015)' }}>
                <td style={{ padding: '10px 14px', fontWeight: 700, color: '#E2E8F0', fontSize: 13 }}>{t.sym}</td>
                <td style={{ padding: '10px 14px' }}>
                  <span style={{ padding: '2px 7px', borderRadius: 5, fontSize: 10, fontWeight: 700, background: t.dir === 'LONG' ? 'rgba(34,197,94,0.12)' : 'rgba(239,68,68,0.12)', color: t.dir === 'LONG' ? '#22C55E' : '#EF4444' }}>{t.dir}</span>
                </td>
                <td style={{ padding: '10px 14px', fontSize: 11, color: '#94A3B8', fontFamily: "'JetBrains Mono', monospace" }}>{t.size}</td>
                <td style={{ padding: '10px 14px', fontSize: 11, color: '#94A3B8', fontFamily: "'JetBrains Mono', monospace" }}>{t.entry}</td>
                <td style={{ padding: '10px 14px', fontSize: 11, color: '#F1F5F9', fontFamily: "'JetBrains Mono', monospace" }}>{t.cur}</td>
                <td style={{ padding: '10px 14px', fontSize: 11, color: '#EF4444', fontFamily: "'JetBrains Mono', monospace" }}>{t.stop}</td>
                <td style={{ padding: '10px 14px', fontSize: 11, color: '#22C55E', fontFamily: "'JetBrains Mono', monospace" }}>{t.target}</td>
                <td style={{ padding: '10px 14px', fontSize: 11, fontFamily: "'JetBrains Mono', monospace", fontWeight: 700, color: t.pos ? '#22C55E' : '#EF4444' }}>{t.pnl}</td>
                <td style={{ padding: '10px 14px', fontSize: 11, fontFamily: "'JetBrains Mono', monospace", fontWeight: 700, color: t.pos ? '#22C55E' : '#EF4444' }}>{t.pct}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Trade history */}
      <div style={{
        background: '#121826', border: '1px solid rgba(255,255,255,0.06)',
        borderRadius: 12, overflow: 'hidden',
      }}>
        <div style={{ padding: '14px 20px', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
          <span style={{ fontSize: 14, fontWeight: 700, color: '#E2E8F0' }}>Paper Trade History</span>
        </div>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ background: 'rgba(255,255,255,0.02)' }}>
              {['Timestamp', 'Symbol', 'Dir', 'Size', 'Entry', 'Exit', 'P&L'].map(h => (
                <th key={h} style={{ padding: '9px 14px', textAlign: 'left', fontSize: 10, fontWeight: 700, color: '#475569', letterSpacing: '0.1em', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {HISTORY.map((t, i) => (
              <tr key={i} style={{ background: i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.015)' }}>
                <td style={{ padding: '10px 14px', fontSize: 11, color: '#475569', fontFamily: "'JetBrains Mono', monospace" }}>{t.date}</td>
                <td style={{ padding: '10px 14px', fontWeight: 700, color: '#E2E8F0', fontSize: 13 }}>{t.sym}</td>
                <td style={{ padding: '10px 14px' }}>
                  <span style={{ padding: '2px 7px', borderRadius: 5, fontSize: 10, fontWeight: 700, background: t.dir === 'LONG' ? 'rgba(34,197,94,0.12)' : 'rgba(239,68,68,0.12)', color: t.dir === 'LONG' ? '#22C55E' : '#EF4444' }}>{t.dir}</span>
                </td>
                <td style={{ padding: '10px 14px', fontSize: 11, color: '#94A3B8', fontFamily: "'JetBrains Mono', monospace" }}>{t.size}</td>
                <td style={{ padding: '10px 14px', fontSize: 11, color: '#94A3B8', fontFamily: "'JetBrains Mono', monospace" }}>{t.entry}</td>
                <td style={{ padding: '10px 14px', fontSize: 11, color: '#94A3B8', fontFamily: "'JetBrains Mono', monospace" }}>{t.exit}</td>
                <td style={{ padding: '10px 14px', fontSize: 12, fontFamily: "'JetBrains Mono', monospace", fontWeight: 700, color: t.pos ? '#22C55E' : '#EF4444' }}>{t.pnl}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </motion.div>
  );
}
