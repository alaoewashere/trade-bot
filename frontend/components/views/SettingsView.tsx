'use client';

import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { Copy, Eye, EyeOff, Check } from 'lucide-react';

function SectionCard({ title, desc, children }: { title: string; desc: string; children: React.ReactNode }) {
  return (
    <div style={{
      background: '#121826', border: '1px solid rgba(255,255,255,0.06)',
      borderRadius: 12, padding: 20, marginBottom: 16,
    }}>
      <div style={{ marginBottom: 16 }}>
        <div style={{ fontSize: 14, fontWeight: 700, color: '#E2E8F0' }}>{title}</div>
        <div style={{ fontSize: 12, color: '#475569', marginTop: 3 }}>{desc}</div>
      </div>
      {children}
    </div>
  );
}

function ApiKey({ name, color, masked }: { name: string; color: string; masked: string }) {
  const [show, setShow] = useState(false);
  const [copied, setCopied] = useState(false);
  const copy = () => { setCopied(true); setTimeout(() => setCopied(false), 1500); };
  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '12px 14px', borderRadius: 10,
      background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.05)',
      marginBottom: 10,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <div style={{
          width: 8, height: 8, borderRadius: '50%', background: color,
          boxShadow: `0 0 6px ${color}`,
        }} />
        <span style={{ fontSize: 13, fontWeight: 600, color: '#E2E8F0', minWidth: 80 }}>{name}</span>
        <code style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 12, color: '#64748B' }}>
          {show ? masked : '••••••••••••••••••••••••••••••'}
        </code>
      </div>
      <div style={{ display: 'flex', gap: 6 }}>
        <button onClick={() => setShow(s => !s)} style={{
          width: 28, height: 28, borderRadius: 7, display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.08)', cursor: 'pointer',
        }}>{show ? <EyeOff size={12} color="#64748B" /> : <Eye size={12} color="#64748B" />}</button>
        <button onClick={copy} style={{
          width: 28, height: 28, borderRadius: 7, display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: copied ? 'rgba(34,197,94,0.1)' : 'rgba(255,255,255,0.05)',
          border: `1px solid ${copied ? 'rgba(34,197,94,0.3)' : 'rgba(255,255,255,0.08)'}`, cursor: 'pointer',
        }}>{copied ? <Check size={12} color="#22C55E" /> : <Copy size={12} color="#64748B" />}</button>
      </div>
    </div>
  );
}

function Toggle({ on, onChange }: { on: boolean; onChange: () => void }) {
  return (
    <div onClick={onChange} style={{
      width: 44, height: 24, borderRadius: 12,
      background: on ? 'rgba(34,197,94,0.3)' : 'rgba(255,255,255,0.08)',
      border: `1px solid ${on ? 'rgba(34,197,94,0.5)' : 'rgba(255,255,255,0.1)'}`,
      position: 'relative', cursor: 'pointer', transition: 'all 0.2s',
      flexShrink: 0,
    }}>
      <div style={{
        position: 'absolute', top: 3, left: on ? 21 : 3,
        width: 16, height: 16, borderRadius: '50%',
        background: on ? '#22C55E' : '#475569',
        transition: 'all 0.2s', boxShadow: on ? '0 0 8px rgba(34,197,94,0.6)' : 'none',
      }} />
    </div>
  );
}

function NumberInput({ label, value, suffix }: { label: string; value: string; suffix?: string }) {
  return (
    <div>
      <div style={{ fontSize: 10, color: '#475569', fontWeight: 700, marginBottom: 6, letterSpacing: '0.1em' }}>{label}</div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <input defaultValue={value} type="number" style={{
          background: '#1a2235', border: '1px solid rgba(255,255,255,0.1)',
          borderRadius: 8, padding: '8px 12px', fontSize: 13, color: '#E2E8F0',
          outline: 'none', width: 120, fontFamily: "'JetBrains Mono', monospace",
        }} />
        {suffix && <span style={{ fontSize: 12, color: '#475569' }}>{suffix}</span>}
      </div>
    </div>
  );
}

const NOTIF_ITEMS = [
  'Trade Execution',
  'AI Signal Alerts',
  'Risk Limit Warnings',
  'Daily P&L Summary',
  'Agent Consensus Reached',
  'News Impact Alerts',
];

const MODELS = [
  { id: 'groq', name: 'Groq LLaMA 3.3 70B', desc: 'Ultra-fast inference, 70B parameter model', speed: 'FAST', badge: 'ACTIVE', color: '#F59E0B' },
  { id: 'claude', name: 'Claude Sonnet 4.6', desc: 'Superior reasoning, context understanding', speed: 'MED', badge: 'FALLBACK', color: '#818CF8' },
];

const THEMES = [
  { id: 'dark', label: 'Dark Pro', bg: '#0B1020', active: true },
  { id: 'midnight', label: 'Midnight', bg: '#050810', active: false },
  { id: 'navy', label: 'Navy', bg: '#0a1628', active: false },
];

