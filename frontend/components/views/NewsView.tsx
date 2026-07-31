'use client';

import React, { useState } from 'react';
import { motion } from 'framer-motion';

const FILTERS = ['All', 'Crypto', 'Stocks', 'Macro', 'Regulatory'];

const NEWS = [
  {
    source: 'BB', sourceName: 'Bloomberg', color: '#4F7CFF',
    headline: 'Bitcoin Surges Past $67K as Institutional Demand Accelerates',
    summary: 'Major asset managers report record inflows into Bitcoin ETFs as macro tailwinds strengthen the bullish case.',
    impact: 'HIGH', sentiment: 'BULLISH', time: '14 min ago',
    assets: ['BTC', 'ETH'], category: 'Crypto',
  },
  {
    source: 'RU', sourceName: 'Reuters', color: '#EF4444',
    headline: 'Fed Officials Signal Potential Rate Cut in September Meeting',
    summary: 'Two Fed governors indicated openness to cutting rates if inflation continues trending toward the 2% target.',
    impact: 'HIGH', sentiment: 'BULLISH', time: '28 min ago',
    assets: ['SPX', 'Gold'], category: 'Macro',
  },
  {
    source: 'CG', sourceName: 'CoinGecko', color: '#22C55E',
    headline: 'Ethereum Staking Yields Rise to 4.8% Amid Network Activity Surge',
    summary: 'Gas fees and validator rewards increase as DeFi protocols record highest TVL since 2022.',
    impact: 'MED', sentiment: 'BULLISH', time: '45 min ago',
    assets: ['ETH', 'SOL'], category: 'Crypto',
  },
  {
    source: 'FT', sourceName: 'Fin Times', color: '#F59E0B',
    headline: 'SEC Delays Decision on Spot Ethereum ETF Applications',
    summary: 'Regulatory body extends review period by 60 days citing need for additional public comment analysis.',
    impact: 'MED', sentiment: 'BEARISH', time: '1h 12m ago',
    assets: ['ETH'], category: 'Regulatory',
  },
  {
    source: 'CN', sourceName: 'CoinDesk', color: '#818CF8',
    headline: 'Solana DEX Volume Hits $8B Weekly Record Amid Memecoin Frenzy',
    summary: 'Raydium and Jupiter see unprecedented swap volumes as traders pile into newly launched tokens.',
    impact: 'MED', sentiment: 'BULLISH', time: '1h 38m ago',
    assets: ['SOL'], category: 'Crypto',
  },
  {
    source: 'WS', sourceName: 'WSJ', color: '#94A3B8',
    headline: 'S&P 500 Hits New All-Time High Driven by Tech and Energy Sectors',
    summary: 'Index crosses 5,300 for the first time as earnings season exceeds analyst expectations across sectors.',
    impact: 'HIGH', sentiment: 'BULLISH', time: '2h ago',
    assets: ['SPX', 'NVDA'], category: 'Stocks',
  },
  {
    source: 'DB', sourceName: 'DeBrief', color: '#22C55E',
    headline: 'MicroStrategy Announces Additional $500M Bitcoin Purchase Plan',
    summary: 'Corporate treasury strategy continues with board approval for new bond issuance to fund BTC accumulation.',
    impact: 'MED', sentiment: 'BULLISH', time: '2h 30m ago',
    assets: ['BTC', 'MSTR'], category: 'Crypto',
  },
  {
    source: 'AP', sourceName: 'AP News', color: '#64748B',
    headline: 'EU Proposes Stricter KYC Rules for Crypto Exchanges Operating in Region',
    summary: 'Draft legislation would require real-time transaction reporting for all trades above €1,000 threshold.',
    impact: 'LOW', sentiment: 'BEARISH', time: '3h ago',
    assets: ['BTC', 'ETH'], category: 'Regulatory',
  },
];

const IMPACT_COLORS: Record<string, { bg: string; text: string }> = {
  HIGH: { bg: 'rgba(239,68,68,0.12)', text: '#EF4444' },
  MED:  { bg: 'rgba(245,158,11,0.12)', text: '#F59E0B' },
  LOW:  { bg: 'rgba(71,85,105,0.3)', text: '#64748B' },
};

