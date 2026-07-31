'use client';

import React, { useMemo, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Copy, Download, ExternalLink, Check } from 'lucide-react';
import { generatePineScript, pineScriptFilename, tradingViewChartUrl, PineSignalInput } from '@/lib/pineGenerator';

interface PineStrategyModalProps {
  open: boolean;
  onClose: () => void;
  signal: PineSignalInput | null;
}

/**
 * "AI -> Pine Strategy" surface (Phase 7 scope item C). Renders the
 * generated Pine v5 script and offers Copy / Download / Open-in-TradingView
 * — the last one only deep-links to a TradingView chart URL, it cannot
 * auto-inject the script (no such API exists on TradingView's free tier).
 */
export default function PineStrategyModal({ open, onClose, signal }: PineStrategyModalProps) {
  const [copied, setCopied] = useState(false);

  const script = useMemo(() => (signal ? generatePineScript(signal) : ''), [signal]);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(script);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      // clipboard API unavailable — user can still select+copy from the code block
    }
  };

  const handleDownload = () => {
    if (!signal) return;
    const blob = new Blob([script], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = pineScriptFilename(signal.symbol);
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <AnimatePresence>
      {open && signal && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.15 }}
          onClick={onClose}
          style={{
            position: 'fixed', inset: 0, zIndex: 200,
            background: 'rgba(4,6,12,0.72)', backdropFilter: 'blur(4px)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24,
          }}
        >
          <motion.div
            initial={{ opacity: 0, y: 12, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 12, scale: 0.98 }}
            transition={{ duration: 0.18 }}
            onClick={(e) => e.stopPropagation()}
            style={{
              width: '100%', maxWidth: 680, maxHeight: '85vh',
              background: '#121826', border: '1px solid rgba(255,255,255,0.08)',
              borderRadius: 14, display: 'flex', flexDirection: 'column',
              boxShadow: '0 24px 64px rgba(0,0,0,0.5)', overflow: 'hidden',
            }}
          >
            {/* Header */}
            <div style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              padding: '16px 20px', borderBottom: '1px solid rgba(255,255,255,0.06)',
            }}>
              <div>
                <div style={{ fontSize: 15, fontWeight: 700, color: '#E2E8F0' }}>AI → Pine Strategy</div>
                <div style={{ fontSize: 12, color: '#475569', marginTop: 2 }}>
                  {signal.symbol} · {signal.direction} · Pine Script v5
                </div>
              </div>
              <button onClick={onClose} style={{
                width: 30, height: 30, borderRadius: 8, display: 'flex', alignItems: 'center',
                justifyContent: 'center', background: 'rgba(255,255,255,0.05)', border: 'none',
                color: '#94A3B8', cursor: 'pointer',
              }}>
                <X size={16} />
              </button>
            </div>

            {/* Code block */}
            <div style={{ padding: 20, overflowY: 'auto', flex: 1 }}>
              <pre style={{
                background: '#0A0E1A', border: '1px solid rgba(255,255,255,0.06)',
                borderRadius: 10, padding: 16, fontSize: 11.5, lineHeight: 1.6,
                color: '#94A3B8', fontFamily: "'JetBrains Mono', monospace",
                whiteSpace: 'pre-wrap', wordBreak: 'break-word', margin: 0,
              }}>
                {script}
              </pre>
            </div>

            {/* Actions */}
            <div style={{
              padding: '14px 20px', borderTop: '1px solid rgba(255,255,255,0.06)',
              display: 'flex', flexDirection: 'column', gap: 10,
            }}>
              <div style={{ display: 'flex', gap: 10 }}>
                <button onClick={handleCopy} style={{
                  flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
                  padding: '10px 14px', borderRadius: 8, fontSize: 12.5, fontWeight: 700, cursor: 'pointer',
                  background: copied ? 'rgba(34,197,94,0.12)' : 'rgba(79,124,255,0.1)',
                  border: `1px solid ${copied ? 'rgba(34,197,94,0.3)' : 'rgba(79,124,255,0.25)'}`,
                  color: copied ? '#22C55E' : '#4F7CFF',
                }}>
                  {copied ? <Check size={14} /> : <Copy size={14} />}
                  {copied ? 'Copied' : 'Copy Script'}
                </button>
                <button onClick={handleDownload} style={{
                  flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
                  padding: '10px 14px', borderRadius: 8, fontSize: 12.5, fontWeight: 700, cursor: 'pointer',
                  background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', color: '#CBD5E1',
                }}>
                  <Download size={14} />
                  Download .pine
                </button>
                <a
                  href={tradingViewChartUrl(signal.symbol)}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{
                    flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
                    padding: '10px 14px', borderRadius: 8, fontSize: 12.5, fontWeight: 700,
                    background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)',
                    color: '#CBD5E1', textDecoration: 'none',
                  }}
                >
                  <ExternalLink size={14} />
                  Open in TradingView
                </a>
              </div>
              <div style={{ fontSize: 11, color: '#475569', lineHeight: 1.5 }}>
                TradingView has no public API for auto-injecting scripts into the chart —
                &ldquo;Open in TradingView&rdquo; opens their site; paste the copied script into
                Pine Editor there (Pine Editor tab at the bottom of the chart page).
              </div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
