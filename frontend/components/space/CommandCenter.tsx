'use client';

import React, { useState, useEffect, useRef } from 'react';
import { motion, useInView, animate } from 'framer-motion';
import { Zap, Clock } from 'lucide-react';

/* ── Types ──────────────────────────────────────────── */
type SignalType = 'BUY' | 'SELL' | 'WAIT';

interface SignalConfig {
  color: string;
  glow: string;
  gradient: string;
  textColor: string;
}

const SIGNAL_CONFIGS: Record<SignalType, SignalConfig> = {
  BUY: {
    color: '#22C55E',
    glow: 'rgba(34,197,94,0.3)',
    gradient: 'linear-gradient(135deg, rgba(34,197,94,0.15) 0%, rgba(34,197,94,0.05) 100%)',
    textColor: '#22C55E',
  },
  SELL: {
    color: '#EF4444',
    glow: 'rgba(239,68,68,0.3)',
    gradient: 'linear-gradient(135deg, rgba(239,68,68,0.15) 0%, rgba(239,68,68,0.05) 100%)',
    textColor: '#EF4444',
  },
  WAIT: {
    color: '#F59E0B',
    glow: 'rgba(245,158,11,0.3)',
    gradient: 'linear-gradient(135deg, rgba(245,158,11,0.12) 0%, rgba(245,158,11,0.04) 100%)',
    textColor: '#F59E0B',
  },
};

/* ── Animated vote bar ───────────────────────────────── */
interface VoteBarProps {
  label: string;
  pct: number;
  color: string;
  delay: number;
}

function VoteBar({ label, pct, color, delay }: VoteBarProps) {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true });

  return (
    <div ref={ref} style={{ marginBottom: 14 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 5, alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <div style={{ width: 7, height: 7, borderRadius: '50%', background: color, boxShadow: `0 0 6px ${color}` }} />
          <span style={{ fontSize: 11, color: '#94A3B8', textTransform: 'uppercase', letterSpacing: '0.08em' }}>{label}</span>
        </div>
        <span style={{ fontSize: 13, fontWeight: 700, color, fontFamily: 'JetBrains Mono, monospace' }}>{pct}%</span>
      </div>
      <div style={{ height: 6, background: 'rgba(255,255,255,0.06)', borderRadius: 3, overflow: 'hidden' }}>
        <motion.div
          initial={{ width: 0 }}
          animate={inView ? { width: `${pct}%` } : { width: 0 }}
          transition={{ duration: 1.2, delay, ease: [0.25, 1, 0.5, 1] }}
          style={{
            height: '100%',
            borderRadius: 3,
            background: `linear-gradient(90deg, ${color}99, ${color})`,
            boxShadow: `0 0 8px ${color}66`,
          }}
        />
      </div>
    </div>
  );
}

/* ── Animated SVG progress circle ───────────────────── */
function ProgressCircle({ pct, color }: { pct: number; color: string }) {
  const r = 36;
  const circ = 2 * Math.PI * r;
  const offset = circ * (1 - pct / 100);
  const ref = useRef<SVGCircleElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const inView = useInView(containerRef, { once: true });

  useEffect(() => {
    if (!inView || !ref.current) return;
    animate(circ, offset, {
      duration: 1.4,
      ease: [0.25, 1, 0.5, 1],
      onUpdate: (v) => {
        if (ref.current) ref.current.style.strokeDashoffset = String(v);
      },
    });
  }, [inView, circ, offset]);

  return (
    <div ref={containerRef} style={{ position: 'relative', width: 90, height: 90 }}>
      <svg width="90" height="90" viewBox="0 0 90 90" style={{ transform: 'rotate(-90deg)' }}>
        <circle cx="45" cy="45" r={r} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="6" />
        <circle
          ref={ref}
          cx="45"
          cy="45"
          r={r}
          fill="none"
          stroke={color}
          strokeWidth="6"
          strokeLinecap="round"
          strokeDasharray={circ}
          strokeDashoffset={circ}
          style={{ filter: `drop-shadow(0 0 4px ${color})` }}
        />
      </svg>
      <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
        <span style={{ fontSize: 18, fontWeight: 800, color, fontFamily: 'JetBrains Mono, monospace' }}>{pct}%</span>
        <span style={{ fontSize: 9, color: '#64748B', textTransform: 'uppercase', letterSpacing: '0.06em' }}>consensus</span>
      </div>
    </div>
  );
}

/* ── Countdown timer ─────────────────────────────────── */
function CountdownTimer() {
  const [seconds, setSeconds] = useState(47);

  useEffect(() => {
    const t = setInterval(() => {
      setSeconds(s => (s <= 1 ? 59 : s - 1));
    }, 1000);
    return () => clearInterval(t);
  }, []);

  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 12 }}>
      <Clock size={12} color="#64748B" />
      <span style={{ fontSize: 11, color: '#64748B' }}>
        Next analysis in:{' '}
        <span style={{ color: '#94A3B8', fontFamily: 'JetBrains Mono, monospace', fontWeight: 600 }}>
          {mins}:{String(secs).padStart(2, '0')}
        </span>
      </span>
    </div>
  );
}

