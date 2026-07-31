'use client';

import React, { useState, useEffect, useRef } from 'react';
import { useAgentActivityWS } from '../hooks/useWebSocket';

// ─── Types ────────────────────────────────────────────────────────────────────

interface ChatMessage {
  id: string;
  agent_id: string;
  agent_name: string;
  department: string;
  message: string;
  signal?: 'bullish' | 'bearish' | 'neutral';
  confidence?: number;
  timestamp: string;
  type?: 'debate_message' | 'system' | 'agent_update';
}

// ─── Mock data ────────────────────────────────────────────────────────────────

const MOCK_MESSAGES: ChatMessage[] = [
  {
    id: 'msg_001',
    agent_id: 'trend_analyst',
    agent_name: 'Trend Analyst',
    department: 'technical',
    message: 'RSI showing strong momentum on 1H chart. EMA 20 above EMA 50 — bullish crossover confirmed. Price action above VWAP. Bias: BULLISH.',
    signal: 'bullish',
    confidence: 85,
    timestamp: new Date(Date.now() - 60000).toISOString(),
  },
  {
    id: 'msg_002',
    agent_id: 'macro_economist',
    agent_name: 'Macro Economist',
    department: 'market_intelligence',
    message: 'Fed minutes indicate potential rate pause. DXY weakening — favorable for risk assets. Global liquidity expanding. Supports upside thesis.',
    signal: 'bullish',
    confidence: 72,
    timestamp: new Date(Date.now() - 95000).toISOString(),
  },
  {
    id: 'msg_003',
    agent_id: 'debate_moderator',
    agent_name: 'Debate Moderator',
    department: 'coordination',
    message: '── ROUND 2 STARTING ── Bull side has established momentum thesis. Bear side: please address macro concern and provide rebuttal.',
    type: 'system',
    timestamp: new Date(Date.now() - 120000).toISOString(),
  },
  {
    id: 'msg_004',
    agent_id: 'volatility_analyst',
    agent_name: 'Volatility Analyst',
    department: 'options',
    message: 'IV rank at 34%. Put/call ratio elevated at 1.32 — options market is hedging. Funding rate at +0.045% signals overleveraged longs. Cautious near-term.',
    signal: 'bearish',
    confidence: 66,
    timestamp: new Date(Date.now() - 160000).toISOString(),
  },
  {
    id: 'msg_005',
    agent_id: 'smc_expert',
    agent_name: 'SMC Expert',
    department: 'technical',
    message: 'Order block at $66,800–$67,100 holding strong. Liquidity sweep confirmed below $66,500. Smart money accumulation phase detected above this zone.',
    signal: 'bullish',
    confidence: 78,
    timestamp: new Date(Date.now() - 200000).toISOString(),
  },
  {
    id: 'msg_006',
    agent_id: 'quant_researcher',
    agent_name: 'Quantitative Researcher',
    department: 'quantitative',
    message: 'Statistical edge confirmed: 78.3% win rate on 500 backtested instances of this setup. Expected value: +2.34R. Z-score 2.1 — statistically significant.',
    signal: 'bullish',
    confidence: 88,
    timestamp: new Date(Date.now() - 250000).toISOString(),
  },
  {
    id: 'msg_007',
    agent_id: 'onchain_analyst',
    agent_name: 'On-Chain Analyst',
    department: 'crypto',
    message: 'Exchange outflows accelerating: 42,000 BTC withdrawn in past 24h. Long-term holder SOPR bullish divergence. Accumulation wallets growing.',
    signal: 'bullish',
    confidence: 72,
    timestamp: new Date(Date.now() - 300000).toISOString(),
  },
  {
    id: 'msg_008',
    agent_id: 'cro_agent',
    agent_name: 'Chief Risk Officer',
    department: 'executive',
    message: 'Portfolio exposure at 28% of NAV. Risk parameters nominal. Max position size for this setup: 2.5% NAV. Stop-loss mandatory at $65,800. Approved.',
    signal: 'neutral',
    confidence: 90,
    timestamp: new Date(Date.now() - 350000).toISOString(),
  },
  {
    id: 'msg_009',
    agent_id: 'debate_moderator',
    agent_name: 'Debate Moderator',
    department: 'coordination',
    message: '── CONSENSUS ROUND 3 COMPLETE ── Bull faction: 31/40 agents. Bear faction: 6/40. Neutral: 3/40. Threshold met (≥75%). Proceeding to signal generation.',
    type: 'system',
    timestamp: new Date(Date.now() - 380000).toISOString(),
  },
  {
    id: 'msg_010',
    agent_id: 'consensus_engine',
    agent_name: 'Consensus Engine',
    department: 'coordination',
    message: 'SIGNAL GENERATED: BTC/USDT LONG. Entry: $67,200–$67,600. Stop: $65,800. Target: $71,500. Consensus: 78%. Awaiting human approval.',
    signal: 'bullish',
    confidence: 78,
    timestamp: new Date(Date.now() - 400000).toISOString(),
  },
];

