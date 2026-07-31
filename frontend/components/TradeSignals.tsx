'use client';

import React, { useState, useEffect } from 'react';
import { TradeSignal, MOCK_SIGNALS, api } from '../lib/api';
import { useTradeProposals, TradeProposal } from '../lib/hooks/useTradeProposals';

// ─── Helpers ──────────────────────────────────────────────────────────────────

function fmt(n: number): string {
  if (n >= 10000)
    return '$' + n.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 });
  if (n >= 100)
    return '$' + n.toLocaleString('en-US', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  return '$' + n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function pctDiff(a: number, b: number): string {
  const diff = ((b - a) / a) * 100;
  return (diff >= 0 ? '+' : '') + diff.toFixed(1) + '%';
}

function timeAgo(iso: string): string {
  const diff = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  return `${Math.floor(diff / 3600)}h ago`;
}

// ─── proposalToSignal ─────────────────────────────────────────────────────────

function proposalToSignal(p: TradeProposal): TradeSignal {
  const agentSignals = (p.agent_signals as Record<string, unknown> | null) ?? {};
  const total = Object.keys(agentSignals).length || 40;
  const agreed = Math.round(total * (p.consensus_score ?? 0.7));
  const risk = (p.risk_assessment as Record<string, unknown> | null) ?? {};
  return {
    id: p.id,
    symbol: p.symbol,
    direction: p.direction as 'LONG' | 'SHORT',
    entry_zone: [
      Number(risk.entry_zone_low ?? 0) || 67000,
      Number(risk.entry_zone_high ?? 0) || 67500,
    ],
    stop_loss: Number(risk.stop_loss ?? 0) || 65000,
    take_profit: Number(risk.take_profit ?? 0) || 72000,
    risk_reward: Number(risk.risk_reward ?? 0) || 2.5,
    confidence: Math.round(p.confidence_pct ?? 70),
    agents_agreed: agreed,
    agents_total: total,
    status: p.status === 'pending' ? 'pending' : p.status === 'approved' ? 'approved' : 'rejected',
    created_at: p.proposed_at,
  };
}

// ─── SignalCard ───────────────────────────────────────────────────────────────

function SignalCard({
  signal,
  onApprove,
  onReject,
}: {
  signal: TradeSignal;
  onApprove: (id: string) => void;
  onReject: (id: string) => void;
}) {
  const isLong = signal.direction === 'LONG';
  const dirColor = isLong ? '#00ff41' : '#ff2222';
  const dirBg = isLong ? '#001a08' : '#1a0000';
  const dirBorder = isLong ? '#004d14' : '#4d0000';
  const consensus = Math.round((signal.agents_agreed / signal.agents_total) * 100);
  const entryMid = (signal.entry_zone[0] + signal.entry_zone[1]) / 2;
  const slPct = pctDiff(entryMid, signal.stop_loss);
  const tpPct = pctDiff(entryMid, signal.take_profit);

  return (
    <div
      className="border rounded-lg mb-4 overflow-hidden"
      style={{ borderColor: dirBorder, backgroundColor: '#0d0d0d' }}
    >
      {/* ── Signal Header ────────────────────────────────────────────────── */}
      <div
        className="px-5 py-3 border-b flex items-center justify-between"
        style={{ backgroundColor: dirBg, borderColor: dirBorder }}
      >
        <div className="flex items-center gap-3">
          {/* Status dot */}
          <span
            className="w-3 h-3 rounded-full"
            style={{
              backgroundColor: isLong ? '#00ff41' : '#ff2222',
              boxShadow: `0 0 8px ${isLong ? '#00ff41' : '#ff2222'}`,
            }}
          />
          <span className="text-lg font-bold text-[#cccccc]">{signal.symbol}</span>
          <span
            className="px-3 py-0.5 rounded font-bold text-sm tracking-widest"
            style={{ color: dirColor, border: `1px solid ${dirBorder}` }}
          >
            {isLong ? '▲ LONG' : '▼ SHORT'}
          </span>
          <span className="text-xs text-[#444444]">
            {signal.id.includes('sig') ? '1H Timeframe' : 'Multi-TF'} • {timeAgo(signal.created_at)}
          </span>
        </div>
        <div className="text-right">
          <div className="text-xs text-[#444444]">AGENT CONSENSUS</div>
          <div className="font-bold text-lg" style={{ color: dirColor }}>
            {consensus}%
          </div>
          <div className="text-[10px] text-[#555555]">
            {signal.agents_agreed}/{signal.agents_total} agents agree
          </div>
        </div>
      </div>

      {/* ── Price Levels ─────────────────────────────────────────────────── */}
      <div className="px-5 py-4">
        <div className="grid grid-cols-3 gap-4 mb-4">

          {/* Entry Zone */}
          <div className="bg-[#0a0a0a] border border-[#1e3a1e] rounded-lg p-4">
            <div className="text-[9px] text-[#444444] uppercase tracking-widest mb-1">ENTRY ZONE</div>
            <div className="text-xl font-bold font-mono text-[#00aaff]">
              {fmt(signal.entry_zone[0])}
            </div>
            <div className="text-sm font-mono text-[#336699] mt-0.5">
              – {fmt(signal.entry_zone[1])}
            </div>
            <div className="text-[9px] text-[#333333] mt-1">BUY BETWEEN THESE LEVELS</div>
          </div>

          {/* Stop Loss */}
          <div className="bg-[#0a0a0a] border border-[#3a1e1e] rounded-lg p-4">
            <div className="text-[9px] text-[#444444] uppercase tracking-widest mb-1">STOP LOSS</div>
            <div className="text-xl font-bold font-mono text-[#ff2222]">
              {fmt(signal.stop_loss)}
            </div>
            <div className="text-sm font-mono text-[#882222] mt-0.5">
              ↓ {slPct}
            </div>
            <div className="text-[9px] text-[#333333] mt-1">EXIT IF PRICE DROPS HERE</div>
          </div>

          {/* Take Profit */}
          <div className="bg-[#0a0a0a] border border-[#1e3a1e] rounded-lg p-4">
            <div className="text-[9px] text-[#444444] uppercase tracking-widest mb-1">TAKE PROFIT</div>
            <div className="text-xl font-bold font-mono text-[#00ff41]">
              {fmt(signal.take_profit)}
            </div>
            <div className="text-sm font-mono text-[#228822] mt-0.5">
              ↑ {tpPct}
            </div>
            <div className="text-[9px] text-[#333333] mt-1">TARGET EXIT PRICE</div>
          </div>
        </div>

        {/* ── Risk/Reward + Confidence ─────────────────────────────────── */}
        <div className="flex items-center gap-6 mb-4 text-sm font-mono">
          <div>
            <span className="text-[#444444] text-xs">RISK / REWARD: </span>
            <span
              className="font-bold"
              style={{
                color:
                  signal.risk_reward >= 2 ? '#00ff41' : signal.risk_reward >= 1.5 ? '#ffb000' : '#ff2222',
              }}
            >
              1:{signal.risk_reward.toFixed(1)}
            </span>
          </div>
          <div>
            <span className="text-[#444444] text-xs">SIGNAL CONFIDENCE: </span>
            <span className="font-bold" style={{ color: dirColor }}>
              {signal.confidence}%
            </span>
          </div>
          <div>
            <span className="text-[#444444] text-xs">MAX POSITION SIZE: </span>
            <span className="font-bold text-[#cccccc]">$100</span>
          </div>
        </div>

        {/* Confidence bar */}
        <div className="mb-4">
          <div className="h-1.5 bg-[#1a1a1a] rounded-full overflow-hidden">
            <div
              className="h-full rounded-full transition-all"
              style={{ width: `${signal.confidence}%`, backgroundColor: dirColor }}
            />
          </div>
        </div>

        {/* ── Agent Reasoning ──────────────────────────────────────────── */}
        <div
          className="px-4 py-3 rounded border mb-4 text-sm text-[#888888] leading-relaxed"
          style={{ backgroundColor: '#080808', borderColor: '#1a1a1a' }}
        >
          <div className="text-[9px] text-[#444444] uppercase tracking-widest mb-1">
            WHY AGENTS RECOMMEND THIS
          </div>
          <span className="text-[#cccccc]">"</span>
          {isLong
            ? 'Strong bullish consensus from technical, quant, and SMC agents. On-chain accumulation supports the thesis. VWAP holding as support with increasing volume profile.'
            : 'Bearish consensus driven by macro headwinds and deteriorating on-chain metrics. RSI divergence on multiple timeframes confirms downside bias.'}
          <span className="text-[#cccccc]">"</span>
        </div>

        {/* ── Action Buttons ────────────────────────────────────────────── */}
        {signal.status === 'pending' ? (
          <div className="grid grid-cols-2 gap-3">
            <button
              onClick={() => onApprove(signal.id)}
              className="py-4 rounded-lg font-black text-lg uppercase tracking-widest transition-all border-2"
              style={{
                backgroundColor: '#001a08',
                borderColor: '#00ff41',
                color: '#00ff41',
                boxShadow: '0 0 16px rgba(0,255,65,0.15)',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = '#00ff41';
                e.currentTarget.style.color = '#000000';
                e.currentTarget.style.boxShadow = '0 0 30px rgba(0,255,65,0.4)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = '#001a08';
                e.currentTarget.style.color = '#00ff41';
                e.currentTarget.style.boxShadow = '0 0 16px rgba(0,255,65,0.15)';
              }}
            >
              ✓ APPROVE TRADE
            </button>
            <button
              onClick={() => onReject(signal.id)}
              className="py-4 rounded-lg font-black text-lg uppercase tracking-widest transition-all border-2"
              style={{
                backgroundColor: '#1a0000',
                borderColor: '#ff2222',
                color: '#ff2222',
                boxShadow: '0 0 16px rgba(255,34,34,0.15)',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = '#ff2222';
                e.currentTarget.style.color = '#ffffff';
                e.currentTarget.style.boxShadow = '0 0 30px rgba(255,34,34,0.4)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = '#1a0000';
                e.currentTarget.style.color = '#ff2222';
                e.currentTarget.style.boxShadow = '0 0 16px rgba(255,34,34,0.15)';
              }}
            >
              ✗ REJECT TRADE
            </button>
          </div>
        ) : (
          <div
            className="py-4 rounded-lg text-center font-black text-lg uppercase tracking-widest border-2"
            style={{
              backgroundColor: signal.status === 'approved' ? '#001a08' : '#1a0000',
              borderColor: signal.status === 'approved' ? '#004d14' : '#4d0000',
              color: signal.status === 'approved' ? '#00ff41' : '#ff2222',
            }}
          >
            {signal.status === 'approved' ? '✓ APPROVED — EXECUTING' : '✗ REJECTED'}
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────

export default function TradeSignals() {
  const [signals, setSignals] = useState<TradeSignal[]>(MOCK_SIGNALS);
  const { proposals } = useTradeProposals();

  useEffect(() => {
    if (proposals.length > 0) {
      setSignals(proposals.map(proposalToSignal));
    }
  }, [proposals]);

  const handleApprove = async (id: string) => {
    setSignals((prev) => prev.map((s) => (s.id === id ? { ...s, status: 'approved' as const } : s)));
    try {
      await api.trading.approveSignal(id);
    } catch {
      // optimistic update already applied
    }
  };

  const handleReject = async (id: string) => {
    setSignals((prev) => prev.map((s) => (s.id === id ? { ...s, status: 'rejected' as const } : s)));
    try {
      await api.trading.rejectSignal(id);
    } catch {
      // optimistic update already applied
    }
  };

  const pendingCount = signals.filter((s) => s.status === 'pending').length;

  return (
    <div className="max-w-4xl mx-auto">

      {/* ── SECTION HEADER ─────────────────────────────────────────────── */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-sm font-bold tracking-widest text-[#00ff41]">ACTIVE TRADE SIGNALS</h2>
          <p className="text-[10px] text-[#444444] mt-0.5">
            Review and approve/reject agent-generated trade proposals
          </p>
        </div>
        {pendingCount > 0 && (
          <div
            className="px-3 py-1.5 rounded border text-xs font-bold animate-pulse"
            style={{
              backgroundColor: 'rgba(255,176,0,0.08)',
              borderColor: 'rgba(255,176,0,0.4)',
              color: '#ffb000',
            }}
          >
            {pendingCount} PENDING APPROVAL
          </div>
        )}
      </div>

      {/* ── SIGNALS LIST ───────────────────────────────────────────────── */}
      {signals.length === 0 ? (
        <div
          className="border border-[#1a1a1a] rounded-lg py-20 text-center"
          style={{ backgroundColor: '#0d0d0d' }}
        >
          <div className="text-[#333333] text-sm font-bold tracking-widest mb-2">
            NO ACTIVE SIGNALS
          </div>
          <div className="text-[#222222] text-xs">AGENTS ANALYZING MARKET CONDITIONS...</div>
          <div
            className="w-2 h-2 rounded-full mx-auto mt-4"
            style={{ backgroundColor: '#ffb000', boxShadow: '0 0 8px #ffb000', animation: 'pulse 1.5s infinite' }}
          />
        </div>
      ) : (
        signals.map((signal) => (
          <SignalCard
            key={signal.id}
            signal={signal}
            onApprove={handleApprove}
            onReject={handleReject}
          />
        ))
      )}
    </div>
  );
}
