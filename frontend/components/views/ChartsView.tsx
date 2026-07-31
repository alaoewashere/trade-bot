'use client';

import React, { useState } from 'react';
import { motion } from 'framer-motion';

const TIMEFRAMES = ['1m', '5m', '15m', '1h', '4h', '1D', '1W'];
const SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT'];

function CandlestickMock() {
  // Generate synthetic OHLC bars
  const bars = Array.from({ length: 60 }, (_, i) => {
    const base = 400 + Math.sin(i * 0.18) * 80 + Math.sin(i * 0.05) * 120 + i * 1.2;
    const open  = base + (Math.random() - 0.5) * 30;
    const close = open + (Math.random() - 0.5) * 40;
    const high  = Math.max(open, close) + Math.random() * 20;
    const low   = Math.min(open, close) - Math.random() * 20;
    return { open, close, high, low, bull: close >= open };
  });

  const allVals = bars.flatMap(b => [b.high, b.low]);
  const minV = Math.min(...allVals);
  const maxV = Math.max(...allVals);
  const range = maxV - minV || 1;
  const h = 280;
  const w = 780;
  const barW = w / bars.length;

  const toY = (v: number) => h - ((v - minV) / range) * (h - 20) - 10;

  return (
    <svg width="100%" height={h} viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" style={{ display: 'block' }}>
      {/* Grid lines */}
      {[0, 0.25, 0.5, 0.75, 1].map(f => (
        <line key={f} x1={0} y1={toY(minV + f * range)} x2={w} y2={toY(minV + f * range)}
          stroke="rgba(255,255,255,0.05)" strokeWidth={1} />
      ))}
      {bars.map((b, i) => {
        const x = i * barW + barW / 2;
        const bw = barW * 0.6;
        const bodyTop = toY(Math.max(b.open, b.close));
        const bodyBot = toY(Math.min(b.open, b.close));
        const bodyH = Math.max(1, bodyBot - bodyTop);
        const color = b.bull ? '#22C55E' : '#EF4444';
        return (
          <g key={i}>
            <line x1={x} y1={toY(b.high)} x2={x} y2={toY(b.low)} stroke={color} strokeWidth={1} opacity={0.7} />
            <rect x={x - bw / 2} y={bodyTop} width={bw} height={bodyH} fill={color} opacity={0.85} rx={1} />
          </g>
        );
      })}
    </svg>
  );
}

export default function ChartsView() {
  const [symbol, setSymbol] = useState('BTC/USDT');
  const [tf, setTf] = useState('1h');

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      style={{ padding: 24, paddingBottom: 48 }}
    >
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 20, fontWeight: 700, color: '#E2E8F0', margin: 0 }}>Live Charts</h1>
        <p style={{ fontSize: 13, color: '#475569', marginTop: 4 }}>Real-time candlestick charts with AI signal overlay</p>
      </div>

      {/* Toolbar */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16,
        flexWrap: 'wrap',
      }}>
        {/* Symbol select */}
        <div style={{ display: 'flex', gap: 6 }}>
          {SYMBOLS.map(s => (
            <button key={s} onClick={() => setSymbol(s)} style={{
              padding: '6px 14px', borderRadius: 8, fontSize: 12, fontWeight: 600, cursor: 'pointer',
              background: symbol === s ? 'rgba(79,124,255,0.15)' : 'rgba(255,255,255,0.04)',
              border: `1px solid ${symbol === s ? 'rgba(79,124,255,0.4)' : 'rgba(255,255,255,0.08)'}`,
              color: symbol === s ? '#4F7CFF' : '#64748B',
              transition: 'all 0.12s',
            }}>{s}</button>
          ))}
        </div>

        <div style={{ width: 1, height: 24, background: 'rgba(255,255,255,0.07)' }} />

        {/* Timeframes */}
        <div style={{ display: 'flex', gap: 4 }}>
          {TIMEFRAMES.map(t => (
            <button key={t} onClick={() => setTf(t)} style={{
              padding: '5px 10px', borderRadius: 7, fontSize: 11, fontWeight: 600, cursor: 'pointer',
              background: tf === t ? '#4F7CFF' : 'transparent',
              border: `1px solid ${tf === t ? '#4F7CFF' : 'rgba(255,255,255,0.08)'}`,
              color: tf === t ? '#fff' : '#64748B',
              transition: 'all 0.12s',
            }}>{t}</button>
          ))}
        </div>
      </div>

      {/* Chart card */}
      <div style={{
        background: '#121826',
        border: '1px solid rgba(255,255,255,0.06)',
        borderRadius: 12, overflow: 'hidden', marginBottom: 16,
      }}>
        {/* Chart header */}
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '12px 20px', borderBottom: '1px solid rgba(255,255,255,0.05)',
        }}>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 12 }}>
            <span style={{ fontWeight: 700, color: '#E2E8F0', fontSize: 15 }}>{symbol}</span>
            <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 22, fontWeight: 700, color: '#F1F5F9' }}>$67,428</span>
            <span style={{
              padding: '2px 8px', borderRadius: 6, fontSize: 11, fontWeight: 700,
              background: 'rgba(34,197,94,0.12)', color: '#22C55E',
            }}>+1.87%</span>
          </div>
          <div style={{ display: 'flex', gap: 16 }}>
            {[['O', '66,842'], ['H', '68,120'], ['L', '65,800'], ['C', '67,428']].map(([lbl, val]) => (
              <div key={lbl} style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 9, color: '#475569', fontWeight: 700, letterSpacing: '0.1em' }}>{lbl}</div>
                <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: '#94A3B8', marginTop: 2 }}>{val}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Chart body */}
        <div style={{ padding: '16px 20px' }}>
          <CandlestickMock />
        </div>

        {/* AI signal overlay bar */}
        <div style={{
          margin: '0 20px 16px', padding: '10px 14px', borderRadius: 10,
          background: 'rgba(34,197,94,0.06)', border: '1px solid rgba(34,197,94,0.15)',
          display: 'flex', alignItems: 'center', gap: 12,
        }}>
          <span style={{ fontSize: 11, fontWeight: 700, color: '#22C55E' }}>AI SIGNAL</span>
          <span style={{ fontSize: 12, color: '#94A3B8' }}>28/40 agents BULLISH · Confidence 78% · Target $71,200 · Stop $64,500</span>
        </div>
      </div>

      {/* Volume bar */}
      <div style={{
        background: '#121826',
        border: '1px solid rgba(255,255,255,0.06)',
        borderRadius: 12, padding: '14px 20px',
      }}>
        <div style={{ fontSize: 11, color: '#475569', fontWeight: 700, marginBottom: 10, letterSpacing: '0.1em' }}>VOLUME</div>
        <div style={{ display: 'flex', alignItems: 'flex-end', gap: 2, height: 60 }}>
          {Array.from({ length: 60 }, (_, i) => {
            const h = 10 + Math.random() * 50;
            const bull = Math.random() > 0.45;
            return (
              <div key={i} style={{
                flex: 1, height: `${h}px`,
                background: bull ? 'rgba(34,197,94,0.4)' : 'rgba(239,68,68,0.4)',
                borderRadius: 2,
              }} />
            );
          })}
        </div>
      </div>
    </motion.div>
  );
}
