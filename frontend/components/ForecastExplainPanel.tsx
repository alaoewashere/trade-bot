'use client';

import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { api, ForecastExplanation } from '@/lib/api';

const BULLISH = '#22C55E';
const BEARISH = '#EF4444';
const AMBER = '#F59E0B';
const GRAY = '#64748B';

function signalColor(signal: string): string {
  if (signal === 'bullish') return BULLISH;
  if (signal === 'bearish') return BEARISH;
  return AMBER;
}

/**
 * Click-to-explain slide-over (Phase 5 part C/D) — reads like an analyst
 * report: department-grouped reasoning, agreement/dissent, scored evidence,
 * final thesis, counterarguments. Same AnimatePresence pattern ConsensusPanel
 * already uses for its inline "explain this decision" section, lifted into a
 * standalone panel so chart markers (current + historical) can both open it.
 */
export default function ForecastExplainPanel({
  forecastId,
  onClose,
}: {
  forecastId: string | null;
  onClose: () => void;
}) {
  const [explanation, setExplanation] = useState<ForecastExplanation | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!forecastId) {
      setExplanation(null);
      return;
    }
    setLoading(true);
    setError(null);
    api.forecasts
      .explain(forecastId)
      .then(setExplanation)
      .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load explanation'))
      .finally(() => setLoading(false));
  }, [forecastId]);

  return (
    <AnimatePresence>
      {forecastId && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            style={{
              position: 'fixed',
              inset: 0,
              background: 'rgba(2,6,16,0.6)',
              zIndex: 60,
            }}
          />
          <motion.div
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'tween', duration: 0.22, ease: 'easeOut' }}
            style={{
              position: 'fixed',
              top: 0,
              right: 0,
              bottom: 0,
              width: 'min(480px, 100vw)',
              background: '#0B0F1A',
              borderLeft: '1px solid rgba(255,255,255,0.08)',
              zIndex: 61,
              overflowY: 'auto',
              padding: 24,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
              <h2 style={{ fontSize: 16, fontWeight: 700, color: '#F1F5F9', margin: 0 }}>Forecast Explanation</h2>
              <button
                onClick={onClose}
                style={{
                  background: 'rgba(255,255,255,0.06)',
                  border: '1px solid rgba(255,255,255,0.08)',
                  borderRadius: 8,
                  color: '#94A3B8',
                  padding: '4px 10px',
                  cursor: 'pointer',
                  fontSize: 12,
                }}
              >
                Close
              </button>
            </div>

            {loading && <div style={{ color: '#475569', fontSize: 13 }}>Loading analyst report...</div>}
            {error && <div style={{ color: BEARISH, fontSize: 13 }}>{error}</div>}

            {explanation && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
                {/* Header summary */}
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                    <span style={{ fontWeight: 700, color: '#E2E8F0', fontSize: 14 }}>{explanation.symbol}</span>
                    <span style={{ fontSize: 11, color: '#475569' }}>{explanation.timeframe}</span>
                    <span
                      style={{
                        fontSize: 11,
                        fontWeight: 700,
                        color: signalColor(explanation.direction),
                        padding: '2px 8px',
                        borderRadius: 6,
                        background: `${signalColor(explanation.direction)}20`,
                      }}
                    >
                      {explanation.direction.toUpperCase()} · {explanation.confidence_pct.toFixed(0)}%
                    </span>
                  </div>
                  <div style={{ fontSize: 10, color: '#475569' }}>
                    Generated {new Date(explanation.generated_at).toLocaleString()}
                  </div>
                </div>

                {/* Final thesis */}
                <section>
                  <h3 style={{ fontSize: 11, fontWeight: 700, color: '#94A3B8', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 }}>
                    Final Consensus Thesis
                  </h3>
                  <p style={{ fontSize: 13, color: '#CBD5E1', lineHeight: 1.6, margin: 0 }}>{explanation.final_thesis}</p>
                </section>

                {/* Agreement */}
                <section>
                  <h3 style={{ fontSize: 11, fontWeight: 700, color: '#94A3B8', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 }}>
                    Agreement / Dissent
                  </h3>
                  <div style={{ display: 'flex', gap: 12 }}>
                    <div style={{ flex: 1, background: 'rgba(79,124,255,0.08)', border: '1px solid rgba(79,124,255,0.15)', borderRadius: 10, padding: 10, textAlign: 'center' }}>
                      <div style={{ fontFamily: 'monospace', fontWeight: 700, fontSize: 16, color: '#4F7CFF' }}>
                        {explanation.agreement.agreeing_agents}/{explanation.agreement.total_agents}
                      </div>
                      <div style={{ fontSize: 9, color: '#475569', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Agree</div>
                    </div>
                    <div style={{ flex: 1, background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.15)', borderRadius: 10, padding: 10, textAlign: 'center' }}>
                      <div style={{ fontFamily: 'monospace', fontWeight: 700, fontSize: 16, color: AMBER }}>
                        {explanation.agreement.agreement_pct.toFixed(0)}%
                      </div>
                      <div style={{ fontSize: 9, color: '#475569', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Agreement</div>
                    </div>
                  </div>
                  {explanation.agreement.dissenting_agent_ids.length > 0 && (
                    <div style={{ marginTop: 8, fontSize: 11, color: AMBER }}>
                      Dissenting: {explanation.agreement.dissenting_agent_ids.join(', ')}
                    </div>
                  )}
                </section>

                {/* Scored evidence (Phase 4 numeric evidence scoring) */}
                <section>
                  <h3 style={{ fontSize: 11, fontWeight: 700, color: '#94A3B8', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 }}>
                    Evidence Scoring
                  </h3>
                  <div style={{ display: 'flex', gap: 12, marginBottom: 10 }}>
                    <div style={{ flex: 1, textAlign: 'center' }}>
                      <div style={{ fontFamily: 'monospace', fontWeight: 700, fontSize: 15, color: BULLISH }}>
                        +{explanation.bullish_score.toFixed(2)}
                      </div>
                      <div style={{ fontSize: 9, color: '#475569' }}>Bullish score</div>
                    </div>
                    <div style={{ flex: 1, textAlign: 'center' }}>
                      <div style={{ fontFamily: 'monospace', fontWeight: 700, fontSize: 15, color: BEARISH }}>
                        -{explanation.bearish_score.toFixed(2)}
                      </div>
                      <div style={{ fontSize: 9, color: '#475569' }}>Bearish score</div>
                    </div>
                    <div style={{ flex: 1, textAlign: 'center' }}>
                      <div
                        style={{
                          fontFamily: 'monospace',
                          fontWeight: 700,
                          fontSize: 15,
                          color: explanation.net_ai_score >= 0 ? BULLISH : BEARISH,
                        }}
                      >
                        {explanation.net_ai_score >= 0 ? '+' : ''}
                        {explanation.net_ai_score.toFixed(2)}
                      </div>
                      <div style={{ fontSize: 9, color: '#475569' }}>Net AI score</div>
                    </div>
                  </div>
                  {explanation.supporting_evidence.length > 0 && (
                    <div style={{ marginBottom: 8 }}>
                      <div style={{ fontSize: 10, color: BULLISH, fontWeight: 700, marginBottom: 3 }}>Supporting</div>
                      {explanation.supporting_evidence.map((e, i) => (
                        <div key={i} style={{ fontSize: 12, color: '#94A3B8', paddingLeft: 8, borderLeft: `2px solid ${BULLISH}40`, marginBottom: 3 }}>
                          {e}
                        </div>
                      ))}
                    </div>
                  )}
                  {explanation.contradicting_evidence.length > 0 && (
                    <div>
                      <div style={{ fontSize: 10, color: BEARISH, fontWeight: 700, marginBottom: 3 }}>Counterarguments</div>
                      {explanation.contradicting_evidence.map((e, i) => (
                        <div key={i} style={{ fontSize: 12, color: '#94A3B8', paddingLeft: 8, borderLeft: `2px solid ${BEARISH}40`, marginBottom: 3 }}>
                          {e}
                        </div>
                      ))}
                    </div>
                  )}
                </section>

                {/* Department-grouped reasoning */}
                <section>
                  <h3 style={{ fontSize: 11, fontWeight: 700, color: '#94A3B8', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 }}>
                    Agent Reasoning by Department
                  </h3>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                    {explanation.departments.map((dept) => (
                      <div key={dept.department} style={{ borderTop: '1px solid rgba(255,255,255,0.06)', paddingTop: 8 }}>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
                          <span style={{ fontSize: 11, fontWeight: 700, color: '#CBD5E1', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                            {dept.department.replace(/_/g, ' ')}
                          </span>
                          <span style={{ fontSize: 11, color: signalColor(dept.dominant_signal) }}>
                            {dept.dominant_signal} · {dept.avg_confidence_pct.toFixed(0)}%
                          </span>
                        </div>
                        {dept.agents.map((a) => (
                          <div key={a.agent_id} style={{ display: 'flex', flexDirection: 'column', padding: '4px 0' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                              <span style={{ fontSize: 11, color: '#64748B' }}>{a.agent_id}</span>
                              <span style={{ fontSize: 11, color: signalColor(a.signal) }}>
                                {a.signal} ({a.confidence_pct.toFixed(0)}%)
                              </span>
                            </div>
                            {a.reasoning && (
                              <div style={{ fontSize: 11, color: '#475569', marginTop: 2 }}>{a.reasoning}</div>
                            )}
                          </div>
                        ))}
                      </div>
                    ))}
                  </div>
                </section>
              </div>
            )}
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
