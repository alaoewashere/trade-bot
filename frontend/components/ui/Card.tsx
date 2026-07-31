'use client';

import React from 'react';
import clsx from 'clsx';

interface CardProps {
  children: React.ReactNode;
  className?: string;
  glow?: 'primary' | 'success' | 'danger' | false;
  hover?: boolean;
  style?: React.CSSProperties;
}

const glowStyles: Record<string, React.CSSProperties> = {
  primary: {
    boxShadow: '0 0 0 1px rgba(79,124,255,0.2), 0 8px 32px rgba(79,124,255,0.08)',
  },
  success: {
    boxShadow: '0 0 0 1px rgba(34,197,94,0.2), 0 8px 32px rgba(34,197,94,0.08)',
  },
  danger: {
    boxShadow: '0 0 0 1px rgba(239,68,68,0.2), 0 8px 32px rgba(239,68,68,0.08)',
  },
};

export default function Card({ children, className, glow = false, hover = false, style }: CardProps) {
  return (
    <div
      className={clsx(
        'rounded-xl border',
        hover && 'transition-all duration-200 hover:-translate-y-0.5',
        className
      )}
      style={{
        background: '#121826',
        borderColor: 'rgba(255,255,255,0.06)',
        ...(glow ? glowStyles[glow] : {}),
        ...(hover
          ? { cursor: 'pointer' }
          : {}),
        ...style,
      }}
    >
      {children}
    </div>
  );
}
