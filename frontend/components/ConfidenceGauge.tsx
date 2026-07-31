'use client';

import React, { useEffect, useRef } from 'react';

interface ConfidenceGaugeProps {
  value: number;
  size?: number;
  label?: string;
  strokeWidth?: number;
}

export default function ConfidenceGauge({
  value,
  size = 80,
  label = 'Confidence',
  strokeWidth = 6,
}: ConfidenceGaugeProps) {
  const circleRef = useRef<SVGCircleElement>(null);

  const clampedValue = Math.max(0, Math.min(100, value));
  const color =
    clampedValue >= 70 ? '#22C55E' : clampedValue >= 50 ? '#F59E0B' : '#EF4444';

  const center = size / 2;
  const radius = center - strokeWidth * 1.5;
  const circumference = 2 * Math.PI * radius;
  // Arc goes from -135deg to 135deg (270deg total)
  const arcFraction = 0.75;
  const offset = circumference * (1 - arcFraction * (clampedValue / 100));

  useEffect(() => {
    if (circleRef.current) {
      circleRef.current.style.strokeDashoffset = `${offset}`;
    }
  }, [offset]);

  return (
    <div className="flex flex-col items-center gap-1">
      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        style={{ transform: 'rotate(135deg)' }}
      >
        {/* Track */}
        <circle
          cx={center}
          cy={center}
          r={radius}
          fill="none"
          stroke="rgba(255,255,255,0.06)"
          strokeWidth={strokeWidth}
          strokeDasharray={`${circumference * arcFraction} ${circumference * (1 - arcFraction)}`}
          strokeLinecap="round"
        />
        {/* Fill */}
        <circle
          ref={circleRef}
          cx={center}
          cy={center}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={strokeWidth}
          strokeDasharray={`${circumference * arcFraction} ${circumference * (1 - arcFraction)}`}
          strokeDashoffset={offset}
          strokeLinecap="round"
          style={{ transition: 'stroke-dashoffset 1s ease-out' }}
        />
      </svg>
      <div
        className="flex flex-col items-center -mt-12 mb-4"
        style={{ color }}
      >
        <span className="font-mono font-bold text-lg leading-none">{clampedValue}%</span>
        <span className="text-[10px] text-[#6B6B7A] mt-0.5">{label}</span>
      </div>
    </div>
  );
}
