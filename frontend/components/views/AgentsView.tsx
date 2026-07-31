'use client';

import React from 'react';
import { motion } from 'framer-motion';
import AgentWorkers from '@/components/space/AgentWorkers';

const STATS = [
  { label: 'Active Agents', value: '40', color: '#4F7CFF', bg: 'rgba(79,124,255,0.1)' },
  { label: 'Bullish',       value: '28', color: '#22C55E', bg: 'rgba(34,197,94,0.1)'  },
  { label: 'Bearish',       value: '6',  color: '#EF4444', bg: 'rgba(239,68,68,0.1)'  },
  { label: 'Neutral',       value: '6',  color: '#F59E0B', bg: 'rgba(245,158,11,0.1)' },
];

export default function AgentsView() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      style={{ padding: 24, paddingBottom: 48 }}
    >
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 20, fontWeight: 700, color: '#E2E8F0', margin: 0 }}>AI Intelligence Network</h1>
        <p style={{ fontSize: 13, color: '#475569', marginTop: 4 }}>40 active agents analyzing markets in parallel</p>
      </div>

      {/* Stats row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 28 }}>
        {STATS.map((s, i) => (
          <motion.div
            key={s.label}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.06, duration: 0.2 }}
            style={{
              background: '#121826',
              border: `1px solid rgba(255,255,255,0.06)`,
              borderRadius: 12, padding: '18px 20px',
            }}
          >
            <div style={{ fontSize: 11, color: '#475569', fontWeight: 700, letterSpacing: '0.1em', marginBottom: 8 }}>
              {s.label.toUpperCase()}
            </div>
            <div style={{
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: 36, fontWeight: 800, color: s.color,
              lineHeight: 1,
            }}>{s.value}</div>
            <div style={{
              marginTop: 10, height: 3, borderRadius: 2,
              background: s.bg, position: 'relative', overflow: 'hidden',
            }}>
              <div style={{
                position: 'absolute', inset: 0, borderRadius: 2,
                background: s.color, width: `${(parseInt(s.value) / 40) * 100}%`,
                opacity: 0.6,
              }} />
            </div>
          </motion.div>
        ))}
      </div>

      <AgentWorkers />
    </motion.div>
  );
}