// ─── Colors ───────────────────────────────────────────────────────────────────

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

const DEPT_ICONS: Record<string, string> = {
  executive:           '👑',
  market_intelligence: '🔵',
  technical:           '🔷',
  quantitative:        '🟣',
  options:             '🟡',
  crypto:              '🟠',
  strategy:            '🟢',
  execution:           '⚡',
  monitoring:          '📊',
  security:            '🔴',
  coordination:        '🟡',
};

// ─── Helpers ──────────────────────────────────────────────────────────────────

function fmtTime(iso: string): string {
  return new Date(iso).toLocaleTimeString('en-US', {
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

// ─── MessageRow ───────────────────────────────────────────────────────────────

function MessageRow({ msg }: { msg: ChatMessage }) {
  const isSystem = msg.type === 'system' || msg.department === 'coordination';
  const deptColor = DEPT_COLORS[msg.department] || '#666666';
  const icon = DEPT_ICONS[msg.department] || '⬤';

  const signalLabel =
    msg.signal === 'bullish'
      ? '▲ BULLISH'
      : msg.signal === 'bearish'
      ? '▼ BEARISH'
      : null;

  const signalColor = msg.signal === 'bullish' ? '#00ff41' : '#ff2222';

  if (isSystem) {
    return (
      <div className="border-b border-[#141414] py-2 px-4 bg-[#0e0e0e]">
        <div className="flex items-center gap-2 text-[10px]">
          <span className="text-[#333333]">[{fmtTime(msg.timestamp)}]</span>
          <span style={{ color: '#ffb000' }} className="font-bold">
            🟡 {msg.agent_name.toUpperCase()}
          </span>
        </div>
        <div className="mt-1 text-xs text-[#ffb000] pl-1 border-l-2 border-[#332200] ml-2">
          {msg.message}
        </div>
      </div>
    );
  }

  return (
    <div className="border-b border-[#141414] py-2.5 px-4 hover:bg-[#111111] transition-colors">
      {/* Header row */}
      <div className="flex items-center gap-2 mb-1">
        <span className="text-[10px] text-[#333333] font-mono shrink-0">[{fmtTime(msg.timestamp)}]</span>
        <span className="text-sm shrink-0">{icon}</span>
        <span
          className="text-xs font-bold uppercase tracking-wider shrink-0"
          style={{ color: deptColor }}
        >
          {msg.agent_name.toUpperCase()}
        </span>
        {signalLabel && (
          <>
            <span className="text-[#333333]">→</span>
            <span className="font-bold text-xs" style={{ color: signalColor }}>
              {signalLabel}
            </span>
            {msg.confidence !== undefined && (
              <span className="text-[10px] text-[#444444]">({msg.confidence / 100})</span>
            )}
          </>
        )}
      </div>

      {/* Message body */}
      <div
        className="text-xs text-[#888888] leading-relaxed pl-6"
        style={{ borderLeft: `2px solid ${deptColor}20` }}
      >
        &ldquo;{msg.message}&rdquo;
      </div>
    </div>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────

export default function AgentChatFeed() {
  const [messages, setMessages] = useState<ChatMessage[]>(MOCK_MESSAGES);
  const [autoScroll, setAutoScroll] = useState(true);
  const scrollRef = useRef<HTMLDivElement>(null);
  const counterRef = useRef(1000);

  const { status } = useAgentActivityWS((wsMsg) => {
    if (
      (wsMsg.type === 'debate_message' || wsMsg.type === 'agent_update') &&
      wsMsg.message &&
      wsMsg.agent_id
    ) {
      const newMsg: ChatMessage = {
        id: `ws_${++counterRef.current}`,
        agent_id: wsMsg.agent_id,
        agent_name: wsMsg.agent_name || wsMsg.agent_id,
        department: wsMsg.department || 'unknown',
        message: wsMsg.message,
        signal: wsMsg.signal,
        confidence: wsMsg.confidence,
        timestamp: wsMsg.timestamp || new Date().toISOString(),
        type: wsMsg.type === 'debate_message' ? 'debate_message' : 'agent_update',
      };
      setMessages((prev) => [newMsg, ...prev].slice(0, 200));
    }
  });

  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = 0;
    }
  }, [messages, autoScroll]);

  const liveColor =
    status === 'connected' ? '#00ff41' : status === 'connecting' ? '#ffb000' : '#333333';
  const liveLabel =
    status === 'connected' ? '● LIVE' : status === 'connecting' ? '◐ CONNECTING' : '○ OFFLINE';

  return (
    <div className="max-w-4xl mx-auto">
      {/* ── HEADER ───────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-sm font-bold tracking-widest text-[#00ff41]">AGENT DEBATE FEED</h2>
          <p className="text-[10px] text-[#444444] mt-0.5">
            Real-time agent deliberation and consensus formation
          </p>
        </div>
        <div className="flex items-center gap-4 text-xs font-mono">
          <span style={{ color: liveColor }}>{liveLabel}</span>
          <button
            onClick={() => setAutoScroll((v) => !v)}
            className="px-2 py-0.5 rounded border text-[10px] transition-colors"
            style={{
              borderColor: autoScroll ? '#00ff41' : '#333333',
              color: autoScroll ? '#00ff41' : '#444444',
            }}
          >
            {autoScroll ? 'AUTO-SCROLL ON' : 'AUTO-SCROLL OFF'}
          </button>
          <span className="text-[#333333]">{messages.length} msgs</span>
        </div>
      </div>

      {/* ── FEED ─────────────────────────────────────────────────────────── */}
      <div
        className="bg-[#0d0d0d] border border-[#1a1a1a] rounded-lg overflow-hidden"
      >
        {/* Column headers */}
        <div className="px-4 py-1.5 bg-[#0a0a0a] border-b border-[#1a1a1a] flex items-center gap-4">
          <span className="text-[9px] text-[#333333] uppercase tracking-widest w-20">TIME</span>
          <span className="text-[9px] text-[#333333] uppercase tracking-widest">AGENT / SIGNAL / MESSAGE</span>
        </div>

        {/* Messages */}
        <div
          ref={scrollRef}
          onScroll={() => {
            if (scrollRef.current) {
              setAutoScroll(scrollRef.current.scrollTop < 20);
            }
          }}
          className="overflow-y-auto"
          style={{ maxHeight: '600px' }}
        >
          {messages.length === 0 ? (
            <div className="text-center py-16 text-[#333333] text-xs">
              AWAITING AGENT MESSAGES...
            </div>
          ) : (
            messages.map((msg) => <MessageRow key={msg.id} msg={msg} />)
          )}
        </div>
      </div>

      {/* Legend */}
      <div className="mt-3 flex flex-wrap items-center gap-4 text-[9px] text-[#333333]">
        <span>DEPARTMENTS:</span>
        {Object.entries(DEPT_COLORS).map(([dept, color]) => (
          <span key={dept} style={{ color }}>
            ■ {dept.replace('_', ' ').toUpperCase()}
          </span>
        ))}
      </div>
    </div>
  );
}
