'use client';

import React, { useEffect, useState } from 'react';
import { Wifi, WifiOff, RadioTower } from 'lucide-react';
import { api, ConnectionStatusResponse } from '../../lib/api';

// Polls GET /system/connection-status rather than piggy-backing on the
// market-data WS itself — the indicator must still show "disconnected"
// correctly even when the WS never manages to open, which a WS-driven
// indicator could not do.
const POLL_MS = 3000;

export default function ConnectionStatusIndicator() {
  const [status, setStatus] = useState<ConnectionStatusResponse | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function poll() {
      try {
        const res = await api.system.getConnectionStatus();
        if (!cancelled) setStatus(res);
      } catch {
        if (!cancelled) setStatus(null);
      }
    }
    poll();
    const id = setInterval(poll, POLL_MS);
    return () => { cancelled = true; clearInterval(id); };
  }, []);

  const connected = status?.ws_status === 'connected';
  const color = connected ? '#22C55E' : status?.ws_status === 'reconnecting' ? '#F59E0B' : '#EF4444';
  const label = status ? status.ws_status.toUpperCase() : 'UNKNOWN';
  const Icon = connected ? RadioTower : status?.ws_status === 'reconnecting' ? Wifi : WifiOff;

  return (
    <div
      title={
        status
          ? `Live data: ${label}${status.latency_ms != null ? ` · ${status.latency_ms.toFixed(0)}ms` : ''}${!status.trading_enabled ? ' · trading paused (stale data)' : ''}`
          : 'Live data status unavailable'
      }
      className="hidden sm:flex items-center gap-1.5 px-2.5 h-8 rounded-lg flex-shrink-0 text-[11px] font-semibold tracking-wide"
      style={{
        background: `${color}14`,
        border: `1px solid ${color}33`,
        color,
      }}
    >
      <Icon className="w-3.5 h-3.5" />
      <span>{label}</span>
      {status?.latency_ms != null && (
        <span className="font-mono" style={{ opacity: 0.85 }}>{status.latency_ms.toFixed(0)}ms</span>
      )}
    </div>
  );
}
