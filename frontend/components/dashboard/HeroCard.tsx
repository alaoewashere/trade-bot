'use client';

import React, { useState, useEffect } from 'react';
import { ChevronDown, TrendingUp, TrendingDown } from 'lucide-react';
import { motion } from 'framer-motion';
import clsx from 'clsx';
import Badge from '@/components/ui/Badge';

const SYMBOLS = ['BTC / USDT', 'ETH / USDT', 'SOL / USDT', 'AAPL', 'TSLA'];

const INITIAL_PRICE = 67428.5;

const STAT_CHIPS = [
  { label: 'Market Regime', value: 'TRENDING BULL' },
  { label: 'Trend', value: 'UPTREND' },
  { label: 'Volatility', value: 'MEDIUM' },
  { label: 'Volume', value: 'HIGH' },
];

export default function HeroCard() {
  const [symbol, setSymbol] = useState('BTC / USDT');
  const [price, setPrice] = useState(INITIAL_PRICE);
  const [prevPrice, setPrevPrice] = useState(INITIAL_PRICE);
  const [change24h] = useState({ amount: 1240.0, pct: 1.87 });
  const [direction, setDirection] = useState<'up' | 'down' | 'flat'>('up');

  useEffect(() => {
    const id = setInterval(() => {
      setPrice((p) => {
        const next = +(p + (Math.random() - 0.48) * 45).toFixed(2);
        setPrevPrice(p);
        setDirection(next > p ? 'up' : next < p ? 'down' : 'flat');
        return next;
      });
    }, 1800);
    return () => clearInterval(id);
  }, []);

  const priceColor =
    direction === 'up' ? '#22C55E' : direction === 'down' ? '#EF4444' : '#F1F5F9';

  return (
    <div
      className="rounded-xl p-5 h-full flex flex-col gap-4"
      style={{
        background: 'linear-gradient(135deg, #121826 0%, #0f1e35 100%)',
        boxShadow:
          '0 0 0 1px rgba(79,124,255,0.2), 0 8px 32px rgba(79,124,255,0.08)',
        border: '1px solid rgba(79,124,255,0.15)',
      }}
    >
      {/* Top row — symbol selector + live badge */}
      <div className="flex items-center justify-between">
        <button
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-semibold transition-colors"
          style={{
            background: 'rgba(255,255,255,0.06)',
            border: '1px solid rgba(255,255,255,0.1)',
            color: '#F1F5F9',
          }}
        >
          {symbol}
          <ChevronDown className="w-3.5 h-3.5" style={{ color: '#94A3B8' }} />
        </button>
        <Badge variant="primary" dot pulse>
          LIVE
        </Badge>
      </div>

      {/* Price */}
      <div>
        <motion.div
          key={Math.round(price)}
          initial={{ opacity: 0.6, y: direction === 'up' ? -4 : 4 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.25 }}
          className="font-mono font-bold tabular-nums leading-none"
          style={{ fontSize: 48, color: priceColor, letterSpacing: '-0.02em' }}
        >
          ${price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
        </motion.div>

        {/* 24h change */}
        <div className="flex items-center gap-2 mt-2">
          {change24h.pct >= 0 ? (
            <TrendingUp className="w-4 h-4" style={{ color: '#22C55E' }} />
          ) : (
            <TrendingDown className="w-4 h-4" style={{ color: '#EF4444' }} />
          )}
          <span
            className="font-mono text-sm font-semibold"
            style={{ color: change24h.pct >= 0 ? '#22C55E' : '#EF4444' }}
          >
            +${change24h.amount.toLocaleString()} (+{change24h.pct}%)
          </span>
          <span className="text-xs" style={{ color: '#475569' }}>
            24h
          </span>
        </div>
      </div>

      {/* Stat chips */}
      <div className="grid grid-cols-2 gap-2 flex-1">
        {STAT_CHIPS.map((chip) => (
          <div
            key={chip.label}
            className="rounded-lg px-3 py-2"
            style={{
              background: 'rgba(255,255,255,0.04)',
              border: '1px solid rgba(255,255,255,0.06)',
            }}
          >
            <div className="text-[10px] font-medium uppercase tracking-wider" style={{ color: '#475569' }}>
              {chip.label}
            </div>
            <div className="text-xs font-semibold mt-0.5" style={{ color: '#F1F5F9' }}>
              {chip.value}
            </div>
          </div>
        ))}
      </div>

      {/* Bottom — overall signal */}
      <div
        className="flex items-center justify-between rounded-lg px-4 py-3"
        style={{
          background: 'rgba(34,197,94,0.08)',
          border: '1px solid rgba(34,197,94,0.15)',
        }}
      >
        <span className="text-xs font-medium" style={{ color: '#94A3B8' }}>
          Overall Signal
        </span>
        <div className="flex items-center gap-2">
          <span
            className="w-2 h-2 rounded-full animate-pulse-success"
            style={{ background: '#22C55E' }}
          />
          <span className="font-mono font-bold text-sm" style={{ color: '#22C55E' }}>
            BULLISH
          </span>
        </div>
      </div>
    </div>
  );
}
