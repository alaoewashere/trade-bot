'use client';

import React, { useEffect, useRef, useState } from 'react';
import { TrendingUp } from 'lucide-react';
import Badge from '@/components/ui/Badge';

interface Candle {
  o: number;
  h: number;
  l: number;
  c: number;
  t: number;
  v: number;
}

function generateCandles(n = 60, basePrice = 65000): Candle[] {
  let price = basePrice;
  const now = Date.now();
  return Array.from({ length: n }, (_, i) => {
    const change = (Math.random() - 0.48) * 800;
    const o = price;
    price += change;
    const h = Math.max(o, price) + Math.random() * 200;
    const l = Math.min(o, price) - Math.random() * 200;
    const c = price;
    return { o, h, l, c, t: now - (n - i) * 14400000, v: Math.random() * 100 + 20 };
  });
}

function MiniChart({ candles }: { candles: Candle[] }) {
  const w = 100;
  const h = 100;
  const prices = candles.map((c) => c.c);
  const min = Math.min(...prices);
  const max = Math.max(...prices);
  const range = max - min || 1;

  const sx = (i: number) => (i / (candles.length - 1)) * w;
  const sy = (v: number) => h - ((v - min) / range) * h;

  const path = prices.map((v, i) => `${i === 0 ? 'M' : 'L'} ${sx(i).toFixed(1)} ${sy(v).toFixed(1)}`).join(' ');
  const lastColor = prices[prices.length - 1] >= prices[0] ? '#22C55E' : '#EF4444';

  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full h-full" preserveAspectRatio="none">
      <defs>
        <linearGradient id="chartGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={lastColor} stopOpacity="0.2" />
          <stop offset="100%" stopColor={lastColor} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path
        d={`${path} L ${sx(prices.length - 1)} ${h} L 0 ${h} Z`}
        fill="url(#chartGrad)"
      />
      <path d={path} fill="none" stroke={lastColor} strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

export default function ChartSection() {
  const [candles] = useState<Candle[]>(() => generateCandles(60, 65000));
  const [currentPrice, setCurrentPrice] = useState(67428.5);

  useEffect(() => {
    const id = setInterval(() => {
      setCurrentPrice((p) => +(p + (Math.random() - 0.48) * 40).toFixed(2));
    }, 2000);
    return () => clearInterval(id);
  }, []);

  const INDICATORS = [
    { label: 'RSI (14)', value: '58.4', neutral: true },
    { label: 'MACD', value: '+124.2', positive: true },
    { label: 'BB Width', value: '0.042', neutral: true },
    { label: 'ATR', value: '$1,248', neutral: true },
    { label: 'ADX', value: '32.1', positive: true },
    { label: 'OBV', value: '↑ Rising', positive: true },
  ];

  return (
    <div
      className="rounded-xl flex flex-col h-full"
      style={{
        background: '#121826',
        border: '1px solid rgba(255,255,255,0.06)',
        minHeight: 340,
      }}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between px-4 py-3"
        style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }}
      >
        <div className="flex items-center gap-3">
          <TrendingUp className="w-4 h-4" style={{ color: '#4F7CFF' }} />
          <span className="text-sm font-semibold" style={{ color: '#F1F5F9' }}>
            BTC / USDT
          </span>
          <span className="font-mono text-lg font-bold" style={{ color: '#22C55E' }}>
            ${currentPrice.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </span>
          <Badge variant="success">+1.87%</Badge>
        </div>
        <div className="flex items-center gap-2">
          {['1H', '4H', '1D', '1W'].map((tf, i) => (
            <button
              key={tf}
              className="px-2.5 py-1 rounded-md text-xs font-medium transition-colors"
              style={
                i === 1
                  ? { background: 'rgba(79,124,255,0.15)', color: '#4F7CFF', border: '1px solid rgba(79,124,255,0.3)' }
                  : { background: 'rgba(255,255,255,0.04)', color: '#94A3B8', border: '1px solid rgba(255,255,255,0.06)' }
              }
            >
              {tf}
            </button>
          ))}
        </div>
      </div>

      {/* Chart area */}
      <div className="flex-1 relative p-4" style={{ minHeight: 200 }}>
        <MiniChart candles={candles} />
        {/* Y-axis labels */}
        <div className="absolute right-5 top-4 bottom-4 flex flex-col justify-between">
          {['$70k', '$68k', '$66k', '$64k'].map((l) => (
            <span key={l} className="font-mono text-[10px]" style={{ color: '#475569' }}>
              {l}
            </span>
          ))}
        </div>
      </div>

      {/* Technical indicators */}
      <div
        className="px-4 py-3 grid grid-cols-6 gap-3"
        style={{ borderTop: '1px solid rgba(255,255,255,0.06)' }}
      >
        {INDICATORS.map((ind) => (
          <div key={ind.label}>
            <div className="text-[10px] uppercase tracking-wider" style={{ color: '#475569' }}>
              {ind.label}
            </div>
            <div
              className="font-mono text-xs font-semibold mt-0.5"
              style={{
                color: ind.positive ? '#22C55E' : ind.neutral ? '#F1F5F9' : '#EF4444',
              }}
            >
              {ind.value}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
