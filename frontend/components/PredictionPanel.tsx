'use client';

import React, { useState, useEffect } from 'react';
import { TrendingUp, TrendingDown, Minus, ChevronDown, ChevronUp } from 'lucide-react';
import { Prediction, MOCK_PREDICTIONS } from '../lib/api';
import { useForecasts } from '../lib/hooks/useForecasts';
import ConfidenceGauge from './ConfidenceGauge';

const TIMEFRAME_ORDER = ['1m', '3m', '5m', '15m', '30m', '1h', '4h', '1d'];

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

const EVIDENCE: Record<string, string[]> = {
  '1m':  ['Short-term momentum strong', 'Micro structure bullish'],
  '3m':  ['RSI cross above 50', 'Price above VWAP'],
  '5m':  ['EMA stack ordered', 'Volume increasing'],
  '15m': ['Order block holding', 'Bullish engulfing candle'],
  '30m': ['Support zone respected', 'OBV trending up'],
  '1h':  ['RSI bullish divergence', 'EMA cross confirmed'],
  '4h':  ['Neutral price action', 'Ranging between key levels'],
  '1d':  ['Bearish macro structure', 'Weekly resistance overhead'],
};

const TF_LABELS: Record<string, string> = {
  '1m': '1m', '3m': '3m', '5m': '5m', '15m': '15m',
  '30m': '30m', '1h': '1H', '4h': '4H', '1d': '1D',
};

