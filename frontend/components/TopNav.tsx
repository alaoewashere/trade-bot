'use client';

import React, { useState, useEffect } from 'react';
import { Bell, Settings, User, Search, ChevronDown, Zap } from 'lucide-react';
import { useMarketDataWS } from '../hooks/useWebSocket';

interface TopNavProps {
  pendingCount?: number;
}

export default function TopNav({ pendingCount = 0 }: TopNavProps) {
  const [price, setPrice] = useState(67428.5);
  const [change, setChange] = useState(+1240.3);
  const [changePct, setChangePct] = useState(+1.87);

  useMarketDataWS((msg) => {
    if (msg.type === 'price' && msg.symbol === 'BTC/USDT') {
      if (msg.price !== undefined) setPrice(msg.price);
      if (msg.change !== undefined) setChange(msg.change);
      if (msg.change_pct !== undefined) setChangePct(msg.change_pct);
    }
  });

  useEffect(() => {
    const interval = setInterval(() => {
      setPrice((p) => +(p + (Math.random() - 0.49) * 50).toFixed(2));
      setChange((c) => +(c + (Math.random() - 0.49) * 10).toFixed(2));
    }, 2500);
    return () => clearInterval(interval);
  }, []);

  const isPositive = change >= 0;
  const priceColor = isPositive ? '#22C55E' : '#EF4444';

  return (
    <header
      className="fixed top-0 left-0 right-0 z-50 h-14 flex items-center px-4 gap-4"
      style={{
        background: 'rgba(2,6,23,0.92)',
        borderBottom: '1px solid rgba(255,255,255,0.07)',
        backdropFilter: 'blur(24px)',
        boxShadow: '0 1px 0 rgba(94,106,210,0.08)',
      }}
    >
      {/* Logo */}
      <div className="flex items-center gap-2 shrink-0">
        <div
          className="w-7 h-7 rounded-lg flex items-center justify-center"
          style={{ background: 'linear-gradient(135deg, #8B5CF6, #3B82F6)' }}
        >
          <Zap className="w-4 h-4 text-white" />
        </div>
        <div>
          <span className="font-bold text-sm tracking-tight text-white">HEDGE</span>
          <span className="font-bold text-sm tracking-tight" style={{ color: '#8B5CF6' }}>-AI</span>
        </div>
        <div
          className="hidden lg:block text-[10px] text-[#6B6B7A] ml-1 border-l pl-2"
          style={{ borderColor: 'rgba(255,255,255,0.06)' }}
        >
          INSTITUTIONAL
        </div>
      </div>

      {/* Asset selector */}
      <div
        className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-lg cursor-pointer border"
        style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}
      >
        <div className="flex flex-col">
          <span className="text-[10px] text-[#6B6B7A]">BTC/USDT</span>
          <span
            className="font-mono font-semibold text-sm leading-none"
            style={{ color: priceColor }}
          >
            ${price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </span>
        </div>
        <span
          className="text-xs font-mono px-1.5 py-0.5 rounded"
          style={{
            color: priceColor,
            background: isPositive ? 'rgba(34,197,94,0.1)' : 'rgba(239,68,68,0.1)',
          }}
        >
          {isPositive ? '+' : ''}{changePct.toFixed(2)}%
        </span>
        <ChevronDown className="w-3 h-3 text-[#6B6B7A]" />
      </div>

      {/* Search */}
      <div
        className="hidden lg:flex flex-1 max-w-xs items-center gap-2 px-3 py-1.5 rounded-lg border"
        style={{ background: 'var(--bg-card)', borderColor: 'var(--bg-border)' }}
      >
        <Search className="w-3.5 h-3.5 text-[#6B6B7A]" />
        <input
          type="text"
          placeholder="Search agents, signals..."
          className="bg-transparent text-sm text-[#9B9BAA] placeholder-[#6B6B7A] outline-none flex-1 min-w-0"
        />
      </div>

      {/* Spacer */}
      <div className="flex-1" />

      {/* Right actions */}
      <div className="flex items-center gap-1">
        {/* Notifications */}
        <button
          className="relative w-8 h-8 flex items-center justify-center rounded-lg transition-colors hover:bg-white/5"
          title="Notifications"
        >
          <Bell className="w-4 h-4 text-[#9B9BAA]" />
          {pendingCount > 0 && (
            <span
              className="absolute top-1 right-1 w-4 h-4 rounded-full flex items-center justify-center text-[9px] font-bold text-white"
              style={{ background: '#EF4444' }}
            >
              {pendingCount}
            </span>
          )}
        </button>

        {/* Settings */}
        <button className="w-8 h-8 flex items-center justify-center rounded-lg transition-colors hover:bg-white/5">
          <Settings className="w-4 h-4 text-[#9B9BAA]" />
        </button>

        {/* User */}
        <button
          className="flex items-center gap-2 px-2 py-1 rounded-lg transition-colors hover:bg-white/5 ml-1"
        >
          <div
            className="w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold"
            style={{ background: 'linear-gradient(135deg, #8B5CF6, #3B82F6)' }}
          >
            <User className="w-3 h-3 text-white" />
          </div>
        </button>
      </div>
    </header>
  );
}
