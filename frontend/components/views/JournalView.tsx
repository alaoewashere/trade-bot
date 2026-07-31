'use client';

import React from 'react';
import { motion } from 'framer-motion';

const ENTRIES = [
  {
    date: '2026-07-30',
    ref: '#1247',
    preview: 'BTC long played out perfectly. Trend alignment across all timeframes, volume confirmed breakout above $66k resistance. Held through minor retest, closed at target.',
    outcome: 'WIN',
    pnl: '+$340',
  },
  {
    date: '2026-07-29',
    ref: '#1240',
    preview: 'ETH setup looked solid but slippage on entry was worse than expected. News event caused brief spike that hit SL. Need to widen stops during high-impact news windows.',
    outcome: 'LOSS',
    pnl: '-$180',
  },
  {
    date: '2026-07-28',
    ref: '#1235',
    preview: 'SOL short — captured the rejection from key resistance at $195. RSI divergence on 4H was the key signal. AI agents reached 24/40 bearish which validated the trade.',
    outcome: 'WIN',
    pnl: '+$45',
  },
  {
    date: '2026-07-27',
    ref: '#1228',
    preview: 'Missed the initial BTC breakout entry. Chased and entered late, got stopped out on pullback. Lesson: stick to planned entry zones, no chasing.',
    outcome: 'LOSS',
    pnl: '-$90',
  },
  {
    date: '2026-07-26',
    ref: '#1222',
    preview: 'Clean trend following trade on ETH. All three confluence factors aligned: trend, momentum, and agent consensus at 31/40 bullish. Held to first target, moved stop to BE.',
    outcome: 'WIN',
    pnl: '+$160',
  },
];

const OUTCOME_COLORS: Record<string, { bg: string; text: string }> = {
  WIN:  { bg: 'rgba(34,197,94,0.12)',  text: '#22C55E' },
  LOSS: { bg: 'rgba(239,68,68,0.12)', text: '#EF4444' },
  BE:   { bg: 'rgba(245,158,11,0.12)', text: '#F59E0B' },
};

export default function JournalView() {
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

      {/* Today's note */}
      <div style={{
        background: '#121826',
        border: '1px solid rgba(255,255,255,0.06)',
        borderRadius: 12, padding: 20, marginBottom: 24,
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
          <div>
            <div style={{ fontSize: 14, fontWeight: 700, color: '#E2E8F0' }}>Today's Notes</div>
            <div style={{ fontSize: 11, color: '#475569', marginTop: 2 }}>Thu, Jul 31, 2026</div>
          </div>
          <button style={{
            padding: '6px 14px', borderRadius: 8, fontSize: 12, fontWeight: 600, cursor: 'pointer',
            background: 'rgba(79,124,255,0.1)', border: '1px solid rgba(79,124,255,0.25)', color: '#4F7CFF',
          }}>Save</button>
        </div>
        <div style={{
          minHeight: 120, padding: '12px 14px', borderRadius: 8,
          background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)',
          fontSize: 13.5, color: '#64748B', lineHeight: 1.6,
        }}>
          <span style={{ color: '#334155' }}>
            Markets showing bullish momentum across crypto. BTC holding above $67k resistance-turned-support.
            AI agents at 70% bullish consensus. Watching for a potential dip to $66,200 for long entry.
            Risk limit at 60% today — being selective with setups. ETH showing relative strength...
          </span>
        </div>
      </div>

      {/* Journal entries */}
      <div style={{
        background: '#121826',
        border: '1px solid rgba(255,255,255,0.06)',
        borderRadius: 12, overflow: 'hidden',
      }}>
        <div style={{ padding: '14px 20px', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
          <span style={{ fontSize: 14, fontWeight: 700, color: '#E2E8F0' }}>Recent Journal Entries</span>
        </div>
        {ENTRIES.map((e, i) => {
          const oc = OUTCOME_COLORS[e.outcome];
          return (
            <div key={i} style={{
              padding: '16px 20px',
              borderBottom: i < ENTRIES.length - 1 ? '1px solid rgba(255,255,255,0.04)' : 'none',
              cursor: 'pointer',
              transition: 'background 0.12s',
            }}
              onMouseEnter={ev => (ev.currentTarget.style.background = 'rgba(255,255,255,0.02)')}
              onMouseLeave={ev => (ev.currentTarget.style.background = 'transparent')}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: '#475569' }}>{e.date}</span>
                  <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: '#4F7CFF', fontWeight: 600 }}>{e.ref}</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 12, fontWeight: 700, color: e.outcome === 'WIN' ? '#22C55E' : '#EF4444' }}>{e.pnl}</span>
                  <span style={{ padding: '2px 8px', borderRadius: 5, fontSize: 10, fontWeight: 700, background: oc.bg, color: oc.text }}>{e.outcome}</span>
                </div>
              </div>
              <p style={{ fontSize: 12.5, color: '#64748B', lineHeight: 1.55, margin: 0 }}>{e.preview}</p>
            </div>
          );
        })}
      </div>
    </motion.div>
  );
}
