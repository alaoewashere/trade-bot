'use client';

import React from 'react';
import { motion } from 'framer-motion';
import { FileText, BarChart2, Lightbulb, ExternalLink } from 'lucide-react';

const REPORTS = [
  { title: 'BTC Q3 2026 Outlook: Halving Cycle Implications', date: '2026-07-28', tags: ['BTC', 'Macro'], sentiment: 'BULLISH', confidence: 84 },
  { title: 'DeFi 2.0: Protocol Revenue and Token Accrual Models', date: '2026-07-25', tags: ['ETH', 'DeFi'], sentiment: 'NEUTRAL', confidence: 67 },
  { title: 'Institutional Crypto Adoption: 2026 State of the Market', date: '2026-07-22', tags: ['BTC', 'Macro'], sentiment: 'BULLISH', confidence: 79 },
];

const ANALYSES = [
  { title: 'BTC/USDT 4H Technical Structure — Key Levels', date: '2026-07-30', type: 'Technical', symbol: 'BTC' },
  { title: 'ETH Supply Dynamics Post-Merge: Deflationary Pressure', date: '2026-07-29', type: 'On-Chain', symbol: 'ETH' },
  { title: 'SOL Ecosystem Growth: TVL and Developer Activity', date: '2026-07-27', type: 'Fundamental', symbol: 'SOL' },
];

const IDEAS = [
  { title: 'BTC Long — Breakout Continuation Setup', sym: 'BTC', status: 'ACTIVE', confidence: 78 },
  { title: 'ETH/BTC Ratio Reversal Trade', sym: 'ETH', status: 'WATCHING', confidence: 62 },
  { title: 'SOL Short — Overbought on Weekly', sym: 'SOL', status: 'INVALIDATED', confidence: 45 },
];

const SENT_C: Record<string, string> = {
  BULLISH: '#22C55E', BEARISH: '#EF4444', NEUTRAL: '#F59E0B',
};

const STATUS_C: Record<string, { bg: string; text: string }> = {
  ACTIVE:      { bg: 'rgba(34,197,94,0.12)',  text: '#22C55E' },
  WATCHING:    { bg: 'rgba(245,158,11,0.12)', text: '#F59E0B' },
  INVALIDATED: { bg: 'rgba(239,68,68,0.12)',  text: '#EF4444' },
};

