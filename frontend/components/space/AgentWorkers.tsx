'use client';

import React, { useRef } from 'react';
import { motion, useInView } from 'framer-motion';
import * as LucideIcons from 'lucide-react';
import clsx from 'clsx';

/* ── Icon lookup ─────────────────────────────────────── */
type LucideIcon = React.ComponentType<{ className?: string; size?: number; color?: string }>;
function getIcon(name: string): LucideIcon {
  return (
    (LucideIcons as unknown as Record<string, LucideIcon>)[name] ??
    (LucideIcons as unknown as Record<string, LucideIcon>)['Bot']
  );
}

/* ── Agent data ──────────────────────────────────────── */
type Signal = 'bullish' | 'bearish' | 'neutral';

interface Agent {
  id: number;
  name: string;
  dept: string;
  icon: string;
  color: string;
  signal: Signal;
  confidence: number;
  task: string;
  lastUpdate: string;
}

const AGENTS: Agent[] = [
  // Executive
  { id: 1,  name: 'Chief Investment Officer',  dept: 'EXECUTIVE',       icon: 'Crown',            color: '#F59E0B', signal: 'bullish',  confidence: 82, task: 'Reviewing portfolio allocation for Q3 rebalancing', lastUpdate: '30s ago' },
  { id: 2,  name: 'Chief Risk Officer',         dept: 'EXECUTIVE',       icon: 'Shield',           color: '#EF4444', signal: 'neutral',  confidence: 68, task: 'Monitoring 3 open positions for stop-loss triggers', lastUpdate: '1m ago' },
  { id: 3,  name: 'Portfolio Manager',          dept: 'EXECUTIVE',       icon: 'Briefcase',        color: '#8B5CF6', signal: 'bullish',  confidence: 75, task: 'Optimizing position sizing across BTC, ETH, SOL', lastUpdate: '2m ago' },
  // Market Intelligence
  { id: 4,  name: 'Macro Economist',            dept: 'MARKET INTEL',    icon: 'Globe',            color: '#3B82F6', signal: 'bullish',  confidence: 71, task: 'Analyzing Fed rate decision impact on crypto markets', lastUpdate: '45s ago' },
  { id: 5,  name: 'News Analyst',               dept: 'MARKET INTEL',    icon: 'Newspaper',        color: '#06B6D4', signal: 'bullish',  confidence: 79, task: 'Processing 847 news articles — BlackRock ETF update', lastUpdate: '12s ago' },
  { id: 6,  name: 'Sentiment Analyst',          dept: 'MARKET INTEL',    icon: 'Heart',            color: '#EC4899', signal: 'bullish',  confidence: 83, task: 'Social media sentiment: 73% positive on BTC/USDT', lastUpdate: '20s ago' },
  { id: 7,  name: 'Regulation Analyst',         dept: 'MARKET INTEL',    icon: 'Scale',            color: '#64748B', signal: 'neutral',  confidence: 55, task: 'Tracking SEC enforcement actions — no immediate threat', lastUpdate: '5m ago' },
  // Technical
  { id: 8,  name: 'Trend Analyst',              dept: 'TECHNICAL',       icon: 'TrendingUp',       color: '#22C55E', signal: 'bullish',  confidence: 88, task: 'EMA 20/50/200 all aligned bullish on 4H timeframe', lastUpdate: '15s ago' },
  { id: 9,  name: 'Price Action Expert',        dept: 'TECHNICAL',       icon: 'CandlestickChart', color: '#10B981', signal: 'bullish',  confidence: 76, task: 'Identified bullish engulfing pattern at $66,800 support', lastUpdate: '1m ago' },
  { id: 10, name: 'SMC Expert',                 dept: 'TECHNICAL',       icon: 'Layers',           color: '#34D399', signal: 'bullish',  confidence: 81, task: 'Order block at $66,500 holding — institutional demand', lastUpdate: '2m ago' },
  { id: 11, name: 'Wyckoff Analyst',            dept: 'TECHNICAL',       icon: 'BarChart2',        color: '#6EE7B7', signal: 'bullish',  confidence: 73, task: 'Phase C accumulation confirmed — spring detected at $65,900', lastUpdate: '3m ago' },
  { id: 12, name: 'Elliott Wave Expert',        dept: 'TECHNICAL',       icon: 'Activity',         color: '#A7F3D0', signal: 'neutral',  confidence: 62, task: 'Wave 3 of 5 in progress — targeting $71,200', lastUpdate: '4m ago' },
  { id: 13, name: 'Volume Profile Analyst',     dept: 'TECHNICAL',       icon: 'BarChart',         color: '#0EA5E9', signal: 'bullish',  confidence: 77, task: 'High volume node at $67,000 acting as magnet', lastUpdate: '30s ago' },
  { id: 14, name: 'Market Structure Analyst',   dept: 'TECHNICAL',       icon: 'GitBranch',        color: '#38BDF8', signal: 'bullish',  confidence: 80, task: 'Higher highs, higher lows confirmed on 1H chart', lastUpdate: '45s ago' },
  // Quantitative
  { id: 15, name: 'Quant Researcher',           dept: 'QUANTITATIVE',    icon: 'Calculator',       color: '#818CF8', signal: 'bullish',  confidence: 74, task: 'Running Monte Carlo simulation — 68% win probability', lastUpdate: '1m ago' },
  { id: 16, name: 'Probability Analyst',        dept: 'QUANTITATIVE',    icon: 'Percent',          color: '#A5B4FC', signal: 'bullish',  confidence: 79, task: 'Kelly criterion suggests 2.3% position size', lastUpdate: '2m ago' },
  { id: 17, name: 'ML Researcher',              dept: 'QUANTITATIVE',    icon: 'Brain',            color: '#C7D2FE', signal: 'bullish',  confidence: 71, task: 'LSTM model predicts +2.1% price increase in 4H', lastUpdate: '3m ago' },
  { id: 18, name: 'Backtesting Expert',         dept: 'QUANTITATIVE',    icon: 'History',          color: '#7C3AED', signal: 'neutral',  confidence: 65, task: 'Strategy win rate: 58.3% over 1,247 historical trades', lastUpdate: '5m ago' },
  { id: 19, name: 'HFT Pattern Detector',       dept: 'QUANTITATIVE',    icon: 'Zap',              color: '#6D28D9', signal: 'bullish',  confidence: 69, task: 'Detected accumulation microstructure at bid side', lastUpdate: '5s ago' },
  // Options
  { id: 20, name: 'Options Flow Analyst',       dept: 'OPTIONS',         icon: 'Sigma',            color: '#F97316', signal: 'bullish',  confidence: 72, task: 'Large call sweep at $70k strike — bullish intent', lastUpdate: '2m ago' },
  { id: 21, name: 'Volatility Analyst',         dept: 'OPTIONS',         icon: 'Waves',            color: '#FB923C', signal: 'neutral',  confidence: 58, task: 'IV at 42% — elevated but decreasing trend', lastUpdate: '3m ago' },
  // Crypto
  { id: 22, name: 'On-Chain Analyst',           dept: 'CRYPTO',          icon: 'Link',             color: '#F59E0B', signal: 'bullish',  confidence: 85, task: 'Exchange outflows: 12,400 BTC withdrawn — supply shock', lastUpdate: '1m ago' },
  { id: 23, name: 'Funding Rate Analyst',       dept: 'CRYPTO',          icon: 'ArrowRightLeft',   color: '#FCD34D', signal: 'neutral',  confidence: 61, task: 'Funding rate at 0.01% — not overheated, healthy longs', lastUpdate: '2m ago' },
  // Strategy
  { id: 24, name: 'Momentum Trader',            dept: 'STRATEGY',        icon: 'Rocket',           color: '#22C55E', signal: 'bullish',  confidence: 86, task: 'RSI momentum breakout above 60 — strong continuation signal', lastUpdate: '30s ago' },
  { id: 25, name: 'Mean Reversion Specialist',  dept: 'STRATEGY',        icon: 'RefreshCw',        color: '#16A34A', signal: 'bearish',  confidence: 55, task: 'Price 2.1 std above mean — reversion risk increasing', lastUpdate: '1m ago' },
  { id: 26, name: 'Range Specialist',           dept: 'STRATEGY',        icon: 'Minus',            color: '#4ADE80', signal: 'neutral',  confidence: 60, task: 'Market in range $65k-$68k — breakout imminent either way', lastUpdate: '2m ago' },
  { id: 27, name: 'Scalping Expert',            dept: 'STRATEGY',        icon: 'Timer',            color: '#86EFAC', signal: 'bullish',  confidence: 70, task: 'Micro-structure bullish — 3 consecutive green 5m candles', lastUpdate: '8s ago' },
  { id: 28, name: 'Swing Specialist',           dept: 'STRATEGY',        icon: 'BarChart3',        color: '#BBF7D0', signal: 'bullish',  confidence: 78, task: 'Multi-day swing setup confirmed — target $70,500', lastUpdate: '4m ago' },
  { id: 29, name: 'Position Expert',            dept: 'STRATEGY',        icon: 'Target',           color: '#D1FAE5', signal: 'bullish',  confidence: 73, task: 'Long-term accumulation zone — adding to core position', lastUpdate: '6m ago' },
  // Execution
  { id: 30, name: 'Trade Planner',              dept: 'EXECUTION',       icon: 'ClipboardList',    color: '#06B6D4', signal: 'bullish',  confidence: 77, task: 'Optimal entry: limit order at $67,200 — 80% fill probability', lastUpdate: '1m ago' },
  { id: 31, name: 'Execution Bot',              dept: 'EXECUTION',       icon: 'Bot',              color: '#22D3EE', signal: 'neutral',  confidence: 0,  task: 'STANDBY — awaiting human approval before execution', lastUpdate: 'Live' },
  { id: 32, name: 'Liquidity Analyst',          dept: 'EXECUTION',       icon: 'Droplets',         color: '#67E8F9', signal: 'bullish',  confidence: 80, task: 'Order book depth healthy — $2.3M bid liquidity at entry', lastUpdate: '30s ago' },
  { id: 33, name: 'Exit Manager',               dept: 'EXECUTION',       icon: 'LogOut',           color: '#A5F3FC', signal: 'neutral',  confidence: 65, task: 'Planning 3-part exit: 50% at $68.5k, 30% at $69.2k, 20% trail', lastUpdate: '2m ago' },
  // Monitoring
  { id: 34, name: 'Performance Analyst',        dept: 'MONITORING',      icon: 'TrendingUp',       color: '#A855F7', signal: 'bullish',  confidence: 74, task: 'Win rate this week: 67% — Sharpe ratio 2.1', lastUpdate: '5m ago' },
  { id: 35, name: 'Journal AI',                 dept: 'MONITORING',      icon: 'BookOpen',         color: '#C084FC', signal: 'neutral',  confidence: 0,  task: 'Logging trade #1,247 — documenting pattern recognition notes', lastUpdate: '1m ago' },
  { id: 36, name: 'Learning Agent',             dept: 'MONITORING',      icon: 'GraduationCap',    color: '#E879F9', signal: 'neutral',  confidence: 0,  task: 'Training on last 30 days of trades — improving pattern weights', lastUpdate: '10m ago' },
  // Security
  { id: 37, name: 'Security Bot',               dept: 'SECURITY',        icon: 'Lock',             color: '#EF4444', signal: 'neutral',  confidence: 0,  task: 'All systems secure — monitoring for anomalous API activity', lastUpdate: '10s ago' },
  { id: 38, name: 'Emergency Bot',              dept: 'SECURITY',        icon: 'AlertTriangle',    color: '#F97316', signal: 'neutral',  confidence: 0,  task: 'No emergency conditions — circuit breakers armed and ready', lastUpdate: '5s ago' },
  // Coordination
  { id: 39, name: 'Debate Moderator',           dept: 'COORDINATION',    icon: 'MessageSquare',    color: '#94A3B8', signal: 'bullish',  confidence: 74, task: 'Moderating round 2 of 3 — 6 agents still debating entry', lastUpdate: '20s ago' },
  { id: 40, name: 'Consensus Engine',           dept: 'COORDINATION',    icon: 'Network',          color: '#CBD5E1', signal: 'bullish',  confidence: 72, task: 'Aggregating 38 agent votes — consensus forming: BULLISH', lastUpdate: '15s ago' },
];

