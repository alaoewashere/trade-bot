'use client';

import React, { useState } from 'react';
import {
  LayoutDashboard, TrendingUp, Bot, PieChart, Zap,
  Search, BookOpen, BarChart2, History, FlaskConical,
  Newspaper, Settings, ChevronLeft, ChevronRight,
  Globe, LineChart,
} from 'lucide-react';

interface NavItem {
  id: string;
  label: string;
  Icon: React.ElementType;
  badge?: string | number;
  section?: string;
}

const NAV: NavItem[] = [
  { id: 'dashboard',   label: 'Dashboard',     Icon: LayoutDashboard, section: 'TRADING' },
  { id: 'markets',     label: 'Markets',        Icon: Globe },
  { id: 'charts',      label: 'Live Charts',    Icon: TrendingUp },
  { id: 'agents',      label: 'AI Agents',      Icon: Bot,             badge: 40 },
  { id: 'portfolio',   label: 'Portfolio',      Icon: PieChart },
  { id: 'strategies',  label: 'Strategies',     Icon: Zap },
  { id: 'research',    label: 'Research',       Icon: Search,          section: 'RESEARCH' },
  { id: 'journal',     label: 'Journal',        Icon: BookOpen },
  { id: 'news',        label: 'News Feed',      Icon: Newspaper,       badge: 'NEW' },
  { id: 'performance', label: 'Performance',    Icon: BarChart2,       section: 'ANALYTICS' },
  { id: 'backtesting', label: 'Backtesting',    Icon: History },
  { id: 'paper',       label: 'Paper Trading',  Icon: FlaskConical },
  { id: 'charts2',     label: 'Chart View',     Icon: LineChart },
  { id: 'settings',    label: 'Settings',       Icon: Settings,        section: 'SYSTEM' },
];

function Section({ label, collapsed }: { label: string; collapsed: boolean }) {
  if (collapsed) return <div style={{ height: 1, margin: '8px 12px', background: 'rgba(255,255,255,0.05)' }} />;
  return (
    <div style={{ padding: '20px 16px 6px' }}>
      <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.18em', color: '#2D3748' }}>
        {label}
      </span>
    </div>
  );
}

function NavBtn({
  item, active, collapsed, onClick,
}: {
  item: NavItem; active: boolean; collapsed: boolean; onClick: () => void;
}) {
  const [hov, setHov] = useState(false);
  const { Icon } = item;

  const bgActive = 'rgba(79,124,255,0.12)';
  const bgHov = 'rgba(255,255,255,0.05)';
  const colActive = '#4F7CFF';
  const colHov = '#CBD5E1';
  const colDefault = '#64748B';

  const col = active ? colActive : hov ? colHov : colDefault;
  const bg = active ? bgActive : hov ? bgHov : 'transparent';

  return (
    <div style={{ position: 'relative', padding: collapsed ? '2px 0' : '2px 8px' }}>
      <button
        onClick={onClick}
        onMouseEnter={() => setHov(true)}
        onMouseLeave={() => setHov(false)}
        title={collapsed ? item.label : undefined}
        style={{
          width: '100%', display: 'flex', alignItems: 'center',
          gap: collapsed ? 0 : 10,
          justifyContent: collapsed ? 'center' : 'flex-start',
          height: 40, borderRadius: 10, padding: collapsed ? '0' : '0 10px',
          background: bg, border: 'none', cursor: 'pointer',
          transition: 'background 0.15s ease, color 0.15s ease',
          color: col, position: 'relative',
        }}
      >
        {active && !collapsed && (
          <span style={{
            position: 'absolute', left: 0, top: 8, bottom: 8, width: 3,
            borderRadius: 99, background: '#4F7CFF',
            boxShadow: '0 0 8px rgba(79,124,255,0.7)',
          }} />
        )}

        <span style={{
          width: 30, height: 30, borderRadius: 8, flexShrink: 0,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: active ? 'rgba(79,124,255,0.15)' : 'transparent',
          transition: 'background 0.15s ease',
        }}>
          <Icon size={16} strokeWidth={active ? 2.2 : 1.8} color={col} />
        </span>

        {!collapsed && (
          <>
            <span style={{
              flex: 1, textAlign: 'left', fontSize: 13.5, fontWeight: active ? 600 : 500,
              color: active ? '#E2E8F0' : col, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
            }}>
              {item.label}
            </span>
            {item.badge != null && (
              <span style={{
                fontSize: 10, fontWeight: 700, padding: '2px 7px', borderRadius: 99, flexShrink: 0,
                background: typeof item.badge === 'number' ? 'rgba(79,124,255,0.15)' : 'rgba(34,197,94,0.15)',
                color: typeof item.badge === 'number' ? '#4F7CFF' : '#22C55E',
              }}>{item.badge}</span>
            )}
          </>
        )}

        {collapsed && item.badge != null && (
          <span style={{
            position: 'absolute', top: 6, right: 10, width: 6, height: 6,
            borderRadius: '50%', background: '#4F7CFF',
            boxShadow: '0 0 6px rgba(79,124,255,0.7)',
          }} />
        )}
      </button>

      {collapsed && hov && (
        <div style={{
          position: 'absolute', left: 'calc(100% + 10px)', top: '50%', transform: 'translateY(-50%)',
          zIndex: 9999, pointerEvents: 'none',
          background: '#1E2940', border: '1px solid rgba(255,255,255,0.1)',
          borderRadius: 8, padding: '6px 12px', whiteSpace: 'nowrap',
          fontSize: 12, fontWeight: 600, color: '#E2E8F0',
          boxShadow: '0 4px 20px rgba(0,0,0,0.5)',
        }}>
          {item.label}
          {item.badge != null && (
            <span style={{ marginLeft: 6, color: '#4F7CFF' }}>{item.badge}</span>
          )}
        </div>
      )}
    </div>
  );
}

