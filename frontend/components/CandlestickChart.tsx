'use client';

import React, { useEffect, useRef, useState } from 'react';

interface PricePoint {
  t: number;
  o: number;
  h: number;
  l: number;
  c: number;
  v: number;
}

function generateMockPrices(basePrice: number, count: number): PricePoint[] {
  const points: PricePoint[] = [];
  let price = basePrice;
  const now = Date.now();
  for (let i = count - 1; i >= 0; i--) {
    const change = (Math.random() - 0.48) * price * 0.003;
    const open = price;
    price = Math.max(price * 0.97, price + change);
    const high = Math.max(open, price) * (1 + Math.random() * 0.002);
    const low  = Math.min(open, price) * (1 - Math.random() * 0.002);
    const vol  = 500 + Math.random() * 2000;
    points.push({ t: now - i * 60000, o: open, h: high, l: low, c: price, v: vol });
  }
  return points;
}

interface ChartProps {
  currentPrice?: number;
  changePct?: number;
}

export default function CandlestickChart({ currentPrice = 67428.5, changePct = 1.87 }: ChartProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [prices, setPrices] = useState<PricePoint[]>([]);
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);
  const [dims, setDims] = useState({ w: 600, h: 240 });

  useEffect(() => {
    setPrices(generateMockPrices(currentPrice, 50));
  }, [currentPrice]);

  useEffect(() => {
    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setDims({ w: entry.contentRect.width, h: entry.contentRect.height });
      }
    });
    if (svgRef.current?.parentElement) {
      ro.observe(svgRef.current.parentElement);
    }
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    const interval = setInterval(() => {
      setPrices((prev) => {
        if (prev.length === 0) return prev;
        const last = prev[prev.length - 1];
        const change = (Math.random() - 0.48) * last.c * 0.003;
        const newPrice = Math.max(last.c * 0.97, last.c + change);
        const newPt: PricePoint = {
          t: Date.now(),
          o: last.c,
          h: Math.max(last.c, newPrice) * (1 + Math.random() * 0.001),
          l: Math.min(last.c, newPrice) * (1 - Math.random() * 0.001),
          c: newPrice,
          v: 500 + Math.random() * 2000,
        };
        return [...prev.slice(1), newPt];
      });
    }, 3000);
    return () => clearInterval(interval);
  }, []);

  if (prices.length === 0) {
    return (
      <div
        className="w-full rounded-xl border skeleton"
        style={{ height: 240, borderColor: 'var(--bg-border)' }}
      />
    );
  }

  const PAD = { top: 16, right: 64, bottom: 40, left: 12 };
  const W = dims.w;
  const H = dims.h;
  const chartW = W - PAD.left - PAD.right;
  const chartH = H - PAD.top - PAD.bottom;
  const volH = 32;

  const closes = prices.map((p) => p.c);
  const highs = prices.map((p) => p.h);
  const lows = prices.map((p) => p.l);
  const minP = Math.min(...lows) * 0.9995;
  const maxP = Math.max(...highs) * 1.0005;
  const priceRange = maxP - minP;

  const toX = (i: number) => PAD.left + (i / (prices.length - 1)) * chartW;
  const toY = (p: number) => PAD.top + (1 - (p - minP) / priceRange) * (chartH - volH - 8);

  // Area path
  const areaPoints = prices.map((p, i) => `${toX(i)},${toY(p.c)}`).join(' ');
  const linePath =
    prices
      .map((p, i) => `${i === 0 ? 'M' : 'L'}${toX(i).toFixed(1)},${toY(p.c).toFixed(1)}`)
      .join(' ');

  const lastClose = prices[prices.length - 1].c;
  const firstClose = prices[0].c;
  const isUp = lastClose >= firstClose;
  const fillColor = isUp ? '#22C55E' : '#EF4444';

  const areaPath =
    linePath +
    ` L${toX(prices.length - 1).toFixed(1)},${(PAD.top + chartH - volH - 8).toFixed(1)}` +
    ` L${PAD.left.toFixed(1)},${(PAD.top + chartH - volH - 8).toFixed(1)} Z`;

  // VWAP approximation
  const vwapPts = prices.map((p, i) => {
    const slice = prices.slice(0, i + 1);
    const vwap = slice.reduce((s, x) => s + x.c * x.v, 0) / slice.reduce((s, x) => s + x.v, 0);
    return `${i === 0 ? 'M' : 'L'}${toX(i).toFixed(1)},${toY(vwap).toFixed(1)}`;
  });

  // Volume bars
  const maxVol = Math.max(...prices.map((p) => p.v));
  const volBase = PAD.top + chartH;
  const volTop = PAD.top + chartH - volH;

  // Axis price labels
  const axisLabels: number[] = [];
  const steps = 4;
  for (let i = 0; i <= steps; i++) {
    axisLabels.push(minP + (priceRange * i) / steps);
  }

  // Hover point
  const hoverPt = hoverIdx !== null ? prices[hoverIdx] : null;

  return (
    <div className="relative w-full" style={{ height: H }}>
      <svg
        ref={svgRef}
        width={W}
        height={H}
        className="w-full h-full"
        onMouseMove={(e) => {
          const rect = (e.currentTarget as SVGSVGElement).getBoundingClientRect();
          const x = e.clientX - rect.left - PAD.left;
          const idx = Math.round((x / chartW) * (prices.length - 1));
          setHoverIdx(Math.max(0, Math.min(prices.length - 1, idx)));
        }}
        onMouseLeave={() => setHoverIdx(null)}
      >
        <defs>
          <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={fillColor} stopOpacity="0.18" />
            <stop offset="100%" stopColor={fillColor} stopOpacity="0" />
          </linearGradient>
          <linearGradient id="volGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={fillColor} stopOpacity="0.5" />
            <stop offset="100%" stopColor={fillColor} stopOpacity="0.1" />
          </linearGradient>
        </defs>

        {/* Grid lines */}
        {axisLabels.map((price, i) => {
          const y = toY(price);
          return (
            <g key={i}>
              <line
                x1={PAD.left}
                y1={y}
                x2={W - PAD.right}
                y2={y}
                stroke="rgba(255,255,255,0.04)"
                strokeWidth={1}
              />
              <text
                x={W - PAD.right + 6}
                y={y + 4}
                fill="#6B6B7A"
                fontSize={9}
                fontFamily="JetBrains Mono, monospace"
              >
                {price.toFixed(0)}
              </text>
            </g>
          );
        })}

        {/* Area fill */}
        <path d={areaPath} fill="url(#areaGrad)" />

        {/* Line */}
        <path
          d={linePath}
          fill="none"
          stroke={fillColor}
          strokeWidth={1.5}
          strokeLinecap="round"
          strokeLinejoin="round"
          className="draw-path"
        />

        {/* VWAP */}
        <path
          d={vwapPts.join(' ')}
          fill="none"
          stroke="#3B82F6"
          strokeWidth={1}
          strokeDasharray="3 3"
          opacity={0.6}
        />

        {/* Volume bars */}
        {prices.map((p, i) => {
          const barH = ((p.v / maxVol) * volH) * 0.85;
          const barW = Math.max(1, chartW / prices.length - 1);
          return (
            <rect
              key={i}
              x={toX(i) - barW / 2}
              y={volBase - barH}
              width={barW}
              height={barH}
              fill={p.c >= p.o ? '#22C55E' : '#EF4444'}
              opacity={0.3}
            />
          );
        })}

        {/* Current price line */}
        <line
          x1={PAD.left}
          y1={toY(lastClose)}
          x2={W - PAD.right}
          y2={toY(lastClose)}
          stroke={fillColor}
          strokeWidth={1}
          strokeDasharray="4 2"
          opacity={0.6}
        />

        {/* Hover crosshair */}
        {hoverIdx !== null && hoverPt && (
          <>
            <line
              x1={toX(hoverIdx)}
              y1={PAD.top}
              x2={toX(hoverIdx)}
              y2={PAD.top + chartH}
              stroke="rgba(255,255,255,0.12)"
              strokeWidth={1}
            />
            <circle
              cx={toX(hoverIdx)}
              cy={toY(hoverPt.c)}
              r={4}
              fill={fillColor}
              stroke="var(--bg-base)"
              strokeWidth={2}
            />
            {/* Tooltip */}
            <g transform={`translate(${Math.min(toX(hoverIdx) + 8, W - PAD.right - 100)},${PAD.top + 8})`}>
              <rect rx={4} ry={4} width={96} height={70} fill="#16161D" stroke="rgba(255,255,255,0.1)" strokeWidth={1} />
              <text x={8} y={16} fill="#6B6B7A" fontSize={9} fontFamily="JetBrains Mono, monospace">
                {new Date(hoverPt.t).toLocaleTimeString('en-US', { hour12: false })}
              </text>
              <text x={8} y={30} fill="#FFFFFF" fontSize={9} fontFamily="JetBrains Mono, monospace">
                O: {hoverPt.o.toFixed(0)}
              </text>
              <text x={8} y={42} fill="#22C55E" fontSize={9} fontFamily="JetBrains Mono, monospace">
                H: {hoverPt.h.toFixed(0)}
              </text>
              <text x={8} y={54} fill="#EF4444" fontSize={9} fontFamily="JetBrains Mono, monospace">
                L: {hoverPt.l.toFixed(0)}
              </text>
              <text x={8} y={66} fill={hoverPt.c >= hoverPt.o ? '#22C55E' : '#EF4444'} fontSize={9} fontFamily="JetBrains Mono, monospace">
                C: {hoverPt.c.toFixed(0)}
              </text>
            </g>
          </>
        )}

        {/* Labels */}
        <text x={PAD.left + 4} y={PAD.top + 14} fill="#6B6B7A" fontSize={9} fontFamily="JetBrains Mono, monospace">
          VWAP
        </text>
        <circle cx={PAD.left + 36} cy={PAD.top + 10} r={3} fill="#3B82F6" />

        {/* Axis time labels */}
        {[0, 12, 24, 36, 49].map((i) => (
          <text
            key={i}
            x={toX(i)}
            y={H - 4}
            fill="#6B6B7A"
            fontSize={8}
            fontFamily="JetBrains Mono, monospace"
            textAnchor="middle"
          >
            {new Date(prices[i]?.t ?? 0).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false })}
          </text>
        ))}
      </svg>

      {/* Chart header overlaid */}
      <div className="absolute top-2 left-3 flex items-center gap-3">
        <span className="text-xs font-medium text-[#9B9BAA]">BTC/USDT · 1m</span>
        <span
          className="text-xs font-mono font-semibold"
          style={{ color: isUp ? '#22C55E' : '#EF4444' }}
        >
          ${lastClose.toFixed(2)}
        </span>
        <span
          className="text-[10px] px-1.5 py-0.5 rounded font-medium"
          style={{
            color: isUp ? '#22C55E' : '#EF4444',
            background: isUp ? 'rgba(34,197,94,0.1)' : 'rgba(239,68,68,0.1)',
          }}
        >
          {isUp ? '+' : ''}{changePct.toFixed(2)}%
        </span>
      </div>
    </div>
  );
}
