'use client';

import React, { useState } from 'react';
import { TrendingUp, TrendingDown, CheckCircle, AlertTriangle } from 'lucide-react';

// ─── Mock data ────────────────────────────────────────────────────────────────

const MOCK_EQUITY: number[] = (() => {
  const pts: number[] = [100000];
  for (let i = 1; i < 30; i++) {
    pts.push(pts[i - 1] * (1 + (Math.random() - 0.44) * 0.025));
  }
  return pts;
})();

interface Trade {
  symbol: string;
  direction: 'LONG' | 'SHORT';
  entry: number;
  exit: number;
  pnl: number;
  pnlPct: number;
  date: string;
}

const MOCK_TRADES: Trade[] = [
  { symbol: 'BTC/USDT', direction: 'LONG',  entry: 65200, exit: 67800, pnl: 2600,  pnlPct: 3.99,  date: '07/28' },
  { symbol: 'ETH/USDT', direction: 'LONG',  entry: 3420,  exit: 3650,  pnl: 230,   pnlPct: 6.73,  date: '07/27' },
  { symbol: 'SOL/USDT', direction: 'SHORT', entry: 186,   exit: 172,   pnl: 14,    pnlPct: 7.53,  date: '07/26' },
  { symbol: 'BTC/USDT', direction: 'SHORT', entry: 68500, exit: 70100, pnl: -1600, pnlPct: -2.34, date: '07/25' },
  { symbol: 'BNB/USDT', direction: 'LONG',  entry: 580,   exit: 612,   pnl: 32,    pnlPct: 5.52,  date: '07/24' },
];

const MOCK_EVIDENCE_SUPPORTING = [
  'RSI bullish at 67.2 on 1H chart',
  'EMA 20 cross above EMA 50 confirmed',
  'VWAP holding as support at $67,200',
  'On-chain: 42K BTC withdrawn from exchanges',
  'Long-term holder SOPR bullish divergence',
];

const MOCK_EVIDENCE_AGAINST = [
  '4H bearish RSI divergence forming',
  'Funding rate elevated at +0.045%',
  'Key resistance zone at $68,500',
  'Options put/call ratio at 1.32',
  'DXY short-term rebound risk',
];

// ─── Tiny SVG equity chart ────────────────────────────────────────────────────

function EquityChart({ data }: { data: number[] }) {
  const W = 280;
  const H = 72;
  const PAD = { t: 4, r: 4, b: 4, l: 4 };
  const cW = W - PAD.l - PAD.r;
  const cH = H - PAD.t - PAD.b;

  const min = Math.min(...data) * 0.998;
  const max = Math.max(...data) * 1.002;
  const range = max - min;

  const toX = (i: number) => PAD.l + (i / (data.length - 1)) * cW;
  const toY = (v: number) => PAD.t + (1 - (v - min) / range) * cH;

  const linePath = data
    .map((v, i) => `${i === 0 ? 'M' : 'L'}${toX(i).toFixed(1)},${toY(v).toFixed(1)}`)
    .join(' ');

  const isUp = data[data.length - 1] >= data[0];
  const color = isUp ? '#22C55E' : '#EF4444';

  const areaPath =
    linePath +
    ` L${toX(data.length - 1).toFixed(1)},${(PAD.t + cH).toFixed(1)}` +
    ` L${PAD.l.toFixed(1)},${(PAD.t + cH).toFixed(1)} Z`;

  return (
    <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} className="w-full">
      <defs>
        <linearGradient id="equityGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.2" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={areaPath} fill="url(#equityGrad)" />
      <path d={linePath} fill="none" stroke={color} strokeWidth={1.5} strokeLinecap="round" />
    </svg>
  );
}

// ─── Portfolio stats ──────────────────────────────────────────────────────────

