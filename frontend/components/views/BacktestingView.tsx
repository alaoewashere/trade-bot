'use client';

import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { api, BacktestRunDetail, BacktestTradeSample } from '@/lib/api';

const SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT'];
const TIMEFRAMES = ['15m', '1h', '4h', '1d'];
// Labels only — the forecasts table this backtest replays has no strategy
// taxonomy (it's symbol/timeframe based, scored by an ensemble of models).
// The selection is stored on the run for reference but does not filter or
// derive the replayed results. See api/routers/backtest.py module docstring.
const STRATEGIES = ['Momentum Breakout', 'Mean Reversion', 'Trend Following', 'Volatility Arbitrage'];

function StyledSelect({ options, value, onChange }: { options: string[]; value: string; onChange: (v: string) => void }) {
  return (
    <select
      value={value}
      onChange={e => onChange(e.target.value)}
      style={{
        background: '#1a2235', border: '1px solid rgba(255,255,255,0.1)',
        borderRadius: 8, padding: '8px 12px', fontSize: 13, color: '#E2E8F0',
        cursor: 'pointer', outline: 'none', minWidth: 160,
      }}
    >
      {options.map(o => <option key={o} value={o}>{o}</option>)}
    </select>
  );
}

function StyledInput({ type = 'text', value, onChange, label }: { type?: string; value: string; onChange: (v: string) => void; label: string }) {
  return (
    <div>
      <div style={{ fontSize: 10, color: '#475569', fontWeight: 700, marginBottom: 6, letterSpacing: '0.1em' }}>{label}</div>
      <input
        type={type}
        value={value}
        onChange={e => onChange(e.target.value)}
        style={{
          background: '#1a2235', border: '1px solid rgba(255,255,255,0.1)',
          borderRadius: 8, padding: '8px 12px', fontSize: 13, color: '#E2E8F0',
          outline: 'none', width: '100%',
        }}
      />
    </div>
  );
}

function fmtUsd(n: number): string {
  const sign = n >= 0 ? '+' : '-';
  return `${sign}$${Math.abs(n).toFixed(0)}`;
}

