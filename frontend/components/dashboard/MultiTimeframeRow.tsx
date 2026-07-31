'use client';

import React, { useMemo } from 'react';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { motion } from 'framer-motion';

interface TFData {
  tf: string;
  direction: 'up' | 'down' | 'flat';
  confidence: number;
  support: number;
  resistance: number;
  points: number[];
}

function generateSparkline(trend: 'up' | 'down' | 'flat', n = 20): number[] {
  let v = 50;
  return Array.from({ length: n }, () => {
    const dir = trend === 'up' ? 0.55 : trend === 'down' ? 0.45 : 0.5;
    v = Math.max(5, Math.min(95, v + (Math.random() > dir ? 3 : -3) * Math.random() * 4));
    return v;
  });
}

const TF_DATA: TFData[] = [
  { tf: '1m', direction: 'up', confidence: 62, support: 67100, resistance: 68200, points: generateSparkline('up') },
  { tf: '3m', direction: 'up', confidence: 68, support: 66900, resistance: 68500, points: generateSparkline('up') },
  { tf: '5m', direction: 'flat', confidence: 51, support: 66800, resistance: 68800, points: generateSparkline('flat') },
  { tf: '15m', direction: 'up', confidence: 77, support: 66200, resistance: 68500, points: generateSparkline('up') },
  { tf: '30m', direction: 'up', confidence: 74, support: 65900, resistance: 68500, points: generateSparkline('up') },
  { tf: '1H', direction: 'up', confidence: 81, support: 65500, resistance: 69200, points: generateSparkline('up') },
  { tf: '4H', direction: 'up', confidence: 78, support: 64800, resistance: 70000, points: generateSparkline('up') },
  { tf: '1D', direction: 'down', confidence: 44, support: 62000, resistance: 72000, points: generateSparkline('down') },
];

function MiniSparkline({ points, color }: { points: number[]; color: string }) {
  const w = 120;
  const h = 32;
  const minV = Math.min(...points);
  const maxV = Math.max(...points);
  const range = maxV - minV || 1;
  const scaleX = (i: number) => (i / (points.length - 1)) * w;
  const scaleY = (v: number) => h - ((v - minV) / range) * h;
  const d = points
    .map((v, i) => `${i === 0 ? 'M' : 'L'} ${scaleX(i).toFixed(1)} ${scaleY(v).toFixed(1)}`)
    .join(' ');

  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} className="overflow-visible">
      <path d={d} fill="none" stroke={color} strokeWidth={1.5} strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

function TFCard({ data, index }: { data: TFData; index: number }) {
  const color =
    data.direction === 'up' ? '#22C55E' : data.direction === 'down' ? '#EF4444' : '#F59E0B';
  const Icon =
    data.direction === 'up' ? TrendingUp : data.direction === 'down' ? TrendingDown : Minus;

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.06, duration: 0.3 }}
      className="flex flex-col gap-2 p-3 rounded-xl shrink-0 transition-all duration-200"
      style={{
        minWidth: 150,
        background: '#121826',
        border: '1px solid rgba(255,255,255,0.06)',
      }}
    >
      {/* Timeframe + icon */}
      <div className="flex items-center justify-between">
        <span className="font-mono text-xs font-bold" style={{ color: '#94A3B8' }}>
          {data.tf}
        </span>
        <Icon className="w-3.5 h-3.5" style={{ color }} />
      </div>

      {/* Confidence */}
      <div className="font-mono font-bold text-xl leading-none" style={{ color }}>
        {data.confidence}%
      </div>

      {/* Sparkline */}
      <div className="overflow-hidden" style={{ height: 32 }}>
        <MiniSparkline points={data.points} color={color} />
      </div>

      {/* Support / Resistance */}
      <div className="flex flex-col gap-0.5">
        <div className="flex items-center justify-between text-[10px]">
          <span style={{ color: '#475569' }}>S</span>
          <span className="font-mono" style={{ color: '#22C55E' }}>
            {(data.support / 1000).toFixed(1)}k
          </span>
        </div>
        <div className="flex items-center justify-between text-[10px]">
          <span style={{ color: '#475569' }}>R</span>
          <span className="font-mono" style={{ color: '#EF4444' }}>
            {(data.resistance / 1000).toFixed(1)}k
          </span>
        </div>
      </div>
    </motion.div>
  );
}

export default function MultiTimeframeRow() {
  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-semibold" style={{ color: '#F1F5F9' }}>
          Multi-Timeframe Analysis
        </h2>
        <span className="text-xs" style={{ color: '#475569' }}>
          BTC / USDT
        </span>
      </div>
      <div className="flex gap-3 overflow-x-auto scrollbar-hide pb-1">
        {TF_DATA.map((d, i) => (
          <TFCard key={d.tf} data={d} index={i} />
        ))}
      </div>
    </div>
  );
}
