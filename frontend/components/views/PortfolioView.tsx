'use client';

import React from 'react';
import { motion } from 'framer-motion';

const STATS = [
  { label: 'Total Value',   value: '$124,830', sub: '+$2,340 today',   color: '#4F7CFF' },
  { label: "Today's P&L",  value: '+$2,340',  sub: '+1.9% return',    color: '#22C55E' },
  { label: 'Week P&L',     value: '+$8,420',  sub: '+7.2% this week', color: '#22C55E' },
  { label: 'Total Return', value: '+24.8%',   sub: 'Since inception',  color: '#22C55E' },
];

const POSITIONS = [
  { sym: 'BTC', dir: 'LONG',  size: '0.15 BTC', entry: '$65,200', cur: '$67,428', pnl: '+$334',  pct: '+3.4%', pos: true },
  { sym: 'ETH', dir: 'LONG',  size: '1.20 ETH', entry: '$3,600',  cur: '$3,842',  pnl: '+$290',  pct: '+6.7%', pos: true },
  { sym: 'SOL', dir: 'SHORT', size: '5.00 SOL', entry: '$192',    cur: '$185',    pnl: '+$35',   pct: '+3.6%', pos: true },
  { sym: 'BNB', dir: 'LONG',  size: '2.00 BNB', entry: '$620',    cur: '$612',    pnl: '-$16',   pct: '-1.3%', pos: false },
  { sym: 'ADA', dir: 'LONG',  size: '200 ADA',  entry: '$0.460',  cur: '$0.478',  pnl: '+$3.60', pct: '+3.9%', pos: true },
];

const ALLOC = [
  { label: 'BTC',  pct: 45, color: '#F59E0B' },
  { label: 'ETH',  pct: 30, color: '#818CF8' },
  { label: 'SOL',  pct: 15, color: '#22C55E' },
  { label: 'Cash', pct: 10, color: '#475569' },
];

const TRADES = [
  { date: '2026-07-30', sym: 'BTC', dir: 'LONG',  size: '0.1',  entry: '$64,200', exit: '$67,100', pnl: '+$290', pos: true },
  { date: '2026-07-29', sym: 'ETH', dir: 'LONG',  size: '0.8',  entry: '$3,500',  exit: '$3,720',  pnl: '+$176', pos: true },
  { date: '2026-07-28', sym: 'SOL', dir: 'SHORT', size: '3.0',  entry: '$195',    exit: '$180',    pnl: '+$45',  pos: true },
  { date: '2026-07-27', sym: 'BNB', dir: 'LONG',  size: '1.5',  entry: '$630',    exit: '$608',    pnl: '-$33',  pos: false },
  { date: '2026-07-26', sym: 'BTC', dir: 'SHORT', size: '0.05', entry: '$68,000', exit: '$66,200', pnl: '+$90',  pos: true },
  { date: '2026-07-25', sym: 'ETH', dir: 'LONG',  size: '1.0',  entry: '$3,400',  exit: '$3,560',  pnl: '+$160', pos: true },
  { date: '2026-07-24', sym: 'LINK', dir: 'LONG', size: '20',   entry: '$13.40',  exit: '$14.80',  pnl: '+$28',  pos: true },
  { date: '2026-07-23', sym: 'ADA', dir: 'LONG',  size: '300',  entry: '$0.450',  exit: '$0.440',  pnl: '-$3',   pos: false },
];