export default function ResearchView() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      style={{ padding: 24, paddingBottom: 48 }}
    >
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 20, fontWeight: 700, color: '#E2E8F0', margin: 0 }}>Research & Analysis</h1>
        <p style={{ fontSize: 13, color: '#475569', marginTop: 4 }}>AI-generated reports, market analysis, and saved trade ideas</p>
      </div>

      {/* AI Research Reports */}
      <Section icon={<FileText size={15} color="#4F7CFF" />} title="AI Research Reports" count={REPORTS.length} mb={24}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 14 }}>
          {REPORTS.map((r, i) => (
            <motion.div key={i}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.06, duration: 0.2 }}
              style={{
                background: 'rgba(255,255,255,0.02)', borderRadius: 10, padding: 16,
                border: '1px solid rgba(255,255,255,0.05)', cursor: 'pointer',
              }}
              whileHover={{ borderColor: 'rgba(255,255,255,0.1)' }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 10 }}>
                <div style={{ display: 'flex', gap: 6 }}>
                  {r.tags.map(t => (
                    <span key={t} style={{ padding: '2px 7px', borderRadius: 5, fontSize: 10, fontWeight: 700, background: 'rgba(79,124,255,0.1)', color: '#4F7CFF' }}>{t}</span>
                  ))}
                </div>
                <ExternalLink size={12} color="#334155" />
              </div>
              <div style={{ fontSize: 13, fontWeight: 600, color: '#E2E8F0', lineHeight: 1.45, marginBottom: 10 }}>{r.title}</div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: 10, color: '#334155' }}>{r.date}</span>
                <span style={{ fontSize: 11, fontWeight: 700, color: SENT_C[r.sentiment] }}>{r.confidence}% {r.sentiment}</span>
              </div>
            </motion.div>
          ))}
        </div>
      </Section>

      {/* Market Analysis */}
      <Section icon={<BarChart2 size={15} color="#818CF8" />} title="Market Analysis" count={ANALYSES.length} mb={24}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 14 }}>
          {ANALYSES.map((a, i) => (
            <motion.div key={i}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.06 + 0.1, duration: 0.2 }}
              style={{
                background: 'rgba(255,255,255,0.02)', borderRadius: 10, padding: 16,
                border: '1px solid rgba(255,255,255,0.05)', cursor: 'pointer',
              }}
              whileHover={{ borderColor: 'rgba(255,255,255,0.1)' }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 10 }}>
                <span style={{ padding: '2px 7px', borderRadius: 5, fontSize: 10, fontWeight: 700, background: 'rgba(129,140,248,0.1)', color: '#818CF8' }}>{a.type}</span>
                <span style={{ padding: '2px 7px', borderRadius: 5, fontSize: 10, fontWeight: 700, background: 'rgba(79,124,255,0.1)', color: '#4F7CFF' }}>{a.symbol}</span>
              </div>
              <div style={{ fontSize: 13, fontWeight: 600, color: '#E2E8F0', lineHeight: 1.45, marginBottom: 8 }}>{a.title}</div>
              <div style={{ fontSize: 10, color: '#334155' }}>{a.date}</div>
            </motion.div>
          ))}
        </div>
      </Section>

      {/* Saved Ideas */}
      <Section icon={<Lightbulb size={15} color="#F59E0B" />} title="Saved Ideas" count={IDEAS.length} mb={0}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 14 }}>
          {IDEAS.map((idea, i) => {
            const sc = STATUS_C[idea.status];
            return (
              <motion.div key={i}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.06 + 0.2, duration: 0.2 }}
                style={{
                  background: 'rgba(255,255,255,0.02)', borderRadius: 10, padding: 16,
                  border: '1px solid rgba(255,255,255,0.05)', cursor: 'pointer',
                }}
                whileHover={{ borderColor: 'rgba(255,255,255,0.1)' }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 10 }}>
                  <span style={{ padding: '2px 7px', borderRadius: 5, fontSize: 10, fontWeight: 700, background: 'rgba(79,124,255,0.1)', color: '#4F7CFF' }}>{idea.sym}</span>
                  <span style={{ padding: '2px 7px', borderRadius: 5, fontSize: 10, fontWeight: 700, background: sc.bg, color: sc.text }}>{idea.status}</span>
                </div>
                <div style={{ fontSize: 13, fontWeight: 600, color: '#E2E8F0', lineHeight: 1.45, marginBottom: 10 }}>{idea.title}</div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <div style={{ flex: 1, height: 4, borderRadius: 2, background: 'rgba(255,255,255,0.06)', overflow: 'hidden' }}>
                    <div style={{ height: '100%', width: `${idea.confidence}%`, background: '#4F7CFF', borderRadius: 2 }} />
                  </div>
                  <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: '#4F7CFF', fontWeight: 700 }}>{idea.confidence}%</span>
                </div>
              </motion.div>
            );
          })}
        </div>
      </Section>
    </motion.div>
  );
}

function Section({ icon, title, count, children, mb }: {
  icon: React.ReactNode; title: string; count: number; children: React.ReactNode; mb: number;
}) {
  return (
    <div style={{
      background: '#121826',
      border: '1px solid rgba(255,255,255,0.06)',
      borderRadius: 12, padding: 20, marginBottom: mb,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
        {icon}
        <span style={{ fontSize: 14, fontWeight: 700, color: '#E2E8F0' }}>{title}</span>
        <span style={{
          padding: '1px 7px', borderRadius: 99, fontSize: 10, fontWeight: 700,
          background: 'rgba(255,255,255,0.06)', color: '#475569',
        }}>{count}</span>
      </div>
      {children}
    </div>
  );
}
