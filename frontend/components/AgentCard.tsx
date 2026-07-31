'use client';

import React from 'react';
import { AgentState } from '../lib/api';

interface AgentCardProps {
  agent: AgentState;
}

const DEPT_COLORS: Record<string, string> = {
  executive:          '#fbbf24',
  market_intelligence:'#60a5fa',
  technical:          '#22d3ee',
  quantitative:       '#c084fc',
  options:            '#f472b6',
  crypto:             '#fb923c',
  strategy:           '#4ade80',
  execution:          '#2dd4bf',
  monitoring:         '#818cf8',
  security:           '#f87171',
  coordination:       '#fbbf24',
};

const DEPT_LABELS: Record<string, string> = {
  executive:          'EXECUTIVE',
  market_intelligence:'MKT-INTEL',
  technical:          'TECHNICAL',
  quantitative:       'QUANTITATIVE',
  options:            'OPTIONS',
  crypto:             'CRYPTO',
  strategy:           'STRATEGY',
  execution:          'EXECUTION',
  monitoring:         'MONITORING',
  security:           'SECURITY',
  coordination:       'COORDINATION',
};

function StatusBadge({ status }: { status: AgentState['status'] }) {
  if (status === 'idle') {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] bg-[#1a1a1a] text-[#555555] border border-[#222222]">
        <span className="w-1.5 h-1.5 rounded-full bg-[#333333]" />
        IDLE
      </span>
    );
  }
  if (status === 'analyzing') {
    return (
      <span className="status-analyzing inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] bg-[#001833] text-[#00aaff] border border-[#003366]">
        <span className="w-1.5 h-1.5 rounded-full bg-[#00aaff] animate-pulse" />
        ANALYZING
      </span>
    );
  }
  return (
    <span className="status-debating inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] bg-[#1a1000] text-[#ffb000] border border-[#332200]">
      <span className="w-1.5 h-1.5 rounded-full bg-[#ffb000] animate-pulse" />
      DEBATING
    </span>
  );
}

function SignalIndicator({ signal }: { signal: AgentState['signal'] }) {
  if (signal === 'bullish') {
    return <span className="text-[11px] font-bold text-[#00ff41]">▲ BULLISH</span>;
  }
  if (signal === 'bearish') {
    return <span className="text-[11px] font-bold text-[#ff2222]">▼ BEARISH</span>;
  }
  return <span className="text-[11px] font-bold text-[#555555]">— NEUTRAL</span>;
}

export default function AgentCard({ agent }: AgentCardProps) {
  const deptColor = DEPT_COLORS[agent.department] || '#666666';
  const deptLabel = DEPT_LABELS[agent.department] || agent.department.toUpperCase();

  const confColor =
    agent.signal === 'bullish' ? '#00ff41' : agent.signal === 'bearish' ? '#ff2222' : '#444444';

  return (
    <div className="agent-card bg-[#111111] border border-[#1a1a1a] rounded p-3 cursor-default select-none hover:border-[#333333] transition-all duration-200">
      {/* Department tag */}
      <div
        className="text-[8px] font-bold uppercase tracking-widest mb-1.5 px-1.5 py-0.5 rounded inline-block"
        style={{ color: deptColor, backgroundColor: deptColor + '15', border: `1px solid ${deptColor}30` }}
      >
        {deptLabel}
      </div>

      {/* Agent name */}
      <div className="text-[#cccccc] text-xs font-semibold leading-tight mb-2 truncate" title={agent.display_name}>
        {agent.display_name}
      </div>

      {/* Status */}
      <div className="mb-2">
        <StatusBadge status={agent.status} />
      </div>

      {/* Signal */}
      <div className="mb-2">
        <SignalIndicator signal={agent.signal} />
      </div>

      {/* Confidence bar */}
      <div>
        <div className="flex justify-between text-[9px] mb-1">
          <span className="text-[#333333]">CONFIDENCE</span>
          <span style={{ color: confColor }}>{agent.confidence}%</span>
        </div>
        <div className="h-1 bg-[#1a1a1a] rounded-full overflow-hidden">
          <div
            className="h-full rounded-full confidence-bar"
            style={{ width: `${agent.confidence}%`, backgroundColor: confColor }}
          />
        </div>
      </div>
    </div>
  );
}
