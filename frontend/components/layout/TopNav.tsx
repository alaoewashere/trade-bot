'use client';

import React, { useState, useEffect } from 'react';
import {
  Zap, Search, Bell, Settings, ChevronDown,
  Wifi, Moon, Sun, Activity, LayoutDashboard,
} from 'lucide-react';

const VIEW_LABELS: Record<string, string> = {
  dashboard: 'Mission Control',
  markets: 'Global Markets',
  charts: 'Live Charts',
  charts2: 'Chart View',
  agents: 'AI Agents',
  portfolio: 'Portfolio',
  strategies: 'Strategies',
  research: 'Research',
  journal: 'Trade Journal',
  news: 'News Feed',
  performance: 'Performance',
  backtesting: 'Backtesting',
  paper: 'Paper Trading',
  settings: 'Settings',
};

function LiveClock() {
  const [t, setT] = useState({ time: '', date: '' });
  useEffect(() => {
    const tick = () => {
      const n = new Date();
      setT({
        time: n.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' }),
        date: n.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' }),
      });
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', lineHeight: 1 }}>
      <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 13, fontWeight: 600, color: '#E2E8F0', letterSpacing: '0.08em' }}>
        {t.time}
      </span>
      <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: '#475569', letterSpacing: '0.06em', marginTop: 3 }}>
        {t.date}
      </span>
    </div>
  );
}

function MarketPill({ label, color, delay = 0 }: { label: string; color: string; delay?: number }) {
  const rgb = color === 'green' ? '34,197,94' : '239,68,68';
  const hex = color === 'green' ? '#22C55E' : '#EF4444';
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 6,
      padding: '5px 12px', borderRadius: 999,
      background: `rgba(${rgb},0.08)`,
      border: `1px solid rgba(${rgb},0.2)`,
      color: hex, fontSize: 11, fontWeight: 700, letterSpacing: '0.1em',
      whiteSpace: 'nowrap', flexShrink: 0,
    }}>
      <span style={{
        width: 6, height: 6, borderRadius: '50%', background: hex, flexShrink: 0,
        boxShadow: `0 0 6px ${hex}`,
        animation: `live-blink 1.4s ease-in-out ${delay}s infinite`,
      }} />
      {label}
    </div>
  );
}

function IBtn({ children, badge, title, onClick }: { children: React.ReactNode; badge?: number; title?: string; onClick?: () => void }) {
  const [hov, setHov] = useState(false);
  return (
    <button
      title={title}
      onClick={onClick}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        position: 'relative', width: 34, height: 34, borderRadius: 10, flexShrink: 0,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: hov ? 'rgba(255,255,255,0.09)' : 'rgba(255,255,255,0.04)',
        border: `1px solid ${hov ? 'rgba(255,255,255,0.14)' : 'rgba(255,255,255,0.07)'}`,
        cursor: 'pointer', transition: 'all 0.15s ease',
      }}
    >
      {children}
      {badge != null && badge > 0 && (
        <span style={{
          position: 'absolute', top: -5, right: -5,
          minWidth: 18, height: 18, borderRadius: 9, padding: '0 4px',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 10, fontWeight: 700, color: '#fff',
          background: 'linear-gradient(135deg,#4F7CFF,#818CF8)',
          boxShadow: '0 2px 8px rgba(79,124,255,0.5)',
        }}>{badge}</span>
      )}
    </button>
  );
}

interface TopNavProps {
  activeView: string;
  onSearchOpen: () => void;
  onNotifOpen: () => void;
}