function PortfolioStats() {
  const stats = [
    { label: 'Total P&L',   value: '+$284,750', color: '#22C55E' },
    { label: 'Daily P&L',   value: '+$18,320',  color: '#22C55E' },
    { label: 'Win Rate',    value: '68.4%',     color: '#22C55E' },
    { label: 'Sharpe',      value: '2.34',      color: '#3B82F6' },
    { label: 'Max DD',      value: '-4.2%',     color: '#EF4444' },
    { label: 'Open Pos.',   value: '3',         color: '#9B9BAA' },
  ];

  return (
    <div
      className="rounded-xl border p-4 flex flex-col gap-3"
      style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}
    >
      <div className="text-xs font-semibold text-[#9B9BAA] uppercase tracking-wide">Portfolio</div>
      <div className="grid grid-cols-3 gap-3">
        {stats.map(({ label, value, color }) => (
          <div key={label}>
            <div className="text-[10px] text-[#6B6B7A]">{label}</div>
            <div className="font-mono font-bold text-sm" style={{ color }}>{value}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Performance chart ────────────────────────────────────────────────────────

function PerformanceChart() {
  return (
    <div
      className="rounded-xl border p-4 flex flex-col gap-2"
      style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}
    >
      <div className="flex items-center justify-between">
        <div className="text-xs font-semibold text-[#9B9BAA] uppercase tracking-wide">Equity Curve</div>
        <span className="text-[10px] text-emerald-400 font-mono">+18.4%</span>
      </div>
      <EquityChart data={MOCK_EQUITY} />
      <div className="flex items-center gap-3 text-[10px] text-[#6B6B7A]">
        <span className="flex items-center gap-1"><span className="w-3 h-px bg-emerald-400 inline-block" />Portfolio</span>
        <span className="flex items-center gap-1"><span className="w-3 h-px bg-blue-400 inline-block border-dashed border-t border-blue-400" />BTC</span>
      </div>
    </div>
  );
}

// ─── Recent trades ────────────────────────────────────────────────────────────

function RecentTrades() {
  const [sortBy, setSortBy] = useState<'date' | 'pnl'>('date');

  const sorted = [...MOCK_TRADES].sort((a, b) =>
    sortBy === 'pnl' ? b.pnl - a.pnl : 0,
  );

  return (
    <div
      className="rounded-xl border flex flex-col overflow-hidden"
      style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}
    >
      <div
        className="flex items-center justify-between px-4 py-3 border-b"
        style={{ borderColor: 'var(--bg-border)' }}
      >
        <div className="text-xs font-semibold text-[#9B9BAA] uppercase tracking-wide">Recent Trades</div>
        <div className="flex gap-1">
          {(['date', 'pnl'] as const).map((key) => (
            <button
              key={key}
              onClick={() => setSortBy(key)}
              className="text-[10px] px-2 py-0.5 rounded transition-all"
              style={{
                background: sortBy === key ? 'rgba(59,130,246,0.1)' : 'transparent',
                color: sortBy === key ? '#3B82F6' : '#6B6B7A',
              }}
            >
              {key.toUpperCase()}
            </button>
          ))}
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
              {['Symbol', 'Dir', 'Entry', 'Exit', 'P&L', 'Date'].map((h) => (
                <th
                  key={h}
                  className="px-4 py-2 text-left font-medium text-[10px] text-[#6B6B7A] uppercase tracking-wide"
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.map((t, i) => {
              const isWin = t.pnl >= 0;
              return (
                <tr
                  key={i}
                  className="transition-colors hover:bg-white/[0.02]"
                  style={{ borderBottom: '1px solid rgba(255,255,255,0.03)' }}
                >
                  <td className="px-4 py-2.5 font-mono font-medium text-white">{t.symbol}</td>
                  <td className="px-4 py-2.5">
                    <span
                      className="flex items-center gap-1 text-[10px] font-semibold"
                      style={{ color: t.direction === 'LONG' ? '#22C55E' : '#EF4444' }}
                    >
                      {t.direction === 'LONG' ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                      {t.direction}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 font-mono text-[#9B9BAA]">${t.entry.toLocaleString()}</td>
                  <td className="px-4 py-2.5 font-mono text-[#9B9BAA]">${t.exit.toLocaleString()}</td>
                  <td className="px-4 py-2.5">
                    <span
                      className="font-mono font-semibold"
                      style={{ color: isWin ? '#22C55E' : '#EF4444' }}
                    >
                      {isWin ? '+' : ''}{t.pnlPct.toFixed(2)}%
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-[#6B6B7A] font-mono">{t.date}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ─── Evidence cards ───────────────────────────────────────────────────────────

function EvidenceCards() {
  return (
    <div
      className="rounded-xl border flex flex-col overflow-hidden"
      style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}
    >
      <div
        className="px-4 py-3 border-b text-xs font-semibold text-[#9B9BAA] uppercase tracking-wide"
        style={{ borderColor: 'var(--bg-border)' }}
      >
        Evidence Summary
      </div>
      <div className="grid grid-cols-2 divide-x p-4 gap-4" style={{ borderColor: 'var(--bg-border)' }}>
        <div className="pr-4">
          <div className="flex items-center gap-1.5 mb-2">
            <CheckCircle className="w-3.5 h-3.5 text-emerald-400" />
            <span className="text-[10px] text-emerald-400 font-semibold uppercase">Supporting</span>
          </div>
          <ul className="space-y-1.5">
            {MOCK_EVIDENCE_SUPPORTING.map((e, i) => (
              <li key={i} className="flex items-start gap-2 text-[11px] text-[#9B9BAA]">
                <span className="text-emerald-400 mt-0.5 shrink-0">·</span>
                {e}
              </li>
            ))}
          </ul>
        </div>
        <div className="pl-4">
          <div className="flex items-center gap-1.5 mb-2">
            <AlertTriangle className="w-3.5 h-3.5 text-red-400" />
            <span className="text-[10px] text-red-400 font-semibold uppercase">Contradicting</span>
          </div>
          <ul className="space-y-1.5">
            {MOCK_EVIDENCE_AGAINST.map((e, i) => (
              <li key={i} className="flex items-start gap-2 text-[11px] text-[#9B9BAA]">
                <span className="text-red-400 mt-0.5 shrink-0">·</span>
                {e}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}

// ─── Main ─────────────────────────────────────────────────────────────────────

export default function BottomSection() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
      <PortfolioStats />
      <PerformanceChart />
      <RecentTrades />
      <EvidenceCards />
    </div>
  );
}