/* ── Main component ──────────────────────────────────── */
export default function CommandCenter() {
  const signal: SignalType = 'BUY';
  const cfg = SIGNAL_CONFIGS[signal];

  return (
    <div
      style={{
        width: '100%',
        background: '#0d1525',
        border: '1px solid rgba(255,255,255,0.06)',
        borderRadius: 16,
        overflow: 'hidden',
        position: 'relative',
      }}
    >
      {/* Top bar */}
      <div style={{ padding: '12px 20px', borderBottom: '1px solid rgba(255,255,255,0.05)', display: 'flex', alignItems: 'center', gap: 8 }}>
        <motion.div
          animate={{ opacity: [1, 0.3, 1] }}
          transition={{ duration: 1.4, repeat: Infinity }}
          style={{ width: 7, height: 7, borderRadius: '50%', background: '#22C55E' }}
        />
        <span style={{ fontSize: 11, color: '#64748B', textTransform: 'uppercase', letterSpacing: '0.12em', fontWeight: 600 }}>
          AI Command Center — Live Analysis
        </span>
      </div>

      {/* Main 3-column layout */}
      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1.5fr 1.5fr', gap: 0 }}>

        {/* ── Left: Signal display ── */}
        <div
          style={{
            padding: '28px 28px',
            borderRight: '1px solid rgba(255,255,255,0.05)',
            background: cfg.gradient,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            position: 'relative',
            minHeight: 220,
          }}
        >
          {/* Glow blob behind signal */}
          <div style={{ position: 'absolute', inset: 0, background: `radial-gradient(circle at 50% 50%, ${cfg.glow} 0%, transparent 65%)`, pointerEvents: 'none' }} />

          {/* Pulsing ring */}
          <div style={{ position: 'relative', marginBottom: 14 }}>
            <motion.div
              animate={{ scale: [1, 1.25, 1], opacity: [0.5, 0, 0.5] }}
              transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
              style={{
                position: 'absolute',
                inset: -20,
                borderRadius: '50%',
                border: `2px solid ${cfg.color}`,
              }}
            />
            <motion.div
              animate={{ scale: [1, 1.4, 1], opacity: [0.3, 0, 0.3] }}
              transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut', delay: 0.5 }}
              style={{
                position: 'absolute',
                inset: -36,
                borderRadius: '50%',
                border: `1px solid ${cfg.color}`,
              }}
            />
            <div
              style={{
                width: 90,
                height: 90,
                borderRadius: '50%',
                border: `3px solid ${cfg.color}`,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                background: `${cfg.color}18`,
                boxShadow: `0 0 30px ${cfg.glow}`,
              }}
            >
              <Zap size={32} color={cfg.color} fill={cfg.color} />
            </div>
          </div>

          <div style={{ position: 'relative', textAlign: 'center' }}>
            <div
              style={{
                fontSize: 42,
                fontWeight: 900,
                color: cfg.textColor,
                letterSpacing: '0.12em',
                textShadow: `0 0 30px ${cfg.glow}`,
                lineHeight: 1,
                marginBottom: 8,
              }}
            >
              {signal}
            </div>
            <div
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 4,
                background: `${cfg.color}22`,
                border: `1px solid ${cfg.color}44`,
                borderRadius: 20,
                padding: '4px 12px',
                fontSize: 11,
                fontWeight: 700,
                color: cfg.color,
                letterSpacing: '0.1em',
                marginBottom: 4,
              }}
            >
              <Zap size={10} color={cfg.color} />
              72% CONFIDENCE
            </div>
            <CountdownTimer />
          </div>
        </div>

        {/* ── Center: AI Consensus ── */}
        <div style={{ padding: '24px 24px', borderRight: '1px solid rgba(255,255,255,0.05)' }}>
          <div style={{ fontSize: 10, color: '#64748B', textTransform: 'uppercase', letterSpacing: '0.12em', marginBottom: 18 }}>
            AI Consensus
          </div>

          <div style={{ display: 'flex', gap: 16, alignItems: 'flex-start', marginBottom: 20 }}>
            <ProgressCircle pct={74} color="#22C55E" />
            <div style={{ flex: 1 }}>
              <VoteBar label="Bullish" pct={74} color="#22C55E" delay={0.2} />
              <VoteBar label="Bearish" pct={18} color="#EF4444" delay={0.4} />
              <VoteBar label="Neutral" pct={8} color="#F59E0B" delay={0.6} />
            </div>
          </div>

          <div
            style={{
              background: 'rgba(255,255,255,0.03)',
              border: '1px solid rgba(255,255,255,0.06)',
              borderRadius: 10,
              padding: '10px 14px',
              display: 'flex',
              alignItems: 'center',
              gap: 10,
            }}
          >
            <div style={{ fontSize: 22, fontWeight: 800, color: '#22C55E', fontFamily: 'JetBrains Mono, monospace' }}>31</div>
            <div>
              <div style={{ fontSize: 11, color: '#94A3B8', fontWeight: 600 }}>of 40 agents agree</div>
              <div style={{ fontSize: 10, color: '#475569' }}>Strong bullish consensus</div>
            </div>
          </div>
        </div>

        {/* ── Right: Trade setup ── */}
        <div style={{ padding: '24px 24px' }}>
          <div style={{ fontSize: 10, color: '#64748B', textTransform: 'uppercase', letterSpacing: '0.12em', marginBottom: 18 }}>
            Trade Setup
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 20 }}>
            {[
              { label: 'Entry', value: '$67,428', color: '#4F7CFF' },
              { label: 'Stop Loss', value: '$66,100', color: '#EF4444' },
              { label: 'Target', value: '$69,200', color: '#22C55E' },
              { label: 'Risk / Reward', value: '1 : 1.33', color: '#F59E0B' },
              { label: 'Position Size', value: '0.15 BTC', color: '#8B5CF6' },
            ].map(row => (
              <div key={row.label} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: 11, color: '#64748B' }}>{row.label}</span>
                <span style={{ fontSize: 13, fontWeight: 700, color: row.color, fontFamily: 'JetBrains Mono, monospace' }}>{row.value}</span>
              </div>
            ))}
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <motion.button
              whileHover={{ scale: 1.02, boxShadow: '0 0 24px rgba(34,197,94,0.35)' }}
              whileTap={{ scale: 0.98 }}
              style={{
                width: '100%',
                padding: '12px',
                borderRadius: 10,
                border: 'none',
                background: 'linear-gradient(135deg, #16a34a, #22C55E)',
                color: '#fff',
                fontSize: 13,
                fontWeight: 800,
                letterSpacing: '0.08em',
                cursor: 'pointer',
                boxShadow: '0 0 16px rgba(34,197,94,0.25)',
              }}
            >
              APPROVE TRADE
            </motion.button>
            <motion.button
              whileHover={{ background: 'rgba(255,255,255,0.08)' }}
              whileTap={{ scale: 0.98 }}
              style={{
                width: '100%',
                padding: '10px',
                borderRadius: 10,
                border: '1px solid rgba(255,255,255,0.1)',
                background: 'transparent',
                color: '#64748B',
                fontSize: 12,
                fontWeight: 600,
                letterSpacing: '0.08em',
                cursor: 'pointer',
              }}
            >
              SKIP
            </motion.button>
          </div>
        </div>
      </div>
    </div>
  );
}
