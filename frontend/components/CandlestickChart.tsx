'use client';

import React from 'react';
import InstitutionalChart from '@/components/InstitutionalChart';

interface ChartProps {
  symbol?: string;
  timeframe?: string;
}

/**
 * Deprecated: this component used to hand-roll SVG candles from
 * Math.random() (generateMockPrices) — fake OHLCV actively lies to the user
 * in an "institutional decision platform", so Phase 5 removed the mock and
 * pointed this at the real chart. Nothing in the codebase imports this
 * component anymore (verified via grep); kept only so any external/future
 * import of `CandlestickChart` still resolves to real data instead of a 404.
 * Prefer importing InstitutionalChart directly for new code.
 */
export default function CandlestickChart({ symbol = 'BTC/USDT', timeframe = '1h' }: ChartProps) {
  return (
    <InstitutionalChart
      symbol={symbol}
      timeframe={timeframe}
      showToolbar={false}
      showHistoryMarkers={false}
      showMultiTimeframeToggle={false}
      height={240}
    />
  );
}
