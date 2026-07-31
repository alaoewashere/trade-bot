'use client';

import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Check } from 'lucide-react';

interface NotificationsPanelProps {
  open: boolean;
  onClose: () => void;
}

const NOTIFS = [
  { icon: '🤖', title: 'AI Consensus: BULLISH on BTC/USDT', desc: '28 of 40 agents aligned on bullish signal', time: '2 min ago', color: '#22C55E' },
  { icon: '⚠️', title: 'Risk Alert: Position approaching stop loss', desc: 'ETH/USDT long at 92% of max drawdown', time: '5 min ago', color: '#F59E0B' },
  { icon: '✅', title: 'Trade #1247 closed: +$340 profit', desc: 'BTC/USDT long closed at $67,420 target', time: '12 min ago', color: '#22C55E' },
  { icon: '📊', title: 'New forecast: BTC 4H BULLISH 78%', desc: 'Trend-following strategy generated new signal', time: '18 min ago', color: '#4F7CFF' },
  { icon: '🔔', title: 'Daily PnL limit at 60% — monitoring', desc: 'Current daily drawdown: $742 / $1,250 limit', time: '1h ago', color: '#F59E0B' },
  { icon: '🔄', title: 'Strategy rebalance complete', desc: 'Momentum Breakout adjusted position sizes', time: '1h 30m ago', color: '#4F7CFF' },
  { icon: '📰', title: 'High-impact news: Fed rate decision', desc: 'Macro event detected — agents on alert mode', time: '2h ago', color: '#EF4444' },
  { icon: '🎯', title: 'Backtest complete: 71.4% win rate', desc: 'Trend Following v2 backtest over 6 months', time: '3h ago', color: '#22C55E' },
];

export default function NotificationsPanel({ open, onClose }: NotificationsPanelProps) {
  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            onClick={onClose}
            style={{
              position: 'fixed', inset: 0, zIndex: 9998,
              background: 'rgba(0,0,0,0.4)',
              backdropFilter: 'blur(4px)',
            }}
          />
          <motion.div
            initial={{ opacity: 0, x: 360 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 360 }}
            transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
            style={{
              position: 'fixed', top: 0, right: 0, bottom: 0,
              width: 360, zIndex: 9999,
              background: '#0d1424',
              borderLeft: '1px solid rgba(255,255,255,0.07)',
              boxShadow: '-20px 0 60px rgba(0,0,0,0.7)',
              display: 'flex', flexDirection: 'column',
            }}
          >
            {/* Header */}
            <div style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              padding: '20px 20px 16px',
              borderBottom: '1px solid rgba(255,255,255,0.06)',
            }}>
              <div>
                <div style={{ fontSize: 16, fontWeight: 700, color: '#E2E8F0' }}>Notifications</div>
                <div style={{ fontSize: 11, color: '#475569', marginTop: 2 }}>{NOTIFS.length} unread</div>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <button style={{
                  display: 'flex', alignItems: 'center', gap: 5,
                  padding: '5px 10px', borderRadius: 7, fontSize: 11, fontWeight: 600,
                  color: '#4F7CFF', background: 'rgba(79,124,255,0.1)',
                  border: '1px solid rgba(79,124,255,0.2)', cursor: 'pointer',
                }}>
                  <Check size={11} /> Mark all read
                </button>
                <button
                  onClick={onClose}
                  style={{
                    width: 30, height: 30, borderRadius: 8, display: 'flex',
                    alignItems: 'center', justifyContent: 'center',
                    background: 'rgba(255,255,255,0.05)',
                    border: '1px solid rgba(255,255,255,0.08)', cursor: 'pointer',
                  }}
                >
                  <X size={14} color="#64748B" />
                </button>
              </div>
            </div>

            {/* List */}
            <div style={{ flex: 1, overflowY: 'auto', padding: '8px 0' }}>
              {NOTIFS.map((n, i) => (
                <div key={i} style={{
                  display: 'flex', gap: 12, padding: '12px 20px',
                  borderBottom: '1px solid rgba(255,255,255,0.03)',
                  cursor: 'pointer', transition: 'background 0.12s',
                }}
                  onMouseEnter={e => (e.currentTarget.style.background = 'rgba(255,255,255,0.03)')}
                  onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                >
                  <div style={{
                    width: 36, height: 36, borderRadius: 10, flexShrink: 0,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    background: `${n.color}18`,
                    border: `1px solid ${n.color}30`,
                    fontSize: 16,
                  }}>{n.icon}</div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 12.5, fontWeight: 600, color: '#E2E8F0', lineHeight: 1.4 }}>{n.title}</div>
                    <div style={{ fontSize: 11.5, color: '#64748B', marginTop: 3, lineHeight: 1.4 }}>{n.desc}</div>
                    <div style={{ fontSize: 10.5, color: '#334155', marginTop: 4 }}>{n.time}</div>
                  </div>
                  <div style={{
                    width: 7, height: 7, borderRadius: '50%',
                    background: n.color, flexShrink: 0, marginTop: 6,
                    boxShadow: `0 0 6px ${n.color}`,
                  }} />
                </div>
              ))}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
