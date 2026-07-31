'use client';

import React, { useState, useEffect } from 'react';
import { Prediction, MOCK_PREDICTIONS } from '../lib/api';
import { useForecasts } from '../lib/hooks/useForecasts';

// ─── Constants ────────────────────────────────────────────────────────────────

const TIMEFRAME_ORDER = ['1m', '3m', '5m', '15m', '30m', '1h', '4h', '1d'];
const TIMEFRAME_LABELS: Record<string, string> = {
  '1m':  ' 1 MIN',
  '3m':  ' 3 MIN',
  '5m':  ' 5 MIN',
  '15m': '15 MIN',
  '30m': '30 MIN',
  '1h':  ' 1 HR ',
  '4h':  ' 4 HR ',
  '1d':  ' 1 DAY',
};

// Mock price data per timeframe (forecast + range)
const MOCK_PRICES: Record<string, { forecast: number; low: number; high: number }> = {
  '1m':  { forecast: 67520, low: 67380, high: 67650 },
  '3m':  { forecast: 67580, low: 67200, high: 67800 },
  '5m':  { forecast: 67450, low: 66900, high: 68100 },
  '15m': { forecast: 67750, low: 66500, high: 68500 },
  '30m': { forecast: 68100, low: 66000, high: 69000 },
  '1h':  { forecast: 68900, low: 65500, high: 70000 },
  '4h':  { forecast: 65200, low: 64000, high: 68000 },
  '1d':  { forecast: 67000, low: 62000, high: 72000 },
};

const MOCK_SUPPORTING = [
  'Strong upward momentum on 1H chart',
  'On-chain accumulation signals active',
  'VWAP support holding at $67,200',
  'Exchange outflows: 42,000 BTC in 24h',
  'Long-term holder SOPR bullish divergence',
];

const MOCK_CONTRADICTING = [
  '4H bearish RSI divergence forming',
  'Funding rate elevated at +0.045%',
  'Key resistance zone at $68,500',
  'Options put/call ratio at 1.32',
  'DXY short-term rebound risk',
];

// ─── Helpers ──────────────────────────────────────────────────────────────────

function fmt(n: number) {
  return '$' + n.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 });
}

function confBar(pct: number, color: string) {
  const filled = Math.round(pct / 10);
  return (
    <span style={{ color }}>
      {Array.from({ length: 10 }, (_, i) => (i < filled ? '█' : '░')).join('')}
    </span>
  );
}

// ─── Direction cell ───────────────────────────────────────────────────────────

function DirectionCell({ direction }: { direction: Prediction['direction'] }) {
  if (direction === 'bullish') {
    return (
      <span className="font-bold" style={{ color: '#00ff41' }}>
        ▲ BULL
      </span>
    );
  }
  if (direction === 'bearish') {
    return (
      <span className="font-bold" style={{ color: '#ff2222' }}>
        ▼ BEAR
      </span>
    );
  }
  return (
    <span className="font-bold" style={{ color: '#ffb000' }}>
      — NEUT
    </span>
  );
}

// ─── Prediction row ───────────────────────────────────────────────────────────

