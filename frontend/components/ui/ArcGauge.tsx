'use client';

import React from 'react';

interface ArcGaugeProps {
  value: number; // 0–100
  size?: number;
  color?: string;
  label?: string;
  strokeWidth?: number;
}

export default function ArcGauge({
  value,
  size = 48,
  color = '#4F7CFF',
  label,
  strokeWidth = 4,
}: ArcGaugeProps) {
  const radius = (size - strokeWidth) / 2;
  const cx = size / 2;
  const cy = size / 2;

  // Arc spans 240 degrees (from 150° to 390°/30°)
  const startAngle = 150;
  const totalAngle = 240;
  const endAngle = startAngle + totalAngle * (value / 100);

  const toRad = (deg: number) => (deg * Math.PI) / 180;

  const arcPath = (start: number, end: number) => {
    const s = {
      x: cx + radius * Math.cos(toRad(start)),
      y: cy + radius * Math.sin(toRad(start)),
    };
    const e = {
      x: cx + radius * Math.cos(toRad(end)),
      y: cy + radius * Math.sin(toRad(end)),
    };
    const largeArc = end - start > 180 ? 1 : 0;
    return `M ${s.x} ${s.y} A ${radius} ${radius} 0 ${largeArc} 1 ${e.x} ${e.y}`;
  };

  return (
    <div className="relative flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} style={{ transform: 'rotate(0deg)' }}>
        {/* Track */}
        <path
          d={arcPath(startAngle, startAngle + totalAngle)}
          fill="none"
          stroke="rgba(255,255,255,0.08)"
          strokeWidth={strokeWidth}
          strokeLinecap="round"
        />
        {/* Value arc */}
        {value > 0 && (
          <path
            d={arcPath(startAngle, endAngle)}
            fill="none"
            stroke={color}
            strokeWidth={strokeWidth}
            strokeLinecap="round"
          />
        )}
      </svg>
      {/* Center label */}
      {label !== undefined && (
        <span
          className="absolute font-mono font-semibold"
          style={{ fontSize: size * 0.22, color }}
        >
          {label}
        </span>
      )}
    </div>
  );
}
