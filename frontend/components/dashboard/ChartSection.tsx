'use client';

import React from 'react';
import InstitutionalChart from '@/components/InstitutionalChart';

/**
 * Dashboard summary tile. Phase 5: replaced the Math.random()-driven
 * generateCandles/MiniChart mock with the same real InstitutionalChart used
 * as the primary chart workspace (ChartsView), just in a smaller/simpler
 * configuration — no symbol/timeframe toolbar, no history markers, no MTF
 * toggle, since this is a glanceable summary tile, not the analysis surface.
 */
export default function ChartSection() {
  return (
    <InstitutionalChart
      symbol="BTC/USDT"
      timeframe="1h"
      showToolbar={false}
      showHistoryMarkers={false}
      showMultiTimeframeToggle={false}
      height={280}
    />
  );
}