export default function SettingsView() {
  const [notifs, setNotifs] = useState(Object.fromEntries(NOTIF_ITEMS.map((n, i) => [n, i < 4])));
  const [selectedModel, setSelectedModel] = useState('groq');
  const [selectedTheme, setSelectedTheme] = useState('dark');

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      style={{ padding: 24, paddingBottom: 48, maxWidth: 820 }}
    >
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 20, fontWeight: 700, color: '#E2E8F0', margin: 0 }}>System Settings</h1>
        <p style={{ fontSize: 13, color: '#475569', marginTop: 4 }}>Configure API connections, risk limits, and system preferences</p>
      </div>

      {/* API Keys */}
      <SectionCard title="API Keys" desc="Manage broker and AI service connections">
        <ApiKey name="Binance" color="#F59E0B" masked="bnc_live_xK9mP3aQ7rT2vN8wL5jE1c..." />
        <ApiKey name="Alpaca"  color="#22C55E" masked="PK8J2H7X4MNVQR3A..." />
        <ApiKey name="Groq"    color="#818CF8" masked="gsk_Yh4kL9pX2mNqR7vT3a..." />
      </SectionCard>

      {/* Risk Limits */}
      <SectionCard title="Risk Limits" desc="Set maximum exposure and loss limits">
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16 }}>
          <NumberInput label="MAX POSITION SIZE" value="5000" suffix="USDT" />
          <NumberInput label="DAILY LOSS LIMIT" value="1250" suffix="USDT" />
          <NumberInput label="MAX OPEN TRADES" value="6" />
          <NumberInput label="DEFAULT STOP LOSS" value="2.5" suffix="%" />
          <NumberInput label="DEFAULT TAKE PROFIT" value="5" suffix="%" />
          <NumberInput label="MAX LEVERAGE" value="3" suffix="×" />
        </div>
        <button style={{
          marginTop: 16, padding: '8px 20px', borderRadius: 8, fontSize: 12, fontWeight: 600, cursor: 'pointer',
          background: 'rgba(79,124,255,0.1)', border: '1px solid rgba(79,124,255,0.25)', color: '#4F7CFF',
        }}>Save Risk Settings</button>
      </SectionCard>

      {/* Notifications */}
      <SectionCard title="Notifications" desc="Choose which alerts to receive">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {NOTIF_ITEMS.map(n => (
            <div key={n} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: 13, color: '#94A3B8' }}>{n}</span>
              <Toggle on={!!notifs[n]} onChange={() => setNotifs(prev => ({ ...prev, [n]: !prev[n] }))} />
            </div>
          ))}
        </div>
      </SectionCard>

      {/* AI Models */}
      <SectionCard title="AI Models" desc="Select and configure AI inference engines">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {MODELS.map(m => (
            <div
              key={m.id}
              onClick={() => setSelectedModel(m.id)}
              style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                padding: '14px 16px', borderRadius: 10, cursor: 'pointer',
                background: selectedModel === m.id ? 'rgba(79,124,255,0.08)' : 'rgba(255,255,255,0.02)',
                border: `1px solid ${selectedModel === m.id ? 'rgba(79,124,255,0.3)' : 'rgba(255,255,255,0.05)'}`,
                transition: 'all 0.15s',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <div style={{
                  width: 36, height: 36, borderRadius: 9,
                  background: `${m.color}22`, border: `1px solid ${m.color}44`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 14, fontWeight: 800, color: m.color,
                }}>AI</div>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: '#E2E8F0' }}>{m.name}</div>
                  <div style={{ fontSize: 11, color: '#475569', marginTop: 2 }}>{m.desc}</div>
                </div>
              </div>
              <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                <span style={{
                  padding: '2px 8px', borderRadius: 5, fontSize: 10, fontWeight: 700,
                  background: 'rgba(255,255,255,0.05)', color: '#475569',
                }}>{m.speed}</span>
                <span style={{
                  padding: '2px 8px', borderRadius: 5, fontSize: 10, fontWeight: 700,
                  background: `${m.color}22`, color: m.color,
                }}>{m.badge}</span>
                {selectedModel === m.id && (
                  <div style={{ width: 16, height: 16, borderRadius: '50%', background: '#4F7CFF', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <Check size={9} color="#fff" />
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      </SectionCard>

      {/* Theme */}
      <SectionCard title="Theme" desc="Customize the visual appearance">
        <div style={{ display: 'flex', gap: 12 }}>
          {THEMES.map(t => (
            <div
              key={t.id}
              onClick={() => setSelectedTheme(t.id)}
              style={{
                display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8,
                cursor: 'pointer',
              }}
            >
              <div style={{
                width: 64, height: 40, borderRadius: 8, background: t.bg,
                border: selectedTheme === t.id ? '2px solid #4F7CFF' : '2px solid rgba(255,255,255,0.1)',
                transition: 'border-color 0.15s',
                boxShadow: selectedTheme === t.id ? '0 0 12px rgba(79,124,255,0.4)' : 'none',
              }}>
                <div style={{ margin: '8px 6px 4px', height: 4, borderRadius: 2, background: 'rgba(79,124,255,0.5)' }} />
                <div style={{ margin: '0 6px', height: 2, borderRadius: 1, background: 'rgba(255,255,255,0.1)' }} />
                <div style={{ margin: '3px 6px', height: 2, borderRadius: 1, background: 'rgba(255,255,255,0.06)' }} />
              </div>
              <span style={{ fontSize: 11, color: selectedTheme === t.id ? '#4F7CFF' : '#475569', fontWeight: 600 }}>{t.label}</span>
            </div>
          ))}
        </div>
      </SectionCard>
    </motion.div>
  );
}