const SENT_COLORS: Record<string, { bg: string; text: string }> = {
  BULLISH:  { bg: 'rgba(34,197,94,0.12)', text: '#22C55E' },
  BEARISH:  { bg: 'rgba(239,68,68,0.12)', text: '#EF4444' },
  NEUTRAL:  { bg: 'rgba(71,85,105,0.2)', text: '#64748B' },
};

export default function NewsView() {
  const [activeFilter, setActiveFilter] = useState('All');

  const filtered = activeFilter === 'All' ? NEWS : NEWS.filter(n => n.category === activeFilter);

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      style={{ padding: 24, paddingBottom: 48 }}
    >
      <div style={{ marginBottom: 20 }}>
        <h1 style={{ fontSize: 20, fontWeight: 700, color: '#E2E8F0', margin: 0 }}>Market Intelligence — News Feed</h1>
        <p style={{ fontSize: 13, color: '#475569', marginTop: 4 }}>AI-curated news with sentiment analysis and market impact scoring</p>
      </div>

      {/* Filter tabs */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 20 }}>
        {FILTERS.map(f => (
          <button key={f} onClick={() => setActiveFilter(f)} style={{
            padding: '7px 16px', borderRadius: 8, fontSize: 12, fontWeight: 600, cursor: 'pointer',
            background: activeFilter === f ? 'rgba(79,124,255,0.15)' : 'rgba(255,255,255,0.04)',
            border: `1px solid ${activeFilter === f ? 'rgba(79,124,255,0.4)' : 'rgba(255,255,255,0.08)'}`,
            color: activeFilter === f ? '#4F7CFF' : '#64748B',
            transition: 'all 0.12s',
          }}>{f}</button>
        ))}
      </div>

      {/* News grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        {filtered.map((n, i) => {
          const ic = IMPACT_COLORS[n.impact];
          const sc = SENT_COLORS[n.sentiment];
          return (
            <motion.div key={i}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.04, duration: 0.2 }}
              style={{
                background: '#121826',
                border: '1px solid rgba(255,255,255,0.06)',
                borderRadius: 12, padding: 18, cursor: 'pointer',
                transition: 'border-color 0.15s',
              }}
              whileHover={{ borderColor: 'rgba(255,255,255,0.12)' }}
            >
              {/* Source + time */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <div style={{
                    width: 30, height: 30, borderRadius: 8, flexShrink: 0,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    background: `${n.color}22`, border: `1px solid ${n.color}44`,
                    fontSize: 10, fontWeight: 800, color: n.color,
                  }}>{n.source}</div>
                  <span style={{ fontSize: 11, color: '#475569' }}>{n.sourceName}</span>
                </div>
                <span style={{ fontSize: 11, color: '#334155' }}>{n.time}</span>
              </div>

              {/* Headline */}
              <div style={{ fontSize: 14, fontWeight: 700, color: '#E2E8F0', lineHeight: 1.45, marginBottom: 8 }}>
                {n.headline}
              </div>

              {/* Summary */}
              <div style={{
                fontSize: 12.5, color: '#64748B', lineHeight: 1.5, marginBottom: 12,
                display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden',
              } as React.CSSProperties}>
                {n.summary}
              </div>

              {/* Badges + assets */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                <span style={{ padding: '2px 8px', borderRadius: 5, fontSize: 10, fontWeight: 700, background: ic.bg, color: ic.text }}>
                  {n.impact} IMPACT
                </span>
                <span style={{ padding: '2px 8px', borderRadius: 5, fontSize: 10, fontWeight: 700, background: sc.bg, color: sc.text }}>
                  {n.sentiment}
                </span>
                <div style={{ flex: 1 }} />
                {n.assets.map(a => (
                  <span key={a} style={{
                    padding: '2px 7px', borderRadius: 5, fontSize: 10, fontWeight: 700,
                    background: 'rgba(79,124,255,0.1)', color: '#4F7CFF',
                  }}>{a}</span>
                ))}
              </div>
            </motion.div>
          );
        })}
      </div>
    </motion.div>
  );
}
