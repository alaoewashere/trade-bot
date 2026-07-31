'use client';

import React, { useEffect, useRef, useState, useCallback } from 'react';
import {
  createChart,
  IChartApi,
  ISeriesApi,
  IPriceLine,
  CrosshairMode,
  SeriesMarker,
  SeriesMarkerPosition,
  SeriesMarkerShape,
  Time,
} from 'lightweight-charts';
import { api, Candle, ForecastResponse, ForecastHistoryEntry, RiskAssessment } from '@/lib/api';

// Palette already used throughout the codebase (Badge.tsx, ChartsView, ChartSection)
const BULLISH = '#22C55E';
const BEARISH = '#EF4444';
const AMBER = '#F59E0B';
const PRIMARY = '#4F7CFF';
const GRAY = '#64748B';

export const ALL_TIMEFRAMES = ['1m', '5m', '15m', '30m', '1h', '4h', '1d'] as const;
export type Timeframe = (typeof ALL_TIMEFRAMES)[number];

// Phase 5 part B.2: proof-of-pattern multi-timeframe overlay — wiring all 7
// timeframes as simultaneous chart overlays is a much larger visual-design
// problem (7 sets of entry/SL/TP/confidence bands all on one price axis
// becomes unreadable) than fits this phase. These 3 are implemented as
// togglable secondary reference lines; the rest are a documented follow-up.
const SECONDARY_OVERLAY_TIMEFRAMES = ['15m', '4h', '1d'] as const;

export interface InstitutionalChartProps {
  symbol: string;
  timeframe: string;
  onSymbolChange?: (symbol: string) => void;
  onTimeframeChange?: (timeframe: string) => void;
  height?: number;
  /** Renders the built-in symbol/timeframe pill toolbar. ChartSection (dashboard
   * summary) passes false and drives symbol/timeframe from its own fixed props. */
  showToolbar?: boolean;
  /** Full overlay suite (forecast bands, history markers, MTF toggles). ChartSection
   * uses a smaller config (candles + current forecast only, no history markers). */
  showHistoryMarkers?: boolean;
  showMultiTimeframeToggle?: boolean;
  symbols?: string[];
  onMarkerClick?: (forecastId: string) => void;
  onOverlayForecastClick?: (forecastId: string) => void;
}

const DEFAULT_SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT'];

function outcomeColor(outcome: string | null): string {
  if (outcome === 'win') return BULLISH;
  if (outcome === 'loss') return BEARISH;
  if (outcome === 'expired') return AMBER;
  return GRAY; // pending / unknown
}

