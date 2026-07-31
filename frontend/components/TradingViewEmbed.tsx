'use client';

import React, { useEffect, useRef, useId } from 'react';

/**
 * TradingView's free public "Advanced Chart" widget embed (embed-widget-
 * advanced-chart script). This is a black-box iframe TradingView serves
 * from its own domain — it streams its own price data independently and
 * exposes no public API to draw custom shapes on top of its own canvas.
 * Any AI overlay (entry/SL/TP/confidence) must therefore be a separate CSS
 * layer positioned over this iframe, not drawn inside it — see
 * TradingViewOverlayPanel below and ChartsView.tsx which composes them.
 */

const INTERVAL_MAP: Record<string, string> = {
  '1m': '1',
  '5m': '5',
  '15m': '15',
  '30m': '30',
  '1h': '60',
  '4h': '240',
  '1d': 'D',
};

function toTradingViewSymbol(symbol: string): string {
  return `BINANCE:${symbol.replace('/', '')}`;
}

export default function TradingViewEmbed({
  symbol,
  timeframe,
  height = 500,
}: {
  symbol: string;
  timeframe: string;
  height?: number;
}) {
  const containerId = `tv_embed_${useId().replace(/[:]/g, '')}`;
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    el.innerHTML = '';

    const script = document.createElement('script');
    script.type = 'text/javascript';
    script.async = true;
    script.src = 'https://s3.tradingview.com/tv.js';
    script.onload = () => {
      const w = window as unknown as { TradingView?: { widget: new (opts: Record<string, unknown>) => unknown } };
      if (!w.TradingView) return;
      new w.TradingView.widget({
        autosize: true,
        symbol: toTradingViewSymbol(symbol),
        interval: INTERVAL_MAP[timeframe] ?? '60',
        timezone: 'Etc/UTC',
        theme: 'dark',
        style: '1',
        locale: 'en',
        toolbar_bg: '#0A0E1A',
        enable_publishing: false,
        hide_top_toolbar: false,
        hide_legend: false,
        save_image: false,
        container_id: containerId,
        backgroundColor: '#0A0E1A',
        gridColor: 'rgba(255,255,255,0.05)',
      });
    };
    el.appendChild(script);

    return () => {
      el.innerHTML = '';
    };
  }, [symbol, timeframe, containerId]);

  return (
    <div style={{ position: 'relative', width: '100%', height }}>
      <div id={containerId} ref={containerRef} style={{ width: '100%', height: '100%' }} />
    </div>
  );
}

export interface OverlaySignal {
  direction: 'LONG' | 'SHORT' | string;
  entry: number | null;
  stop_loss: number | null;
  take_profit: number | null;
  confidence: number | null;
  consensus_pct?: number | null;
}

/**
 * Floating info card positioned over the TradingView iframe via CSS
 * (absolute positioning within the same relative container), never drawn
 * inside the widget itself. Honest about what it is: an AI overlay
 * alongside TradingView's chart, not shapes rendered on TradingView's
 * canvas.
 */
export function TradingViewOverlayPanel({ signal }: { signal: OverlaySignal | null }) {
  if (!signal) return null;
  const isLong = signal.direction === 'LONG';
  const dirColor = isLong ? '#22C55E' : '#EF4444';

  return (
    <div
      style={{
        position: 'absolute', top: 12, right: 12, zIndex: 10, width: 200,
        background: 'rgba(10,14,26,0.92)', border: '1px solid rgba(255,255,255,0.1)',
        borderRadius: 10, padding: 12, backdropFilter: 'blur(6px)',
        boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
        <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.1em', color: '#475569' }}>AI OVERLAY</span>
        <span style={{
          fontSize: 10, fontWeight: 700, padding: '2px 7px', borderRadius: 5,
          background: `${dirColor}22`, color: dirColor,
        }}>{signal.direction}</span>
      </div>
      {[
        { label: 'Entry', value: signal.entry, color: '#4F7CFF' },
        { label: 'Stop Loss', value: signal.stop_loss, color: '#EF4444' },
        { label: 'Take Profit', value: signal.take_profit, color: '#22C55E' },
      ].map((row) => (
        <div key={row.label} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
          <span style={{ fontSize: 11, color: '#64748B' }}>{row.label}</span>
          <span style={{ fontSize: 11, fontFamily: "'JetBrains Mono', monospace", fontWeight: 700, color: row.color }}>
            {row.value != null ? row.value.toLocaleString(undefined, { maximumFractionDigits: 4 }) : '—'}
          </span>
        </div>
      ))}
      <div style={{ height: 1, background: 'rgba(255,255,255,0.06)', margin: '8px 0' }} />
      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
        <span style={{ fontSize: 11, color: '#64748B' }}>Confidence</span>
        <span style={{ fontSize: 11, fontFamily: "'JetBrains Mono', monospace", fontWeight: 700, color: '#E2E8F0' }}>
          {signal.confidence != null ? `${Math.round(signal.confidence)}%` : '—'}
        </span>
      </div>
      {signal.consensus_pct != null && (
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4 }}>
          <span style={{ fontSize: 11, color: '#64748B' }}>Consensus</span>
          <span style={{ fontSize: 11, fontFamily: "'JetBrains Mono', monospace", fontWeight: 700, color: '#E2E8F0' }}>
            {Math.round(signal.consensus_pct)}%
          </span>
        </div>
      )}
      <div style={{ fontSize: 9, color: '#334155', marginTop: 8, lineHeight: 1.4 }}>
        Overlaid by Hedge-AI — not drawn on TradingView&rsquo;s own chart canvas.
      </div>
    </div>
  );
}
