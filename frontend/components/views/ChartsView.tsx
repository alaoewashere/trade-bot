'use client';

import React, { useState } from 'react';
import { motion } from 'framer-motion';
import InstitutionalChart from '@/components/InstitutionalChart';
import ForecastExplainPanel from '@/components/ForecastExplainPanel';
import DecisionTimeline from '@/components/DecisionTimeline';
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
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 20, fontWeight: 700, color: '#E2E8F0', margin: 0 }}>Live Charts</h1>
        <p style={{ fontSize: 13, color: '#475569', marginTop: 4 }}>
          Real candles + AI forecast overlay, prediction history, and click-to-explain agent reasoning — the primary workspace.
        </p>
      </div>

      <InstitutionalChart
        symbol={symbol}
        timeframe={timeframe}
        onSymbolChange={setSymbol}
        onTimeframeChange={setTimeframe}
        height={460}
        onMarkerClick={openExplainFor}
        onOverlayForecastClick={openExplainFor}
      />

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
