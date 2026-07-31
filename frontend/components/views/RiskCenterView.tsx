'use client';

import React, { useEffect, useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import { api, RiskAssessment, PortfolioHeatmap, VaRSummary } from '@/lib/api';

const CATEGORY_COLORS: Record<string, { bg: string; text: string }> = {
  very_low: { bg: 'rgba(34,197,94,0.14)', text: '#22C55E' },
  low: { bg: 'rgba(34,197,94,0.10)', text: '#4ADE80' },
  medium: { bg: 'rgba(245,158,11,0.12)', text: '#F59E0B' },
  high: { bg: 'rgba(239,68,68,0.12)', text: '#EF4444' },
  extreme: { bg: 'rgba(239,68,68,0.22)', text: '#F87171' },
};

const card: React.CSSProperties = {
  background: '#121826',
  border: '1px solid rgba(255,255,255,0.06)',
  borderRadius: 12,
};

// ---------------------------------------------------------------------------
// Client-side position size calculator (no backend call — pure arithmetic)
// ---------------------------------------------------------------------------
function PositionSizeCalculator() {
  const [equity, setEquity] = useState(10000);
  const [riskPct, setRiskPct] = useState(1);
  const [entry, setEntry] = useState(65000);
  const [stop, setStop] = useState(63700);

  const { riskUsd, stopDistance, stopPct, positionUnits, positionUsd } = useMemo(() => {
    const riskUsd = equity * (riskPct / 100);
    const stopDistance = Math.abs(entry - stop);
    const stopPct = entry > 0 ? (stopDistance / entry) * 100 : 0;
    const positionUnits = stopDistance > 0 ? riskUsd / stopDistance : 0;
    const positionUsd = positionUnits * entry;
    return { riskUsd, stopDistance, stopPct, positionUnits, positionUsd };
  }, [equity, riskPct, entry, stop]);

  const inputStyle: React.CSSProperties = {
    width: '100%', padding: '8px 10px', borderRadius: 8, fontSize: 13,
    background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)',
    color: '#E2E8F0', fontFamily: "'JetBrains Mono', monospace",
  };
  const label: React.CSSProperties = { fontSize: 11, color: '#64748B', marginBottom: 6, fontWeight: 600 };

  return (
    <div style={{ ...card, padding: 20 }}>
      <div style={{ fontSize: 14, fontWeight: 700, color: '#E2E8F0', marginBottom: 16 }}>Position Size Calculator</div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 14, marginBottom: 18 }}>
        <div>
          <div style={label}>ACCOUNT EQUITY (USD)</div>
          <input style={inputStyle} type="number" value={equity} onChange={e => setEquity(Number(e.target.value))} />
        </div>
        <div>
          <div style={label}>RISK % PER TRADE</div>
          <input style={inputStyle} type="number" step="0.1" value={riskPct} onChange={e => setRiskPct(Number(e.target.value))} />
        </div>
        <div>
          <div style={label}>ENTRY PRICE</div>
          <input style={inputStyle} type="number" value={entry} onChange={e => setEntry(Number(e.target.value))} />
        </div>
        <div>
          <div style={label}>STOP LOSS PRICE</div>
          <input style={inputStyle} type="number" value={stop} onChange={e => setStop(Number(e.target.value))} />
        </div>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
        {[
          { l: 'Risk (USD)', v: `$${riskUsd.toFixed(2)}` },
          { l: 'Stop Distance', v: `${stopPct.toFixed(2)}%` },
          { l: 'Position Size', v: `${positionUnits.toFixed(6)} units` },
          { l: 'Notional (USD)', v: `$${positionUsd.toFixed(2)}` },
        ].map(x => (
          <div key={x.l} style={{ background: 'rgba(79,124,255,0.06)', border: '1px solid rgba(79,124,255,0.15)', borderRadius: 8, padding: '10px 12px' }}>
            <div style={{ fontSize: 10, color: '#475569', fontWeight: 700, marginBottom: 4 }}>{x.l.toUpperCase()}</div>
            <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 14, fontWeight: 700, color: '#4F7CFF' }}>{x.v}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function RiskCenterView() {
  const [assessments, setAssessments] = useState<RiskAssessment[]>([]);
  const [heatmap, setHeatmap] = useState<PortfolioHeatmap | null>(null);
  const [varSummary, setVarSummary] = useState<VaRSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [a, h, v] = await Promise.all([
          api.risk.getAssessments({ limit: 50 }),
          api.risk.getHeatmap(),
          api.risk.getVar(),
        ]);
        if (!cancelled) {
          setAssessments(a);
          setHeatmap(h);
          setVarSummary(v);
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Failed to load risk data');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  // symbol x risk_category grid
  const heatmapGrid = useMemo(() => {
    const symbols = Array.from(new Set(assessments.map(a => a.symbol)));
    const categories = ['very_low', 'low', 'medium', 'high', 'extreme'];
    return { symbols, categories };
  }, [assessments]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      style={{ padding: 24, paddingBottom: 48 }}
    >
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 20, fontWeight: 700, color: '#E2E8F0', margin: 0 }}>Risk Management Center</h1>
        <p style={{ fontSize: 13, color: '#475569', marginTop: 4 }}>Portfolio risk exposure, VaR/CVaR, and per-trade risk breakdown</p>
      </div>

      {error && (
        <div style={{ ...card, padding: 16, marginBottom: 20, borderColor: 'rgba(239,68,68,0.3)', color: '#F87171', fontSize: 13 }}>
          Could not load live risk data ({error}). Showing calculator only.
        </div>
      )}

      {/* KPIs */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14, marginBottom: 24 }}>
        {[
          { label: 'Portfolio Heat', value: heatmap ? `${heatmap.total_heat_pct.toFixed(1)}%` : '—', color: '#F59E0B' },
          { label: 'VaR (95%)', value: varSummary ? `$${varSummary.portfolio_var_95_usd.toFixed(0)}` : '—', color: '#EF4444' },
          { label: 'CVaR / Expected Shortfall', value: assessments.length ? `$${assessments.reduce((s, a) => s + a.cvar_95, 0).toFixed(0)}` : '—', color: '#EF4444' },
          { label: 'Equity', value: heatmap ? `$${heatmap.equity_usd.toLocaleString()}` : '—', color: '#4F7CFF' },
        ].map((k, i) => (
          <motion.div key={k.label}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.04, duration: 0.2 }}
            style={{ ...card, padding: '16px 18px' }}>
            <div style={{ fontSize: 10, color: '#475569', fontWeight: 700, letterSpacing: '0.1em', marginBottom: 6 }}>{k.label.toUpperCase()}</div>
            <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 20, fontWeight: 800, color: k.color }}>{k.value}</div>
          </motion.div>
        ))}
      </div>

      <div style={{ marginBottom: 24 }}>
        <PositionSizeCalculator />
      </div>

      {/* Risk heatmap: symbol x risk_category */}
      <div style={{ ...card, overflow: 'hidden', marginBottom: 24 }}>
        <div style={{ padding: '14px 20px', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
          <span style={{ fontSize: 14, fontWeight: 700, color: '#E2E8F0' }}>Risk Heatmap — Symbol × Category</span>
        </div>
        {heatmapGrid.symbols.length === 0 ? (
          <div style={{ padding: 20, fontSize: 13, color: '#475569' }}>{loading ? 'Loading...' : 'No risk assessments yet.'}</div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
              <thead>
                <tr>
                  <th style={{ textAlign: 'left', padding: '10px 20px', color: '#475569' }}>Symbol</th>
                  {heatmapGrid.categories.map(c => (
                    <th key={c} style={{ textAlign: 'center', padding: '10px 12px', color: '#475569', textTransform: 'capitalize' }}>{c.replace('_', ' ')}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {heatmapGrid.symbols.map(sym => {
                  const rowAssessments = assessments.filter(a => a.symbol === sym);
                  return (
                    <tr key={sym} style={{ borderTop: '1px solid rgba(255,255,255,0.04)' }}>
                      <td style={{ padding: '10px 20px', fontWeight: 700, color: '#E2E8F0' }}>{sym}</td>
                      {heatmapGrid.categories.map(cat => {
                        const count = rowAssessments.filter(a => a.risk_category === cat).length;
                        const colors = CATEGORY_COLORS[cat];
                        return (
                          <td key={cat} style={{ padding: '8px 12px', textAlign: 'center' }}>
                            {count > 0 ? (
                              <span style={{ padding: '3px 10px', borderRadius: 6, background: colors.bg, color: colors.text, fontWeight: 700 }}>{count}</span>
                            ) : (
                              <span style={{ color: '#1E293B' }}>—</span>
                            )}
                          </td>
                        );
                      })}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Per-trade risk breakdown */}
      <div style={{ ...card, overflow: 'hidden' }}>
        <div style={{ padding: '14px 20px', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
          <span style={{ fontSize: 14, fontWeight: 700, color: '#E2E8F0' }}>Per-Trade Risk Breakdown</span>
        </div>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
            <thead>
              <tr>
                {['Symbol', 'Entry', 'Stop', 'TP', 'R:R', 'Max Loss', 'Max Profit', 'Win Prob', 'EV', 'Kelly', 'Category'].map(h => (
                  <th key={h} style={{ textAlign: 'left', padding: '10px 14px', color: '#475569', whiteSpace: 'nowrap' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {assessments.map(a => {
                const colors = CATEGORY_COLORS[a.risk_category] ?? CATEGORY_COLORS.medium;
                const maxProfit = a.max_risk_usd * a.risk_reward;
                return (
                  <tr key={a.assessment_id} style={{ borderTop: '1px solid rgba(255,255,255,0.04)' }}>
                    <td style={{ padding: '10px 14px', fontWeight: 700, color: '#E2E8F0' }}>{a.symbol}</td>
                    <td style={{ padding: '10px 14px', fontFamily: "'JetBrains Mono', monospace", color: '#94A3B8' }}>{a.entry_price.toFixed(2)}</td>
                    <td style={{ padding: '10px 14px', fontFamily: "'JetBrains Mono', monospace", color: '#EF4444' }}>{a.stop_loss.toFixed(2)}</td>
                    <td style={{ padding: '10px 14px', fontFamily: "'JetBrains Mono', monospace", color: '#22C55E' }}>{a.take_profit.toFixed(2)}</td>
                    <td style={{ padding: '10px 14px', fontFamily: "'JetBrains Mono', monospace", color: '#94A3B8' }}>{a.risk_reward.toFixed(2)}</td>
                    <td style={{ padding: '10px 14px', fontFamily: "'JetBrains Mono', monospace", color: '#EF4444' }}>${a.max_risk_usd.toFixed(2)}</td>
                    <td style={{ padding: '10px 14px', fontFamily: "'JetBrains Mono', monospace", color: '#22C55E' }}>${maxProfit.toFixed(2)}</td>
                    <td style={{ padding: '10px 14px', fontFamily: "'JetBrains Mono', monospace", color: '#94A3B8' }}>{a.consensus_confidence_pct != null ? `${a.consensus_confidence_pct.toFixed(0)}%` : '—'}</td>
                    <td style={{ padding: '10px 14px', fontFamily: "'JetBrains Mono', monospace", color: a.expected_value_usd >= 0 ? '#22C55E' : '#EF4444' }}>${a.expected_value_usd.toFixed(2)}</td>
                    <td style={{ padding: '10px 14px', fontFamily: "'JetBrains Mono', monospace", color: '#4F7CFF' }}>{(a.kelly_fraction * 100).toFixed(1)}%</td>
                    <td style={{ padding: '10px 14px' }}>
                      <span style={{ padding: '3px 10px', borderRadius: 6, background: colors.bg, color: colors.text, fontWeight: 700, textTransform: 'capitalize' }}>
                        {a.risk_category.replace('_', ' ')}
                      </span>
                    </td>
                  </tr>
                );
              })}
              {assessments.length === 0 && !loading && (
                <tr><td colSpan={11} style={{ padding: 20, color: '#475569' }}>No risk assessments recorded yet.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </motion.div>
  );
}
