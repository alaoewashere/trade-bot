'use client';

import React, { useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Search, ArrowRight, Clock, Zap } from 'lucide-react';

interface SearchModalProps {
  open: boolean;
  onClose: () => void;
}

const QUICK_ACTIONS = [
  { label: 'Go to Dashboard', shortcut: '⌘ 1' },
  { label: 'View AI Agents', shortcut: '⌘ 2' },
  { label: 'Open Portfolio', shortcut: '⌘ 3' },
  { label: 'Settings', shortcut: '⌘ ,' },
];

const RECENT = [
  'BTC analysis',
  'agent performance',
  'risk settings',
  'portfolio overview',
];

export default function SearchModal({ open, onClose }: SearchModalProps) {
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open && inputRef.current) {
      setTimeout(() => inputRef.current?.focus(), 80);
    }
  }, [open]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.15 }}
          onClick={onClose}
          style={{
            position: 'fixed', inset: 0, zIndex: 9999,
            background: 'rgba(0,0,0,0.7)',
            backdropFilter: 'blur(8px)',
            WebkitBackdropFilter: 'blur(8px)',
            display: 'flex', alignItems: 'flex-start', justifyContent: 'center',
            paddingTop: 100,
          }}
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: -10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: -10 }}
            transition={{ duration: 0.18 }}
            onClick={e => e.stopPropagation()}
            style={{
              width: 600, maxWidth: '90vw',
              background: '#121826',
              border: '1px solid rgba(255,255,255,0.1)',
              borderRadius: 16,
              boxShadow: '0 24px 80px rgba(0,0,0,0.8), 0 0 0 1px rgba(79,124,255,0.15)',
              overflow: 'hidden',
            }}
          >
            {/* Input row */}
            <div style={{
              display: 'flex', alignItems: 'center', gap: 12,
              padding: '14px 16px',
              borderBottom: '1px solid rgba(255,255,255,0.06)',
            }}>
              <Search size={18} color="#4F7CFF" />
              <input
                ref={inputRef}
                placeholder="Search agents, signals, markets…"
                style={{
                  flex: 1, background: 'none', border: 'none', outline: 'none',
                  fontSize: 15, color: '#F1F5F9',
                  fontFamily: "'Inter', sans-serif",
                }}
              />
              <kbd style={{
                padding: '3px 8px', borderRadius: 6, fontSize: 11,
                fontFamily: 'monospace', fontWeight: 600, color: '#475569',
                background: 'rgba(255,255,255,0.05)',
                border: '1px solid rgba(255,255,255,0.09)',
              }}>ESC</kbd>
            </div>

            {/* Quick actions */}
            <div style={{ padding: '12px 16px 4px' }}>
              <div style={{
                fontSize: 10, fontWeight: 700, letterSpacing: '0.14em',
                color: '#475569', marginBottom: 8,
              }}>QUICK ACTIONS</div>
              {QUICK_ACTIONS.map((a, i) => (
                <div key={i} style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  padding: '9px 10px', borderRadius: 8, cursor: 'pointer',
                  transition: 'background 0.12s',
                }}
                  onMouseEnter={e => (e.currentTarget.style.background = 'rgba(79,124,255,0.08)')}
                  onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <Zap size={14} color="#4F7CFF" />
                    <span style={{ fontSize: 13, color: '#E2E8F0', fontWeight: 500 }}>{a.label}</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <kbd style={{
                      padding: '2px 7px', borderRadius: 5, fontSize: 10,
                      fontFamily: 'monospace', color: '#475569',
                      background: 'rgba(255,255,255,0.05)',
                      border: '1px solid rgba(255,255,255,0.09)',
                    }}>{a.shortcut}</kbd>
                    <ArrowRight size={12} color="#334155" />
                  </div>
                </div>
              ))}
            </div>

            {/* Recent */}
            <div style={{ padding: '8px 16px 16px' }}>
              <div style={{
                fontSize: 10, fontWeight: 700, letterSpacing: '0.14em',
                color: '#475569', marginBottom: 8,
              }}>RECENT SEARCHES</div>
              {RECENT.map((r, i) => (
                <div key={i} style={{
                  display: 'flex', alignItems: 'center', gap: 10,
                  padding: '9px 10px', borderRadius: 8, cursor: 'pointer',
                  transition: 'background 0.12s',
                }}
                  onMouseEnter={e => (e.currentTarget.style.background = 'rgba(255,255,255,0.04)')}
                  onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                >
                  <Clock size={13} color="#475569" />
                  <span style={{ fontSize: 13, color: '#94A3B8' }}>{r}</span>
                </div>
              ))}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