/* ── Signal config ───────────────────────────────────── */
const SIGNAL_COLORS: Record<Signal, { color: string; bg: string; label: string }> = {
  bullish: { color: '#22C55E', bg: 'rgba(34,197,94,0.12)', label: 'BULLISH' },
  bearish: { color: '#EF4444', bg: 'rgba(239,68,68,0.12)', label: 'BEARISH' },
  neutral: { color: '#F59E0B', bg: 'rgba(245,158,11,0.1)', label: 'NEUTRAL' },
};

/* ── Confidence bar (animated on first view) ─────────── */
function ConfidenceBar({ pct, color, inView }: { pct: number; color: string; inView: boolean }) {
  return (
    <div style={{ height: 4, background: 'rgba(255,255,255,0.06)', borderRadius: 2, overflow: 'hidden', marginTop: 4 }}>
      <motion.div
        initial={{ width: 0 }}
        animate={inView ? { width: `${pct}%` } : { width: 0 }}
        transition={{ duration: 0.9, ease: [0.25, 1, 0.5, 1] }}
        style={{ height: '100%', borderRadius: 2, background: `linear-gradient(90deg, ${color}80, ${color})`, boxShadow: `0 0 6px ${color}66` }}
      />
    </div>
  );
}

/* ── Single agent card ───────────────────────────────── */
function AgentCard({ agent, index }: { agent: Agent; index: number }) {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: '0px 0px -40px 0px' });
  const Icon = getIcon(agent.icon);
  const sig = SIGNAL_COLORS[agent.signal];
  const isStandby = agent.confidence === 0;

  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, y: 20 }}
      animate={inView ? { opacity: 1, y: 0 } : { opacity: 0, y: 20 }}
      transition={{ duration: 0.45, delay: index * 0.03, ease: [0.25, 1, 0.5, 1] }}
      whileHover={{
        y: -2,
        borderColor: `${agent.color}44`,
        boxShadow: `0 8px 32px ${agent.color}18, 0 2px 8px rgba(0,0,0,0.4)`,
      }}
      style={{
        background: '#121826',
        border: '1px solid rgba(255,255,255,0.06)',
        borderRadius: 12,
        padding: '14px 14px 12px',
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
        cursor: 'default',
        transition: 'border-color 0.2s, box-shadow 0.2s',
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      {/* Subtle dept color corner glow */}
      <div style={{ position: 'absolute', top: 0, left: 0, width: 60, height: 60, background: `radial-gradient(circle at 0 0, ${agent.color}12 0%, transparent 70%)`, pointerEvents: 'none' }} />

      {/* Top row: dept badge + timestamp */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
          {/* Status dot */}
          {isStandby ? (
            <div style={{ width: 6, height: 6, borderRadius: '50%', background: '#475569' }} />
          ) : (
            <motion.div
              animate={{ opacity: [1, 0.3, 1], scale: [1, 1.3, 1] }}
              transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut', delay: index * 0.07 }}
              style={{ width: 6, height: 6, borderRadius: '50%', background: '#22C55E', boxShadow: '0 0 6px rgba(34,197,94,0.8)' }}
            />
          )}
          <span style={{
            fontSize: 9,
            fontWeight: 700,
            color: agent.color,
            textTransform: 'uppercase',
            letterSpacing: '0.08em',
            background: `${agent.color}18`,
            padding: '2px 6px',
            borderRadius: 4,
            border: `1px solid ${agent.color}30`,
          }}>
            {agent.dept}
          </span>
        </div>
        <span style={{ fontSize: 9, color: '#475569', fontFamily: 'JetBrains Mono, monospace' }}>{agent.lastUpdate}</span>
      </div>

      {/* Agent name + icon */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <div style={{
          width: 30,
          height: 30,
          borderRadius: 8,
          background: `${agent.color}18`,
          border: `1px solid ${agent.color}30`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexShrink: 0,
        }}>
          <Icon size={14} color={agent.color} />
        </div>
        <span style={{ fontSize: 13, fontWeight: 700, color: '#F1F5F9', lineHeight: 1.3 }}>{agent.name}</span>
      </div>

      {/* Task description */}
      <p style={{
        fontSize: 11,
        color: '#64748B',
        fontStyle: 'italic',
        lineHeight: 1.5,
        display: '-webkit-box',
        WebkitLineClamp: 2,
        WebkitBoxOrient: 'vertical',
        overflow: 'hidden',
        margin: 0,
      }}>
        {agent.task}
      </p>

      {/* Signal + confidence */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 2 }}>
        <span style={{
          fontSize: 9,
          fontWeight: 800,
          color: sig.color,
          background: sig.bg,
          border: `1px solid ${sig.color}30`,
          borderRadius: 4,
          padding: '2px 7px',
          letterSpacing: '0.08em',
        }}>
          {isStandby ? 'STANDBY' : sig.label}
        </span>
        {!isStandby && (
          <span style={{ fontSize: 10, fontWeight: 700, color: sig.color, fontFamily: 'JetBrains Mono, monospace' }}>
            {agent.confidence}%
          </span>
        )}
      </div>

      {/* Confidence bar */}
      {!isStandby ? (
        <ConfidenceBar pct={agent.confidence} color={sig.color} inView={inView} />
      ) : (
        <div style={{ height: 4, background: 'rgba(255,255,255,0.04)', borderRadius: 2 }}>
          <div style={{ width: '100%', height: '100%', borderRadius: 2, background: 'repeating-linear-gradient(90deg, rgba(255,255,255,0.04) 0px, rgba(255,255,255,0.04) 4px, transparent 4px, transparent 8px)' }} />
        </div>
      )}
    </motion.div>
  );
}

/* ── Main component ──────────────────────────────────── */
export default function AgentWorkers() {
  return (
    <div>
      {/* Section header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
        <motion.div
          animate={{ opacity: [1, 0.2, 1], scale: [1, 1.4, 1] }}
          transition={{ duration: 1.6, repeat: Infinity, ease: 'easeInOut' }}
          style={{ width: 9, height: 9, borderRadius: '50%', background: '#22C55E', boxShadow: '0 0 10px rgba(34,197,94,0.8)' }}
        />
        <h2 style={{
          fontSize: 13,
          fontWeight: 800,
          color: '#94A3B8',
          textTransform: 'uppercase',
          letterSpacing: '0.14em',
        }}>
          Intelligence Network —{' '}
          <span style={{ color: '#22C55E' }}>40 Active Agents</span>
        </h2>
        <div style={{ flex: 1, height: 1, background: 'linear-gradient(90deg, rgba(255,255,255,0.06) 0%, transparent 100%)' }} />
        <span style={{ fontSize: 10, color: '#475569', fontFamily: 'JetBrains Mono, monospace' }}>
          {AGENTS.filter(a => a.signal === 'bullish').length} BULLISH ·{' '}
          {AGENTS.filter(a => a.signal === 'bearish').length} BEARISH ·{' '}
          {AGENTS.filter(a => a.signal === 'neutral').length} NEUTRAL
        </span>
      </div>

      {/* Agent grid */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(4, 1fr)',
          gap: 10,
        }}
        className="agent-grid"
      >
        {AGENTS.map((agent, i) => (
          <AgentCard key={agent.id} agent={agent} index={i} />
        ))}
      </div>

      <style>{`
        @media (max-width: 1280px) { .agent-grid { grid-template-columns: repeat(3, 1fr) !important; } }
        @media (max-width: 900px)  { .agent-grid { grid-template-columns: repeat(2, 1fr) !important; } }
        @media (max-width: 560px)  { .agent-grid { grid-template-columns: repeat(1, 1fr) !important; } }
      `}</style>
    </div>
  );
}
