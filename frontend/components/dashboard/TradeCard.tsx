'use client';

import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { CheckCircle, XCircle, TrendingUp } from 'lucide-react';
import Badge from '@/components/ui/Badge';
import clsx from 'clsx';

const FIELDS: { label: string; value: string; highlight?: string }[] = [
  { label: 'Entry', value: '$67,428', highlight: 'primary' },
  { label: 'Stop Loss', value: '$66,100', highlight: 'danger' },
  { label: 'Target', value: '$69,200', highlight: 'success' },
  { label: 'Risk', value: '$1,328 (1.96%)' },
  { label: 'Reward', value: '$1,772 (2.62%)' },
  { label: 'R:R Ratio', value: '1 : 1.33', highlight: 'primary' },
  { label: 'Position', value: '0.15 BTC' },
  { label: 'Confidence', value: '78%', highlight: 'success' },
  { label: 'Timeframe', value: '4H' },
  { label: 'Est. Duration', value: '2–6 days' },
  { label: 'Max Drawdown', value: '-3.2%', highlight: 'danger' },
  { label: 'Expected Return', value: '+2.62%', highlight: 'success' },
];

const highlightColor = (h?: string) => {
  if (h === 'primary') return '#4F7CFF';
  if (h === 'success') return '#22C55E';
  if (h === 'danger') return '#EF4444';
  return '#F1F5F9';
};

export default function TradeCard() {
  const [approved, setApproved] = useState<null | 'approved' | 'rejected'>(null);

  return (
    <motion.div
      className="rounded-xl p-5 flex flex-col gap-4 h-full"
      style={{
        background: 'linear-gradient(160deg, #121826 0%, #0d1e2e 50%, #121826 100%)',
        border: '1px solid rgba(255,255,255,0.08)',
      }}
      whileHover={{ scale: 1.005 }}
      transition={{ type: 'spring', stiffness: 300, damping: 20 }}
    >
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <TrendingUp className="w-4 h-4" style={{ color: '#4F7CFF' }} />
          <span className="text-xs font-bold uppercase tracking-wider" style={{ color: '#F1F5F9' }}>
            Trade Proposal
          </span>
        </div>
        {approved === null && (
          <Badge variant="warning" dot pulse>
            PENDING APPROVAL
          </Badge>
        )}
        {approved === 'approved' && <Badge variant="success" dot>APPROVED</Badge>}
        {approved === 'rejected' && <Badge variant="danger" dot>REJECTED</Badge>}
      </div>

      {/* Fields grid */}
      <div className="grid grid-cols-2 gap-x-4 gap-y-3 flex-1">
        {FIELDS.map((f) => (
          <div key={f.label}>
            <div className="text-[10px] font-medium uppercase tracking-wider mb-0.5" style={{ color: '#475569' }}>
              {f.label}
            </div>
            <div
              className="font-mono text-xs font-semibold"
              style={{ color: highlightColor(f.highlight) }}
            >
              {f.value}
            </div>
          </div>
        ))}
      </div>

      {/* Divider */}
      <div style={{ height: 1, background: 'rgba(255,255,255,0.06)' }} />

      {/* Buttons */}
      {approved === null ? (
        <div className="flex gap-2">
          <motion.button
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.97 }}
            onClick={() => setApproved('approved')}
            className="flex-1 flex items-center justify-center gap-2 py-3 rounded-lg text-sm font-bold text-white transition-all"
            style={{
              background: 'linear-gradient(135deg, #22C55E 0%, #16A34A 100%)',
            }}
          >
            <CheckCircle className="w-4 h-4" />
            APPROVE TRADE
          </motion.button>
          <motion.button
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.97 }}
            onClick={() => setApproved('rejected')}
            className="px-4 py-3 rounded-lg text-sm font-bold transition-all"
            style={{
              border: '1px solid rgba(239,68,68,0.4)',
              color: '#EF4444',
            }}
          >
            REJECT
          </motion.button>
        </div>
      ) : (
        <div
          className="rounded-lg py-3 text-center text-sm font-bold"
          style={{
            background:
              approved === 'approved'
                ? 'rgba(34,197,94,0.12)'
                : 'rgba(239,68,68,0.12)',
            color: approved === 'approved' ? '#22C55E' : '#EF4444',
            border: `1px solid ${approved === 'approved' ? 'rgba(34,197,94,0.2)' : 'rgba(239,68,68,0.2)'}`,
          }}
        >
          {approved === 'approved' ? '✓ Trade Approved — Sending to Broker' : '✕ Trade Rejected'}
        </div>
      )}
    </motion.div>
  );
}
