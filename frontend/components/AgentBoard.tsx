'use client';

import React, { useState, useEffect } from 'react';
import AgentCard from './AgentCard';
import { AgentState, MOCK_AGENTS, api } from '../lib/api';
import { useAgentActivityWS } from '../hooks/useWebSocket';

// ─── Department definitions ───────────────────────────────────────────────────

interface Department {
  key: string;
  label: string;
  agentIds: string[];
}

const DEPARTMENTS: Department[] = [
  {
    key: 'executive',
    label: 'EXECUTIVE',
    agentIds: ['cio_agent', 'cro_agent', 'portfolio_manager'],
  },
  {
    key: 'market_intelligence',
    label: 'MARKET INTELLIGENCE',
    agentIds: ['macro_economist', 'news_analyst', 'sentiment_analyst', 'regulation_analyst'],
  },
  {
    key: 'technical',
    label: 'TECHNICAL ANALYSIS',
    agentIds: [
      'trend_analyst',
      'price_action',
      'smc_expert',
      'wyckoff_analyst',
      'elliott_wave',
      'volume_profile',
      'market_structure',
    ],
  },
  {
    key: 'quantitative',
    label: 'QUANTITATIVE',
    agentIds: [
      'quant_researcher',
      'probability_analyst',
      'ml_researcher',
      'backtesting_expert',
      'hf_pattern_detector',
    ],
  },
  {
    key: 'options',
    label: 'OPTIONS',
    agentIds: ['options_flow_analyst', 'volatility_analyst'],
  },
  {
    key: 'crypto',
    label: 'CRYPTO SPECIALIST',
    agentIds: ['onchain_analyst', 'funding_rate_analyst'],
  },
  {
    key: 'strategy',
    label: 'STRATEGY',
    agentIds: [
      'momentum_trader',
      'mean_reversion',
      'range_specialist',
      'scalping_expert',
      'swing_specialist',
      'position_expert',
    ],
  },
  {
    key: 'execution',
    label: 'EXECUTION',
    agentIds: ['trade_planner', 'execution_bot', 'liquidity_analyst', 'exit_manager'],
  },
  {
    key: 'monitoring',
    label: 'MONITORING',
    agentIds: ['performance_analyst', 'journal_ai', 'learning_agent'],
  },
  {
    key: 'security',
    label: 'SECURITY',
    agentIds: ['security_bot', 'emergency_bot'],
  },
  {
    key: 'coordination',
    label: 'COORDINATION',
    agentIds: ['debate_moderator', 'consensus_engine'],
  },
];

const DEPT_COLORS: Record<string, string> = {
  executive:           '#fbbf24',
  market_intelligence: '#60a5fa',
  technical:           '#22d3ee',
  quantitative:        '#c084fc',
  options:             '#f472b6',
  crypto:              '#fb923c',
  strategy:            '#4ade80',
  execution:           '#2dd4bf',
  monitoring:          '#818cf8',
  security:            '#f87171',
  coordination:        '#fbbf24',
};

// ─── DepartmentSection ────────────────────────────────────────────────────────

function DepartmentSection({
  dept,
  agents,
}: {
  dept: Department;
  agents: AgentState[];
}) {
  const color = DEPT_COLORS[dept.key] || '#555555';
  const bullCount = agents.filter((a) => a.signal === 'bullish').length;
  const bearCount = agents.filter((a) => a.signal === 'bearish').length;

  return (
    <div className="mb-6">
      {/* Department header */}
      <div className="flex items-center gap-3 mb-2">
        <div
          className="h-px flex-1"
          style={{ backgroundColor: color + '30' }}
        />
        <div className="flex items-center gap-2">
          <span
            className="text-[10px] font-bold uppercase tracking-widest"
            style={{ color }}
          >
            {dept.label}
          </span>
          <span className="text-[9px] text-[#333333]">
            ({agents.length} agents)
          </span>
          {bullCount > 0 && (
            <span className="text-[9px] text-[#00ff41]">▲{bullCount}</span>
          )}
          {bearCount > 0 && (
            <span className="text-[9px] text-[#ff2222]">▼{bearCount}</span>
          )}
        </div>
        <div
          className="h-px flex-1"
          style={{ backgroundColor: color + '30' }}
        />
      </div>

      {/* Agent cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 gap-2">
        {agents.map((agent) => (
          <AgentCard key={agent.agent_id} agent={agent} />
        ))}
      </div>
    </div>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────

export default function AgentBoard() {
  const [agents, setAgents] = useState<AgentState[]>(MOCK_AGENTS);

  useEffect(() => {
    api.agents
      .getAll()
      .then((data) => {
        if (data && data.length > 0) setAgents(data);
      })
      .catch(() => {
        // fallback to mock data
      });
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

  const agentMap = new Map(agents.map((a) => [a.agent_id, a]));

  const bullCount = agents.filter((a) => a.signal === 'bullish').length;
  const bearCount = agents.filter((a) => a.signal === 'bearish').length;
  const analyzingCount = agents.filter((a) => a.status === 'analyzing').length;
  const debatingCount = agents.filter((a) => a.status === 'debating').length;

  return (
    <div>
      {/* ── SECTION HEADER ───────────────────────────────────────────────── */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-sm font-bold tracking-widest text-[#00ff41]">
            AGENT BOARD — ALL 40 AGENTS
          </h2>
          <p className="text-[10px] text-[#444444] mt-0.5">
            Multi-model consensus engine grouped by department
          </p>
        </div>
        <div className="flex items-center gap-5 text-xs font-mono">
          <span>
            <span className="text-[#444444]">BULL: </span>
            <span className="text-[#00ff41] font-bold">{bullCount}</span>
          </span>
          <span>
            <span className="text-[#444444]">BEAR: </span>
            <span className="text-[#ff2222] font-bold">{bearCount}</span>
          </span>
          <span>
            <span className="text-[#444444]">ANALYZING: </span>
            <span className="text-[#00aaff] font-bold">{analyzingCount}</span>
          </span>
          <span>
            <span className="text-[#444444]">DEBATING: </span>
            <span className="text-[#ffb000] font-bold">{debatingCount}</span>
          </span>
        </div>
      </div>

      {/* ── DEPARTMENTS ──────────────────────────────────────────────────── */}
      {DEPARTMENTS.map((dept) => {
        const deptAgents = dept.agentIds
          .map((id) => agentMap.get(id))
          .filter((a): a is AgentState => a !== undefined);

        // If backend returned agents not in our list, append them to their dept
        const extraAgents = agents.filter(
          (a) => a.department === dept.key && !dept.agentIds.includes(a.agent_id),
        );
        const allDeptAgents = [...deptAgents, ...extraAgents];

        if (allDeptAgents.length === 0) return null;

        return (
          <DepartmentSection
            key={dept.key}
            dept={dept}
            agents={allDeptAgents}
          />
        );
      })}
    </div>
  );
}
