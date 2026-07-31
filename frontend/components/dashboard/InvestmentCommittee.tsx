'use client';

import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { CheckCircle, XCircle } from 'lucide-react';

interface AgentVote {
  name: string;
  vote: 'bull' | 'bear' | 'neutral';
  confidence: number;
}

const voteColor = {
  bull: '#22C55E',
  bear: '#EF4444',
  neutral: '#F59E0B',
};

const voteBg = {
  bull: 'rgba(34,197,94,0.12)',
  bear: 'rgba(239,68,68,0.12)',
  neutral: 'rgba(245,158,11,0.12)',
};

const voteLabel = {
  bull: 'B',
  bear: 'S',
  neutral: 'N',
};

const AGENTS: AgentVote[] = [
  { name: 'Macro Intel', vote: 'bull', confidence: 82 },
  { name: 'Tech Analyst', vote: 'bull', confidence: 79 },
  { name: 'Quant Model', vote: 'bull', confidence: 88 },
  { name: 'Risk Manager', vote: 'neutral', confidence: 51 },
  { name: 'Sentiment AI', vote: 'bull', confidence: 74 },
  { name: 'Options Flow', vote: 'bull', confidence: 71 },
  { name: 'On-Chain', vote: 'bull', confidence: 85 },
  { name: 'Market Maker', vote: 'bear', confidence: 62 },
  { name: 'Momentum', vote: 'bull', confidence: 77 },
  { name: 'Mean Revert', vote: 'bear', confidence: 55 },
  { name: 'Volatility', vote: 'neutral', confidence: 48 },
  { name: 'Trend Follow', vote: 'bull', confidence: 83 },
  { name: 'Fund Flow', vote: 'bull', confidence: 69 },
  { name: 'Derivatives', vote: 'bull', confidence: 72 },
  { name: 'Pair Trade', vote: 'neutral', confidence: 53 },
  { name: 'Stat Arb', vote: 'bull', confidence: 76 },
  { name: 'ML Forecast', vote: 'bull', confidence: 81 },
  { name: 'News NLP', vote: 'bull', confidence: 74 },
  { name: 'Whale Watch', vote: 'bull', confidence: 86 },
  { name: 'Order Book', vote: 'bear', confidence: 58 },
  { name: 'Liquidity', vote: 'bull', confidence: 70 },
  { name: 'Correlation', vote: 'bull', confidence: 68 },
  { name: 'Sector Rot', vote: 'bull', confidence: 73 },
  { name: 'Global Macro', vote: 'bull', confidence: 80 },
  { name: 'Credit Risk', vote: 'neutral', confidence: 49 },
  { name: 'FX Pairs', vote: 'bull', confidence: 66 },
  { name: 'Rates Watch', vote: 'bear', confidence: 57 },
  { name: 'Commodity', vote: 'bull', confidence: 71 },
  { name: 'ESG Score', vote: 'neutral', confidence: 52 },
  { name: 'Alt Data', vote: 'bull', confidence: 77 },
  { name: 'Dark Pool', vote: 'bull', confidence: 84 },
  { name: 'Tape Reader', vote: 'bull', confidence: 79 },
  { name: 'Event Drive', vote: 'bull', confidence: 75 },
  { name: 'Regime Det', vote: 'bull', confidence: 82 },
  { name: 'Vol Surface', vote: 'bear', confidence: 61 },
  { name: 'Carry Trade', vote: 'bull', confidence: 69 },
  { name: 'CTA Signal', vote: 'bull', confidence: 76 },
  { name: 'Microstr', vote: 'bull', confidence: 73 },
  { name: 'Cross Asset', vote: 'bull', confidence: 78 },
  { name: 'Chief Alpha', vote: 'bull', confidence: 87 },
];

const AGREEING = AGENTS.filter((a) => a.vote === 'bull').length;
const TOTAL = AGENTS.length;

function AgreementCircle({ agreeing, total }: { agreeing: number; total: number }) {
  const pct = agreeing / total;
  const size = 100;
  const sw = 8;
  const r = (size - sw) / 2;
  const circ = 2 * Math.PI * r;
  const offset = circ - pct * circ;

  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth={sw} />
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="#22C55E"
          strokeWidth={sw}
          strokeLinecap="round"
          strokeDasharray={circ}
          initial={{ strokeDashoffset: circ }}
          animate={{ strokeDashoffset: offset }}
          transition={{ duration: 1.2, ease: 'easeOut', delay: 0.5 }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="font-mono font-bold text-lg" style={{ color: '#22C55E' }}>
          {agreeing}/{total}
        </span>
        <span className="text-[9px] uppercase tracking-wider" style={{ color: '#475569' }}>
          Agree
        </span>
      </div>
    </div>
  );
}

