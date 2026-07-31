'use client';

import React from 'react';
import clsx from 'clsx';

type BadgeVariant = 'success' | 'danger' | 'warning' | 'primary' | 'ghost';

interface BadgeProps {
  children: React.ReactNode;
  variant?: BadgeVariant;
  className?: string;
  dot?: boolean;
  pulse?: boolean;
}

const variantStyles: Record<BadgeVariant, React.CSSProperties> = {
  success: {
    background: 'rgba(34,197,94,0.12)',
    border: '1px solid rgba(34,197,94,0.2)',
    color: '#22C55E',
  },
  danger: {
    background: 'rgba(239,68,68,0.12)',
    border: '1px solid rgba(239,68,68,0.2)',
    color: '#EF4444',
  },
  warning: {
    background: 'rgba(245,158,11,0.12)',
    border: '1px solid rgba(245,158,11,0.2)',
    color: '#F59E0B',
  },
  primary: {
    background: 'rgba(79,124,255,0.12)',
    border: '1px solid rgba(79,124,255,0.2)',
    color: '#4F7CFF',
  },
  ghost: {
    background: 'rgba(255,255,255,0.06)',
    border: '1px solid rgba(255,255,255,0.1)',
    color: '#94A3B8',
  },
};

const dotColors: Record<BadgeVariant, string> = {
  success: '#22C55E',
  danger: '#EF4444',
  warning: '#F59E0B',
  primary: '#4F7CFF',
  ghost: '#94A3B8',
};

export default function Badge({ children, variant = 'ghost', className, dot = false, pulse = false }: BadgeProps) {
  return (
    <span
      className={clsx('inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold', className)}
      style={variantStyles[variant]}
    >
      {dot && (
        <span
          className={clsx('w-1.5 h-1.5 rounded-full shrink-0', pulse && 'animate-live-blink')}
          style={{ background: dotColors[variant] }}
        />
      )}
      {children}
    </span>
  );
}