function PredictionRow({ pred, currentPrice }: { pred: Prediction; currentPrice: number }) {
  const prices = MOCK_PRICES[pred.timeframe] ?? { forecast: currentPrice, low: currentPrice * 0.98, high: currentPrice * 1.02 };
  const confColor =
    pred.direction === 'bullish' ? '#00ff41' : pred.direction === 'bearish' ? '#ff2222' : '#ffb000';

  const isHighlighted =
    (pred.direction === 'bullish' && pred.confidence >= 75) ||
    (pred.direction === 'bearish' && pred.confidence >= 70);

  return (
    <div
      className="grid items-center px-4 py-2 border-b border-[#141414] hover:bg-[#111111] transition-colors"
      style={{
        gridTemplateColumns: '70px 90px 100px 180px 100px',
        background: isHighlighted ? 'rgba(0,255,65,0.02)' : undefined,
      }}
    >
      {/* Timeframe */}
      <span className="font-bold text-[#cccccc] text-sm tracking-wider">
        {TIMEFRAME_LABELS[pred.timeframe] ?? pred.timeframe}
      </span>

      {/* Direction */}
      <span className="text-sm">
        <DirectionCell direction={pred.direction} />
      </span>

      {/* Forecast price */}
      <span className="font-mono text-sm text-[#cccccc]">{fmt(prices.forecast)}</span>

      {/* Range */}
      <span className="font-mono text-xs text-[#666666]">
        {fmt(prices.low)}
        <span className="text-[#333333]"> – </span>
        {fmt(prices.high)}
      </span>

      {/* Confidence with bar */}
      <span className="font-mono text-sm">
        <span style={{ color: confColor }}>{pred.confidence}%</span>
        <span className="ml-2 text-xs">{confBar(pred.confidence, confColor)}</span>
      </span>
    </div>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────

export default function PredictionTerminal() {
  const [predictions, setPredictions] = useState<Prediction[]>(MOCK_PREDICTIONS);
  const [symbol, setSymbol] = useState('BTC/USDT');
  const [currentPrice] = useState(67428.5);
  const [lastUpdate, setLastUpdate] = useState(new Date());

  const { forecasts } = useForecasts(symbol, 8);

  useEffect(() => {
    if (forecasts.length > 0) {
      const mapped: Prediction[] = forecasts.map((f) => ({
        timeframe: f.timeframe,
        direction: f.direction,
        confidence: Math.round(f.confidence_pct ?? 70),
        bull_prob: Math.round((f.bull_probability ?? 0.5) * 100),
        bear_prob: Math.round((f.bear_probability ?? 0.5) * 100),
        neutral_prob: Math.round((f.neutral_probability ?? 0) * 100),
        predicted_low: f.predicted_low ?? 0,
        predicted_high: f.predicted_high ?? 0,
        market_regime: f.market_regime ?? 'unknown',
      }));
      const sorted = [...mapped].sort(
        (a, b) => TIMEFRAME_ORDER.indexOf(a.timeframe) - TIMEFRAME_ORDER.indexOf(b.timeframe),
      );
      setPredictions(sorted);
      setLastUpdate(new Date());
    }
  }, [forecasts]);

  // Simulate live updates in demo mode
  useEffect(() => {
    const interval = setInterval(() => {
      setPredictions((prev) =>
        prev.map((p) => ({
          ...p,
          confidence: Math.max(40, Math.min(95, p.confidence + Math.floor((Math.random() - 0.5) * 6))),
          bull_prob: Math.max(10, Math.min(85, p.bull_prob + Math.floor((Math.random() - 0.5) * 4))),
        })),
      );
      setLastUpdate(new Date());
    }, 30000);
    return () => clearInterval(interval);
  }, []);

  const bullCount = predictions.filter((p) => p.direction === 'bullish').length;
  const bearCount = predictions.filter((p) => p.direction === 'bearish').length;
  const neutralCount = predictions.length - bullCount - bearCount;

  const overallDir = bullCount > bearCount ? 'TRENDING UP' : bearCount > bullCount ? 'TRENDING DOWN' : 'RANGING';
  const overallColor = bullCount > bearCount ? '#00ff41' : bearCount > bullCount ? '#ff2222' : '#ffb000';

  // Derive signal when 1h+ majority agree
  const longTermPreds = predictions.filter((p) => ['1h', '4h', '1d'].includes(p.timeframe));
  const ltBull = longTermPreds.filter((p) => p.direction === 'bullish').length;
  const ltBear = longTermPreds.filter((p) => p.direction === 'bearish').length;
  const macroSignal =
    ltBull > ltBear ? 'BUY SIGNAL' : ltBear > ltBull ? 'SELL SIGNAL' : null;
  const macroSignalColor = ltBull > ltBear ? '#00ff41' : '#ff2222';

  // Probability breakdown (avg)
  const avgBull = Math.round(predictions.reduce((s, p) => s + p.bull_prob, 0) / predictions.length);
  const avgBear = Math.round(predictions.reduce((s, p) => s + p.bear_prob, 0) / predictions.length);
  const avgNeut = Math.round(predictions.reduce((s, p) => s + p.neutral_prob, 0) / predictions.length);

  return (
    <div className="max-w-5xl mx-auto">
      <div className="bg-[#0d0d0d] border border-[#1a1a1a] rounded-lg overflow-hidden">

        {/* ── TERMINAL TITLE BAR ─────────────────────────────────────────── */}
        <div className="bg-[#111111] border-b border-[#1a1a1a] px-4 py-2 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-[#00ff41] font-bold tracking-widest text-sm">
              ULTRA SHORT-TERM PREDICTION ENGINE
            </span>
            <span className="text-[#333333]">─</span>
            <select
              value={symbol}
              onChange={(e) => setSymbol(e.target.value)}
              className="bg-[#0a0a0a] border border-[#222222] text-[#00ff41] text-xs px-2 py-0.5 rounded font-mono"
            >
              <option>BTC/USDT</option>
              <option>ETH/USDT</option>
              <option>SOL/USDT</option>
              <option>BNB/USDT</option>
              <option>XRP/USDT</option>
            </select>
          </div>
          <div className="text-[10px] text-[#333333]">
            LAST UPDATED:{' '}
            {lastUpdate.toLocaleTimeString('en-US', { hour12: false })} UTC
          </div>
        </div>

        {/* ── PRICE + REGIME STRIP ───────────────────────────────────────── */}
        <div className="px-4 py-3 border-b border-[#1a1a1a] bg-[#0a0a0a] flex items-center justify-between">
          <div className="flex items-center gap-6">
            <div>
              <div className="text-[9px] text-[#444444] uppercase tracking-widest mb-0.5">Current Price</div>
              <div className="text-2xl font-bold font-mono text-[#00ff41]">
                ${currentPrice.toLocaleString('en-US', { minimumFractionDigits: 2 })}
              </div>
              <div className="text-xs text-[#00ff41] mt-0.5">▲ +1.87%</div>
            </div>
            <div className="border-l border-[#1a1a1a] pl-6">
              <div className="text-[9px] text-[#444444] uppercase tracking-widest mb-0.5">Market Regime</div>
              <div className="text-lg font-bold" style={{ color: overallColor }}>
                {overallDir}
              </div>
            </div>
            {macroSignal && (
              <div className="border-l border-[#1a1a1a] pl-6">
                <div className="text-[9px] text-[#444444] uppercase tracking-widest mb-0.5">1H+ Consensus</div>
                <div
                  className="text-lg font-bold animate-pulse"
                  style={{ color: macroSignalColor }}
                >
                  ⬤ {macroSignal}
                </div>
              </div>
            )}
          </div>
          <div className="flex items-center gap-4 text-xs text-[#444444]">
            <span>
              <span style={{ color: '#00ff41' }}>BULL: {bullCount}</span>
              {' / '}
              <span style={{ color: '#ff2222' }}>BEAR: {bearCount}</span>
              {' / '}
              <span style={{ color: '#ffb000' }}>NEUT: {neutralCount}</span>
            </span>
          </div>
        </div>

        {/* ── TABLE SECTION ──────────────────────────────────────────────── */}
        <div className="px-4 py-2 border-b border-[#1a1a1a] bg-[#080808]">
          <div className="text-[10px] text-[#444444] uppercase tracking-widest py-1">
            8 TIMEFRAME FORECASTS
          </div>
        </div>

        {/* Column headers */}
        <div
          className="grid px-4 py-2 border-b border-[#1a1a1a] bg-[#0a0a0a] text-[9px] text-[#444444] uppercase tracking-widest"
          style={{ gridTemplateColumns: '70px 90px 100px 180px 100px' }}
        >
          <span>TF</span>
          <span>DIRECTION</span>
          <span>FORECAST</span>
          <span>RANGE (LOW – HIGH)</span>
          <span>CONFIDENCE</span>
        </div>

        {/* Rows */}
        <div>
          {predictions.map((pred) => (
            <PredictionRow key={pred.timeframe} pred={pred} currentPrice={currentPrice} />
          ))}
        </div>

        {/* ── PROBABILITY BREAKDOWN ──────────────────────────────────────── */}
        <div className="border-t border-[#1a1a1a] px-4 py-3 bg-[#0a0a0a]">
          <div className="text-[9px] text-[#444444] uppercase tracking-widest mb-2">
            PROBABILITY BREAKDOWN (AVERAGE ACROSS ALL TIMEFRAMES)
          </div>
          <div className="flex items-center gap-4 text-sm font-mono">
            <div>
              <span style={{ color: '#00ff41' }}>Bull: {avgBull}% </span>
              <span className="text-xs" style={{ color: '#00ff41' }}>
                {confBar(avgBull, '#00ff41')}
              </span>
            </div>
            <div>
              <span style={{ color: '#ff2222' }}>Bear: {avgBear}% </span>
              <span className="text-xs" style={{ color: '#ff2222' }}>
                {confBar(avgBear, '#ff2222')}
              </span>
            </div>
            <div>
              <span style={{ color: '#ffb000' }}>Neutral: {avgNeut}%</span>
            </div>
          </div>
        </div>

        {/* ── EVIDENCE PANELS ────────────────────────────────────────────── */}
        <div className="border-t border-[#1a1a1a] grid grid-cols-2 divide-x divide-[#1a1a1a]">
          <div className="px-4 py-3">
            <div className="text-[9px] text-[#00ff41] uppercase tracking-widest mb-2">
              SUPPORTING EVIDENCE
            </div>
            <ul className="space-y-1">
              {MOCK_SUPPORTING.map((s, i) => (
                <li key={i} className="text-xs text-[#888888] flex items-start gap-1">
                  <span style={{ color: '#00ff41' }}>•</span>
                  <span>{s}</span>
                </li>
              ))}
            </ul>
          </div>
          <div className="px-4 py-3">
            <div className="text-[9px] text-[#ff2222] uppercase tracking-widest mb-2">
              CONTRADICTING EVIDENCE
            </div>
            <ul className="space-y-1">
              {MOCK_CONTRADICTING.map((s, i) => (
                <li key={i} className="text-xs text-[#888888] flex items-start gap-1">
                  <span style={{ color: '#ff2222' }}>•</span>
                  <span>{s}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>

        {/* ── SELF-EVALUATION ────────────────────────────────────────────── */}
        <div className="border-t border-[#1a1a1a] px-4 py-3 bg-[#080808]">
          <div className="text-[9px] text-[#444444] uppercase tracking-widest mb-2">
            SELF-EVALUATION (LAST 100 PREDICTIONS)
          </div>
          <div className="grid grid-cols-5 gap-4 text-xs font-mono">
            <div>
              <div className="text-[9px] text-[#333333] mb-0.5">DIRECTION ACCURACY</div>
              <div className="text-[#00ff41] font-bold">68%</div>
            </div>
            <div>
              <div className="text-[9px] text-[#333333] mb-0.5">AVG PRICE ERROR</div>
              <div className="text-[#ffb000] font-bold">0.34%</div>
            </div>
            <div>
              <div className="text-[9px] text-[#333333] mb-0.5">BRIER SCORE</div>
              <div className="text-[#00ff41] font-bold">0.21</div>
            </div>
            <div>
              <div className="text-[9px] text-[#333333] mb-0.5">WIN STREAK</div>
              <div className="text-[#00ff41] font-bold">7</div>
            </div>
            <div>
              <div className="text-[9px] text-[#333333] mb-0.5">CALIBRATION</div>
              <div className="text-[#00ff41] font-bold">GOOD</div>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
