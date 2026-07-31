'use client';

import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { ChevronRight } from 'lucide-react';
import ArcGauge from '@/components/ui/ArcGauge';
import Badge from '@/components/ui/Badge';

type Signal = 'BULLISH' | 'BEARISH' | 'NEUTRAL';
type Status = 'ANALYZING' | 'COMPLETE';

interface AgentData {
  name: string;
  department: string;
  deptColor: string;
  signal: Signal;
  confidence: number;
  status: Status;
  reasoning: string;
  updatedAgo: string;
}

const DEPT_COLORS: Record<string, string> = {
  'MARKET INTEL': '#4F7CFF',
  'QUANT RESEARCH': '#818CF8',
  'RISK MGMT': '#F59E0B',
  'ON-CHAIN': '#22C55E',
  'MACRO': '#06B6D4',
  'DERIVATIVES': '#EC4899',
  'SENTIMENT': '#A78BFA',
  'EXECUTION': '#14B8A6',
};

const AGENTS: AgentData[] = [
  { name: 'Macro Economist', department: 'MACRO', deptColor: DEPT_COLORS['MACRO'], signal: 'BULLISH', confidence: 82, status: 'COMPLETE', reasoning: 'Fed pivot signals rate cuts, risk-on environment favoring BTC upside', updatedAgo: '2m ago' },
  { name: 'Tech Analyst', department: 'MARKET INTEL', deptColor: DEPT_COLORS['MARKET INTEL'], signal: 'BULLISH', confidence: 79, status: 'COMPLETE', reasoning: 'Break above 200 EMA with volume confirmation on 4H chart', updatedAgo: '1m ago' },
  { name: 'Quant Modeler', department: 'QUANT RESEARCH', deptColor: DEPT_COLORS['QUANT RESEARCH'], signal: 'BULLISH', confidence: 88, status: 'COMPLETE', reasoning: 'Factor model shows momentum + value alignment, alpha expectation +2.8%', updatedAgo: '3m ago' },
  { name: 'Risk Manager', department: 'RISK MGMT', deptColor: DEPT_COLORS['RISK MGMT'], signal: 'NEUTRAL', confidence: 51, status: 'COMPLETE', reasoning: 'VaR within limits but correlation with equities elevated at 0.72', updatedAgo: '4m ago' },
  { name: 'Sentiment AI', department: 'SENTIMENT', deptColor: DEPT_COLORS['SENTIMENT'], signal: 'BULLISH', confidence: 74, status: 'COMPLETE', reasoning: 'Twitter/Reddit sentiment score 7.2/10 bullish, social volume +34%', updatedAgo: '2m ago' },
  { name: 'Options Analyst', department: 'DERIVATIVES', deptColor: DEPT_COLORS['DERIVATIVES'], signal: 'BULLISH', confidence: 71, status: 'ANALYZING', reasoning: 'Put/call ratio 0.68 bullish, max pain $68k, significant call OI at $70k', updatedAgo: '5m ago' },
  { name: 'On-Chain Intel', department: 'ON-CHAIN', deptColor: DEPT_COLORS['ON-CHAIN'], signal: 'BULLISH', confidence: 85, status: 'COMPLETE', reasoning: 'Whale accumulation detected, exchange reserves hit 3-year low', updatedAgo: '1m ago' },
  { name: 'Market Maker', department: 'EXECUTION', deptColor: DEPT_COLORS['EXECUTION'], signal: 'BEARISH', confidence: 62, status: 'COMPLETE', reasoning: 'Thin order book above $68.5k, potential for rapid moves, liquidity gaps', updatedAgo: '6m ago' },
  { name: 'Momentum Trader', department: 'QUANT RESEARCH', deptColor: DEPT_COLORS['QUANT RESEARCH'], signal: 'BULLISH', confidence: 77, status: 'COMPLETE', reasoning: 'RSI 58 with room to run, MACD bullish cross confirmed on 1H', updatedAgo: '2m ago' },
  { name: 'Mean Reversion', department: 'QUANT RESEARCH', deptColor: DEPT_COLORS['QUANT RESEARCH'], signal: 'BEARISH', confidence: 55, status: 'COMPLETE', reasoning: 'Price extended 2.1σ from 20-period mean, reversion probability 64%', updatedAgo: '3m ago' },
  { name: 'Volatility Desk', department: 'DERIVATIVES', deptColor: DEPT_COLORS['DERIVATIVES'], signal: 'NEUTRAL', confidence: 48, status: 'ANALYZING', reasoning: 'IV rank 38, VIX analog at 22, neutral vol regime with event risk ahead', updatedAgo: '8m ago' },
  { name: 'Trend Follower', department: 'MARKET INTEL', deptColor: DEPT_COLORS['MARKET INTEL'], signal: 'BULLISH', confidence: 83, status: 'COMPLETE', reasoning: 'Strong uptrend across all major timeframes, breakout from 3-week base', updatedAgo: '1m ago' },
  { name: 'Fund Flow Intel', department: 'MARKET INTEL', deptColor: DEPT_COLORS['MARKET INTEL'], signal: 'BULLISH', confidence: 69, status: 'COMPLETE', reasoning: 'ETF inflows $2.1B this week, institutional accumulation in derivatives', updatedAgo: '5m ago' },
  { name: 'Derivatives Desk', department: 'DERIVATIVES', deptColor: DEPT_COLORS['DERIVATIVES'], signal: 'BULLISH', confidence: 72, status: 'COMPLETE', reasoning: 'Funding rate positive but not extreme at 0.032%, longs healthy', updatedAgo: '4m ago' },
  { name: 'Stat Arbitrage', department: 'QUANT RESEARCH', deptColor: DEPT_COLORS['QUANT RESEARCH'], signal: 'BULLISH', confidence: 76, status: 'COMPLETE', reasoning: 'BTC-ETH spread at historical low, pair trade favors BTC long', updatedAgo: '3m ago' },
  { name: 'ML Forecaster', department: 'QUANT RESEARCH', deptColor: DEPT_COLORS['QUANT RESEARCH'], signal: 'BULLISH', confidence: 81, status: 'COMPLETE', reasoning: 'LSTM model 72h forecast: $69,200 ± $1,200 with 81% confidence interval', updatedAgo: '2m ago' },
  { name: 'NLP News Bot', department: 'SENTIMENT', deptColor: DEPT_COLORS['SENTIMENT'], signal: 'BULLISH', confidence: 74, status: 'COMPLETE', reasoning: 'Positive coverage ratio 68%, no major negative catalysts in news feed', updatedAgo: '1m ago' },
  { name: 'Whale Watcher', department: 'ON-CHAIN', deptColor: DEPT_COLORS['ON-CHAIN'], signal: 'BULLISH', confidence: 86, status: 'COMPLETE', reasoning: '3 wallets >1000 BTC accumulated $180M in past 48h, strong conviction', updatedAgo: '2m ago' },
  { name: 'Order Book AI', department: 'EXECUTION', deptColor: DEPT_COLORS['EXECUTION'], signal: 'BEARISH', confidence: 58, status: 'ANALYZING', reasoning: 'Sell walls detected at $68.2k and $69.5k, buyer absorption questionable', updatedAgo: '7m ago' },
  { name: 'Liquidity Model', department: 'EXECUTION', deptColor: DEPT_COLORS['EXECUTION'], signal: 'BULLISH', confidence: 70, status: 'COMPLETE', reasoning: 'Market depth improved 18% this session, bid-ask spread normalizing', updatedAgo: '4m ago' },
  { name: 'Correlation', department: 'QUANT RESEARCH', deptColor: DEPT_COLORS['QUANT RESEARCH'], signal: 'BULLISH', confidence: 68, status: 'COMPLETE', reasoning: 'Risk-asset correlation positive, BTC beta to NDX elevated at 1.4', updatedAgo: '5m ago' },
  { name: 'Sector Rotation', department: 'MACRO', deptColor: DEPT_COLORS['MACRO'], signal: 'BULLISH', confidence: 73, status: 'COMPLETE', reasoning: 'Capital rotating from bonds to risk assets, crypto prime beneficiary', updatedAgo: '6m ago' },
  { name: 'Global Macro', department: 'MACRO', deptColor: DEPT_COLORS['MACRO'], signal: 'BULLISH', confidence: 80, status: 'COMPLETE', reasoning: 'Dollar weakening, EM recovery, global liquidity expanding per M2 data', updatedAgo: '3m ago' },
  { name: 'Credit Risk', department: 'RISK MGMT', deptColor: DEPT_COLORS['RISK MGMT'], signal: 'NEUTRAL', confidence: 49, status: 'COMPLETE', reasoning: 'Credit spreads stable, no systemic stress signals, counterparty risk low', updatedAgo: '9m ago' },
  { name: 'FX Analyst', department: 'MACRO', deptColor: DEPT_COLORS['MACRO'], signal: 'BULLISH', confidence: 66, status: 'COMPLETE', reasoning: 'DXY breakdown from key support, USD weakness historically BTC bullish', updatedAgo: '7m ago' },
  { name: 'Rates Watcher', department: 'MACRO', deptColor: DEPT_COLORS['MACRO'], signal: 'BEARISH', confidence: 57, status: 'COMPLETE', reasoning: 'Short-end rates still elevated, real yield positive at 1.8% is headwind', updatedAgo: '5m ago' },
  { name: 'Commodity Intel', department: 'MACRO', deptColor: DEPT_COLORS['MACRO'], signal: 'BULLISH', confidence: 71, status: 'COMPLETE', reasoning: 'Gold breaking out, silver surging — inflation hedging narrative aiding BTC', updatedAgo: '4m ago' },
  { name: 'Alt Data Scout', department: 'SENTIMENT', deptColor: DEPT_COLORS['SENTIMENT'], signal: 'BULLISH', confidence: 77, status: 'COMPLETE', reasoning: 'Google Trends for "buy bitcoin" up 45%, app downloads record high', updatedAgo: '3m ago' },
  { name: 'Dark Pool Radar', department: 'EXECUTION', deptColor: DEPT_COLORS['EXECUTION'], signal: 'BULLISH', confidence: 84, status: 'COMPLETE', reasoning: 'Large block trades detected off-exchange suggesting institutional accumulation', updatedAgo: '2m ago' },
  { name: 'Tape Reader', department: 'EXECUTION', deptColor: DEPT_COLORS['EXECUTION'], signal: 'BULLISH', confidence: 79, status: 'COMPLETE', reasoning: 'Tape shows consistent lifting of offers, buying pressure overwhelming sellers', updatedAgo: '1m ago' },
  { name: 'Event Driver', department: 'MARKET INTEL', deptColor: DEPT_COLORS['MARKET INTEL'], signal: 'BULLISH', confidence: 75, status: 'COMPLETE', reasoning: 'BTC ETF rebalancing event next week, 3 major conferences in 30 days', updatedAgo: '6m ago' },
  { name: 'Regime Detector', department: 'QUANT RESEARCH', deptColor: DEPT_COLORS['QUANT RESEARCH'], signal: 'BULLISH', confidence: 82, status: 'COMPLETE', reasoning: 'Hidden Markov Model at 94% probability of Bull regime state', updatedAgo: '2m ago' },
  { name: 'Vol Surface AI', department: 'DERIVATIVES', deptColor: DEPT_COLORS['DERIVATIVES'], signal: 'BEARISH', confidence: 61, status: 'COMPLETE', reasoning: 'Volatility smile skewed put-heavy above $70k, market hedging upside', updatedAgo: '8m ago' },
  { name: 'Carry Trader', department: 'DERIVATIVES', deptColor: DEPT_COLORS['DERIVATIVES'], signal: 'BULLISH', confidence: 69, status: 'COMPLETE', reasoning: 'Positive carry on BTC futures, basis trade generating 8% annualized', updatedAgo: '5m ago' },
  { name: 'CTA Signal', department: 'QUANT RESEARCH', deptColor: DEPT_COLORS['QUANT RESEARCH'], signal: 'BULLISH', confidence: 76, status: 'ANALYZING', reasoning: 'Systematic trend followers increasing BTC exposure, estimated +$500M inflows', updatedAgo: '4m ago' },
  { name: 'Microstructure', department: 'EXECUTION', deptColor: DEPT_COLORS['EXECUTION'], signal: 'BULLISH', confidence: 73, status: 'COMPLETE', reasoning: 'Order flow imbalance 0.68 favoring buys, high-frequency signals positive', updatedAgo: '3m ago' },
  { name: 'Cross Asset', department: 'MACRO', deptColor: DEPT_COLORS['MACRO'], signal: 'BULLISH', confidence: 78, status: 'COMPLETE', reasoning: 'Risk-on tone across equities, credit, and commodities — crypto lagging, catch-up trade', updatedAgo: '2m ago' },
  { name: 'ESG Monitor', department: 'MARKET INTEL', deptColor: DEPT_COLORS['MARKET INTEL'], signal: 'NEUTRAL', confidence: 52, status: 'COMPLETE', reasoning: 'Mining energy mix improving but regulatory uncertainty in EU persists', updatedAgo: '10m ago' },
  { name: 'Pair Trader', department: 'QUANT RESEARCH', deptColor: DEPT_COLORS['QUANT RESEARCH'], signal: 'NEUTRAL', confidence: 53, status: 'COMPLETE', reasoning: 'BTC/ETH ratio at 52-week mean, no clear directional edge from relative value', updatedAgo: '7m ago' },
  { name: 'Chief Alpha', department: 'MARKET INTEL', deptColor: DEPT_COLORS['MARKET INTEL'], signal: 'BULLISH', confidence: 87, status: 'COMPLETE', reasoning: 'Confluence of 7 independent alpha signals with low correlation, high conviction', updatedAgo: '1m ago' },
];

