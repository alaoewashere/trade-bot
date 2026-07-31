'use client';

import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { supabase } from '@/lib/supabase';
import { api } from '@/lib/api';

const BULLISH = '#22C55E';
const BEARISH = '#EF4444';
const AMBER = '#F59E0B';
const PRIMARY = '#4F7CFF';
const GRAY = '#64748B';

type TimelineEventType = 'agent_decision' | 'proposal' | 'trade_opened' | 'trade_closed';

interface TimelineEvent {
  timestamp: string;
  type: TimelineEventType;
  title: string;
  detail: string;
  color: string;
}

/**
 * Phase 5 part E — narrower, honest scope: this is a read-only, client-side
 * reconstruction from existing timestamped tables (agent_decisions.decided_at,
 * trade_proposals.proposed_at/decided_at, trades.opened_at/closed_at). There is
 * no dedicated decision-audit-trail/event-log table in this codebase; building
 * one would make the "Technical AI detected breakout -> ... -> Closed" story
 * richer (exact causal links, not just temporal proximity) but is out of scope
 * for this phase. What you see here is everything in that window, ordered by
 * time — a faithful replay of *what happened when*, not a guaranteed causal
 * chain.
 */
export default function DecisionTimeline({
  symbol,
  windowStart,
  windowEnd,
}: {
  symbol: string;
  windowStart: string;
  windowEnd: string;
}) {
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        // Pad the window slightly — trades and decisions triggered by this
        // forecast can land a few minutes either side of created_at/expiry_at.
        const padMs = 30 * 60 * 1000;
        const start = new Date(new Date(windowStart).getTime() - padMs).toISOString();
        const end = new Date(new Date(windowEnd).getTime() + padMs).toISOString();

        const [decisionsRes, proposalsRes, tradesRes] = await Promise.allSettled([
          supabase
            .from('agent_decisions')
            .select('*')
            .eq('symbol', symbol)
            .gte('decided_at', start)
            .lte('decided_at', end)
            .order('decided_at', { ascending: true }),
          supabase
            .from('trade_proposals')
            .select('*')
            .eq('symbol', symbol)
            .gte('proposed_at', start)
            .lte('proposed_at', end)
            .order('proposed_at', { ascending: true }),
          api.trades.list({ symbol, limit: 50 }),
        ]);

        if (cancelled) return;

        const events: TimelineEvent[] = [];

        if (decisionsRes.status === 'fulfilled' && !decisionsRes.value.error) {
          for (const d of decisionsRes.value.data ?? []) {
            events.push({
              timestamp: d.decided_at,
              type: 'agent_decision',
              title: `${d.agent_id} → ${String(d.signal).toUpperCase()}`,
              detail: d.reasoning || `confidence ${((d.confidence ?? 0) * 100).toFixed(0)}%`,
              color: d.signal === 'bullish' ? BULLISH : d.signal === 'bearish' ? BEARISH : GRAY,
            });
          }
        }

        if (proposalsRes.status === 'fulfilled' && !proposalsRes.value.error) {
          for (const p of proposalsRes.value.data ?? []) {
            events.push({
              timestamp: p.proposed_at,
              type: 'proposal',
              title: `Consensus updated — trade proposal (${p.status})`,
              detail: `${p.direction} · confidence ${p.confidence_pct?.toFixed(0) ?? '?'}%`,
              color: PRIMARY,
            });
            if (p.decided_at) {
              events.push({
                timestamp: p.decided_at,
                type: 'proposal',
                title: `Proposal ${p.status}`,
                detail: p.human_reason || 'Human/automated decision recorded',
                color: p.status === 'approved' ? BULLISH : p.status === 'rejected' ? BEARISH : AMBER,
              });
            }
          }
        }

        if (tradesRes.status === 'fulfilled') {
          for (const t of tradesRes.value) {
            const opened = new Date(t.opened_at).getTime();
            if (opened >= new Date(start).getTime() && opened <= new Date(end).getTime()) {
              events.push({
                timestamp: t.opened_at,
                type: 'trade_opened',
                title: `Trade executed — ${t.direction} ${t.symbol}`,
                detail: `Filled ${t.filled_price ?? t.entry_price ?? '?'} via ${t.broker}`,
                color: PRIMARY,
              });
            }
            if (t.closed_at) {
              const closed = new Date(t.closed_at).getTime();
              if (closed >= new Date(start).getTime() && closed <= new Date(end).getTime()) {
                events.push({
                  timestamp: t.closed_at,
                  type: 'trade_closed',
                  title: `Trade closed — PnL ${t.pnl_usd != null ? `$${t.pnl_usd.toFixed(2)}` : '?'}`,
                  detail: t.notes || '',
                  color: (t.pnl_usd ?? 0) >= 0 ? BULLISH : BEARISH,
                });
              }
            }
          }
        }

        events.sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());
        setEvents(events);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Failed to reconstruct timeline');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [symbol, windowStart, windowEnd]);

  return (
    <div
      style={{
        background: '#121826',
        border: '1px solid rgba(255,255,255,0.06)',
        borderRadius: 12,
        padding: 16,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
        <span style={{ fontSize: 12, fontWeight: 700, color: '#E2E8F0' }}>Decision Timeline</span>
        <span style={{ fontSize: 10, color: '#475569' }}>reconstructed from agent_decisions / trade_proposals / trades</span>
      </div>

      {loading && <div style={{ fontSize: 12, color: '#475569' }}>Reconstructing timeline...</div>}
      {error && <div style={{ fontSize: 12, color: BEARISH }}>{error}</div>}
      {!loading && !error && events.length === 0 && (
        <div style={{ fontSize: 12, color: '#475569' }}>No agent decisions, proposals, or trades recorded in this window.</div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column' }}>
        {events.map((ev, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, x: -6 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.15, delay: i * 0.02 }}
            style={{ display: 'flex', gap: 10, paddingBottom: i === events.length - 1 ? 0 : 14, position: 'relative' }}
          >
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
              <div style={{ width: 8, height: 8, borderRadius: '50%', background: ev.color, marginTop: 3 }} />
              {i !== events.length - 1 && (
                <div style={{ width: 1, flex: 1, background: 'rgba(255,255,255,0.08)', marginTop: 2 }} />
              )}
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                <span style={{ fontSize: 12, fontWeight: 600, color: '#E2E8F0' }}>{ev.title}</span>
                <span style={{ fontSize: 10, color: '#475569', whiteSpace: 'nowrap' }}>
                  {new Date(ev.timestamp).toLocaleTimeString()}
                </span>
              </div>
              {ev.detail && <div style={{ fontSize: 11, color: '#64748B', marginTop: 1 }}>{ev.detail}</div>}
            </div>
          </motion.div>
        ))}
      </div>
    </div>
  );
}
