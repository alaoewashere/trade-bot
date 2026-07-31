'use client';

import React from 'react';
import { motion } from 'framer-motion';
import { CheckCircle2, Circle } from 'lucide-react';

interface BrokerRow {
  name: string;
  status: 'connected' | 'not_configured';
  detail: string;
}

// Static — reflects what's actually implemented in brokers/ (only
// PaperBroker exists; base_broker.py is the abstract interface every future
// adapter must implement). Not sourced from a backend endpoint because
// there is nothing dynamic to report yet: this is the honest list of what
// this codebase currently ships, mirroring the "not yet configured" pattern
// used elsewhere (whale-alerts/exchange-flows in Phase 3).
const BROKERS: BrokerRow[] = [
  { name: 'Paper Broker', status: 'connected', detail: 'Simulated fills, Redis-persisted — brokers/paper_broker.py' },
  { name: 'Live Binance', status: 'not_configured', detail: 'No live exchange API credentials wired up' },
  { name: 'MetaTrader 5 (MT5)', status: 'not_configured', detail: 'Adapter not built — deferred to a future phase' },
  { name: 'Alpaca', status: 'not_configured', detail: 'Adapter not built — deferred to a future phase' },
];

export default function BrokerConnectionsView() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      style={{ padding: 24, paddingBottom: 48 }}
    >
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 20, fontWeight: 700, color: '#E2E8F0', margin: 0 }}>Broker Connections</h1>
        <p style={{ fontSize: 13, color: '#475569', marginTop: 4 }}>
          Every broker adapter this platform implements, and its actual connection status
        </p>
      </div>

      <div style={{
        background: '#121826', border: '1px solid rgba(255,255,255,0.06)',
        borderRadius: 12, overflow: 'hidden',
      }}>
        {BROKERS.map((b, i) => (
          <div key={b.name} style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '16px 20px',
            borderBottom: i < BROKERS.length - 1 ? '1px solid rgba(255,255,255,0.05)' : 'none',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              {b.status === 'connected'
                ? <CheckCircle2 size={18} color="#22C55E" />
                : <Circle size={18} color="#334155" />}
              <div>
                <div style={{ fontSize: 14, fontWeight: 700, color: '#E2E8F0' }}>{b.name}</div>
                <div style={{ fontSize: 12, color: '#475569', marginTop: 2 }}>{b.detail}</div>
              </div>
            </div>
            <span style={{
              padding: '4px 12px', borderRadius: 6, fontSize: 10, fontWeight: 800, letterSpacing: '0.08em',
              background: b.status === 'connected' ? 'rgba(34,197,94,0.12)' : 'rgba(255,255,255,0.05)',
              color: b.status === 'connected' ? '#22C55E' : '#64748B',
              border: `1px solid ${b.status === 'connected' ? 'rgba(34,197,94,0.25)' : 'rgba(255,255,255,0.08)'}`,
            }}>
              {b.status === 'connected' ? 'CONNECTED (SIMULATED)' : 'NOT CONFIGURED'}
            </span>
          </div>
        ))}
      </div>
    </motion.div>
  );
}