export default function BacktestingView() {
  const [symbol, setSymbol] = useState(SYMBOLS[0]);
  const [timeframe, setTimeframe] = useState(TIMEFRAMES[2]);
  const [strategy, setStrategy] = useState(STRATEGIES[0]);
  const [startDate, setStartDate] = useState('2026-01-01');
  const [endDate, setEndDate] = useState('2026-07-31');

  const [running, setRunning] = useState(false);
  const [run, setRun] = useState<BacktestRunDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  const runBacktest = async () => {
    setRunning(true);
    setError(null);
    try {
      const result = await api.backtest.run({
        symbol: symbol.replace('/', ''),
        timeframe,
        strategy,
        date_range_start: new Date(startDate).toISOString(),
        date_range_end: new Date(endDate).toISOString(),
      });
      setRun(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Backtest run failed');
      setRun(null);
    } finally {
      setRunning(false);
    }
  };

  const results = run?.results;
  const kpis = results
    ? [
        { label: 'Total Return', value: `${results.total_return_pct >= 0 ? '+' : ''}${results.total_return_pct.toFixed(1)}%`, color: results.total_return_pct >= 0 ? '#22C55E' : '#EF4444' },
        { label: 'Win Rate', value: `${results.win_rate_pct.toFixed(1)}%`, color: '#22C55E' },
        { label: 'Max Drawdown', value: `-${results.max_drawdown_pct.toFixed(1)}%`, color: '#EF4444' },
        { label: 'Total Trades', value: String(results.num_trades), color: '#4F7CFF' },
      ]
    : [];

  const trades: BacktestTradeSample[] = [];
  if (results?.best_trade) trades.push(results.best_trade);
  if (results?.worst_trade && results.worst_trade.forecast_id !== results.best_trade?.forecast_id) {
    trades.push(results.worst_trade);
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      style={{ padding: 24, paddingBottom: 48 }}
    >
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 20, fontWeight: 700, color: '#E2E8F0', margin: 0 }}>Strategy Backtesting</h1>
        <p style={{ fontSize: 13, color: '#475569', marginTop: 4 }}>
          Replays historical AI forecasts against their recorded outcomes over a date range
        </p>
      </div>

      {/* Config panel */}
      <div style={{
        background: '#121826', border: '1px solid rgba(255,255,255,0.06)',
        borderRadius: 12, padding: 20, marginBottom: 20,
      }}>
        <div style={{ fontSize: 14, fontWeight: 700, color: '#E2E8F0', marginBottom: 16 }}>Configuration</div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 16, marginBottom: 16 }}>
          <div>
            <div style={{ fontSize: 10, color: '#475569', fontWeight: 700, marginBottom: 6, letterSpacing: '0.1em' }}>SYMBOL</div>
            <StyledSelect options={SYMBOLS} value={symbol} onChange={setSymbol} />
          </div>
          <div>
            <div style={{ fontSize: 10, color: '#475569', fontWeight: 700, marginBottom: 6, letterSpacing: '0.1em' }}>TIMEFRAME</div>
            <StyledSelect options={TIMEFRAMES} value={timeframe} onChange={setTimeframe} />
          </div>
          <div>
            <div style={{ fontSize: 10, color: '#475569', fontWeight: 700, marginBottom: 6, letterSpacing: '0.1em' }}>STRATEGY (LABEL)</div>
            <StyledSelect options={STRATEGIES} value={strategy} onChange={setStrategy} />
          </div>
          <StyledInput label="START DATE" value={startDate} onChange={setStartDate} type="date" />
          <StyledInput label="END DATE" value={endDate} onChange={setEndDate} type="date" />
        </div>
        <button
          onClick={runBacktest}
          disabled={running}
          style={{
            padding: '10px 24px', borderRadius: 8, fontSize: 13, fontWeight: 700, cursor: running ? 'wait' : 'pointer',
            background: 'linear-gradient(135deg,#4F7CFF,#818CF8)',
            border: 'none', color: '#fff', opacity: running ? 0.7 : 1,
            boxShadow: '0 4px 16px rgba(79,124,255,0.4)',
          }}>{running ? 'Running…' : 'Run Backtest'}</button>
        {error && <div style={{ marginTop: 12, fontSize: 12, color: '#EF4444' }}>{error}</div>}
        {results?.note && (
          <div style={{ marginTop: 12, fontSize: 12, color: '#F59E0B' }}>{results.note}</div>
        )}
      </div>

      {!run && !running && (
        <div style={{
          background: '#121826', border: '1px solid rgba(255,255,255,0.06)', borderRadius: 12,
          padding: 40, textAlign: 'center', color: '#475569', fontSize: 13,
        }}>
          Configure a run above and click &ldquo;Run Backtest&rdquo; to replay historical forecasts.
        </div>
      )}

      {results && (
        <>
          {/* Results KPIs */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14, marginBottom: 20 }}>
            {kpis.map((k, i) => (
              <motion.div key={k.label}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.05, duration: 0.2 }}
                style={{
                  background: '#121826', border: '1px solid rgba(255,255,255,0.06)',
                  borderRadius: 12, padding: '16px 18px',
                }}>
                <div style={{ fontSize: 10, color: '#475569', fontWeight: 700, letterSpacing: '0.1em', marginBottom: 6 }}>{k.label.toUpperCase()}</div>
                <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 24, fontWeight: 800, color: k.color }}>{k.value}</div>
              </motion.div>
            ))}
          </div>

          {/* Streaks + profit factor row */}
          <div style={{
            display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14, marginBottom: 20,
          }}>
            <div style={{ background: '#121826', border: '1px solid rgba(255,255,255,0.06)', borderRadius: 12, padding: '14px 18px' }}>
              <div style={{ fontSize: 10, color: '#475569', fontWeight: 700, letterSpacing: '0.1em', marginBottom: 6 }}>PROFIT FACTOR</div>
              <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 18, fontWeight: 700, color: '#E2E8F0' }}>
                {Number.isFinite(results.profit_factor) ? results.profit_factor.toFixed(2) : '∞'}
              </div>
            </div>
            <div style={{ background: '#121826', border: '1px solid rgba(255,255,255,0.06)', borderRadius: 12, padding: '14px 18px' }}>
              <div style={{ fontSize: 10, color: '#475569', fontWeight: 700, letterSpacing: '0.1em', marginBottom: 6 }}>AVG TRADE</div>
              <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 18, fontWeight: 700, color: results.avg_trade_pnl_usd >= 0 ? '#22C55E' : '#EF4444' }}>
                {fmtUsd(results.avg_trade_pnl_usd)}
              </div>
            </div>
            <div style={{ background: '#121826', border: '1px solid rgba(255,255,255,0.06)', borderRadius: 12, padding: '14px 18px' }}>
              <div style={{ fontSize: 10, color: '#475569', fontWeight: 700, letterSpacing: '0.1em', marginBottom: 6 }}>WIN STREAK</div>
              <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 18, fontWeight: 700, color: '#22C55E' }}>{results.longest_winning_streak}</div>
            </div>
            <div style={{ background: '#121826', border: '1px solid rgba(255,255,255,0.06)', borderRadius: 12, padding: '14px 18px' }}>
              <div style={{ fontSize: 10, color: '#475569', fontWeight: 700, letterSpacing: '0.1em', marginBottom: 6 }}>LOSS STREAK</div>
              <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 18, fontWeight: 700, color: '#EF4444' }}>{results.longest_losing_streak}</div>
            </div>
          </div>

          {/* Monthly heatmap */}
          {results.monthly_heatmap.length > 0 && (
            <div style={{
              background: '#121826', border: '1px solid rgba(255,255,255,0.06)',
              borderRadius: 12, padding: 20, marginBottom: 20,
            }}>
              <div style={{ fontSize: 14, fontWeight: 700, color: '#E2E8F0', marginBottom: 16 }}>Monthly Heatmap</div>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                {results.monthly_heatmap.map((m) => (
                  <div key={m.month} style={{
                    padding: '10px 14px', borderRadius: 8,
                    background: m.pnl_usd >= 0 ? 'rgba(34,197,94,0.12)' : 'rgba(239,68,68,0.12)',
                    border: `1px solid ${m.pnl_usd >= 0 ? 'rgba(34,197,94,0.3)' : 'rgba(239,68,68,0.3)'}`,
                    minWidth: 90,
                  }}>
                    <div style={{ fontSize: 10, color: '#475569', fontWeight: 700 }}>{m.month}</div>
                    <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 13, fontWeight: 700, color: m.pnl_usd >= 0 ? '#22C55E' : '#EF4444' }}>
                      {fmtUsd(m.pnl_usd)}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Trade distribution */}
          {results.trade_distribution.length > 0 && (
            <div style={{
              background: '#121826', border: '1px solid rgba(255,255,255,0.06)',
              borderRadius: 12, padding: 20, marginBottom: 20,
            }}>
              <div style={{ fontSize: 14, fontWeight: 700, color: '#E2E8F0', marginBottom: 16 }}>Trade Distribution</div>
              <div style={{ display: 'grid', gridTemplateColumns: `repeat(${results.trade_distribution.length}, 1fr)`, gap: 8 }}>
                {results.trade_distribution.map((b) => {
                  const maxCount = Math.max(1, ...results.trade_distribution.map((x) => x.count));
                  const barH = (b.count / maxCount) * 70;
                  return (
                    <div key={b.bucket} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6 }}>
                      <div style={{ fontSize: 11, fontWeight: 700, color: '#94A3B8' }}>{b.count}</div>
                      <div style={{ width: '100%', height: `${barH}px`, minHeight: 4, borderRadius: 4, background: 'rgba(79,124,255,0.4)', border: '1px solid rgba(79,124,255,0.3)' }} />
                      <div style={{ fontSize: 9, color: '#475569', fontWeight: 600, textAlign: 'center' }}>{b.bucket}</div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Best / worst trade */}
          <div style={{
            background: '#121826', border: '1px solid rgba(255,255,255,0.06)',
            borderRadius: 12, overflow: 'hidden',
          }}>
            <div style={{ padding: '14px 20px', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
              <span style={{ fontSize: 14, fontWeight: 700, color: '#E2E8F0' }}>Best / Worst Replayed Trade</span>
            </div>
            {trades.length === 0 ? (
              <div style={{ padding: 20, fontSize: 13, color: '#475569' }}>No trades were generated in this window.</div>
            ) : (
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ background: 'rgba(255,255,255,0.02)' }}>
                    {['Closed', 'Dir', 'Entry', 'Exit', 'Return', 'P&L'].map(h => (
                      <th key={h} style={{ padding: '9px 16px', textAlign: 'left', fontSize: 10, fontWeight: 700, color: '#475569', letterSpacing: '0.1em', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {trades.map((t, i) => (
                    <tr key={t.forecast_id} style={{ background: i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.015)' }}>
                      <td style={{ padding: '10px 16px', fontSize: 11, color: '#475569', fontFamily: "'JetBrains Mono', monospace" }}>{t.closed_at?.slice(0, 10) ?? '—'}</td>
                      <td style={{ padding: '10px 16px' }}>
                        <span style={{ padding: '2px 7px', borderRadius: 5, fontSize: 10, fontWeight: 700, background: t.direction === 'LONG' ? 'rgba(34,197,94,0.12)' : 'rgba(239,68,68,0.12)', color: t.direction === 'LONG' ? '#22C55E' : '#EF4444' }}>{t.direction}</span>
                      </td>
                      <td style={{ padding: '10px 16px', fontSize: 11, color: '#94A3B8', fontFamily: "'JetBrains Mono', monospace" }}>${t.entry_price.toFixed(2)}</td>
                      <td style={{ padding: '10px 16px', fontSize: 11, color: '#94A3B8', fontFamily: "'JetBrains Mono', monospace" }}>${t.exit_price.toFixed(2)}</td>
                      <td style={{ padding: '10px 16px', fontSize: 11, color: t.return_pct >= 0 ? '#22C55E' : '#EF4444', fontFamily: "'JetBrains Mono', monospace" }}>{t.return_pct >= 0 ? '+' : ''}{t.return_pct.toFixed(2)}%</td>
                      <td style={{ padding: '10px 16px', fontSize: 12, fontFamily: "'JetBrains Mono', monospace", fontWeight: 700, color: t.pnl_usd >= 0 ? '#22C55E' : '#EF4444' }}>{fmtUsd(t.pnl_usd)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </>
      )}
    </motion.div>
  );
}
