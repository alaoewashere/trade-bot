'use client';

import React from 'react';
import clsx from 'clsx';
import {
  LayoutDashboard, LineChart, TrendingUp, Bot,
  PieChart, Zap, Search, BookOpen, BarChart2,
  History, FlaskConical, Newspaper, Settings,
  ChevronLeft, ChevronRight, Globe, ShieldAlert,
} from 'lucide-react';
import { useAppStore } from '@/lib/store';

/* ─── Nav data ────────────────────────────────────── */
interface NavItem {
  id: string;
  label: string;
  icon: React.ElementType;
  badge?: string | number;
  section?: string; // section header before this item
}

const NAV_ITEMS: NavItem[] = [
  { id: 'dashboard',    label: 'Dashboard',     icon: LayoutDashboard, section: 'TRADING' },
  { id: 'markets',      label: 'Markets',        icon: Globe },
  { id: 'charts',       label: 'Live Charts',    icon: TrendingUp },
  { id: 'agents',       label: 'AI Agents',      icon: Bot,            badge: 40 },
  { id: 'portfolio',    label: 'Portfolio',      icon: PieChart },
  { id: 'risk-center',  label: 'Risk Center',    icon: ShieldAlert },
  { id: 'strategies',   label: 'Strategies',     icon: Zap },
  { id: 'research',     label: 'Research',       icon: Search,         section: 'RESEARCH' },
  { id: 'journal',      label: 'Journal',        icon: BookOpen },
  { id: 'news',         label: 'News Feed',      icon: Newspaper,      badge: 'NEW' },
  { id: 'performance',  label: 'Performance',    icon: BarChart2,      section: 'ANALYTICS' },
  { id: 'backtesting',  label: 'Backtesting',    icon: History },
  { id: 'paper',        label: 'Paper Trading',  icon: FlaskConical },
  { id: 'charts2',      label: 'Charts',         icon: LineChart },
  { id: 'settings',     label: 'Settings',       icon: Settings,       section: 'SYSTEM' },
];

/* ─── Section label ───────────────────────────────── */
function SectionLabel({ label, collapsed }: { label: string; collapsed: boolean }) {
  if (collapsed) {
    return <div className="h-px mx-3 my-2" style={{ background: 'rgba(255,255,255,0.06)' }} />;
  }
  return (
    <div className="px-4 pt-5 pb-1.5">
      <span
        className="text-[10px] font-semibold tracking-[0.18em] select-none"
        style={{ color: '#334155' }}
      >
        {label}
      </span>
    </div>
  );
}

/* ─── Single nav item ─────────────────────────────── */
function NavButton({
  item,
  isActive,
  collapsed,
  onClick,
}: {
  item: NavItem;
  isActive: boolean;
  collapsed: boolean;
  onClick: () => void;
}) {
  const Icon = item.icon;

  return (
    <button
      onClick={onClick}
      title={collapsed ? item.label : undefined}
      className={clsx(
        'group relative w-full flex items-center transition-all duration-200 outline-none',
        collapsed ? 'justify-center h-10 mx-0 px-0' : 'gap-3 h-10 mx-2 px-3 rounded-xl',
      )}
      style={
        isActive
          ? {
              background: collapsed ? undefined : 'rgba(79,124,255,0.12)',
              color: '#4F7CFF',
            }
          : {
              background: 'transparent',
              color: '#64748B',
            }
      }
      onMouseEnter={e => {
        if (!isActive) {
          (e.currentTarget as HTMLElement).style.background = collapsed
            ? 'transparent'
            : 'rgba(255,255,255,0.05)';
          (e.currentTarget as HTMLElement).style.color = '#CBD5E1';
        }
      }}
      onMouseLeave={e => {
        if (!isActive) {
          (e.currentTarget as HTMLElement).style.background = 'transparent';
          (e.currentTarget as HTMLElement).style.color = '#64748B';
        }
      }}
    >
      {/* Active left bar */}
      {isActive && !collapsed && (
        <span
          className="absolute left-0 top-2 bottom-2 w-[3px] rounded-full"
          style={{ background: '#4F7CFF', boxShadow: '0 0 8px rgba(79,124,255,0.6)' }}
        />
      )}

      {/* Icon container */}
      <span
        className={clsx(
          'flex-shrink-0 flex items-center justify-center rounded-lg transition-all duration-200',
          collapsed ? 'w-10 h-10' : 'w-[30px] h-[30px]',
        )}
        style={
          isActive
            ? {
                background: 'rgba(79,124,255,0.15)',
                boxShadow: '0 0 12px rgba(79,124,255,0.2)',
              }
            : { background: 'transparent' }
        }
      >
        <Icon
          className={collapsed ? 'w-[18px] h-[18px]' : 'w-[17px] h-[17px]'}
          strokeWidth={isActive ? 2.2 : 1.8}
        />
      </span>

      {/* Label + badge */}
      {!collapsed && (
        <>
          <span
            className="flex-1 text-left text-[13px] font-medium tracking-[-0.01em] truncate"
            style={{ color: isActive ? '#E2E8F0' : 'inherit' }}
          >
            {item.label}
          </span>
          {item.badge != null && (
            <span
              className="flex-shrink-0 text-[10px] font-semibold px-1.5 py-0.5 rounded-full leading-none"
              style={
                typeof item.badge === 'number'
                  ? { background: 'rgba(79,124,255,0.15)', color: '#4F7CFF' }
                  : { background: 'rgba(34,197,94,0.15)', color: '#22C55E' }
              }
            >
              {item.badge}
            </span>
          )}
        </>
      )}

      {/* Collapsed badge dot */}
      {collapsed && item.badge != null && (
        <span
          className="absolute top-1.5 right-1.5 w-1.5 h-1.5 rounded-full"
          style={{ background: '#4F7CFF', boxShadow: '0 0 6px rgba(79,124,255,0.6)' }}
        />
      )}

      {/* Tooltip on collapsed */}
      {collapsed && (
        <span
          className="pointer-events-none absolute left-full ml-3 z-50 whitespace-nowrap px-2.5 py-1.5 rounded-lg text-[12px] font-medium opacity-0 group-hover:opacity-100 transition-opacity duration-150"
          style={{
            background: '#1a2235',
            border: '1px solid rgba(255,255,255,0.1)',
            color: '#E2E8F0',
            boxShadow: '0 4px 16px rgba(0,0,0,0.4)',
          }}
        >
          {item.label}
          {item.badge != null && (
            <span className="ml-2 text-[10px]" style={{ color: '#4F7CFF' }}>{item.badge}</span>
          )}
        </span>
      )}
    </button>
  );
}

