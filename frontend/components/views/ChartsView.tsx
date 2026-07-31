'use client';

import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import InstitutionalChart from '@/components/InstitutionalChart';
import ForecastExplainPanel from '@/components/ForecastExplainPanel';
import DecisionTimeline from '@/components/DecisionTimeline';
import TradingViewEmbed, { TradingViewOverlayPanel, OverlaySignal } from '@/components/TradingViewEmbed';
import { api, ForecastHistoryEntry } from '@/lib/api';

/**
 * Phase 5: "the chart becomes the primary workspace." This view now owns
 * symbol/timeframe as the single source of truth (passed into
 * InstitutionalChart, which re-fetches candles + all overlays whenever either
 * changes — see InstitutionalChart's effect comment) rather than each panel
 * keeping its own disconnected state like the old CandlestickMock version did.
 */
export default function ChartsView() {
  const [symbol, setSymbol] = useState('BTC/USDT');
  const [timeframe, setTimeframe] = useState('1h');
  const [explainForecastId, setExplainForecastId] = useState<string | null>(null);
  const [selectedHistoryEntry, setSelectedHistoryEntry] = useState<ForecastHistoryEntry | null>(null);
  const [mode, setMode] = useState<'native' | 'tradingview'>('native');
  const [overlaySignal, setOverlaySignal] = useState<OverlaySignal | null>(null);

  useEffect(() => {
    if (mode !== 'tradingview') return;
    let cancelled = false;
    // Reuses the same risk-assessment source ConsensusPanel/TradeSignalPanel
    // draw from — no new backend endpoint for this overlay.
    api.risk
      .getAssessments({ symbol, limit: 1 })
      .then((rows) => {
        if (cancelled || rows.length === 0) return;
        const r = rows[0];
        setOverlaySignal({
          direction: r.direction,
          entry: r.entry_price,
          stop_loss: r.stop_loss,
          take_profit: r.take_profit,
          confidence: r.consensus_confidence_pct,
        });
      })
      .catch(() => setOverlaySignal(null));
    return () => {
      cancelled = true;
    };
  }, [mode, symbol]);

  async function openExplainFor(forecastId: string) {
    setExplainForecastId(forecastId);
    // Best-effort: pull the matching history entry so the Decision Timeline
    // below has a created_at/expiry_at window to reconstruct against. If the
    // forecast isn't in the recent history page (e.g. a live, unevaluated
    // one), the timeline just falls back to "now" as the window end.
    try {
      const page = await api.forecasts.history({ symbol, timeframe, limit: 200 });
      const match = page.items.find((h) => h.forecast_id === forecastId);
      if (match) setSelectedHistoryEntry(match);
    } catch {
      // non-critical enrichment
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      style={{ padding: 24, paddingBottom: 48 }}
    >
      <div style={{ marginBottom: 24, display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 16 }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 700, color: '#E2E8F0', margin: 0 }}>Live Charts</h1>
          <p style={{ fontSize: 13, color: '#475569', marginTop: 4 }}>
            {mode === 'native'
              ? 'Real candles + AI forecast overlay, prediction history, and click-to-explain agent reasoning — the primary workspace.'
              : "TradingView's own Advanced Chart widget, with the AI's entry/SL/TP/confidence as a floating overlay panel alongside it."}
          </p>
        </div>
        <div style={{ display: 'flex', gap: 6, background: '#121826', border: '1px solid rgba(255,255,255,0.06)', borderRadius: 10, padding: 4, flexShrink: 0 }}>
          {(['native', 'tradingview'] as const).map((m) => (
            <button
              key={m}
              onClick={() => setMode(m)}
              style={{
                padding: '6px 14px', borderRadius: 7, fontSize: 12, fontWeight: 700, cursor: 'pointer',
                border: 'none',
                background: mode === m ? 'rgba(79,124,255,0.15)' : 'transparent',
                color: mode === m ? '#4F7CFF' : '#64748B',
              }}
            >
              {m === 'native' ? 'Native Chart' : 'TradingView'}
            </button>
          ))}
        </div>
      </div>

      {mode === 'native' ? (
        <InstitutionalChart
          symbol={symbol}
          timeframe={timeframe}
          onSymbolChange={setSymbol}
          onTimeframeChange={setTimeframe}
          height={460}
          onMarkerClick={openExplainFor}
          onOverlayForecastClick={openExplainFor}
        />
      ) : (
        <div style={{
          background: '#121826', border: '1px solid rgba(255,255,255,0.06)',
          borderRadius: 12, overflow: 'hidden', position: 'relative',
        }}>
          <div style={{ padding: '12px 16px', borderBottom: '1px solid rgba(255,255,255,0.05)', display: 'flex', gap: 8 }}>
            {['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT'].map((s) => (
              <button
                key={s}
                onClick={() => setSymbol(s)}
                style={{
                  padding: '6px 12px', borderRadius: 7, fontSize: 12, fontWeight: 700, cursor: 'pointer',
                  border: `1px solid ${symbol === s ? 'rgba(79,124,255,0.3)' : 'rgba(255,255,255,0.08)'}`,
                  background: symbol === s ? 'rgba(79,124,255,0.12)' : 'transparent',
                  color: symbol === s ? '#4F7CFF' : '#64748B',
                }}
              >
                {s}
              </button>
            ))}
            {['1m', '5m', '15m', '1h', '4h', '1d'].map((t) => (
              <button
                key={t}
                onClick={() => setTimeframe(t)}
                style={{
                  padding: '6px 12px', borderRadius: 7, fontSize: 12, fontWeight: 700, cursor: 'pointer',
                  border: `1px solid ${timeframe === t ? 'rgba(79,124,255,0.3)' : 'rgba(255,255,255,0.08)'}`,
                  background: timeframe === t ? 'rgba(79,124,255,0.12)' : 'transparent',
                  color: timeframe === t ? '#4F7CFF' : '#64748B',
                }}
              >
                {t}
              </button>
            ))}
          </div>
          <div style={{ position: 'relative' }}>
            <TradingViewEmbed symbol={symbol} timeframe={timeframe} height={460} />
            <TradingViewOverlayPanel signal={overlaySignal} />
          </div>
        </div>
      )}

      <div style={{ marginTop: 16 }}>
        <DecisionTimeline
          symbol={symbol}
          windowStart={selectedHistoryEntry?.created_at ?? new Date(Date.now() - 24 * 3600 * 1000).toISOString()}
          windowEnd={selectedHistoryEntry?.expiry_at ?? new Date().toISOString()}
        />
      </div>

      <ForecastExplainPanel forecastId={explainForecastId} onClose={() => setExplainForecastId(null)} />
    </motion.div>
  );
}