export default function InstitutionalChart({
  symbol,
  timeframe,
  onSymbolChange,
  onTimeframeChange,
  height = 420,
  showToolbar = true,
  showHistoryMarkers = true,
  showMultiTimeframeToggle = true,
  symbols = DEFAULT_SYMBOLS,
  onMarkerClick,
  onOverlayForecastClick,
}: InstitutionalChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<'Histogram'> | null>(null);
  const priceLinesRef = useRef<IPriceLine[]>([]);
  const historyRef = useRef<ForecastHistoryEntry[]>([]);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currentForecast, setCurrentForecast] = useState<ForecastResponse | null>(null);
  const [riskAssessment, setRiskAssessment] = useState<RiskAssessment | null>(null);
  const [secondaryOverlays, setSecondaryOverlays] = useState<Set<string>>(new Set());
  const [lastPrice, setLastPrice] = useState<number | null>(null);

  // --- Chart lifecycle: created once, resized on container changes ---
  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      layout: {
        background: { color: 'transparent' },
        textColor: '#94A3B8',
        fontFamily: "'JetBrains Mono', monospace",
      },
      grid: {
        vertLines: { color: 'rgba(255,255,255,0.04)' },
        horzLines: { color: 'rgba(255,255,255,0.04)' },
      },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: 'rgba(255,255,255,0.08)' },
      timeScale: { borderColor: 'rgba(255,255,255,0.08)', timeVisible: true, secondsVisible: false },
      autoSize: true,
      height,
    });

    const series = chart.addCandlestickSeries({
      upColor: BULLISH,
      downColor: BEARISH,
      borderVisible: false,
      wickUpColor: BULLISH,
      wickDownColor: BEARISH,
      priceScaleId: 'right',
    });
    series.priceScale().applyOptions({ scaleMargins: { top: 0.08, bottom: 0.24 } });

    const volumeSeries = chart.addHistogramSeries({
      priceFormat: { type: 'volume' },
      priceScaleId: 'volume',
    });
    volumeSeries.priceScale().applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });

    chart.subscribeClick((param) => {
      if (!param.time) return;
      const clickedTime = param.time as number;
      // History markers are placed at each forecast's created_at candle time;
      // lightweight-charts doesn't hit-test markers directly, so we match the
      // clicked bar's time against the nearest forecast within a small window.
      const hit = historyRef.current.find((h) => {
        const t = Math.floor(new Date(h.created_at).getTime() / 1000);
        return Math.abs(t - clickedTime) < 1;
      });
      if (hit) {
        onMarkerClick?.(hit.forecast_id);
      }
    });

    chartRef.current = chart;
    seriesRef.current = series;
    volumeSeriesRef.current = volumeSeries;

    return () => {
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
      volumeSeriesRef.current = null;
      priceLinesRef.current = [];
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const clearPriceLines = useCallback(() => {
    const series = seriesRef.current;
    if (!series) return;
    for (const line of priceLinesRef.current) {
      try {
        series.removePriceLine(line);
      } catch {
        // series/chart already torn down — nothing to clean up
      }
    }
    priceLinesRef.current = [];
  }, []);

  // --- Candles: timeframe/symbol are the single source of truth here; this
  // effect is the only place candles + overlays get re-fetched, so nothing
  // else can let the chart's data drift out of sync with the selector. ---
  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      clearPriceLines();
      try {
        const [candlesRes, forecastRes, riskRes, historyRes] = await Promise.allSettled([
          api.markets.getCandles(symbol, timeframe, 300),
          api.forecasts.getLatest(symbol, timeframe),
          api.risk.getAssessments({ symbol, limit: 1 }),
          showHistoryMarkers
            ? api.forecasts.history({ symbol, timeframe, limit: 200 })
            : Promise.resolve(null),
        ]);

        if (cancelled) return;

        if (candlesRes.status === 'fulfilled') {
          const candles: Candle[] = candlesRes.value.candles;
          const series = seriesRef.current;
          const volSeries = volumeSeriesRef.current;
          if (series) {
            series.setData(
              candles.map((c) => ({
                time: c.time as Time,
                open: c.open,
                high: c.high,
                low: c.low,
                close: c.close,
              }))
            );
          }
          if (volSeries) {
            volSeries.setData(
              candles.map((c) => ({
                time: c.time as Time,
                value: c.volume,
                color: c.close >= c.open ? 'rgba(34,197,94,0.4)' : 'rgba(239,68,68,0.4)',
              }))
            );
          }
          setLastPrice(candles.length ? candles[candles.length - 1].close : null);
          chartRef.current?.timeScale().fitContent();
        } else {
          setError('Could not load candle data — market feed unavailable.');
        }

        setCurrentForecast(forecastRes.status === 'fulfilled' ? forecastRes.value : null);
        setRiskAssessment(
          riskRes.status === 'fulfilled' && riskRes.value.length > 0 ? riskRes.value[0] : null
        );

        if (showHistoryMarkers) {
          const items = historyRes.status === 'fulfilled' && historyRes.value ? historyRes.value.items : [];
          historyRef.current = items;
          drawHistoryMarkers(items);
        }

        drawForecastOverlay(
          forecastRes.status === 'fulfilled' ? forecastRes.value : null,
          riskRes.status === 'fulfilled' && riskRes.value.length > 0 ? riskRes.value[0] : null
        );
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Failed to load chart data');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [symbol, timeframe, showHistoryMarkers]);

  function drawHistoryMarkers(items: ForecastHistoryEntry[]) {
    const series = seriesRef.current;
    if (!series) return;
    const markers: SeriesMarker<Time>[] = items
      .filter((h) => h.price_at_creation > 0)
      .map((h) => ({
        time: Math.floor(new Date(h.created_at).getTime() / 1000) as Time,
        position: (h.direction === 'bearish' ? 'aboveBar' : 'belowBar') as SeriesMarkerPosition,
        color: outcomeColor(h.outcome),
        shape: (h.direction === 'bearish' ? 'arrowDown' : 'arrowUp') as SeriesMarkerShape,
        text: h.outcome ? h.outcome.toUpperCase() : 'PENDING',
      }))
      .sort((a, b) => (a.time as number) - (b.time as number));
    series.setMarkers(markers);
  }

  function drawForecastOverlay(forecast: ForecastResponse | null, risk: RiskAssessment | null) {
    const series = seriesRef.current;
    if (!series) return;
    const lines: IPriceLine[] = [];
    const dirColor = forecast?.direction === 'bearish' ? BEARISH : forecast?.direction === 'bullish' ? BULLISH : GRAY;

    if (forecast && forecast.predicted_low > 0 && forecast.predicted_high > 0) {
      lines.push(
        series.createPriceLine({
          price: forecast.predicted_high,
          color: dirColor,
          lineWidth: 1,
          lineStyle: 3, // dotted — confidence band edge, distinct from hard SL/TP lines
          axisLabelVisible: true,
          title: `Conf.High (${forecast.confidence_pct.toFixed(0)}%)`,
        }),
        series.createPriceLine({
          price: forecast.predicted_low,
          color: dirColor,
          lineWidth: 1,
          lineStyle: 3,
          axisLabelVisible: true,
          title: 'Conf.Low',
        })
      );
    }

    // Entry/SL/TP come from the most recent risk assessment for this symbol —
    // RiskAssessmentResponse only carries a single `take_profit` field (no
    // TP2 in the data model), so we draw exactly one clearly-labeled TP
    // rather than fabricating a second level.
    if (risk) {
      lines.push(
        series.createPriceLine({
          price: risk.entry_price,
          color: PRIMARY,
          lineWidth: 2,
          lineStyle: 0,
          axisLabelVisible: true,
          title: 'Entry',
        }),
        series.createPriceLine({
          price: risk.stop_loss,
          color: BEARISH,
          lineWidth: 2,
          lineStyle: 2, // dashed
          axisLabelVisible: true,
          title: 'Stop Loss',
        }),
        series.createPriceLine({
          price: risk.take_profit,
          color: BULLISH,
          lineWidth: 2,
          lineStyle: 2,
          axisLabelVisible: true,
          title: 'TP1',
        })
      );
    }

    priceLinesRef.current = lines;
  }

  // --- Part B.2: secondary timeframe overlay lines (proof of pattern, 3 TFs) ---
  const secondaryLinesRef = useRef<IPriceLine[]>([]);
  useEffect(() => {
    let cancelled = false;
    async function loadSecondary() {
      const series = seriesRef.current;
      if (!series) return;
      for (const l of secondaryLinesRef.current) {
        try {
          series.removePriceLine(l);
        } catch {
          /* chart torn down */
        }
      }
      secondaryLinesRef.current = [];
      if (secondaryOverlays.size === 0) return;

      try {
        const dashboard = await api.forecasts.getDashboard(symbol);
        if (cancelled) return;
        const newLines: IPriceLine[] = [];
        for (const tf of Array.from(secondaryOverlays)) {
          const entry = dashboard.timeframes.find((e) => e.timeframe === tf && e.forecast_id);
          if (!entry) continue;
          const mid = (entry.predicted_low + entry.predicted_high) / 2;
          if (mid <= 0) continue;
          const color = entry.direction === 'bearish' ? BEARISH : entry.direction === 'bullish' ? BULLISH : GRAY;
          newLines.push(
            series.createPriceLine({
              price: mid,
              color,
              lineWidth: 1,
              lineStyle: 1, // dashed-thin, visually distinct from the main-TF overlay
              axisLabelVisible: true,
              title: `${tf} mid`,
            })
          );
        }
        secondaryLinesRef.current = newLines;
      } catch {
        // best-effort overlay; silently skip if the dashboard call fails
      }
    }
    loadSecondary();
    return () => {
      cancelled = true;
    };
  }, [symbol, timeframe, secondaryOverlays]);

  function toggleSecondary(tf: string) {
    setSecondaryOverlays((prev) => {
      const next = new Set(prev);
      if (next.has(tf)) next.delete(tf);
      else next.add(tf);
      return next;
    });
  }

  return (
    <div className="flex flex-col gap-3">
      {showToolbar && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', gap: 6 }}>
            {symbols.map((s) => (
              <button
                key={s}
                onClick={() => onSymbolChange?.(s)}
                style={{
                  padding: '6px 14px',
                  borderRadius: 8,
                  fontSize: 12,
                  fontWeight: 600,
                  cursor: 'pointer',
                  background: symbol === s ? 'rgba(79,124,255,0.15)' : 'rgba(255,255,255,0.04)',
                  border: `1px solid ${symbol === s ? 'rgba(79,124,255,0.4)' : 'rgba(255,255,255,0.08)'}`,
                  color: symbol === s ? PRIMARY : '#64748B',
                }}
              >
                {s}
              </button>
            ))}
          </div>
          <div style={{ width: 1, height: 24, background: 'rgba(255,255,255,0.07)' }} />
          <div style={{ display: 'flex', gap: 4 }}>
            {ALL_TIMEFRAMES.map((t) => (
              <button
                key={t}
                onClick={() => onTimeframeChange?.(t)}
                style={{
                  padding: '5px 10px',
                  borderRadius: 7,
                  fontSize: 11,
                  fontWeight: 600,
                  cursor: 'pointer',
                  background: timeframe === t ? PRIMARY : 'transparent',
                  border: `1px solid ${timeframe === t ? PRIMARY : 'rgba(255,255,255,0.08)'}`,
                  color: timeframe === t ? '#fff' : '#64748B',
                }}
              >
                {t}
              </button>
            ))}
          </div>
        </div>
      )}

      <div
        style={{
          background: '#121826',
          border: '1px solid rgba(255,255,255,0.06)',
          borderRadius: 12,
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '12px 20px',
            borderBottom: '1px solid rgba(255,255,255,0.05)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 12 }}>
            <span style={{ fontWeight: 700, color: '#E2E8F0', fontSize: 15 }}>{symbol}</span>
            {lastPrice != null && (
              <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 20, fontWeight: 700, color: '#F1F5F9' }}>
                ${lastPrice.toLocaleString('en-US', { maximumFractionDigits: 2 })}
              </span>
            )}
            {currentForecast && (
              <span
                style={{
                  padding: '2px 8px',
                  borderRadius: 6,
                  fontSize: 11,
                  fontWeight: 700,
                  background:
                    currentForecast.direction === 'bullish'
                      ? 'rgba(34,197,94,0.12)'
                      : currentForecast.direction === 'bearish'
                      ? 'rgba(239,68,68,0.12)'
                      : 'rgba(100,116,139,0.12)',
                  color:
                    currentForecast.direction === 'bullish'
                      ? BULLISH
                      : currentForecast.direction === 'bearish'
                      ? BEARISH
                      : GRAY,
                }}
              >
                {currentForecast.direction.toUpperCase()} · {currentForecast.confidence_pct.toFixed(0)}%
              </span>
            )}
          </div>
          {currentForecast && onOverlayForecastClick && (
            <button
              onClick={() => onOverlayForecastClick(currentForecast.forecast_id)}
              style={{
                fontSize: 11,
                fontWeight: 600,
                color: PRIMARY,
                background: 'rgba(79,124,255,0.08)',
                border: '1px solid rgba(79,124,255,0.2)',
                borderRadius: 7,
                padding: '5px 10px',
                cursor: 'pointer',
              }}
            >
              Explain this forecast
            </button>
          )}
        </div>

        <div ref={containerRef} style={{ width: '100%', height }} />

        {error && (
          <div style={{ padding: '8px 20px', fontSize: 12, color: BEARISH }}>{error}</div>
        )}
        {loading && !error && (
          <div style={{ padding: '8px 20px', fontSize: 12, color: '#475569' }}>Loading market data...</div>
        )}

        {showMultiTimeframeToggle && (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              padding: '10px 20px',
              borderTop: '1px solid rgba(255,255,255,0.05)',
            }}
          >
            <span style={{ fontSize: 10, color: '#475569', fontWeight: 700, letterSpacing: '0.06em' }}>
              MTF OVERLAY (proof-of-pattern: 3 of 7 timeframes)
            </span>
            {SECONDARY_OVERLAY_TIMEFRAMES.map((tf) => (
              <button
                key={tf}
                onClick={() => toggleSecondary(tf)}
                style={{
                  fontSize: 11,
                  fontWeight: 600,
                  padding: '3px 9px',
                  borderRadius: 6,
                  cursor: 'pointer',
                  background: secondaryOverlays.has(tf) ? 'rgba(79,124,255,0.15)' : 'rgba(255,255,255,0.04)',
                  border: `1px solid ${secondaryOverlays.has(tf) ? 'rgba(79,124,255,0.4)' : 'rgba(255,255,255,0.08)'}`,
                  color: secondaryOverlays.has(tf) ? PRIMARY : '#64748B',
                }}
              >
                {tf}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
