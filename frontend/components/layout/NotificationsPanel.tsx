'use client';

import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Check } from 'lucide-react';
import { api, AlertRecord } from '@/lib/api';

interface NotificationsPanelProps {
  open: boolean;
  onClose: () => void;
}

const SEVERITY_ICON: Record<string, string> = {
  critical: '⚠️',
  warning: '🔔',
  info: 'ℹ️',
};

const SEVERITY_COLOR: Record<string, string> = {
  critical: '#EF4444',
  warning: '#F59E0B',
  info: '#4F7CFF',
};

function timeAgo(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins} min ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

export default function NotificationsPanel({ open, onClose }: NotificationsPanelProps) {
  const [alerts, setAlerts] = React.useState<AlertRecord[]>([]);
  const [unread, setUnread] = React.useState(0);

  const load = React.useCallback(async () => {
    try {
      const [list, count] = await Promise.all([
        api.alerts.list({ limit: 30 }),
        api.alerts.unreadCount(),
      ]);
      setAlerts(list);
      setUnread(count.unread_count);
    } catch {
      // Backend unavailable — leave prior state, panel just shows what it has.
    }
  }, []);

  React.useEffect(() => {
    if (!open) return;
    load();
    const interval = setInterval(load, 15000);
    return () => clearInterval(interval);
  }, [open, load]);

  async function acknowledge(id: string) {
    try {
      await api.alerts.acknowledge(id);
      setAlerts(prev => prev.map(a => a.id === id ? { ...a, acknowledged: true } : a));
      setUnread(prev => Math.max(0, prev - 1));
    } catch {
      // best-effort UI update only
    }
  }

  async function markAllRead() {
    const unacked = alerts.filter(a => !a.acknowledged);
    await Promise.all(unacked.map(a => api.alerts.acknowledge(a.id).catch(() => null)));
    setAlerts(prev => prev.map(a => ({ ...a, acknowledged: true })));
    setUnread(0);
  }

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
                <div style={{ fontSize: 11, color: '#475569', marginTop: 2 }}>{unread} unread</div>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <button onClick={markAllRead} style={{
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
              {alerts.length === 0 && (
                <div style={{ padding: '32px 20px', textAlign: 'center', fontSize: 12, color: '#475569' }}>
                  No alerts yet.
                </div>
              )}
              {alerts.map((n) => {
                const color = SEVERITY_COLOR[n.severity] || '#4F7CFF';
                return (
                  <div key={n.id} onClick={() => !n.acknowledged && acknowledge(n.id)} style={{
                    display: 'flex', gap: 12, padding: '12px 20px',
                    borderBottom: '1px solid rgba(255,255,255,0.03)',
                    cursor: 'pointer', transition: 'background 0.12s',
                    opacity: n.acknowledged ? 0.55 : 1,
                  }}
                    onMouseEnter={e => (e.currentTarget.style.background = 'rgba(255,255,255,0.03)')}
                    onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                  >
                    <div style={{
                      width: 36, height: 36, borderRadius: 10, flexShrink: 0,
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      background: `${color}18`,
                      border: `1px solid ${color}30`,
                      fontSize: 16,
                    }}>{SEVERITY_ICON[n.severity] || '🔔'}</div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 12.5, fontWeight: 600, color: '#E2E8F0', lineHeight: 1.4 }}>
                        {n.symbol ? `${n.symbol}: ` : ''}{n.alert_type.replace(/_/g, ' ')}
                      </div>
                      <div style={{ fontSize: 11.5, color: '#64748B', marginTop: 3, lineHeight: 1.4 }}>{n.message}</div>
                      <div style={{ fontSize: 10.5, color: '#334155', marginTop: 4 }}>{timeAgo(n.created_at)}</div>
                    </div>
                    {!n.acknowledged && (
                      <div style={{
                        width: 7, height: 7, borderRadius: '50%',
                        background: color, flexShrink: 0, marginTop: 6,
                        boxShadow: `0 0 6px ${color}`,
                      }} />
                    )}
                  </div>
                );
              })}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
