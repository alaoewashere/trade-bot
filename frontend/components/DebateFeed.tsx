'use client';

import React, { useState, useEffect, useRef } from 'react';
import { useAgentActivityWS } from '../hooks/useWebSocket';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

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

const DEPT_COLORS: Record<string, string> = {
  executive:           '#8B5CF6',
  market_intelligence: '#06B6D4',
  technical:           '#3B82F6',
  quantitative:        '#6366F1',
  options:             '#F97316',
  crypto:              '#F59E0B',
  strategy:            '#22C55E',
  execution:           '#F43F5E',
  monitoring:          '#64748B',
  security:            '#EF4444',
  coordination:        '#7C3AED',
};

const DEPT_INITIALS: Record<string, string> = {
  executive:           'EX',
  market_intelligence: 'MI',
  technical:           'TA',
  quantitative:        'QA',
  options:             'OP',
  crypto:              'CR',
  strategy:            'ST',
  execution:           'EX',
  monitoring:          'MO',
  security:            'SE',
  coordination:        'CO',
};

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
    message: 'ROUND 2 STARTING — Bull side has established momentum thesis. Bear side: please address macro concern and provide rebuttal.',
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
    message: 'Order block at $66,800–$67,100 holding strong. Liquidity sweep confirmed below $66,500. Smart money accumulation phase detected.',
    signal: 'bullish',
    confidence: 78,
    timestamp: new Date(Date.now() - 200000).toISOString(),
  },
  {
    id: 'msg_006',
    agent_id: 'quant_researcher',
    agent_name: 'Quantitative Researcher',
    department: 'quantitative',
    message: 'Statistical edge confirmed: 78.3% win rate on 500 backtested instances. Expected value: +2.34R. Z-score 2.1 — statistically significant.',
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
    agent_id: 'consensus_engine',
    agent_name: 'Consensus Engine',
    department: 'coordination',
    message: 'SIGNAL GENERATED: BTC/USDT LONG. Entry: $67,200–$67,600. Stop: $65,800. Target: $71,500. Consensus: 78%. Awaiting human approval.',
    signal: 'bullish',
    confidence: 78,
    type: 'system',
    timestamp: new Date(Date.now() - 400000).toISOString(),
  },
];

function fmtTime(iso: string): string {
  return new Date(iso).toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function MessageBubble({ msg }: { msg: ChatMessage }) {
  const isSystem = msg.type === 'system' || msg.department === 'coordination';
  const deptColor = DEPT_COLORS[msg.department] || '#6B6B7A';
  const initials = DEPT_INITIALS[msg.department] ?? msg.agent_name.slice(0, 2).toUpperCase();

  const isUp = msg.signal === 'bullish';
  const isDown = msg.signal === 'bearish';
  const sigColor = isUp ? '#22C55E' : isDown ? '#EF4444' : '#6B6B7A';
  const SigIcon = isUp ? TrendingUp : isDown ? TrendingDown : Minus;

  if (isSystem) {
    return (
      <div
        className="rounded-lg px-3 py-2 mx-2 my-1.5 text-center text-xs border"
        style={{
          background: 'rgba(124,58,237,0.06)',
          borderColor: 'rgba(124,58,237,0.2)',
          color: '#A78BFA',
        }}
      >
        <span className="font-semibold">{msg.agent_name.toUpperCase()}</span>
        <span className="text-[#6B6B7A] ml-2">{fmtTime(msg.timestamp)}</span>
        <p className="mt-1 text-[11px] leading-relaxed">{msg.message}</p>
      </div>
    );
  }

  return (
    <div className="flex gap-2.5 px-3 py-2 hover:bg-white/[0.01] transition-colors animate-fade-in-up">
      {/* Avatar */}
      <div
        className="w-7 h-7 rounded-lg shrink-0 flex items-center justify-center text-[10px] font-bold mt-0.5"
        style={{ background: `${deptColor}20`, color: deptColor }}
      >
        {initials}
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-xs font-semibold text-white">{msg.agent_name}</span>
          {msg.signal && (
            <div
              className="flex items-center gap-0.5 text-[10px] font-semibold"
              style={{ color: sigColor }}
            >
              <SigIcon className="w-3 h-3" />
              {isUp ? 'BULLISH' : isDown ? 'BEARISH' : 'NEUTRAL'}
              {msg.confidence !== undefined && (
                <span className="font-mono ml-1">· {msg.confidence}%</span>
              )}
            </div>
          )}
          <span className="text-[10px] text-[#6B6B7A] ml-auto font-mono shrink-0">
            {fmtTime(msg.timestamp)}
          </span>
        </div>
        <p
          className="text-xs text-[#9B9BAA] leading-relaxed pl-2"
          style={{ borderLeft: `2px solid ${deptColor}30` }}
        >
          {msg.message}
        </p>
      </div>
    </div>
  );
}

export default function DebateFeed() {
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
      setMessages((prev) => [newMsg, ...prev].slice(0, 100));
    }
  });

  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = 0;
    }
  }, [messages, autoScroll]);

  const isLive = status === 'connected';

  return (
    <div
      className="rounded-xl border flex flex-col overflow-hidden"
      style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between px-4 py-3 border-b shrink-0"
        style={{ borderColor: 'var(--bg-border)' }}
      >
        <span className="text-xs font-semibold text-[#9B9BAA] uppercase tracking-wide">Agent Debate</span>
        <div className="flex items-center gap-3">
          <button
            onClick={() => setAutoScroll((v) => !v)}
            className="text-[10px] text-[#6B6B7A] hover:text-[#9B9BAA] transition-colors"
          >
            {autoScroll ? 'Auto-scroll on' : 'Auto-scroll off'}
          </button>
          <div className="flex items-center gap-1.5">
            <span
              className="w-1.5 h-1.5 rounded-full"
              style={{
                background: isLive ? '#22C55E' : '#374151',
                boxShadow: isLive ? '0 0 6px #22C55E' : undefined,
              }}
            />
            <span
              className="text-[10px] font-medium uppercase"
              style={{ color: isLive ? '#22C55E' : '#6B6B7A' }}
            >
              {isLive ? 'LIVE' : 'OFFLINE'}
            </span>
          </div>
        </div>
      </div>

      {/* Messages */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto py-2"
        style={{ maxHeight: 320 }}
        onScroll={() => {
          if (scrollRef.current) {
            setAutoScroll(scrollRef.current.scrollTop < 20);
          }
        }}
      >
        {messages.length === 0 ? (
          <div className="text-center py-10 text-[#6B6B7A] text-xs">
            Awaiting agent messages...
          </div>
        ) : (
          messages.map((msg) => <MessageBubble key={msg.id} msg={msg} />)
        )}
      </div>

      {/* Footer */}
      <div
        className="px-4 py-2 border-t shrink-0"
        style={{ borderColor: 'var(--bg-border)' }}
      >
        <span className="text-[10px] text-[#6B6B7A]">{messages.length} messages</span>
      </div>
    </div>
  );
}