function PredictionRow({ pred }: { pred: Prediction }) {
  const [expanded, setExpanded] = useState(false);
  const prices = MOCK_PRICES[pred.timeframe] ?? { forecast: 67000, low: 66000, high: 68000 };
  const isUp = pred.direction === 'bullish';
  const isDown = pred.direction === 'bearish';
  const color = isUp ? '#22C55E' : isDown ? '#EF4444' : '#F59E0B';
  const bgColor = isUp ? 'rgba(34,197,94,0.07)' : isDown ? 'rgba(239,68,68,0.07)' : 'rgba(245,158,11,0.07)';
  const borderColor = isUp ? 'rgba(34,197,94,0.18)' : isDown ? 'rgba(239,68,68,0.18)' : 'rgba(245,158,11,0.18)';
  const evidence = EVIDENCE[pred.timeframe] ?? [];

  const label = isUp ? 'BULLISH' : isDown ? 'BEARISH' : 'NEUTRAL';
  const Icon = isUp ? TrendingUp : isDown ? TrendingDown : Minus;

  return (
    <div
      className="rounded-xl border transition-all duration-200 overflow-hidden"
      style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}
    >
      <div
        className="flex items-center gap-3 p-3 cursor-pointer select-none hover:bg-white/[0.02]"
        onClick={() => setExpanded((v) => !v)}
      >
        {/* Timeframe */}
        <div
          className="w-10 text-center shrink-0 font-mono font-bold text-xs py-1 rounded"
          style={{ background: 'rgba(255,255,255,0.05)', color: '#9B9BAA' }}
        >
          {TF_LABELS[pred.timeframe] ?? pred.timeframe}
        </div>

        {/* Direction */}
        <div
          className="flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-semibold shrink-0 border"
          style={{ color, background: bgColor, borderColor }}
        >
          <Icon className="w-3 h-3" />
          {label}
        </div>

        {/* Progress bar */}
        <div className="flex-1 flex items-center gap-2">
          <div className="flex-1 h-1.5 rounded-full bg-white/5">
            <div
              className="h-full rounded-full transition-all duration-700"
              style={{ width: `${pred.confidence}%`, background: color }}
            />
          </div>
          <span className="font-mono text-xs font-semibold shrink-0" style={{ color }}>
            {pred.confidence}%
          </span>
        </div>

        {/* Price range */}
        <div className="hidden md:flex items-center gap-1 font-mono text-xs text-[#6B6B7A] shrink-0">
          <span className="text-[#9B9BAA]">${prices.low.toLocaleString()}</span>
          <span>–</span>
          <span className="text-[#9B9BAA]">${prices.high.toLocaleString()}</span>
        </div>

        {/* Expand */}
        <div className="shrink-0 text-[#6B6B7A]">
          {expanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
        </div>
      </div>

      {expanded && (
        <div
          className="px-4 pb-3 pt-1 border-t"
          style={{ borderColor: 'rgba(255,255,255,0.06)', background: 'rgba(255,255,255,0.01)' }}
        >
          <div className="text-[10px] text-[#6B6B7A] mb-2 uppercase tracking-wide">Evidence</div>
          <div className="flex flex-wrap gap-2">
            {evidence.map((e, i) => (
              <span
                key={i}
                className="text-xs px-2 py-1 rounded-lg border"
                style={{
                  color,
                  background: bgColor,
                  borderColor,
                }}
              >
                {e}
              </span>
            ))}
          </div>
          <div className="flex gap-4 mt-3 text-xs font-mono">
            <div>
              <span className="text-[#6B6B7A]">Bull: </span>
              <span className="text-emerald-400">{pred.bull_prob}%</span>
            </div>
            <div>
              <span className="text-[#6B6B7A]">Bear: </span>
              <span className="text-red-400">{pred.bear_prob}%</span>
            </div>
            <div>
              <span className="text-[#6B6B7A]">Neut: </span>
              <span className="text-amber-400">{pred.neutral_prob}%</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

interface PredictionPanelProps {
  symbol?: string;
  onPredictionsChange?: (preds: Prediction[]) => void;
}

export default function PredictionPanel({ symbol = 'BTC/USDT', onPredictionsChange }: PredictionPanelProps) {
  const [predictions, setPredictions] = useState<Prediction[]>(MOCK_PREDICTIONS);
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
    }
  }, [forecasts]);

  useEffect(() => {
    onPredictionsChange?.(predictions);
  }, [predictions, onPredictionsChange]);

  useEffect(() => {
    const interval = setInterval(() => {
      setPredictions((prev) =>
        prev.map((p) => ({
          ...p,
          confidence: Math.max(40, Math.min(95, p.confidence + Math.floor((Math.random() - 0.5) * 6))),
          bull_prob: Math.max(10, Math.min(85, p.bull_prob + Math.floor((Math.random() - 0.5) * 4))),
        })),
      );
    }, 30000);
    return () => clearInterval(interval);
  }, []);

  const bullCount = predictions.filter((p) => p.direction === 'bullish').length;
  const bearCount = predictions.filter((p) => p.direction === 'bearish').length;
  const overallDir = bullCount > bearCount ? 'BULLISH' : bearCount > bullCount ? 'BEARISH' : 'NEUTRAL';
  const overallColor = bullCount > bearCount ? '#22C55E' : bearCount > bullCount ? '#EF4444' : '#F59E0B';
  const avgConf = Math.round(predictions.reduce((s, p) => s + p.confidence, 0) / (predictions.length || 1));
  const avgBull = Math.round(predictions.reduce((s, p) => s + p.bull_prob, 0) / (predictions.length || 1));
  const avgBear = Math.round(predictions.reduce((s, p) => s + p.bear_prob, 0) / (predictions.length || 1));
  const avgNeut = Math.round(predictions.reduce((s, p) => s + p.neutral_prob, 0) / (predictions.length || 1));

  const OverallIcon = bullCount > bearCount ? TrendingUp : bearCount > bullCount ? TrendingDown : Minus;

  return (
    <div className="flex flex-col gap-3">
      {/* Overall signal card */}
      <div
        className="rounded-xl border p-4"
        style={{
          background: 'linear-gradient(135deg, rgba(14,18,35,0.95) 0%, rgba(15,23,42,0.85) 100%)',
          borderColor: 'rgba(255,255,255,0.09)',
          backdropFilter: 'blur(8px)',
        }}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div
              className="w-10 h-10 rounded-xl flex items-center justify-center"
              style={{
                background:
                  bullCount > bearCount
                    ? 'rgba(34,197,94,0.1)'
                    : bearCount > bullCount
                    ? 'rgba(239,68,68,0.1)'
                    : 'rgba(245,158,11,0.1)',
              }}
            >
              <OverallIcon className="w-5 h-5" style={{ color: overallColor }} />
            </div>
            <div>
              <div className="text-[10px] text-[#6B6B7A] uppercase tracking-wide">Overall Signal</div>
              <div className="font-bold text-lg" style={{ color: overallColor }}>
                {overallDir}
              </div>
            </div>
          </div>
          <ConfidenceGauge value={avgConf} size={72} label="Conf" />
        </div>

        {/* Probability bars */}
        <div className="mt-3 space-y-1.5">
          {[
            { label: 'Bull', value: avgBull, color: '#22C55E' },
            { label: 'Bear', value: avgBear, color: '#EF4444' },
            { label: 'Neut', value: avgNeut, color: '#F59E0B' },
          ].map(({ label, value, color }) => (
            <div key={label} className="flex items-center gap-2">
              <span className="text-[10px] text-[#6B6B7A] w-8">{label}</span>
              <div className="flex-1 h-1.5 rounded-full bg-white/5">
                <div
                  className="h-full rounded-full transition-all duration-700"
                  style={{ width: `${value}%`, background: color }}
                />
              </div>
              <span className="text-[10px] font-mono" style={{ color }}>{value}%</span>
            </div>
          ))}
        </div>
      </div>

      {/* Timeframe rows */}
      <div className="space-y-2">
        {predictions.map((pred) => (
          <PredictionRow key={pred.timeframe} pred={pred} />
        ))}
      </div>
    </div>
  );
}
