'use client';

import React, { useState, useEffect } from 'react';
import {
  Zap, Search, Bell, Settings, ChevronDown,
  Wifi, WifiOff, Sun, Moon, Activity,
} from 'lucide-react';

/* ─── Live clock ──────────────────────────────────── */
function LiveClock() {
  const [time, setTime] = useState('');
  const [date, setDate] = useState('');

  useEffect(() => {
    const tick = () => {
      const now = new Date();
      setTime(now.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' }));
      setDate(now.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' }));
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="flex flex-col items-end">
      <span className="font-mono text-[13px] font-semibold tracking-widest text-white tabular-nums leading-none">
        {time}
      </span>
      <span className="font-mono text-[10px] tracking-wide leading-none mt-0.5" style={{ color: '#475569' }}>
        {date}
      </span>
    </div>
  );
}

/* ─── Market status badge ─────────────────────────── */
function MarketBadge({ label, open, delay = 0 }: { label: string; open: boolean; delay?: number }) {
  return (
    <div
      className="flex items-center gap-2 px-3 py-1.5 rounded-full text-[11px] font-semibold tracking-wide select-none"
      style={{
        background: open ? 'rgba(34,197,94,0.08)' : 'rgba(239,68,68,0.08)',
        border: `1px solid ${open ? 'rgba(34,197,94,0.2)' : 'rgba(239,68,68,0.2)'}`,
        color: open ? '#22C55E' : '#EF4444',
      }}
    >
      <span
        className="w-1.5 h-1.5 rounded-full flex-shrink-0"
        style={{
          background: open ? '#22C55E' : '#EF4444',
          animation: open ? `live-blink 1.4s ease-in-out ${delay}s infinite` : 'none',
          boxShadow: open ? '0 0 6px rgba(34,197,94,0.6)' : 'none',
        }}
      />
      {label}
    </div>
  );
}

/* ─── Icon button ─────────────────────────────────── */
function IconBtn({
  children, badge, onClick, title,
}: {
  children: React.ReactNode;
  badge?: number;
  onClick?: () => void;
  title?: string;
}) {
  return (
    <button
      onClick={onClick}
      title={title}
      className="relative w-8 h-8 rounded-lg flex items-center justify-center transition-all duration-150 group"
      style={{
        background: 'rgba(255,255,255,0.04)',
        border: '1px solid rgba(255,255,255,0.07)',
      }}
      onMouseEnter={e => {
        (e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.08)';
        (e.currentTarget as HTMLElement).style.borderColor = 'rgba(255,255,255,0.14)';
      }}
      onMouseLeave={e => {
        (e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.04)';
        (e.currentTarget as HTMLElement).style.borderColor = 'rgba(255,255,255,0.07)';
      }}
    >
      {children}
      {badge != null && badge > 0 && (
        <span
          className="absolute -top-1.5 -right-1.5 min-w-[18px] h-[18px] px-1 rounded-full flex items-center justify-center text-[10px] font-bold text-white leading-none"
          style={{ background: 'linear-gradient(135deg,#4F7CFF,#818CF8)', boxShadow: '0 2px 8px rgba(79,124,255,0.5)' }}
        >
          {badge}
        </span>
      )}
    </button>
  );
}

/* ─── TopBar ──────────────────────────────────────── */
export default function TopBar() {
  const [darkMode, setDarkMode] = useState(true);
  const [notifications] = useState(3);
  const [brokerConnected] = useState(true);

  return (
    <header
      className="flex-shrink-0 z-50 flex items-center gap-3 px-5"
      style={{
        height: 60,
        background: 'rgba(11,16,32,0.96)',
        backdropFilter: 'blur(20px)',
        WebkitBackdropFilter: 'blur(20px)',
        borderBottom: '1px solid rgba(255,255,255,0.06)',
        boxShadow: '0 1px 0 rgba(79,124,255,0.06), 0 4px 24px rgba(0,0,0,0.4)',
      }}
    >
      {/* ── Logo ───────────────────────────────────── */}
      <div className="flex items-center gap-2.5 flex-shrink-0 mr-2">
        <div
          className="w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0"
          style={{
            background: 'linear-gradient(135deg,#4F7CFF 0%,#818CF8 100%)',
            boxShadow: '0 0 16px rgba(79,124,255,0.4), 0 2px 8px rgba(0,0,0,0.3)',
          }}
        >
          <Zap className="w-4 h-4 text-white" strokeWidth={2.5} />
        </div>
        <div className="flex flex-col leading-none">
          <span
            className="text-[13px] font-black tracking-[0.18em]"
            style={{
              background: 'linear-gradient(135deg,#4F7CFF 0%,#a78bfa 100%)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              backgroundClip: 'text',
            }}
          >
            HEDGE-AI
          </span>
          <span className="text-[9px] font-semibold tracking-[0.22em] mt-0.5" style={{ color: '#334155' }}>
            INSTITUTIONAL
          </span>
        </div>
      </div>

      {/* ── Divider ────────────────────────────────── */}
      <div className="w-px h-6 flex-shrink-0" style={{ background: 'rgba(255,255,255,0.08)' }} />

      {/* ── Search ─────────────────────────────────── */}
      <button
        className="flex items-center gap-2.5 px-3 h-9 rounded-xl flex-shrink-0 transition-all duration-150 group"
        style={{
          background: 'rgba(255,255,255,0.04)',
          border: '1px solid rgba(255,255,255,0.08)',
          minWidth: 220,
        }}
        onMouseEnter={e => {
          (e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.07)';
          (e.currentTarget as HTMLElement).style.borderColor = 'rgba(79,124,255,0.3)';
          (e.currentTarget as HTMLElement).style.boxShadow = '0 0 0 3px rgba(79,124,255,0.06)';
        }}
        onMouseLeave={e => {
          (e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.04)';
          (e.currentTarget as HTMLElement).style.borderColor = 'rgba(255,255,255,0.08)';
          (e.currentTarget as HTMLElement).style.boxShadow = 'none';
        }}
      >
        <Search className="w-3.5 h-3.5 flex-shrink-0" style={{ color: '#475569' }} />
        <span className="text-[13px] flex-1 text-left" style={{ color: '#475569' }}>
          Search agents, signals…
        </span>
        <div className="flex items-center gap-1">
          <kbd
            className="inline-flex items-center px-1.5 h-5 rounded text-[10px] font-mono font-semibold leading-none"
            style={{ background: 'rgba(255,255,255,0.07)', border: '1px solid rgba(255,255,255,0.1)', color: '#64748b' }}
          >
            ⌘K
          </kbd>
        </div>
      </button>

      {/* ── Market status ──────────────────────────── */}
      <div className="hidden lg:flex items-center gap-2 flex-shrink-0">
        <MarketBadge label="NYSE OPEN" open={true} delay={0} />
        <MarketBadge label="CRYPTO 24/7" open={true} delay={0.6} />
        <MarketBadge label="FOREX OPEN" open={true} delay={1.1} />
      </div>

      {/* ── Spacer ─────────────────────────────────── */}
      <div className="flex-1" />

      {/* ── Clock ──────────────────────────────────── */}
      <div className="hidden md:block flex-shrink-0">
        <LiveClock />
      </div>

      {/* ── Divider ────────────────────────────────── */}
      <div className="w-px h-6 flex-shrink-0" style={{ background: 'rgba(255,255,255,0.08)' }} />

      {/* ── Broker status ──────────────────────────── */}
      <div
        className="hidden sm:flex items-center gap-2 px-3 h-8 rounded-lg flex-shrink-0 text-[11px] font-semibold tracking-wide"
        style={{
          background: brokerConnected ? 'rgba(34,197,94,0.08)' : 'rgba(239,68,68,0.08)',
          border: `1px solid ${brokerConnected ? 'rgba(34,197,94,0.2)' : 'rgba(239,68,68,0.2)'}`,
          color: brokerConnected ? '#22C55E' : '#EF4444',
        }}
      >
        {brokerConnected
          ? <Wifi className="w-3.5 h-3.5" />
          : <WifiOff className="w-3.5 h-3.5" />}
        <span>PAPER</span>
        <span
          className="w-1.5 h-1.5 rounded-full"
          style={{
            background: '#22C55E',
            animation: 'live-blink 1.4s ease-in-out infinite',
            boxShadow: '0 0 6px rgba(34,197,94,0.6)',
          }}
        />
      </div>

      {/* ── Right icons ────────────────────────────── */}
      <div className="flex items-center gap-1.5">
        <IconBtn title="Activity" onClick={() => {}}>
          <Activity className="w-4 h-4" style={{ color: '#94A3B8' }} />
        </IconBtn>

        <IconBtn badge={notifications} title="Notifications">
          <Bell className="w-4 h-4" style={{ color: '#94A3B8' }} />
        </IconBtn>

        <IconBtn title="Settings">
          <Settings className="w-4 h-4" style={{ color: '#94A3B8' }} />
        </IconBtn>

        <IconBtn title={darkMode ? 'Light mode' : 'Dark mode'} onClick={() => setDarkMode(d => !d)}>
          {darkMode
            ? <Moon className="w-4 h-4" style={{ color: '#94A3B8' }} />
            : <Sun className="w-4 h-4" style={{ color: '#F59E0B' }} />}
        </IconBtn>
      </div>

      {/* ── User profile ───────────────────────────── */}
      <button
        className="flex items-center gap-2.5 pl-2 pr-3 h-9 rounded-xl transition-all duration-150 flex-shrink-0"
        style={{
          background: 'rgba(255,255,255,0.04)',
          border: '1px solid rgba(255,255,255,0.08)',
        }}
        onMouseEnter={e => {
          (e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.08)';
          (e.currentTarget as HTMLElement).style.borderColor = 'rgba(255,255,255,0.14)';
        }}
        onMouseLeave={e => {
          (e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.04)';
          (e.currentTarget as HTMLElement).style.borderColor = 'rgba(255,255,255,0.08)';
        }}
      >
        <div
          className="w-6 h-6 rounded-full flex items-center justify-center text-[11px] font-bold text-white flex-shrink-0"
          style={{
            background: 'linear-gradient(135deg,#4F7CFF,#818CF8)',
            boxShadow: '0 0 10px rgba(79,124,255,0.4)',
          }}
        >
          PM
        </div>
        <div className="hidden md:flex flex-col leading-none text-left">
          <span className="text-[12px] font-semibold" style={{ color: '#E2E8F0' }}>Portfolio Mgr</span>
          <span className="text-[10px] mt-0.5" style={{ color: '#475569' }}>Admin</span>
        </div>
        <ChevronDown className="w-3 h-3 flex-shrink-0" style={{ color: '#475569' }} />
      </button>
    </header>
  );
}
