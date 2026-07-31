'use client';

import React, { useState, useEffect } from 'react';
import { AgentState, MOCK_AGENTS, api } from '../lib/api';
import { useAgentActivityWS } from '../hooks/useWebSocket';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

// ─── Agent Registry ───────────────────────────────────────────────────────────

interface AgentInfo {
  name: string;
  dept: string;
  initials: string;
}

const AGENT_REGISTRY: Record<string, AgentInfo> = {
  cio_agent:           { name: 'Chief Investment Officer', dept: 'EXECUTIVE',     initials: 'CIO' },
  cro_agent:           { name: 'Chief Risk Officer',       dept: 'EXECUTIVE',     initials: 'CRO' },
  portfolio_manager:   { name: 'Portfolio Manager',        dept: 'EXECUTIVE',     initials: 'PM'  },
  macro_economist:     { name: 'Macro Economist',          dept: 'INTELLIGENCE',  initials: 'ME'  },
  news_analyst:        { name: 'News Analyst',             dept: 'INTELLIGENCE',  initials: 'NA'  },
  sentiment_analyst:   { name: 'Sentiment Analyst',        dept: 'INTELLIGENCE',  initials: 'SA'  },
  regulation_analyst:  { name: 'Regulation Analyst',       dept: 'INTELLIGENCE',  initials: 'RA'  },
  trend_analyst:       { name: 'Trend Analyst',            dept: 'TECHNICAL',     initials: 'TA'  },
  price_action:        { name: 'Price Action Expert',      dept: 'TECHNICAL',     initials: 'PA'  },
  smc_expert:          { name: 'SMC Expert',               dept: 'TECHNICAL',     initials: 'SC'  },
  wyckoff_analyst:     { name: 'Wyckoff Analyst',          dept: 'TECHNICAL',     initials: 'WA'  },
  elliott_wave:        { name: 'Elliott Wave Analyst',     dept: 'TECHNICAL',     initials: 'EW'  },
  volume_profile:      { name: 'Volume Profile Analyst',   dept: 'TECHNICAL',     initials: 'VP'  },
  market_structure:    { name: 'Market Structure',         dept: 'TECHNICAL',     initials: 'MS'  },
  quant_researcher:    { name: 'Quant Researcher',         dept: 'QUANT',         initials: 'QR'  },
  probability_analyst: { name: 'Probability Analyst',      dept: 'QUANT',         initials: 'PR'  },
  ml_researcher:       { name: 'ML Researcher',            dept: 'QUANT',         initials: 'ML'  },
  backtesting_expert:  { name: 'Backtesting Expert',       dept: 'QUANT',         initials: 'BT'  },
  hf_pattern_detector: { name: 'HF Pattern Detector',      dept: 'QUANT',         initials: 'HF'  },
  options_flow_analyst:{ name: 'Options Flow Analyst',     dept: 'OPTIONS',       initials: 'OF'  },
  volatility_analyst:  { name: 'Volatility Analyst',       dept: 'OPTIONS',       initials: 'VA'  },
  onchain_analyst:     { name: 'On-Chain Analyst',         dept: 'CRYPTO',        initials: 'OC'  },
  funding_rate_analyst:{ name: 'Funding Rate Analyst',     dept: 'CRYPTO',        initials: 'FR'  },
  momentum_trader:     { name: 'Momentum Trader',          dept: 'STRATEGY',      initials: 'MT'  },
  mean_reversion:      { name: 'Mean Reversion',           dept: 'STRATEGY',      initials: 'MR'  },
  range_specialist:    { name: 'Range Specialist',         dept: 'STRATEGY',      initials: 'RS'  },
  scalping_expert:     { name: 'Scalping Expert',          dept: 'STRATEGY',      initials: 'SE'  },
  swing_specialist:    { name: 'Swing Specialist',         dept: 'STRATEGY',      initials: 'SW'  },
  position_expert:     { name: 'Position Expert',          dept: 'STRATEGY',      initials: 'PE'  },
  trade_planner:       { name: 'Trade Planner',            dept: 'EXECUTION',     initials: 'TP'  },
  execution_bot:       { name: 'Execution Bot',            dept: 'EXECUTION',     initials: 'EB'  },
  liquidity_analyst:   { name: 'Liquidity Analyst',        dept: 'EXECUTION',     initials: 'LA'  },
  exit_manager:        { name: 'Exit Manager',             dept: 'EXECUTION',     initials: 'EM'  },
  performance_analyst: { name: 'Performance Analyst',      dept: 'MONITORING',    initials: 'PF'  },
  journal_ai:          { name: 'AI Journal',               dept: 'MONITORING',    initials: 'AJ'  },
  learning_agent:      { name: 'Learning Agent',           dept: 'MONITORING',    initials: 'LA'  },
  security_bot:        { name: 'Security Bot',             dept: 'SECURITY',      initials: 'SB'  },
  emergency_bot:       { name: 'Emergency Bot',            dept: 'SECURITY',      initials: 'EB'  },
  debate_moderator:    { name: 'Debate Moderator',         dept: 'COORDINATION',  initials: 'DM'  },
  consensus_engine:    { name: 'Consensus Engine',         dept: 'COORDINATION',  initials: 'CE'  },
};

