'use client';

import React from 'react';
import { motion } from 'framer-motion';

const MARKET_CARDS = [
  { symbol: 'BTC/USDT', name: 'Bitcoin',       price: '67,428.00', change: '+1.87', pos: true,  high: '68,120', low: '65,800', vol: '$42.1B' },
  { symbol: 'ETH/USDT', name: 'Ethereum',      price: '3,842.10',  change: '+2.10', pos: true,  high: '3,890',  low: '3,760',  vol: '$18.3B' },
  { symbol: 'SOL/USDT', name: 'Solana',        price: '185.20',    change: '-0.80', pos: false, high: '192',    low: '182',    vol: '$4.2B'  },
  { symbol: 'BNB/USDT', name: 'BNB',           price: '612.40',    change: '+0.50', pos: true,  high: '618',    low: '606',    vol: '$2.1B'  },
  { symbol: 'EUR/USD',  name: 'Euro / Dollar',  price: '1.0842',    change: '+0.12', pos: true,  high: '1.0861', low: '1.0820', vol: '$78.4B' },
  { symbol: 'GBP/USD',  name: 'Pound / Dollar', price: '1.2654',    change: '-0.30', pos: false, high: '1.2700', low: '1.2630', vol: '$38.1B' },
  { symbol: 'XAU/USD',  name: 'Gold (Spot)',    price: '2,342.50',  change: '+0.60', pos: true,  high: '2,358',  low: '2,328',  vol: '$12.6B' },
  { symbol: 'SPX',      name: 'S&P 500',        price: '5,280.10',  change: '+0.40', pos: true,  high: '5,295',  low: '5,255',  vol: '$340B'  },
];

const WATCHLIST = [
  { symbol: 'BTC',   price: '67,428', d1: '+1.87', d7: '+8.4',  vol: '42.1B', cap: '1.32T', signal: 'BUY' },
  { symbol: 'ETH',   price: '3,842',  d1: '+2.10', d7: '+5.2',  vol: '18.3B', cap: '461B',  signal: 'BUY' },
  { symbol: 'SOL',   price: '185',    d1: '-0.80', d7: '+12.1', vol: '4.2B',  cap: '84B',   signal: 'HOLD' },
  { symbol: 'BNB',   price: '612',    d1: '+0.50', d7: '+2.3',  vol: '2.1B',  cap: '90B',   signal: 'HOLD' },
  { symbol: 'AVAX',  price: '38.20',  d1: '-1.20', d7: '-4.1',  vol: '890M',  cap: '15.7B', signal: 'SELL' },
  { symbol: 'DOGE',  price: '0.152',  d1: '+3.40', d7: '+18.2', vol: '2.8B',  cap: '21.8B', signal: 'BUY' },
  { symbol: 'LINK',  price: '14.80',  d1: '+0.90', d7: '+6.7',  vol: '640M',  cap: '8.7B',  signal: 'BUY' },
  { symbol: 'ADA',   price: '0.478',  d1: '-0.40', d7: '-2.8',  vol: '520M',  cap: '16.8B', signal: 'HOLD' },
  { symbol: 'DOT',   price: '7.92',   d1: '+1.10', d7: '+3.5',  vol: '390M',  cap: '11.0B', signal: 'HOLD' },
  { symbol: 'MATIC', price: '0.864',  d1: '-1.80', d7: '-6.3',  vol: '780M',  cap: '8.5B',  signal: 'SELL' },
  { symbol: 'UNI',   price: '9.34',   d1: '+2.30', d7: '+9.1',  vol: '310M',  cap: '5.6B',  signal: 'BUY'  },
  { symbol: 'ATOM',  price: '10.12',  d1: '+0.70', d7: '+4.4',  vol: '280M',  cap: '3.9B',  signal: 'HOLD' },
];

function Sparkline({ pos }: { pos: boolean }) {
  const pts = Array.from({ length: 20 }, (_, i) => {
    const base = 30 + Math.sin(i * 0.7) * 10 + (pos ? i * 0.8 : -i * 0.5) + Math.random() * 8;
    return `${i * 4},${Math.max(5, Math.min(55, 60 - base))}`;
  }).join(' ');
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

export default function MarketsView() {
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
      </div>

      {/* Market cards grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 28 }}>
        {MARKET_CARDS.map((m, i) => (
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
                <div style={{ fontSize: 11, color: '#475569', marginTop: 2 }}>{m.name}</div>
              </div>
              <Sparkline pos={m.pos} />
            </div>
            <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 18, fontWeight: 700, color: '#F1F5F9', marginBottom: 6 }}>
              ${m.price}
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{
                padding: '2px 8px', borderRadius: 6, fontSize: 11, fontWeight: 700,
                background: m.pos ? 'rgba(34,197,94,0.12)' : 'rgba(239,68,68,0.12)',
                color: m.pos ? '#22C55E' : '#EF4444',
              }}>{m.change}%</span>
              <span style={{ fontSize: 10, color: '#334155', fontFamily: "'JetBrains Mono', monospace" }}>Vol {m.vol}</span>
            </div>
            <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
              <span style={{ fontSize: 10, color: '#22C55E', fontFamily: "'JetBrains Mono', monospace" }}>H {m.high}</span>
              <span style={{ fontSize: 10, color: '#475569' }}>·</span>
              <span style={{ fontSize: 10, color: '#EF4444', fontFamily: "'JetBrains Mono', monospace" }}>L {m.low}</span>
            </div>
          </motion.div>
        ))}
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
                {['Symbol', 'Price', '24h %', '7d %', 'Volume', 'Market Cap', 'Signal'].map(h => (
                  <th key={h} style={{
                    padding: '10px 16px', textAlign: 'left', fontSize: 10, fontWeight: 700,
                    color: '#475569', letterSpacing: '0.1em', borderBottom: '1px solid rgba(255,255,255,0.05)',
                  }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {WATCHLIST.map((r, i) => (
                <tr key={r.symbol} style={{ background: i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.015)' }}>
                  <td style={{ padding: '11px 16px', fontWeight: 700, color: '#E2E8F0', fontSize: 13 }}>{r.symbol}</td>
                  <td style={{ padding: '11px 16px', fontFamily: "'JetBrains Mono', monospace", fontSize: 12, color: '#F1F5F9' }}>${r.price}</td>
                  <td style={{ padding: '11px 16px', fontFamily: "'JetBrains Mono', monospace", fontSize: 12, color: r.d1.startsWith('+') ? '#22C55E' : '#EF4444', fontWeight: 600 }}>{r.d1}%</td>
                  <td style={{ padding: '11px 16px', fontFamily: "'JetBrains Mono', monospace", fontSize: 12, color: r.d7.startsWith('+') ? '#22C55E' : '#EF4444', fontWeight: 600 }}>{r.d7}%</td>
                  <td style={{ padding: '11px 16px', fontSize: 12, color: '#94A3B8', fontFamily: "'JetBrains Mono', monospace" }}>{r.vol}</td>
                  <td style={{ padding: '11px 16px', fontSize: 12, color: '#94A3B8', fontFamily: "'JetBrains Mono', monospace" }}>{r.cap}</td>
                  <td style={{ padding: '11px 16px' }}><SignalBadge signal={r.signal} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </motion.div>
  );
}