function DonutChart() {
  let cumulative = 0;
  const total = 100;
  const r = 60;
  const circumference = 2 * Math.PI * r;
  const cx = 80, cy = 80;

  const arcs = ALLOC.map(a => {
    const startAngle = (cumulative / total) * 360 - 90;
    const sliceAngle = (a.pct / total) * 360;
    const endAngle = startAngle + sliceAngle;
    cumulative += a.pct;

    const startRad = (startAngle * Math.PI) / 180;
    const endRad = (endAngle * Math.PI) / 180;
    const x1 = cx + r * Math.cos(startRad);
    const y1 = cy + r * Math.sin(startRad);
    const x2 = cx + r * Math.cos(endRad);
    const y2 = cy + r * Math.sin(endRad);
    const largeArc = sliceAngle > 180 ? 1 : 0;

    const strokeDash = (a.pct / total) * circumference;
    const strokeOffset = circumference - strokeDash;
    const startOffset = ((cumulative - a.pct) / total) * circumference;

    return { ...a, startOffset, strokeDash, strokeOffset };
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
        {ALLOC.map(a => (
          <div key={a.label} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{ width: 10, height: 10, borderRadius: 3, background: a.color, flexShrink: 0 }} />
            <span style={{ fontSize: 12, color: '#94A3B8', minWidth: 40 }}>{a.label}</span>
            <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 12, fontWeight: 700, color: '#E2E8F0' }}>{a.pct}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function PortfolioView() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      style={{ padding: 24, paddingBottom: 48 }}
    >
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 20, fontWeight: 700, color: '#E2E8F0', margin: 0 }}>Portfolio Overview</h1>
        <p style={{ fontSize: 13, color: '#475569', marginTop: 4 }}>Real-time portfolio tracking and position management</p>
      </div>

      {/* Stats */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 24 }}>
        {STATS.map((s, i) => (
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
              {POSITIONS.map((p, i) => (
                <tr key={i} style={{ background: i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.015)' }}>
                  <td style={{ padding: '10px 14px', fontWeight: 700, color: '#E2E8F0', fontSize: 13 }}>{p.sym}</td>
                  <td style={{ padding: '10px 14px' }}>
                    <span style={{ padding: '2px 7px', borderRadius: 5, fontSize: 10, fontWeight: 700, background: p.dir === 'LONG' ? 'rgba(34,197,94,0.12)' : 'rgba(239,68,68,0.12)', color: p.dir === 'LONG' ? '#22C55E' : '#EF4444' }}>{p.dir}</span>
                  </td>
                  <td style={{ padding: '10px 14px', fontSize: 11, color: '#94A3B8', fontFamily: "'JetBrains Mono', monospace" }}>{p.size}</td>
                  <td style={{ padding: '10px 14px', fontSize: 11, color: '#94A3B8', fontFamily: "'JetBrains Mono', monospace" }}>{p.entry}</td>
                  <td style={{ padding: '10px 14px', fontSize: 11, color: '#F1F5F9', fontFamily: "'JetBrains Mono', monospace" }}>{p.cur}</td>
                  <td style={{ padding: '10px 14px', fontSize: 11, fontFamily: "'JetBrains Mono', monospace", fontWeight: 700, color: p.pos ? '#22C55E' : '#EF4444' }}>{p.pnl}</td>
                  <td style={{ padding: '10px 14px', fontSize: 11, fontFamily: "'JetBrains Mono', monospace", fontWeight: 700, color: p.pos ? '#22C55E' : '#EF4444' }}>{p.pct}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Donut */}
        <div style={{ background: '#121826', border: '1px solid rgba(255,255,255,0.06)', borderRadius: 12, padding: 20 }}>
          <div style={{ fontSize: 14, fontWeight: 700, color: '#E2E8F0', marginBottom: 20 }}>Allocation</div>
          <DonutChart />
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
            {TRADES.map((t, i) => (
              <tr key={i} style={{ background: i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.015)' }}>
                <td style={{ padding: '10px 14px', fontSize: 11, color: '#475569', fontFamily: "'JetBrains Mono', monospace" }}>{t.date}</td>
                <td style={{ padding: '10px 14px', fontWeight: 700, color: '#E2E8F0', fontSize: 13 }}>{t.sym}</td>
                <td style={{ padding: '10px 14px' }}>
                  <span style={{ padding: '2px 7px', borderRadius: 5, fontSize: 10, fontWeight: 700, background: t.dir === 'LONG' ? 'rgba(34,197,94,0.12)' : 'rgba(239,68,68,0.12)', color: t.dir === 'LONG' ? '#22C55E' : '#EF4444' }}>{t.dir}</span>
                </td>
                <td style={{ padding: '10px 14px', fontSize: 11, color: '#94A3B8', fontFamily: "'JetBrains Mono', monospace" }}>{t.size}</td>
                <td style={{ padding: '10px 14px', fontSize: 11, color: '#94A3B8', fontFamily: "'JetBrains Mono', monospace" }}>{t.entry}</td>
                <td style={{ padding: '10px 14px', fontSize: 11, color: '#94A3B8', fontFamily: "'JetBrains Mono', monospace" }}>{t.exit}</td>
                <td style={{ padding: '10px 14px', fontSize: 11, fontFamily: "'JetBrains Mono', monospace", fontWeight: 700, color: t.pos ? '#22C55E' : '#EF4444' }}>{t.pnl}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </motion.div>
  );
}
