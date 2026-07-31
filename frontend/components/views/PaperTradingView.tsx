'use client';

import React, { useEffect, useState, useCallback } from 'react';
import { motion } from 'framer-motion';
import { api, OpenPosition, TradeRecord, TradeStats } from '@/lib/api';
import { useTradeProposals, TradeProposal } from '@/lib/hooks/useTradeProposals';

function fmtUsd(n: number | null | undefined): string {
  if (n == null) return '—';
  const sign = n >= 0 ? '+' : '-';
  return `${sign}$${Math.abs(n).toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}

function fmtPrice(n: number | null | undefined): string {
  if (n == null) return '—';
  return `$${n.toLocaleString(undefined, { maximumFractionDigits: n >= 100 ? 2 : 4 })}`;
}

/**
 * Real "Paper Trading" hub — replaces the previous fully-mocked component.
 * Sources: GET /trades/open + GET /trades/stats (paper-broker trades are
 * the only trades in this system, since there's no live broker wired up —
 * see settings.is_live), and the pending trade_proposals feed for the
 * "Execute on Paper" signal card.
 */
export default function PaperTradingView() {
  const [open, setOpen] = useState<OpenPosition[]>([]);
  const [history, setHistory] = useState<TradeRecord[]>([]);
  const [stats, setStats] = useState<TradeStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [executing, setExecuting] = useState(false);
  const [executeError, setExecuteError] = useState<string | null>(null);
  const [executeSuccess, setExecuteSuccess] = useState<string | null>(null);

  const { proposals } = useTradeProposals();
  const primaryProposal: TradeProposal | undefined = proposals[0];

  const load = useCallback(async () => {
    try {
      const [openPositions, closedHistory, tradeStats] = await Promise.all([
        api.trades.listOpen(),
        api.trades.list({ status: 'closed', limit: 25 }),
        api.trades.stats(),
      ]);
      setOpen(openPositions);
      setHistory(closedHistory);
      setStats(tradeStats);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load paper trading data');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, 15_000);
    return () => clearInterval(id);
  }, [load]);

  const handleExecute = async () => {
    if (!primaryProposal) return;
    const risk = (primaryProposal.risk_assessment as Record<string, unknown> | null) ?? {};
    const entry = Number(risk.entry_price ?? 0);
    const stopLoss = Number(risk.stop_loss ?? 0);
    const takeProfit = Number(risk.take_profit ?? 0);
    const quantity = Number(risk.position_size_units ?? 0.01) || 0.01;

    if (!stopLoss || !takeProfit) {
      setExecuteError('Risk assessment for this signal has no stop-loss/take-profit — cannot execute.');
      return;
    }

    setExecuting(true);
    setExecuteError(null);
    setExecuteSuccess(null);
    try {
      const result = await api.trades.executePaper({
        symbol: primaryProposal.symbol,
        direction: primaryProposal.direction === 'SHORT' ? 'SHORT' : 'LONG',
        quantity,
        entry_price: entry || null,
        stop_loss: stopLoss,
        take_profit: takeProfit,
        consensus_direction: primaryProposal.direction,
        consensus_confidence_pct: primaryProposal.confidence_pct ?? undefined,
        proposal_id: primaryProposal.id,
        notes: 'Executed via Trading Execution hub',
      });
      setExecuteSuccess(`Filled ${result.symbol} @ ${fmtPrice(result.filled_price)}`);
      await load();
    } catch (err) {
      setExecuteError(err instanceof Error ? err.message : 'Execution failed');
    } finally {
      setExecuting(false);
    }
  };

  const account = stats
    ? [
        { label: 'Equity', value: fmtPrice(stats.equity_usd), color: '#F1F5F9' },
        { label: 'Realized P&L', value: fmtUsd(stats.realized_pnl_usd), color: stats.realized_pnl_usd >= 0 ? '#22C55E' : '#EF4444' },
        { label: 'Unrealized P&L', value: fmtUsd(stats.unrealized_pnl_usd), color: stats.unrealized_pnl_usd >= 0 ? '#22C55E' : '#EF4444' },
        { label: 'Win Rate', value: `${stats.win_rate_pct.toFixed(1)}%`, color: '#4F7CFF' },
      ]
    : [];

  const secondaryStats = stats
    ? [
        { label: 'Avg R/R', value: stats.avg_risk_reward.toFixed(2) },
        { label: 'Profit Factor', value: Number.isFinite(stats.profit_factor) ? stats.profit_factor.toFixed(2) : '∞' },
        { label: 'Max Drawdown', value: `${stats.max_drawdown_pct.toFixed(1)}%` },
        { label: 'Sharpe', value: stats.sharpe_ratio != null ? stats.sharpe_ratio.toFixed(2) : '—' },
        { label: 'Expectancy', value: fmtUsd(stats.expectancy_usd) },
      ]
    : [];

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      style={{ padding: 24, paddingBottom: 48 }}
    >
      <div style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <h1 style={{ fontSize: 20, fontWeight: 700, color: '#E2E8F0', margin: 0 }}>Paper Trading</h1>
          <span style={{
            padding: '3px 10px', borderRadius: 6, fontSize: 10, fontWeight: 800,
            background: 'rgba(34,197,94,0.12)', color: '#22C55E',
            letterSpacing: '0.1em', border: '1px solid rgba(34,197,94,0.2)',
          }}>SIMULATION</span>
        </div>
        <p style={{ fontSize: 13, color: '#475569', marginTop: 4 }}>
          Real Redis-persisted simulated fills via brokers/paper_broker.py — market-data-gated, never fabricated.
        </p>
      </div>

      {error && (
        <div style={{ marginBottom: 16, padding: 12, borderRadius: 8, background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)', color: '#EF4444', fontSize: 12 }}>
          {error}
        </div>
      )}

      {/* Execute-on-paper signal card */}
      <div style={{
        background: '#121826', border: '1px solid rgba(255,255,255,0.06)',
        borderRadius: 12, padding: 20, marginBottom: 20,
      }}>
        <div style={{ fontSize: 14, fontWeight: 700, color: '#E2E8F0', marginBottom: 12 }}>Execute AI Signal</div>
        {!primaryProposal ? (
          <div style={{ fontSize: 13, color: '#475569' }}>No pending AI trade signal to execute right now.</div>
        ) : (
          <>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 12, marginBottom: 14 }}>
              {[
                { label: 'Symbol', value: primaryProposal.symbol },
                { label: 'Direction', value: primaryProposal.direction },
                { label: 'Confidence', value: primaryProposal.confidence_pct != null ? `${Math.round(primaryProposal.confidence_pct)}%` : '—' },
                { label: 'Consensus', value: primaryProposal.consensus_score != null ? `${Math.round(primaryProposal.consensus_score * 100)}%` : '—' },
                { label: 'Status', value: primaryProposal.status },
              ].map((c) => (
                <div key={c.label} style={{ background: 'rgba(255,255,255,0.03)', borderRadius: 8, padding: '10px 12px' }}>
                  <div style={{ fontSize: 9, color: '#475569', fontWeight: 700, letterSpacing: '0.08em', marginBottom: 4 }}>{c.label.toUpperCase()}</div>
                  <div style={{ fontSize: 13, fontWeight: 700, color: '#E2E8F0' }}>{c.value}</div>
                </div>
              ))}
            </div>
            <button
              onClick={handleExecute}
              disabled={executing}
              style={{
                padding: '10px 22px', borderRadius: 8, fontSize: 13, fontWeight: 700,
                cursor: executing ? 'wait' : 'pointer', border: 'none', color: '#fff',
                background: 'linear-gradient(135deg,#4F7CFF,#818CF8)', opacity: executing ? 0.7 : 1,
                boxShadow: '0 4px 16px rgba(79,124,255,0.4)',
              }}
            >
              {executing ? 'Executing…' : 'Execute on Paper'}
            </button>
            {executeError && <div style={{ marginTop: 10, fontSize: 12, color: '#EF4444' }}>{executeError}</div>}
            {executeSuccess && <div style={{ marginTop: 10, fontSize: 12, color: '#22C55E' }}>{executeSuccess}</div>}
          </>
        )}
      </div>

      {/* Account summary */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14, marginBottom: 14 }}>
        {account.map((a, i) => (
          <motion.div key={a.label}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.05, duration: 0.2 }}
            style={{
              background: '#121826', border: '1px solid rgba(255,255,255,0.06)',
              borderRadius: 12, padding: '16px 18px',
            }}>
            <div style={{ fontSize: 10, color: '#475569', fontWeight: 700, letterSpacing: '0.1em', marginBottom: 6 }}>{a.label.toUpperCase()}</div>
            <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 22, fontWeight: 800, color: a.color }}>{a.value}</div>
          </motion.div>
        ))}
      </div>

      {stats && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 14, marginBottom: 24 }}>
          {secondaryStats.map((s) => (
            <div key={s.label} style={{ background: '#121826', border: '1px solid rgba(255,255,255,0.06)', borderRadius: 12, padding: '12px 14px' }}>
              <div style={{ fontSize: 9, color: '#475569', fontWeight: 700, letterSpacing: '0.08em', marginBottom: 4 }}>{s.label.toUpperCase()}</div>
              <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 14, fontWeight: 700, color: '#E2E8F0' }}>{s.value}</div>
            </div>
          ))}
        </div>
      )}

      {/* Open trades */}
      <div style={{
        background: '#121826', border: '1px solid rgba(255,255,255,0.06)',
        borderRadius: 12, overflow: 'hidden', marginBottom: 20,
      }}>
        <div style={{ padding: '14px 20px', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
          <span style={{ fontSize: 14, fontWeight: 700, color: '#E2E8F0' }}>Open Paper Trades</span>
        </div>
        {!loading && open.length === 0 ? (
          <div style={{ padding: 20, fontSize: 13, color: '#475569' }}>No open paper positions.</div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: 'rgba(255,255,255,0.02)' }}>
                {['Symbol', 'Dir', 'Qty', 'Entry', 'Current', 'Stop', 'Target', 'P&L', '%'].map(h => (
                  <th key={h} style={{ padding: '9px 14px', textAlign: 'left', fontSize: 10, fontWeight: 700, color: '#475569', letterSpacing: '0.1em', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {open.map((t, i) => (
                <tr key={t.trade_id} style={{ background: i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.015)' }}>
                  <td style={{ padding: '10px 14px', fontWeight: 700, color: '#E2E8F0', fontSize: 13 }}>{t.symbol}</td>
                  <td style={{ padding: '10px 14px' }}>
                    <span style={{ padding: '2px 7px', borderRadius: 5, fontSize: 10, fontWeight: 700, background: t.direction === 'LONG' ? 'rgba(34,197,94,0.12)' : 'rgba(239,68,68,0.12)', color: t.direction === 'LONG' ? '#22C55E' : '#EF4444' }}>{t.direction}</span>
                  </td>
                  <td style={{ padding: '10px 14px', fontSize: 11, color: '#94A3B8', fontFamily: "'JetBrains Mono', monospace" }}>{t.quantity}</td>
                  <td style={{ padding: '10px 14px', fontSize: 11, color: '#94A3B8', fontFamily: "'JetBrains Mono', monospace" }}>{fmtPrice(t.entry_price)}</td>
                  <td style={{ padding: '10px 14px', fontSize: 11, color: '#F1F5F9', fontFamily: "'JetBrains Mono', monospace" }}>{fmtPrice(t.current_price)}</td>
                  <td style={{ padding: '10px 14px', fontSize: 11, color: '#EF4444', fontFamily: "'JetBrains Mono', monospace" }}>{fmtPrice(t.stop_loss)}</td>
                  <td style={{ padding: '10px 14px', fontSize: 11, color: '#22C55E', fontFamily: "'JetBrains Mono', monospace" }}>{fmtPrice(t.take_profit_levels[0])}</td>
                  <td style={{ padding: '10px 14px', fontSize: 11, fontFamily: "'JetBrains Mono', monospace", fontWeight: 700, color: (t.unrealised_pnl_usd ?? 0) >= 0 ? '#22C55E' : '#EF4444' }}>{fmtUsd(t.unrealised_pnl_usd)}</td>
                  <td style={{ padding: '10px 14px', fontSize: 11, fontFamily: "'JetBrains Mono', monospace", fontWeight: 700, color: (t.unrealised_pnl_pct ?? 0) >= 0 ? '#22C55E' : '#EF4444' }}>{t.unrealised_pnl_pct != null ? `${t.unrealised_pnl_pct >= 0 ? '+' : ''}${t.unrealised_pnl_pct.toFixed(1)}%` : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Trade history */}
      <div style={{
        background: '#121826', border: '1px solid rgba(255,255,255,0.06)',
        borderRadius: 12, overflow: 'hidden',
      }}>
        <div style={{ padding: '14px 20px', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
          <span style={{ fontSize: 14, fontWeight: 700, color: '#E2E8F0' }}>Paper Trade History</span>
        </div>
        {!loading && history.length === 0 ? (
          <div style={{ padding: 20, fontSize: 13, color: '#475569' }}>No closed paper trades yet.</div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: 'rgba(255,255,255,0.02)' }}>
                {['Closed', 'Symbol', 'Dir', 'Qty', 'Entry', 'P&L'].map(h => (
                  <th key={h} style={{ padding: '9px 14px', textAlign: 'left', fontSize: 10, fontWeight: 700, color: '#475569', letterSpacing: '0.1em', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {history.map((t, i) => (
                <tr key={t.trade_id} style={{ background: i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.015)' }}>
                  <td style={{ padding: '10px 14px', fontSize: 11, color: '#475569', fontFamily: "'JetBrains Mono', monospace" }}>{t.closed_at?.slice(0, 16).replace('T', ' ') ?? '—'}</td>
                  <td style={{ padding: '10px 14px', fontWeight: 700, color: '#E2E8F0', fontSize: 13 }}>{t.symbol}</td>
                  <td style={{ padding: '10px 14px' }}>
                    <span style={{ padding: '2px 7px', borderRadius: 5, fontSize: 10, fontWeight: 700, background: t.direction === 'LONG' ? 'rgba(34,197,94,0.12)' : 'rgba(239,68,68,0.12)', color: t.direction === 'LONG' ? '#22C55E' : '#EF4444' }}>{t.direction}</span>
                  </td>
                  <td style={{ padding: '10px 14px', fontSize: 11, color: '#94A3B8', fontFamily: "'JetBrains Mono', monospace" }}>{t.quantity}</td>
                  <td style={{ padding: '10px 14px', fontSize: 11, color: '#94A3B8', fontFamily: "'JetBrains Mono', monospace" }}>{fmtPrice(t.filled_price)}</td>
                  <td style={{ padding: '10px 14px', fontSize: 12, fontFamily: "'JetBrains Mono', monospace", fontWeight: 700, color: (t.pnl_usd ?? 0) >= 0 ? '#22C55E' : '#EF4444' }}>{fmtUsd(t.pnl_usd)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </motion.div>
  );
}
