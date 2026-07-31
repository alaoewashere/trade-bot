'use client';

import React, { useState, useEffect } from 'react';
import { TrendingUp, TrendingDown, Activity, Brain, Clock, BarChart2 } from 'lucide-react';
import { Prediction } from '../lib/api';

interface StatsBarProps {
  predictions: Prediction[];
  price?: number;
  changePct?: number;
}

function StatCard({
  icon,
  label,
  value,
  sub,
  valueColor,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  sub?: string;
  valueColor?: string;
}) {
  return (
    <div
      className="flex items-center gap-3 px-4 py-3 rounded-xl border shrink-0"
      style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}
    >
      <div
        className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0"
        style={{ background: 'rgba(255,255,255,0.04)' }}
      >
        {icon}
      </div>
      <div>
        <div className="text-[10px] text-[#6B6B7A] uppercase tracking-wide font-medium">{label}</div>
        <div
          className="font-mono font-semibold text-sm leading-tight"
          style={{ color: valueColor || '#FFFFFF' }}
        >
          {value}
        </div>
        {sub && <div className="text-[10px] text-[#6B6B7A]">{sub}</div>}
      </div>
    </div>
  );
}

export default function StatsBar({ predictions, price = 67428.5, changePct = 1.87 }: StatsBarProps) {
  const [lastUpdate, setLastUpdate] = useState(new Date());

  useEffect(() => {
    const t = setInterval(() => setLastUpdate(new Date()), 30000);
    return () => clearInterval(t);
  }, []);

  const bullCount = predictions.filter((p) => p.direction === 'bullish').length;
  const bearCount = predictions.filter((p) => p.direction === 'bearish').length;
  const total = predictions.length || 8;
  const bullPct = Math.round((bullCount / total) * 100);
  const avgConf = Math.round(
    predictions.reduce((s, p) => s + p.confidence, 0) / (predictions.length || 1),
  );

  const regime =
    bullCount > bearCount ? 'TRENDING UP' : bearCount > bullCount ? 'TRENDING DOWN' : 'RANGING';
  const regimeColor =
    bullCount > bearCount ? '#22C55E' : bearCount > bullCount ? '#EF4444' : '#F59E0B';

  const consensus =
    bullPct > 60 ? 'BULLISH' : bullPct < 40 ? 'BEARISH' : 'NEUTRAL';
  const consensusColor =
    bullPct > 60 ? '#22C55E' : bullPct < 40 ? '#EF4444' : '#F59E0B';

  const isPositive = changePct >= 0;
  const priceColor = isPositive ? '#22C55E' : '#EF4444';

  const timeAgo = () => {
    const diff = Math.floor((Date.now() - lastUpdate.getTime()) / 1000);
    if (diff < 5) return 'just now';
    if (diff < 60) return `${diff}s ago`;
    return `${Math.floor(diff / 60)}m ago`;
  };

  return (
    <div
      className="flex items-center gap-3 px-4 py-2 overflow-x-auto"
      style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }}
    >
      <StatCard
        icon={<BarChart2 className="w-4 h-4 text-[#9B9BAA]" />}
        label="BTC/USDT"
        value={`$${price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
        sub={`${isPositive ? '+' : ''}${changePct.toFixed(2)}% 24h`}
        valueColor={priceColor}
      />

      <StatCard
        icon={
          isPositive
            ? <TrendingUp className="w-4 h-4 text-emerald-400" />
            : <TrendingDown className="w-4 h-4 text-red-400" />
        }
        label="24H Change"
        value={`${isPositive ? '+' : ''}${changePct.toFixed(2)}%`}
        valueColor={priceColor}
      />

      <StatCard
        icon={<Activity className="w-4 h-4 text-[#9B9BAA]" />}
        label="Market Regime"
        value={regime}
        valueColor={regimeColor}
      />

      <StatCard
        icon={<Brain className="w-4 h-4 text-[#8B5CF6]" />}
        label="AI Consensus"
        value={`${consensus} ${bullPct}%`}
        sub={`${bullCount}/${total} TF bullish`}
        valueColor={consensusColor}
      />

      <StatCard
        icon={<Activity className="w-4 h-4 text-[#3B82F6]" />}
        label="Avg Confidence"
        value={`${avgConf}%`}
        sub="across 8 TFs"
        valueColor={avgConf >= 70 ? '#22C55E' : avgConf >= 50 ? '#F59E0B' : '#EF4444'}
      />

      <StatCard
        icon={<Clock className="w-4 h-4 text-[#9B9BAA]" />}
        label="Last Update"
        value={timeAgo()}
        sub={lastUpdate.toLocaleTimeString('en-US', { hour12: false })}
      />

      {/* Live indicator */}
      <div className="flex items-center gap-2 shrink-0 ml-auto">
        <span className="w-2 h-2 rounded-full bg-emerald-400 live-dot" />
        <span className="text-xs text-[#9B9BAA] font-medium">LIVE</span>
      </div>
    </div>
  );
}
