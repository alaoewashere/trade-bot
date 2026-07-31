'use client';

import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import Badge from '@/components/ui/Badge';
import { api, ForecastExplanation } from '@/lib/api';

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

export default function ConsensusPanel({ forecastId }: { forecastId?: string } = {}) {
  const [now, setNow] = useState('');
  const [explainOpen, setExplainOpen] = useState(false);
  const [explanation, setExplanation] = useState<ForecastExplanation | null>(null);
  const [explainLoading, setExplainLoading] = useState(false);
  const [explainError, setExplainError] = useState<string | null>(null);

  useEffect(() => {
    const tick = () => setNow(new Date().toLocaleTimeString());
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  const toggleExplain = () => {
    const next = !explainOpen;
    setExplainOpen(next);
    if (next && !explanation && forecastId) {
      setExplainLoading(true);
      setExplainError(null);
      api.forecasts
        .explain(forecastId)
        .then(setExplanation)
        .catch(e => setExplainError(e instanceof Error ? e.message : 'Failed to load explanation'))
        .finally(() => setExplainLoading(false));
    }
  };

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

      {/* Explain this decision */}
      <div>
        <button
          onClick={toggleExplain}
          className="w-full text-xs font-semibold rounded-lg py-2 transition-colors"
          style={{
            background: 'rgba(79,124,255,0.08)',
            border: '1px solid rgba(79,124,255,0.2)',
            color: '#4F7CFF',
            cursor: forecastId ? 'pointer' : 'default',
            opacity: forecastId ? 1 : 0.5,
          }}
          disabled={!forecastId}
        >
          {explainOpen ? 'Hide explanation ▲' : 'Explain this decision ▼'}
        </button>

        <AnimatePresence>
          {explainOpen && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: 0.2 }}
              className="overflow-hidden"
            >
              <div className="pt-3 flex flex-col gap-3 text-xs">
                {explainLoading && <div style={{ color: '#475569' }}>Loading agent breakdown...</div>}
                {explainError && <div style={{ color: '#EF4444' }}>{explainError}</div>}
                {!forecastId && !explainLoading && (
                  <div style={{ color: '#475569' }}>No forecast selected to explain yet.</div>
                )}
                {explanation && (
                  <>
                    <div style={{ color: '#94A3B8', lineHeight: 1.5 }}>{explanation.final_thesis}</div>
                    <div className="flex items-center justify-between" style={{ color: '#475569' }}>
                      <span>{explanation.agreement.agreeing_agents}/{explanation.agreement.total_agents} agents agree</span>
                      <span>{explanation.agreement.agreement_pct.toFixed(0)}% agreement</span>
                    </div>
                    {explanation.departments.map(dept => (
                      <div key={dept.department} style={{ borderTop: '1px solid rgba(255,255,255,0.05)', paddingTop: 8 }}>
                        <div className="flex items-center justify-between mb-1">
                          <span className="font-semibold uppercase tracking-wider" style={{ color: '#CBD5E1', fontSize: 10 }}>
                            {dept.department.replace('_', ' ')}
                          </span>
                          <span style={{ color: '#475569' }}>{dept.dominant_signal} · {dept.avg_confidence_pct.toFixed(0)}%</span>
                        </div>
                        {dept.agents.map(a => (
                          <div key={a.agent_id} className="flex items-start justify-between gap-2 py-0.5">
                            <span style={{ color: '#64748B' }}>{a.agent_id}</span>
                            <span style={{ color: a.signal === 'bullish' ? '#22C55E' : a.signal === 'bearish' ? '#EF4444' : '#F59E0B' }}>
                              {a.signal} ({a.confidence_pct.toFixed(0)}%)
                            </span>
                          </div>
                        ))}
                      </div>
                    ))}
                    {explanation.agreement.dissenting_agent_ids.length > 0 && (
                      <div style={{ color: '#F59E0B' }}>
                        Dissenting: {explanation.agreement.dissenting_agent_ids.join(', ')}
                      </div>
                    )}
                  </>
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Last updated */}
      <div className="flex items-center justify-between text-xs" style={{ color: '#475569' }}>
        <span>Last updated</span>
        <span className="font-mono">{now}</span>
      </div>
    </div>
  );
}