export default function TopNav({ activeView, onSearchOpen, onNotifOpen }: TopNavProps) {
  const [dark, setDark] = useState(true);
  const [notes] = useState(3);
  const viewLabel = VIEW_LABELS[activeView] || 'Dashboard';

  return (
    <header style={{
      width: '100%', height: '100%',
      display: 'flex', alignItems: 'center', gap: 12, padding: '0 20px',
      background: 'rgba(10,14,26,0.97)',
      borderBottom: '1px solid rgba(255,255,255,0.06)',
      boxShadow: '0 1px 0 rgba(79,124,255,0.07), 0 4px 24px rgba(0,0,0,0.5)',
      backdropFilter: 'blur(20px)',
      WebkitBackdropFilter: 'blur(20px)',
      overflow: 'hidden',
    }}>
      {/* Breadcrumb */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
        <LayoutDashboard size={15} color="#475569" />
        <span style={{ fontSize: 12, color: '#475569' }}>/</span>
        <span style={{ fontSize: 13, fontWeight: 600, color: '#94A3B8' }}>Dashboard</span>
        <span style={{ fontSize: 12, color: '#334155' }}>/</span>
        <span style={{ fontSize: 13, fontWeight: 600, color: '#E2E8F0' }}>{viewLabel}</span>
      </div>

      <div style={{ width: 1, height: 20, background: 'rgba(255,255,255,0.07)', flexShrink: 0 }} />

      {/* Search */}
      <div style={{ flex: 1, maxWidth: 360, minWidth: 0 }}>
        <SearchBar onOpen={onSearchOpen} />
      </div>

      <div style={{ flex: 1 }} />

      {/* Market pills */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
        <MarketPill label="NYSE OPEN" color="green" delay={0} />
        <MarketPill label="CRYPTO 24/7" color="green" delay={0.5} />
      </div>

      <div style={{ width: 1, height: 20, background: 'rgba(255,255,255,0.07)', flexShrink: 0 }} />

      <div style={{ flexShrink: 0 }}>
        <LiveClock />
      </div>

      <div style={{ width: 1, height: 20, background: 'rgba(255,255,255,0.07)', flexShrink: 0 }} />

      {/* Broker status */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 6, padding: '5px 12px',
        borderRadius: 8, flexShrink: 0, fontSize: 11, fontWeight: 700,
        letterSpacing: '0.1em', color: '#22C55E',
        background: 'rgba(34,197,94,0.08)', border: '1px solid rgba(34,197,94,0.2)',
      }}>
        <Wifi size={13} />
        <span>PAPER</span>
        <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#22C55E', boxShadow: '0 0 6px #22C55E', animation: 'live-blink 1.4s ease-in-out 0.3s infinite' }} />
      </div>

      {/* Icon buttons */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
        <IBtn title="Activity"><Activity size={15} color="#64748B" /></IBtn>
        <IBtn badge={notes} title="Notifications" onClick={onNotifOpen}><Bell size={15} color="#64748B" /></IBtn>
        <IBtn title="Settings"><Settings size={15} color="#64748B" /></IBtn>
        <IBtn title={dark ? 'Light mode' : 'Dark mode'} onClick={() => setDark(d => !d)}>
          {dark ? <Moon size={15} color="#64748B" /> : <Sun size={15} color="#F59E0B" />}
        </IBtn>
      </div>

      <UserChip />
    </header>
  );
}

function SearchBar({ onOpen }: { onOpen: () => void }) {
  return (
    <div
      onClick={onOpen}
      style={{
        display: 'flex', alignItems: 'center', gap: 8,
        height: 36, padding: '0 12px', borderRadius: 10,
        background: 'rgba(255,255,255,0.04)',
        border: '1px solid rgba(255,255,255,0.08)',
        transition: 'all 0.15s ease', cursor: 'text', width: '100%',
      }}
      onMouseEnter={e => {
        (e.currentTarget as HTMLDivElement).style.background = 'rgba(79,124,255,0.06)';
        (e.currentTarget as HTMLDivElement).style.borderColor = 'rgba(79,124,255,0.25)';
      }}
      onMouseLeave={e => {
        (e.currentTarget as HTMLDivElement).style.background = 'rgba(255,255,255,0.04)';
        (e.currentTarget as HTMLDivElement).style.borderColor = 'rgba(255,255,255,0.08)';
      }}
    >
      <Search size={14} color="#475569" style={{ flexShrink: 0 }} />
      <span style={{ flex: 1, fontSize: 13, color: '#475569' }}>Search agents, signals, markets…</span>
      <kbd style={{
        display: 'flex', alignItems: 'center', padding: '2px 6px',
        borderRadius: 5, fontSize: 10, fontFamily: 'monospace', fontWeight: 600,
        color: '#334155', background: 'rgba(255,255,255,0.06)',
        border: '1px solid rgba(255,255,255,0.09)', flexShrink: 0, whiteSpace: 'nowrap',
      }}>⌘K</kbd>
    </div>
  );
}

function UserChip() {
  const [hov, setHov] = useState(false);
  return (
    <button
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        display: 'flex', alignItems: 'center', gap: 8,
        padding: '0 12px 0 6px', height: 36, borderRadius: 10, flexShrink: 0,
        background: hov ? 'rgba(255,255,255,0.08)' : 'rgba(255,255,255,0.04)',
        border: `1px solid ${hov ? 'rgba(255,255,255,0.14)' : 'rgba(255,255,255,0.08)'}`,
        cursor: 'pointer', transition: 'all 0.15s ease',
      }}
    >
      <div style={{
        width: 26, height: 26, borderRadius: '50%', flexShrink: 0,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 10, fontWeight: 700, color: '#fff',
        background: 'linear-gradient(135deg,#4F7CFF,#818CF8)',
        boxShadow: '0 0 10px rgba(79,124,255,0.4)',
      }}>PM</div>
      <div style={{ display: 'flex', flexDirection: 'column', lineHeight: 1, textAlign: 'left' }}>
        <span style={{ fontSize: 12, fontWeight: 600, color: '#E2E8F0' }}>Portfolio Mgr</span>
        <span style={{ fontSize: 10, color: '#475569', marginTop: 2 }}>Admin</span>
      </div>
      <ChevronDown size={12} color="#475569" style={{ flexShrink: 0 }} />
    </button>
  );
}