/* ─── Sidebar ─────────────────────────────────────── */
export default function Sidebar() {
  const { sidebarCollapsed, toggleSidebar, activeView, setActiveView } = useAppStore();
  const W = sidebarCollapsed ? 68 : 280;

  return (
    <aside
      className="relative z-40 flex flex-col flex-shrink-0 overflow-hidden transition-all duration-300 ease-in-out"
      style={{
        width: W,
        minWidth: W,
        background: 'rgba(10,14,26,0.98)',
        borderRight: '1px solid rgba(255,255,255,0.05)',
        boxShadow: '1px 0 0 rgba(255,255,255,0.03), 4px 0 24px rgba(0,0,0,0.3)',
      }}
    >
      {/* ── Nav list ───────────────────────────────── */}
      <nav className="flex-1 overflow-y-auto overflow-x-hidden py-3 scrollbar-hide">
        {NAV_ITEMS.map((item) => {
          const isActive = activeView === item.id;
          return (
            <React.Fragment key={item.id}>
              {item.section && (
                <SectionLabel label={item.section} collapsed={sidebarCollapsed} />
              )}
              <NavButton
                item={item}
                isActive={isActive}
                collapsed={sidebarCollapsed}
                onClick={() => setActiveView(item.id)}
              />
            </React.Fragment>
          );
        })}
      </nav>

      {/* ── Bottom: portfolio value + collapse ──────── */}
      <div
        className="flex-shrink-0 p-3"
        style={{ borderTop: '1px solid rgba(255,255,255,0.05)' }}
      >
        {/* Portfolio value strip (expanded only) */}
        {!sidebarCollapsed && (
          <div
            className="mb-3 px-3 py-2.5 rounded-xl"
            style={{
              background: 'rgba(79,124,255,0.07)',
              border: '1px solid rgba(79,124,255,0.14)',
            }}
          >
            <div className="flex items-center justify-between mb-0.5">
              <span className="text-[10px] font-semibold tracking-wide" style={{ color: '#475569' }}>
                PORTFOLIO VALUE
              </span>
              <span className="text-[10px] font-semibold" style={{ color: '#22C55E' }}>
                +4.2%
              </span>
            </div>
            <span className="font-mono text-[15px] font-bold" style={{ color: '#E2E8F0' }}>
              $124,830.40
            </span>
          </div>
        )}

        {/* Collapse button */}
        <button
          onClick={toggleSidebar}
          className={clsx(
            'flex items-center justify-center rounded-xl h-9 transition-all duration-200 w-full',
          )}
          style={{
            background: 'rgba(255,255,255,0.04)',
            border: '1px solid rgba(255,255,255,0.07)',
            color: '#475569',
          }}
          onMouseEnter={e => {
            (e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.08)';
            (e.currentTarget as HTMLElement).style.borderColor = 'rgba(255,255,255,0.12)';
            (e.currentTarget as HTMLElement).style.color = '#94A3B8';
          }}
          onMouseLeave={e => {
            (e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.04)';
            (e.currentTarget as HTMLElement).style.borderColor = 'rgba(255,255,255,0.07)';
            (e.currentTarget as HTMLElement).style.color = '#475569';
          }}
          title={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {sidebarCollapsed
            ? <ChevronRight className="w-4 h-4" strokeWidth={2} />
            : (
              <span className="flex items-center gap-2 text-[12px] font-medium">
                <ChevronLeft className="w-4 h-4" strokeWidth={2} />
                Collapse
              </span>
            )}
        </button>
      </div>
    </aside>
  );
}