export default function InvestmentCommittee() {
  const [decision, setDecision] = useState<null | 'approved' | 'rejected'>(null);

  return (
    <div
      className="rounded-xl p-5 flex flex-col gap-5"
      style={{
        background: '#121826',
        border: '1px solid rgba(255,255,255,0.06)',
      }}
    >
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-sm font-bold" style={{ color: '#F1F5F9' }}>
            Investment Committee
          </h2>
          <p className="text-xs mt-0.5" style={{ color: '#475569' }}>
            Live Vote — 40 Agents
          </p>
        </div>
        <div
          className="flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold"
          style={{
            background: 'rgba(34,197,94,0.1)',
            border: '1px solid rgba(34,197,94,0.2)',
            color: '#22C55E',
          }}
        >
          <span className="w-1.5 h-1.5 rounded-full animate-live-blink" style={{ background: '#22C55E' }} />
          LIVE
        </div>
      </div>

      {/* Agent vote grid — 8 cols × 5 rows */}
      <div className="grid gap-2" style={{ gridTemplateColumns: 'repeat(8, 1fr)' }}>
        {AGENTS.map((agent, i) => (
          <motion.div
            key={agent.name}
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: i * 0.025, duration: 0.25 }}
            className="rounded-lg p-2 flex flex-col items-center gap-1"
            style={{
              background: 'rgba(255,255,255,0.03)',
              border: '1px solid rgba(255,255,255,0.06)',
            }}
            title={`${agent.name} — ${agent.vote.toUpperCase()} ${agent.confidence}%`}
          >
            <div
              className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold"
              style={{
                background: voteBg[agent.vote],
                color: voteColor[agent.vote],
                border: `1px solid ${voteColor[agent.vote]}33`,
              }}
            >
              {voteLabel[agent.vote]}
            </div>
            <div className="text-[9px] text-center leading-tight truncate w-full" style={{ color: '#475569' }}>
              {agent.name}
            </div>
            <div className="font-mono text-[9px] font-semibold" style={{ color: '#94A3B8' }}>
              {agent.confidence}%
            </div>
          </motion.div>
        ))}
      </div>

      {/* CIO section */}
      <div
        className="rounded-xl p-4 flex flex-col gap-4"
        style={{
          background: 'rgba(255,255,255,0.02)',
          border: '1px solid rgba(255,255,255,0.06)',
        }}
      >
        <div className="flex items-center justify-between">
          <div>
            <div className="text-[10px] font-bold uppercase tracking-widest" style={{ color: '#475569' }}>
              Chief Investment Officer
            </div>
            <div className="text-sm font-semibold mt-0.5" style={{ color: '#F1F5F9' }}>
              Awaiting Executive Decision
            </div>
          </div>
          <AgreementCircle agreeing={AGREEING} total={TOTAL} />
        </div>

        {decision === null ? (
          <div className="flex gap-3">
            <motion.button
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.97 }}
              onClick={() => setDecision('approved')}
              className="flex-1 flex items-center justify-center gap-2 py-3.5 rounded-xl text-sm font-bold text-white"
              style={{ background: 'linear-gradient(135deg, #22C55E 0%, #16A34A 100%)' }}
            >
              <CheckCircle className="w-4 h-4" />
              EXECUTE TRADE
            </motion.button>
            <motion.button
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.97 }}
              onClick={() => setDecision('rejected')}
              className="flex-1 flex items-center justify-center gap-2 py-3.5 rounded-xl text-sm font-bold"
              style={{
                border: '2px solid rgba(239,68,68,0.4)',
                color: '#EF4444',
              }}
            >
              <XCircle className="w-4 h-4" />
              REJECT PROPOSAL
            </motion.button>
          </div>
        ) : (
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="rounded-xl py-4 text-center text-base font-bold"
            style={{
              background:
                decision === 'approved' ? 'rgba(34,197,94,0.12)' : 'rgba(239,68,68,0.12)',
              color: decision === 'approved' ? '#22C55E' : '#EF4444',
              border: `1px solid ${decision === 'approved' ? 'rgba(34,197,94,0.25)' : 'rgba(239,68,68,0.25)'}`,
            }}
          >
            {decision === 'approved'
              ? '✓ TRADE EXECUTED — ORDER SENT TO BROKER'
              : '✕ PROPOSAL REJECTED BY CIO'}
          </motion.div>
        )}
      </div>
    </div>
  );
}