export default function SideNav({
  collapsed,
  onToggle,
  activeView,
  setActiveView,
}: {
  collapsed: boolean;
  onToggle: () => void;
  activeView: string;
  setActiveView: (v: string) => void;
}) {
  return (
    <aside style={{
      width: '100%', height: '100%',
      display: 'flex', flexDirection: 'column',
      background: 'rgba(8,12,24,0.99)',
      borderRight: '1px solid rgba(255,255,255,0.05)',
      boxShadow: '2px 0 20px rgba(0,0,0,0.4)',
      overflow: 'hidden',
    }}>
      {/* Logo */}
      <div style={{
        height: 72, display: 'flex', alignItems: 'center', flexShrink: 0,
        padding: collapsed ? '0' : '0 16px',
        justifyContent: collapsed ? 'center' : 'flex-start',
        borderBottom: '1px solid rgba(255,255,255,0.05)',
      }}>
        <div style={{
          width: 36, height: 36, borderRadius: 10, flexShrink: 0,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: 'linear-gradient(135deg,#4F7CFF 0%,#818CF8 100%)',
          boxShadow: '0 0 20px rgba(79,124,255,0.5), 0 2px 8px rgba(0,0,0,0.3)',
        }}>
          <Zap size={18} color="#fff" strokeWidth={2.5} />
        </div>
        {!collapsed && (
          <div style={{ marginLeft: 10, lineHeight: 1 }}>
            <div style={{
              fontSize: 14, fontWeight: 900, letterSpacing: '0.18em',
              background: 'linear-gradient(135deg,#4F7CFF,#a78bfa)',
              WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text',
            }}>HEDGE-AI</div>
            <div style={{ fontSize: 9, fontWeight: 700, letterSpacing: '0.22em', color: '#2D3748', marginTop: 3 }}>
              INSTITUTIONAL
            </div>
          </div>
        )}
      </div>

      {/* Nav items */}
      <div style={{ flex: 1, overflowY: 'auto', overflowX: 'hidden', padding: '4px 0' }}
        className="scrollbar-hide"
      >
        {NAV.map(item => (
          <React.Fragment key={item.id}>
            {item.section && <Section label={item.section} collapsed={collapsed} />}
            <NavBtn
              item={item}
              active={activeView === item.id}
              collapsed={collapsed}
              onClick={() => setActiveView(item.id)}
            />
          </React.Fragment>
        ))}
      </div>

      {/* Portfolio strip */}
      {!collapsed && (
        <div style={{
          margin: '0 8px 8px', padding: '10px 12px', borderRadius: 10,
          background: 'rgba(79,124,255,0.07)', border: '1px solid rgba(79,124,255,0.14)',
          flexShrink: 0,
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
            <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.12em', color: '#334155' }}>PORTFOLIO</span>
            <span style={{ fontSize: 10, fontWeight: 700, color: '#22C55E' }}>+4.2%</span>
          </div>
          <div style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 15, fontWeight: 700, color: '#E2E8F0' }}>
            $124,830.40
          </div>
        </div>
      )}

      {/* Collapse toggle */}
      <div style={{ padding: '0 8px 12px', flexShrink: 0 }}>
        <CollapseBtn collapsed={collapsed} onToggle={onToggle} />
      </div>
    </aside>
  );
}

function CollapseBtn({ collapsed, onToggle }: { collapsed: boolean; onToggle: () => void }) {
  const [hov, setHov] = useState(false);
  return (
    <button
      onClick={onToggle}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
      style={{
        width: '100%', height: 36, borderRadius: 8, display: 'flex',
        alignItems: 'center', justifyContent: collapsed ? 'center' : 'flex-start',
        gap: 8, padding: collapsed ? 0 : '0 12px',
        background: hov ? 'rgba(255,255,255,0.07)' : 'rgba(255,255,255,0.03)',
        border: `1px solid ${hov ? 'rgba(255,255,255,0.12)' : 'rgba(255,255,255,0.06)'}`,
        cursor: 'pointer', transition: 'all 0.15s ease',
        color: hov ? '#94A3B8' : '#475569', fontSize: 12, fontWeight: 500,
      }}
    >
      {collapsed
        ? <ChevronRight size={16} color="currentColor" strokeWidth={2} />
        : <><ChevronLeft size={16} color="currentColor" strokeWidth={2} /><span>Collapse</span></>
      }
    </button>
  );
}
