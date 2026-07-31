'use client';

import React, { useEffect, useState } from 'react';
import { AlertTriangle } from 'lucide-react';
import { api, ConnectionStatusResponse } from '../../lib/api';

const POLL_MS = 3000;

// Impossible-to-miss banner: only renders (fixed, full-width, top of
// viewport) when the staleness gate's global trading_enabled is false —
// i.e. the same condition Phase 7's execution engine will block orders
// on via MarketDataStalenessGate.assert_fresh_or_raise().
export default function StalenessBanner() {
  const [status, setStatus] = useState<ConnectionStatusResponse | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function poll() {
      try {
        const res = await api.system.getConnectionStatus();
        if (!cancelled) setStatus(res);
      } catch {
        // Backend unreachable is itself a staleness condition worth
        // surfacing, but we don't fabricate a fake ConnectionStatusResponse —
        // just leave the previous known state until it recovers.
      }
    }
    poll();
    const id = setInterval(poll, POLL_MS);
    return () => { cancelled = true; clearInterval(id); };
  }, []);

  if (!status || status.trading_enabled) return null;

  const staleSymbols = status.symbols.filter((s) => !s.trading_enabled);

  return (
    <div
      role="alert"
      className="fixed top-0 left-0 right-0 z-[100] flex items-center justify-center gap-2 px-4 py-2 text-[12px] font-semibold"
      style={{
        background: '#EF4444',
        color: '#fff',
        boxShadow: '0 2px 12px rgba(239,68,68,0.5)',
      }}
    >
      <AlertTriangle className="w-4 h-4 flex-shrink-0" />
      <span>
        Live data disconnected — trading paused until data is restored
        {staleSymbols.length > 0 && (
          <span style={{ opacity: 0.85 }}> ({staleSymbols.map((s) => s.symbol).join(', ')})</span>
        )}
      </span>
    </div>
  );
}
