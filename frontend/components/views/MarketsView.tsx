'use client';

import React from 'react';
import { motion } from 'framer-motion';
import { api, LiveTicker, FearGreedResponse, ProviderGatedResponse } from '@/lib/api';

const WATCHLIST_SYMBOLS = [
  'BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT',
  'XRP/USDT', 'ADA/USDT', 'DOGE/USDT', 'AVAX/USDT',
];

const SYMBOL_NAMES: Record<string, string> = {
  'BTC/USDT': 'Bitcoin', 'ETH/USDT': 'Ethereum', 'SOL/USDT': 'Solana', 'BNB/USDT': 'BNB',
  'XRP/USDT': 'XRP', 'ADA/USDT': 'Cardano', 'DOGE/USDT': 'Dogecoin', 'AVAX/USDT': 'Avalanche',
};

function fmt(n: number, digits = 2): string {
  return n.toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

// Sparkline is derived from the ticker's real 24h high/low/current price
// (not a fabricated random walk) — it's a 3-point visual cue (low -> current
// -> a projection toward the 24h extreme implied by the change sign) rather
// than a full historical series, since a per-symbol OHLCV fetch on every
// poll would be an unnecessary exchange hit for a decorative sparkline.
function Sparkline({ ticker }: { ticker: LiveTicker }) {
  const pos = ticker.change_24h_pct >= 0;
  const { low_24h, high_24h, price } = ticker;
  const range = Math.max(high_24h - low_24h, 0.0001);
  const norm = (v: number) => 60 - ((v - low_24h) / range) * 50 - 5;
  const pts = [
    `0,${norm(low_24h)}`,
    `38,${norm((low_24h + high_24h) / 2)}`,
    `76,${norm(price)}`,
  ].join(' ');
  const color = pos ? '#22C55E' : '#EF4444';
  return (
    <svg width="80" height="32" viewBox="0 0 76 60" style={{ flexShrink: 0 }}>
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" opacity="0.8" />
    </svg>
  );
}

function SignalBadge({ signal }: { signal: string }) {
  const colors: Record<string, { bg: string; text: string }> = {
    BUY:  { bg: 'rgba(34,197,94,0.12)',  text: '#22C55E' },
    SELL: { bg: 'rgba(239,68,68,0.12)',  text: '#EF4444' },
    HOLD: { bg: 'rgba(245,158,11,0.12)', text: '#F59E0B' },
  };
  const c = colors[signal] || colors.HOLD;
  return (
    <span style={{
      padding: '2px 8px', borderRadius: 6, fontSize: 10, fontWeight: 700,
      background: c.bg, color: c.text,
    }}>{signal}</span>
  );
}

function FearGreedBanner({ data }: { data: FearGreedResponse | null }) {
  if (!data) return null;
  const color = data.value >= 55 ? '#22C55E' : data.value <= 45 ? '#EF4444' : '#F59E0B';
  return (
    <div style={{
      background: '#121826', border: '1px solid rgba(255,255,255,0.06)', borderRadius: 12,
      padding: '14px 18px', display: 'flex', alignItems: 'center', gap: 16,
    }}>
      <div style={{
        width: 44, height: 44, borderRadius: '50%', border: `3px solid ${color}`,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 14, fontWeight: 800, color, flexShrink: 0,
      }}>{data.value}</div>
      <div>
        <div style={{ fontSize: 12, fontWeight: 700, color: '#E2E8F0' }}>Fear &amp; Greed Index: {data.classification}</div>
        <div style={{ fontSize: 10.5, color: '#475569', marginTop: 2 }}>Source: {data.source} · updated {new Date(data.updated_at).toLocaleTimeString()}</div>
      </div>
    </div>
  );
}

function ProviderBanner({ title, data }: { title: string; data: ProviderGatedResponse | null }) {
  if (!data) return null;
  return (
    <div style={{
      background: '#121826', border: '1px solid rgba(255,255,255,0.06)', borderRadius: 12,
      padding: '14px 18px',
    }}>
      <div style={{ fontSize: 12, fontWeight: 700, color: '#E2E8F0' }}>{title}</div>
      <div style={{ fontSize: 10.5, color: data.provider_configured ? '#22C55E' : '#F59E0B', marginTop: 4 }}>
        {data.provider_configured ? 'Provider connected' : 'Provider not configured'}
      </div>
      <div style={{ fontSize: 10.5, color: '#475569', marginTop: 4, lineHeight: 1.4 }}>{data.message}</div>
    </div>
  );
}

export default function MarketsView() {
  const [tickers, setTickers] = React.useState<LiveTicker[]>([]);
  const [fearGreed, setFearGreed] = React.useState<FearGreedResponse | null>(null);
  const [whale, setWhale] = React.useState<ProviderGatedResponse | null>(null);
  const [flows, setFlows] = React.useState<ProviderGatedResponse | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [live, fg, wh, ex] = await Promise.all([
          api.markets.getLive(WATCHLIST_SYMBOLS),
          api.markets.getFearGreed().catch(() => null),
          api.markets.getWhaleActivity().catch(() => null),
          api.markets.getExchangeFlows().catch(() => null),
        ]);
        if (cancelled) return;
        setTickers(live);
        setFearGreed(fg);
        setWhale(wh);
        setFlows(ex);
        setError(null);
      } catch (e) {
        if (!cancelled) setError('Backend unavailable — showing empty state.');
      }
    }
    load();
    const interval = setInterval(load, 8000);
    return () => { cancelled = true; clearInterval(interval); };
  }, []);

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      style={{ padding: 24, paddingBottom: 48 }}
    >
      {/* Header */}
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 20, fontWeight: 700, color: '#E2E8F0', margin: 0 }}>Global Markets</h1>
        <p style={{ fontSize: 13, color: '#475569', marginTop: 4 }}>Real-time market overview across crypto, forex and indices</p>
        {error && <div style={{ fontSize: 11, color: '#F59E0B', marginTop: 6 }}>{error}</div>}
      </div>

      {/* Sentiment / provider status row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, marginBottom: 24 }}>
        <FearGreedBanner data={fearGreed} />
        <ProviderBanner title="Whale Activity" data={whale} />
        <ProviderBanner title="Exchange Flows" data={flows} />
      </div>

      {/* Market cards grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 28 }}>
        {tickers.length === 0 && (
          <div style={{ gridColumn: '1 / -1', padding: 24, textAlign: 'center', fontSize: 12, color: '#475569' }}>Loading live market data…</div>
        )}
        {tickers.map((m, i) => {
          const pos = m.change_24h_pct >= 0;
          return (
            <motion.div
              key={m.symbol}
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.2, delay: i * 0.04 }}
              style={{
                background: '#121826',
                border: '1px solid rgba(255,255,255,0.06)',
                borderRadius: 12,
                padding: '14px 16px',
                cursor: 'pointer',
                transition: 'border-color 0.15s, transform 0.15s',
              }}
              whileHover={{ borderColor: 'rgba(255,255,255,0.12)', y: -1 }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 10 }}>
                <div>
                  <div style={{ fontSize: 12, fontWeight: 700, color: '#94A3B8', letterSpacing: '0.08em' }}>{m.symbol}</div>
                  <div style={{ fontSize: 11, color: '#475569', marginTop: 2 }}>{SYMBOL_NAMES[m.symbol] || m.symbol}</div>
                </div>
                <Sparkline ticker={m} />
              </div>
              <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 18, fontWeight: 700, color: '#F1F5F9', marginBottom: 6 }}>
                ${fmt(m.price)}
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{
                  padding: '2px 8px', borderRadius: 6, fontSize: 11, fontWeight: 700,
                  background: pos ? 'rgba(34,197,94,0.12)' : 'rgba(239,68,68,0.12)',
                  color: pos ? '#22C55E' : '#EF4444',
                }}>{fmt(m.change_24h_pct)}%</span>
                <span style={{ fontSize: 10, color: '#334155', fontFamily: "'JetBrains Mono', monospace" }}>Vol ${(m.volume_24h_quote / 1e9).toFixed(2)}B</span>
              </div>
              <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                <span style={{ fontSize: 10, color: '#22C55E', fontFamily: "'JetBrains Mono', monospace" }}>H {fmt(m.high_24h)}</span>
                <span style={{ fontSize: 10, color: '#475569' }}>·</span>
                <span style={{ fontSize: 10, color: '#EF4444', fontFamily: "'JetBrains Mono', monospace" }}>L {fmt(m.low_24h)}</span>
              </div>
            </motion.div>
          );
        })}
      </div>

      {/* Watchlist */}
      <div style={{
        background: '#121826',
        border: '1px solid rgba(255,255,255,0.06)',
        borderRadius: 12,
        overflow: 'hidden',
      }}>
        <div style={{ padding: '14px 20px', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
          <span style={{ fontSize: 14, fontWeight: 700, color: '#E2E8F0' }}>Market Watchlist</span>
        </div>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: 'rgba(255,255,255,0.02)' }}>
                {['Symbol', 'Price', '24h %', '24h High', '24h Low', 'Volume', 'Signal'].map(h => (
                  <th key={h} style={{
                    padding: '10px 16px', textAlign: 'left', fontSize: 10, fontWeight: 700,
                    color: '#475569', letterSpacing: '0.1em', borderBottom: '1px solid rgba(255,255,255,0.05)',
                  }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {tickers.map((r, i) => {
                // Signal is a simple heuristic derived from real 24h change —
                // this is not a consensus-engine call, just a directional cue
                // for the watchlist row (the real AI consensus lives under
                // Agents / Research views).
                const signal = r.change_24h_pct > 1.5 ? 'BUY' : r.change_24h_pct < -1.5 ? 'SELL' : 'HOLD';
                return (
                  <tr key={r.symbol} style={{ background: i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.015)' }}>
                    <td style={{ padding: '11px 16px', fontWeight: 700, color: '#E2E8F0', fontSize: 13 }}>{r.symbol}</td>
                    <td style={{ padding: '11px 16px', fontFamily: "'JetBrains Mono', monospace", fontSize: 12, color: '#F1F5F9' }}>${fmt(r.price)}</td>
                    <td style={{ padding: '11px 16px', fontFamily: "'JetBrains Mono', monospace", fontSize: 12, color: r.change_24h_pct >= 0 ? '#22C55E' : '#EF4444', fontWeight: 600 }}>{fmt(r.change_24h_pct)}%</td>
                    <td style={{ padding: '11px 16px', fontSize: 12, color: '#94A3B8', fontFamily: "'JetBrains Mono', monospace" }}>${fmt(r.high_24h)}</td>
                    <td style={{ padding: '11px 16px', fontSize: 12, color: '#94A3B8', fontFamily: "'JetBrains Mono', monospace" }}>${fmt(r.low_24h)}</td>
                    <td style={{ padding: '11px 16px', fontSize: 12, color: '#94A3B8', fontFamily: "'JetBrains Mono', monospace" }}>${(r.volume_24h_quote / 1e9).toFixed(2)}B</td>
                    <td style={{ padding: '11px 16px' }}><SignalBadge signal={signal} /></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </motion.div>
  );
}