const signalVariant = (s: Signal) =>
  s === 'BULLISH' ? 'success' : s === 'BEARISH' ? 'danger' : 'warning';

const signalColor = (s: Signal) =>
  s === 'BULLISH' ? '#22C55E' : s === 'BEARISH' ? '#EF4444' : '#F59E0B';

function AgentCard({ agent, index }: { agent: AgentData; index: number }) {
  const initials = agent.name
    .split(' ')
    .map((w) => w[0])
    .join('')
    .slice(0, 2)
    .toUpperCase();

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.03, duration: 0.3 }}
      className="rounded-xl p-4 flex flex-col gap-3 group transition-all duration-200"
      style={{
        background: '#121826',
        border: '1px solid rgba(255,255,255,0.06)',
        cursor: 'default',
      }}
      whileHover={{
        y: -2,
        boxShadow: `0 8px 32px rgba(0,0,0,0.4), 0 0 0 1px ${agent.deptColor}22`,
        borderColor: `${agent.deptColor}33`,
      }}
    >
      {/* Avatar + name + dept */}
      <div className="flex items-start gap-3">
        <div
          className="w-10 h-10 rounded-xl flex items-center justify-center text-xs font-bold text-white shrink-0"
          style={{ background: `${agent.deptColor}22`, border: `1px solid ${agent.deptColor}44`, color: agent.deptColor }}
        >
          {initials}
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-xs font-semibold truncate" style={{ color: '#F1F5F9' }}>
            {agent.name}
          </div>
          <div
            className="text-[10px] font-bold uppercase tracking-wider mt-0.5 truncate"
            style={{ color: agent.deptColor }}
          >
            {agent.department}
          </div>
        </div>
        {/* Status */}
        <div className="flex items-center gap-1 shrink-0">
          <span
            className="w-1.5 h-1.5 rounded-full"
            style={{
              background: agent.status === 'ANALYZING' ? '#F59E0B' : '#22C55E',
              animation: agent.status === 'ANALYZING' ? 'live-blink 1s infinite' : undefined,
            }}
          />
          <span className="text-[9px] font-medium" style={{ color: '#475569' }}>
            {agent.status === 'ANALYZING' ? 'ANALYZING' : 'DONE'}
          </span>
        </div>
      </div>

      {/* Confidence + signal */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ArcGauge
            value={agent.confidence}
            size={40}
            color={signalColor(agent.signal)}
            strokeWidth={3.5}
            label={`${agent.confidence}`}
          />
        </div>
        <Badge variant={signalVariant(agent.signal)}>
          {agent.signal}
        </Badge>
      </div>

      {/* Reasoning */}
      <p
        className="text-[11px] leading-relaxed line-clamp-2"
        style={{ color: '#94A3B8' }}
      >
        {agent.reasoning}
      </p>

      {/* Footer */}
      <div className="flex items-center justify-between">
        <span className="text-[10px]" style={{ color: '#475569' }}>
          {agent.updatedAgo}
        </span>
        <button
          className="flex items-center gap-1 text-[10px] font-medium transition-colors opacity-0 group-hover:opacity-100"
          style={{ color: '#4F7CFF' }}
        >
          View Details
          <ChevronRight className="w-3 h-3" />
        </button>
      </div>
    </motion.div>
  );
}

export default function AgentGrid() {
  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-bold" style={{ color: '#F1F5F9' }}>
          AI Agent Network
        </h2>
        <span className="text-xs" style={{ color: '#475569' }}>
          40 agents active
        </span>
      </div>
      <div className="grid grid-cols-4 gap-3">
        {AGENTS.map((agent, i) => (
          <AgentCard key={agent.name} agent={agent} index={i} />
        ))}
      </div>
    </div>
  );
}
