'use client';

import React from 'react';
import { motion } from 'framer-motion';
import { Radio } from 'lucide-react';

/**
 * Honest "not configured" state — mirrors the whale-alerts/exchange-flows
 * pattern from Phase 3 (ProviderGatedResponse). There is no live broker
 * wired into this system (config/settings.py's is_live is only true when
 * environment == "live", and no live broker adapter exists in brokers/ —
 * only PaperBroker). Building a fake "enabled" toggle here would violate
 * the no-fake-data constraint, so this view states the real state plainly.
 */
export default function LiveTradingView() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      style={{ padding: 24, paddingBottom: 48 }}
    >
      <div style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <h1 style={{ fontSize: 20, fontWeight: 700, color: '#E2E8F0', margin: 0 }}>Live Trading</h1>
          <span style={{
            padding: '3px 10px', borderRadius: 6, fontSize: 10, fontWeight: 800,
            background: 'rgba(245,158,11,0.12)', color: '#F59E0B',
            letterSpacing: '0.1em', border: '1px solid rgba(245,158,11,0.2)',
          }}>NOT CONNECTED</span>
        </div>
        <p style={{ fontSize: 13, color: '#475569', marginTop: 4 }}>
          Executes real trades through a connected broker with real capital
        </p>
      </div>

      <div style={{
        background: '#121826', border: '1px solid rgba(245,158,11,0.2)',
        borderRadius: 12, padding: 40, textAlign: 'center',
      }}>
        <div style={{
          width: 56, height: 56, borderRadius: 14, margin: '0 auto 16px',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: 'rgba(245,158,11,0.1)', border: '1px solid rgba(245,158,11,0.25)',
        }}>
          <Radio size={26} color="#F59E0B" />
        </div>
        <div style={{ fontSize: 15, fontWeight: 700, color: '#E2E8F0', marginBottom: 8 }}>
          Live trading requires a configured live broker — none connected
        </div>
        <div style={{ fontSize: 13, color: '#64748B', maxWidth: 460, margin: '0 auto', lineHeight: 1.6 }}>
          This deployment runs in {'{'}paper{'}'} mode (config/settings.py). Only
          the simulated Paper Broker is wired up — there is no live Binance,
          MT5, or other broker adapter connected. Live execution, real-money
          balances, and order routing shown here would be fabricated, so
          this view intentionally shows nothing until a real broker is
          configured in a future phase.
        </div>
      </div>
    </motion.div>
  );
}