const DEPT_COLORS: Record<string, string> = {
  EXECUTIVE:    '#8B5CF6',
  INTELLIGENCE: '#06B6D4',
  TECHNICAL:    '#3B82F6',
  QUANT:        '#6366F1',
  STRATEGY:     '#22C55E',
  CRYPTO:       '#F59E0B',
  OPTIONS:      '#F97316',
  EXECUTION:    '#F43F5E',
  MONITORING:   '#64748B',
  SECURITY:     '#EF4444',
  COORDINATION: '#7C3AED',
};

const DEPT_TABS = ['ALL', 'TECHNICAL', 'QUANT', 'STRATEGY', 'CRYPTO', 'INTELLIGENCE'];

// ─── Mini agent card ──────────────────────────────────────────────────────────

function AgentMiniCard({ agent }: { agent: AgentState }) {
  const info = AGENT_REGISTRY[agent.agent_id];
  const dept = info?.dept ?? agent.department.toUpperCase();
  const initials = info?.initials ?? agent.display_name.slice(0, 2).toUpperCase();
  const name = info?.name ?? agent.display_name;
  const deptColor = DEPT_COLORS[dept] ?? '#6B6B7A';

  const isUp = agent.signal === 'bullish';
  const isDown = agent.signal === 'bearish';
  const sigColor = isUp ? '#22C55E' : isDown ? '#EF4444' : '#6B6B7A';
  const Icon = isUp ? TrendingUp : isDown ? TrendingDown : Minus;

  const statusDotColor =
    agent.status === 'analyzing' ? '#22C55E' : agent.status === 'debating' ? '#F59E0B' : '#374151';

  const confColor = agent.confidence >= 70 ? '#22C55E' : agent.confidence >= 50 ? '#F59E0B' : '#EF4444';

  return (
    <div
      className="rounded-xl border p-3 cursor-default select-none card-hover"
      style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}
    >
      {/* Header row */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          {/* Avatar */}
          <div
            className="w-7 h-7 rounded-lg flex items-center justify-center text-[10px] font-bold shrink-0"
            style={{ background: `${deptColor}20`, color: deptColor }}
          >
            {initials}
          </div>
          {/* Name */}
          <div className="min-w-0">
            <div className="text-xs font-medium text-white truncate leading-tight" style={{ maxWidth: 80 }}>
              {name.split(' ')[0]}
            </div>
            <div className="text-[9px]" style={{ color: deptColor }}>{dept}</div>
          </div>
        </div>
        {/* Status dot */}
        <span
          className="w-2 h-2 rounded-full shrink-0"
          style={{
            background: statusDotColor,
            boxShadow: agent.status !== 'idle' ? `0 0 6px ${statusDotColor}` : undefined,
          }}
        />
      </div>

      {/* Signal */}
      <div className="flex items-center gap-1 mb-2">
        <Icon className="w-3 h-3" style={{ color: sigColor }} />
        <span className="text-xs font-semibold" style={{ color: sigColor }}>
          {isUp ? 'Bullish' : isDown ? 'Bearish' : 'Neutral'}
        </span>
        <span className="text-xs font-mono ml-auto" style={{ color: confColor }}>
          {agent.confidence}%
        </span>
      </div>

      {/* Confidence bar */}
      <div className="h-1 rounded-full bg-white/5">
        <div
          className="h-full rounded-full transition-all duration-700"
          style={{ width: `${agent.confidence}%`, background: confColor }}
        />
      </div>

      {/* Reasoning snippet */}
      {agent.last_message && (
        <div className="text-[9px] text-[#6B6B7A] mt-2 truncate leading-tight">
          {agent.last_message}
        </div>
      )}
    </div>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────

export default function AgentGrid() {
  const [agents, setAgents] = useState<AgentState[]>(MOCK_AGENTS);
  const [filter, setFilter] = useState('ALL');
  const [showAll, setShowAll] = useState(false);

  useEffect(() => {
    api.agents.getAll()
      .then((data) => { if (data && data.length > 0) setAgents(data); })
      .catch(() => {});
  }, []);

  useAgentActivityWS((msg) => {
    if (msg.type === 'agent_update' && msg.agent_id) {
      setAgents((prev) =>
        prev.map((a) =>
          a.agent_id === msg.agent_id
            ? {
                ...a,
                status: (msg.status as AgentState['status']) ?? a.status,
                signal: (msg.signal as AgentState['signal']) ?? a.signal,
                confidence: msg.confidence ?? a.confidence,
                last_message: msg.message ?? a.last_message,
              }
            : a,
        ),
      );
    }
  });

  const filtered = filter === 'ALL'
    ? agents
    : agents.filter((a) => {
        const info = AGENT_REGISTRY[a.agent_id];
        const dept = info?.dept ?? a.department.toUpperCase();
        return dept === filter;
      });

  const displayed = showAll ? filtered : filtered.slice(0, 12);

  const bullCount = agents.filter((a) => a.signal === 'bullish').length;
  const bearCount = agents.filter((a) => a.signal === 'bearish').length;

  return (
    <div className="flex flex-col gap-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="text-xs font-semibold text-[#9B9BAA] uppercase tracking-wide">Agent Network</div>
          <div className="text-[10px] text-[#6B6B7A] mt-0.5">
            <span className="text-emerald-400">{bullCount} bull</span>
            <span className="text-[#6B6B7A] mx-1">·</span>
            <span className="text-red-400">{bearCount} bear</span>
            <span className="text-[#6B6B7A] mx-1">·</span>
            <span className="text-[#9B9BAA]">{agents.length} total</span>
          </div>
        </div>
      </div>

      {/* Filter tabs */}
      <div className="flex gap-1 overflow-x-auto">
        {DEPT_TABS.map((tab) => (
          <button
            key={tab}
            onClick={() => setFilter(tab)}
            className="shrink-0 px-2.5 py-1 rounded-lg text-[10px] font-medium transition-all"
            style={{
              background: filter === tab ? 'rgba(139,92,246,0.15)' : 'rgba(255,255,255,0.04)',
              color: filter === tab ? '#8B5CF6' : '#6B6B7A',
              border: `1px solid ${filter === tab ? 'rgba(139,92,246,0.3)' : 'rgba(255,255,255,0.06)'}`,
            }}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Grid */}
      <div className="grid grid-cols-2 gap-2">
        {displayed.map((agent) => (
          <AgentMiniCard key={agent.agent_id} agent={agent} />
        ))}
      </div>

      {/* Show all toggle */}
      {filtered.length > 12 && (
        <button
          onClick={() => setShowAll((v) => !v)}
          className="text-xs text-[#8B5CF6] text-center py-1 hover:underline transition-all"
        >
          {showAll ? 'Show less' : `View all ${filtered.length} agents →`}
        </button>
      )}
    </div>
  );
}
