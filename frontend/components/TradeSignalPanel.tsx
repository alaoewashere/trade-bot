'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { CheckCircle, XCircle, TrendingUp, TrendingDown, AlertTriangle, Shield } from 'lucide-react';
import { TradeSignal, MOCK_SIGNALS, api } from '../lib/api';
import { useTradeProposals, TradeProposal } from '../lib/hooks/useTradeProposals';
import ConfidenceGauge from './ConfidenceGauge';

function fmt(n: number): string {
  if (n >= 10000) return '$' + n.toLocaleString('en-US', { maximumFractionDigits: 0 });
  if (n >= 100) return '$' + n.toLocaleString('en-US', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  return '$' + n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function pctDiff(a: number, b: number): string {
  const diff = ((b - a) / a) * 100;
  return (diff >= 0 ? '+' : '') + diff.toFixed(1) + '%';
}

function proposalToSignal(p: TradeProposal): TradeSignal {
  const agentSignals = (p.agent_signals as Record<string, unknown> | null) ?? {};
  const total = Object.keys(agentSignals).length || 40;
  const agreed = Math.round(total * (p.consensus_score ?? 0.7));
  const risk = (p.risk_assessment as Record<string, unknown> | null) ?? {};
  return {
    id: p.id,
    symbol: p.symbol,
    direction: p.direction as 'LONG' | 'SHORT',
    entry_zone: [Number(risk.entry_zone_low ?? 0) || 67000, Number(risk.entry_zone_high ?? 0) || 67500],
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

// Kill Switch embedded
type KillState = 'armed' | 'confirming' | 'executing' | 'triggered';

function KillSwitchCard() {
  const [state, setState] = useState<KillState>('armed');
  const [countdown, setCountdown] = useState(3);

  const handleInitiate = useCallback(() => {
    if (state !== 'armed') return;
    setState('confirming');
    setCountdown(3);
    let count = 3;
    const interval = setInterval(() => {
      count--;
      setCountdown(count);
      if (count <= 0) {
        clearInterval(interval);
        setState('armed');
      }
    }, 1000);
  }, [state]);

  const handleConfirm = useCallback(async () => {
    if (state !== 'confirming') return;
    setState('executing');
    try {
      await api.system.killSwitch();
    } catch {
      // demo
    }
    setState('triggered');
  }, [state]);

  const handleReset = () => {
    setState('armed');
    setCountdown(3);
  };

  return (
    <div
      className="rounded-xl border p-4 mt-3"
      style={{ background: 'rgba(239,68,68,0.04)', borderColor: 'rgba(239,68,68,0.2)' }}
    >
      <div className="flex items-center gap-2 mb-3">
        <Shield className="w-4 h-4 text-red-400" />
        <span className="text-xs font-semibold text-red-400 uppercase tracking-wide">Emergency Kill Switch</span>
      </div>

      {state === 'triggered' ? (
        <div className="space-y-2">
          <div className="text-center py-2">
            <div className="text-red-400 font-bold text-sm animate-pulse">KILL SWITCH TRIGGERED</div>
            <div className="text-red-600 text-xs mt-1">All positions closing...</div>
          </div>
          <button
            onClick={handleReset}
            className="w-full text-xs text-[#6B6B7A] underline"
          >
            Reset (Demo)
          </button>
        </div>
      ) : state === 'executing' ? (
        <div className="text-center py-2 text-red-400 text-sm font-medium animate-pulse">
          Executing...
        </div>
      ) : state === 'confirming' ? (
        <div className="space-y-2">
          <div className="text-center text-red-400 text-xs font-bold animate-pulse">
            CONFIRM EMERGENCY STOP?
          </div>
          <div className="text-center text-[#6B6B7A] text-[10px]">Auto-cancels in {countdown}s</div>
          <div className="flex gap-2">
            <button
              onClick={handleConfirm}
              className="flex-1 py-2 rounded-lg text-xs font-bold text-white uppercase tracking-wide transition-all"
              style={{ background: '#EF4444' }}
            >
              CONFIRM KILL
            </button>
            <button
              onClick={handleReset}
              className="flex-1 py-2 rounded-lg text-xs font-medium text-[#9B9BAA] transition-all"
              style={{ background: 'rgba(255,255,255,0.05)', border: '1px solid var(--bg-border)' }}
            >
              ABORT
            </button>
          </div>
        </div>
      ) : (
        <button
          onClick={handleInitiate}
          className="w-full py-2.5 rounded-lg text-sm font-bold uppercase tracking-wide transition-all hover:opacity-90 active:scale-95"
          style={{
            background: 'rgba(239,68,68,0.1)',
            border: '1px solid rgba(239,68,68,0.3)',
            color: '#EF4444',
          }}
        >
          ACTIVATE KILL SWITCH
        </button>
      )}
      <div className="text-[10px] text-[#6B6B7A] text-center mt-2">
        Closes all open positions immediately
      </div>
    </div>
  );
}

// Analyzing skeleton
function AnalyzingState() {
  return (
    <div className="flex flex-col gap-3">
      <div
        className="rounded-xl border p-5 text-center"
        style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}
      >
        <div className="flex items-center justify-center gap-2 mb-4">
          <span className="w-2 h-2 rounded-full bg-amber-400 live-dot" />
          <span className="text-xs text-amber-400 font-semibold uppercase tracking-wide">Analyzing Markets</span>
        </div>
        <div className="space-y-3">
          {[64, 80, 48].map((w, i) => (
            <div key={i} className="skeleton h-4 mx-auto rounded" style={{ width: `${w}%` }} />
          ))}
        </div>
        <div className="mt-4 grid grid-cols-3 gap-2">
          {[1, 2, 3].map((i) => (
            <div key={i} className="skeleton h-16 rounded-lg" />
          ))}
        </div>
        <p className="text-xs text-[#6B6B7A] mt-4">
          40 agents deliberating consensus...
        </p>
      </div>
      <KillSwitchCard />
    </div>
  );
}

interface SignalCardProps {
  signal: TradeSignal;
  onApprove: (id: string) => void;
  onReject: (id: string) => void;
}

function SignalCard({ signal, onApprove, onReject }: SignalCardProps) {
  const isLong = signal.direction === 'LONG';
  const dirColor = isLong ? '#22C55E' : '#EF4444';
  const dirBg = isLong ? 'rgba(34,197,94,0.08)' : 'rgba(239,68,68,0.08)';
  const dirBorder = isLong ? 'rgba(34,197,94,0.2)' : 'rgba(239,68,68,0.2)';
  const consensus = Math.round((signal.agents_agreed / signal.agents_total) * 100);
  const entryMid = (signal.entry_zone[0] + signal.entry_zone[1]) / 2;
  const DirIcon = isLong ? TrendingUp : TrendingDown;

  return (
    <div
      className="rounded-xl border overflow-hidden"
      style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}
    >
      {/* Header */}
      <div
        className="px-4 pt-4 pb-3 border-b"
        style={{ borderColor: 'var(--bg-border)' }}
      >
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full live-dot" style={{ background: dirColor }} />
            <span className="text-[10px] text-[#9B9BAA] uppercase tracking-wide font-medium">Live Signal</span>
          </div>
          <span className="text-xs text-[#6B6B7A] font-mono">
            {new Date(signal.created_at).toLocaleTimeString('en-US', { hour12: false })}
          </span>
        </div>

        <div className="text-lg font-bold text-white">{signal.symbol}</div>

        <div className="flex items-center justify-between mt-2">
          <div
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg border font-semibold text-sm"
            style={{ color: dirColor, background: dirBg, borderColor: dirBorder }}
          >
            <DirIcon className="w-4 h-4" />
            {isLong ? 'BUY (LONG)' : 'SELL (SHORT)'}
          </div>
          <div className="text-right">
            <div className="text-[10px] text-[#6B6B7A]">Confidence</div>
            <div className="font-mono font-bold text-lg" style={{ color: dirColor }}>
              {signal.confidence}%
            </div>
          </div>
        </div>
      </div>

      {/* Price levels */}
      <div className="p-4 space-y-3">
        <div className="grid grid-cols-3 gap-2">
          {[
            { label: 'ENTRY', value: fmt(signal.entry_zone[0]), sub: `–${fmt(signal.entry_zone[1])}`, color: '#3B82F6' },
            { label: 'STOP', value: fmt(signal.stop_loss), sub: pctDiff(entryMid, signal.stop_loss), color: '#EF4444' },
            { label: 'TARGET', value: fmt(signal.take_profit), sub: pctDiff(entryMid, signal.take_profit), color: '#22C55E' },
          ].map(({ label, value, sub, color }) => (
            <div
              key={label}
              className="rounded-lg p-3 text-center"
              style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}
            >
              <div className="text-[9px] text-[#6B6B7A] uppercase tracking-wider mb-1">{label}</div>
              <div className="font-mono font-bold text-sm" style={{ color }}>{value}</div>
              <div className="text-[10px] font-mono" style={{ color: `${color}99` }}>{sub}</div>
            </div>
          ))}
        </div>

        {/* R/R + size */}
        <div
          className="flex items-center justify-between px-3 py-2 rounded-lg text-xs"
          style={{ background: 'rgba(255,255,255,0.03)' }}
        >
          <div>
            <span className="text-[#6B6B7A]">R/R: </span>
            <span
              className="font-mono font-semibold"
              style={{ color: signal.risk_reward >= 2 ? '#22C55E' : signal.risk_reward >= 1.5 ? '#F59E0B' : '#EF4444' }}
            >
              1:{signal.risk_reward.toFixed(1)}
            </span>
          </div>
          <div>
            <span className="text-[#6B6B7A]">Max Size: </span>
            <span className="font-mono text-white">$100</span>
          </div>
        </div>

        {/* Gauge */}
        <div className="flex items-center justify-center py-2">
          <ConfidenceGauge value={consensus} size={88} label={`${signal.agents_agreed}/${signal.agents_total} agents`} />
        </div>

        {/* Reasoning */}
        <div
          className="rounded-lg px-3 py-2.5 text-xs text-[#9B9BAA] leading-relaxed"
          style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.05)' }}
        >
          {signal.agents_agreed} of {signal.agents_total} agents in agreement. Technical and on-chain signals aligned with {isLong ? 'bullish' : 'bearish'} thesis.
        </div>

        {/* Action buttons */}
        {signal.status === 'pending' ? (
          <div className="space-y-2 pt-1">
            <button
              onClick={() => onApprove(signal.id)}
              className="w-full py-3 rounded-xl font-semibold text-sm text-white flex items-center justify-center gap-2 transition-all hover:opacity-90 active:scale-95"
              style={{ background: '#22C55E' }}
            >
              <CheckCircle className="w-4 h-4" />
              APPROVE TRADE
            </button>
            <button
              onClick={() => onReject(signal.id)}
              className="w-full py-3 rounded-xl font-semibold text-sm flex items-center justify-center gap-2 transition-all hover:opacity-90 active:scale-95 border"
              style={{
                background: 'rgba(239,68,68,0.06)',
                borderColor: 'rgba(239,68,68,0.2)',
                color: '#EF4444',
              }}
            >
              <XCircle className="w-4 h-4" />
              REJECT
            </button>
          </div>
        ) : (
          <div
            className="w-full py-3 rounded-xl text-center font-semibold text-sm"
            style={{
              background: signal.status === 'approved' ? 'rgba(34,197,94,0.1)' : 'rgba(239,68,68,0.1)',
              border: `1px solid ${signal.status === 'approved' ? 'rgba(34,197,94,0.2)' : 'rgba(239,68,68,0.2)'}`,
              color: signal.status === 'approved' ? '#22C55E' : '#EF4444',
            }}
          >
            {signal.status === 'approved' ? 'APPROVED — EXECUTING' : 'REJECTED'}
          </div>
        )}
      </div>
    </div>
  );
}

