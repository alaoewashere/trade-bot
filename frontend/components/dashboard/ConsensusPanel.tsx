'use client';

import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import Badge from '@/components/ui/Badge';

const CONFIDENCE = 74;
const TOTAL_AGENTS = 40;
const AGREEING = 31;

const VOTES = [
  { label: 'BULLISH', pct: 74, color: '#22C55E', bg: 'rgba(34,197,94,0.12)' },
  { label: 'BEARISH', pct: 18, color: '#EF4444', bg: 'rgba(239,68,68,0.12)' },
  { label: 'NEUTRAL', pct: 8, color: '#F59E0B', bg: 'rgba(245,158,11,0.12)' },
];

function RingGauge({ value, size = 140 }: { value: number; size?: number }) {
  const strokeWidth = 10;
  const radius = (size - strokeWidth) / 2;
  const cx = size / 2;
  const cy = size / 2;
  const circumference = 2 * Math.PI * radius;
  const dashOffset = circumference - (value / 100) * circumference;

  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
        {/* Track */}
        <circle
          cx={cx}
          cy={cy}
          r={radius}
          fill="none"
          stroke="rgba(255,255,255,0.08)"
          strokeWidth={strokeWidth}
        />
        {/* Value */}
        <motion.circle
          cx={cx}
          cy={cy}
          r={radius}
          fill="none"
          stroke="#4F7CFF"
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: dashOffset }}
          transition={{ duration: 1.4, ease: 'easeOut', delay: 0.3 }}
        />
      </svg>
      {/* Center text */}
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="font-mono font-bold text-3xl" style={{ color: '#4F7CFF' }}>
          {value}%
        </span>
        <span className="text-[10px] font-medium uppercase tracking-widest" style={{ color: '#475569' }}>
          Confidence
        </span>
      </div>
    </div>
  );
}

export default function ConsensusPanel() {
  const [now, setNow] = useState('');

  useEffect(() => {
    const tick = () => setNow(new Date().toLocaleTimeString());
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  return (
    <div
      className="rounded-xl p-5 h-full flex flex-col gap-5"
      style={{
        background: '#121826',
        border: '1px solid rgba(255,255,255,0.06)',
      }}
    >
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold" style={{ color: '#F1F5F9' }}>
          AI Consensus
        </h2>
        <Badge variant="success" dot pulse>
          LIVE
        </Badge>
      </div>

      {/* Ring gauge */}
      <div className="flex justify-center">
        <RingGauge value={CONFIDENCE} />
      </div>

      {/* Vote bars */}
      <div className="flex flex-col gap-3">
        {VOTES.map((vote, i) => (
          <div key={vote.label} className="flex flex-col gap-1">
            <div className="flex items-center justify-between text-xs font-medium">
              <span style={{ color: vote.color }}>{vote.label}</span>
              <span className="font-mono" style={{ color: '#94A3B8' }}>
                {vote.pct}%
              </span>
            </div>
            <div className="h-2 rounded-full overflow-hidden" style={{ background: 'rgba(255,255,255,0.06)' }}>
              <motion.div
                className="h-full rounded-full"
                style={{ background: vote.color }}
                initial={{ width: 0 }}
                animate={{ width: `${vote.pct}%` }}
                transition={{ duration: 0.9, ease: 'easeOut', delay: 0.4 + i * 0.15 }}
              />
            </div>
          </div>
        ))}
      </div>

      {/* Stats row */}
      <div className="flex items-center gap-3">
        <div
          className="flex-1 rounded-lg p-3 text-center"
          style={{ background: 'rgba(79,124,255,0.08)', border: '1px solid rgba(79,124,255,0.15)' }}
        >
          <div className="font-mono font-bold text-lg" style={{ color: '#4F7CFF' }}>
            {AGREEING}/{TOTAL_AGENTS}
          </div>
          <div className="text-[10px] font-medium uppercase tracking-wider mt-0.5" style={{ color: '#475569' }}>
            Agents Agree
          </div>
        </div>
        <div
          className="flex-1 rounded-lg p-3 text-center"
          style={{ background: 'rgba(34,197,94,0.08)', border: '1px solid rgba(34,197,94,0.15)' }}
        >
          <div className="text-xs font-bold" style={{ color: '#22C55E' }}>
            BULL MARKET
          </div>
          <div className="text-[10px] font-medium uppercase tracking-wider mt-0.5" style={{ color: '#475569' }}>
            Regime
          </div>
        </div>
      </div>

      {/* Last updated */}
      <div className="flex items-center justify-between text-xs" style={{ color: '#475569' }}>
        <span>Last updated</span>
        <span className="font-mono">{now}</span>
      </div>
    </div>
  );
}