export default function TradeSignalPanel() {
  const [signals, setSignals] = useState<TradeSignal[]>(MOCK_SIGNALS);
  const { proposals } = useTradeProposals();

  useEffect(() => {
    if (proposals.length > 0) {
      setSignals(proposals.map(proposalToSignal));
    }
  }, [proposals]);

  const handleApprove = async (id: string) => {
    setSignals((prev) => prev.map((s) => (s.id === id ? { ...s, status: 'approved' as const } : s)));
    try { await api.trading.approveSignal(id); } catch { /* optimistic */ }
  };

  const handleReject = async (id: string) => {
    setSignals((prev) => prev.map((s) => (s.id === id ? { ...s, status: 'rejected' as const } : s)));
    try { await api.trading.rejectSignal(id); } catch { /* optimistic */ }
  };

  const pendingSignals = signals.filter((s) => s.status === 'pending');
  const primarySignal = pendingSignals[0] ?? signals[0];

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-[#9B9BAA] uppercase tracking-wide">Trade Signal</span>
        {pendingSignals.length > 0 && (
          <span
            className="text-[10px] px-2 py-0.5 rounded-full font-semibold"
            style={{ background: 'rgba(245,158,11,0.1)', color: '#F59E0B', border: '1px solid rgba(245,158,11,0.2)' }}
          >
            {pendingSignals.length} PENDING
          </span>
        )}
      </div>

      {primarySignal ? (
        <SignalCard
          signal={primarySignal}
          onApprove={handleApprove}
          onReject={handleReject}
        />
      ) : (
        <AnalyzingState />
      )}

      {/* Multiple signals indicator */}
      {signals.length > 1 && (
        <div className="flex gap-2">
          {signals.slice(1).map((s) => (
            <div
              key={s.id}
              className="flex-1 rounded-lg p-2.5 text-center text-xs cursor-pointer transition-all hover:bg-white/5"
              style={{ background: 'var(--bg-card)', border: '1px solid var(--bg-border)' }}
              onClick={() => setSignals((prev) => [s, ...prev.filter((x) => x.id !== s.id)])}
            >
              <div className="text-[#6B6B7A] text-[9px]">{s.symbol}</div>
              <div
                className="font-semibold font-mono text-xs"
                style={{ color: s.direction === 'LONG' ? '#22C55E' : '#EF4444' }}
              >
                {s.direction === 'LONG' ? '▲' : '▼'} {s.confidence}%
              </div>
            </div>
          ))}
        </div>
      )}

      <KillSwitchCard />
    </div>
  );
}
