'use client';

import React, { useState, useEffect, useRef } from 'react';
import { motion } from 'framer-motion';

/* ── Star field ─────────────────────────────────────── */
interface Star {
  id: number;
  x: number;
  y: number;
  size: number;
  opacity: number;
  delay: number;
  duration: number;
}

function useStars(count: number): Star[] {
  const ref = useRef<Star[]>([]);
  if (ref.current.length === 0) {
    ref.current = Array.from({ length: count }, (_, i) => ({
      id: i,
      x: Math.random() * 100,
      y: Math.random() * 100,
      size: Math.random() * 2 + 0.5,
      opacity: Math.random() * 0.5 + 0.2,
      delay: Math.random() * 4,
      duration: Math.random() * 3 + 2,
    }));
  }
  return ref.current;
}

/* ── Stat orb card ──────────────────────────────────── */
interface StatOrbProps {
  label: string;
  value: string;
  color: string;
  delay: number;
  style: React.CSSProperties;
}

function StatOrb({ label, value, color, delay, style }: StatOrbProps) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.8 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ delay, duration: 0.5, ease: 'easeOut' }}
      style={{
        ...style,
        position: 'absolute',
        background: 'rgba(13,21,37,0.85)',
        border: `1px solid ${color}44`,
        borderRadius: 10,
        padding: '8px 14px',
        backdropFilter: 'blur(12px)',
        boxShadow: `0 0 20px ${color}22, inset 0 1px 0 ${color}22`,
        minWidth: 110,
        zIndex: 10,
      }}
    >
      <motion.div
        animate={{ y: [0, -6, 0] }}
        transition={{ duration: 3.5, repeat: Infinity, ease: 'easeInOut', delay }}
      >
        <div style={{ fontSize: 10, color: '#64748B', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 2 }}>
          {label}
        </div>
        <div style={{ fontSize: 15, fontWeight: 700, color, fontFamily: 'JetBrains Mono, monospace' }}>
          {value}
        </div>
      </motion.div>
    </motion.div>
  );
}

/* ── Continent blob ─────────────────────────────────── */
function ContinentBlob({ style }: { style: React.CSSProperties }) {
  return (
    <div
      style={{
        position: 'absolute',
        background: 'rgba(5,15,40,0.75)',
        ...style,
      }}
    />
  );
}

/* ── Main component ─────────────────────────────────── */
export default function PlanetHero() {
  const stars = useStars(80);
  const [btcPrice, setBtcPrice] = useState(67428);
  const [priceChange, setPriceChange] = useState(1.87);

  useEffect(() => {
    const interval = setInterval(() => {
      setBtcPrice(prev => {
        const delta = (Math.random() - 0.48) * 80;
        return Math.round(prev + delta);
      });
      setPriceChange(prev => {
        const delta = (Math.random() - 0.48) * 0.05;
        return parseFloat((prev + delta).toFixed(2));
      });
    }, 2000);
    return () => clearInterval(interval);
  }, []);

  const changeColor = priceChange >= 0 ? '#22C55E' : '#EF4444';
  const changePrefix = priceChange >= 0 ? '+' : '';

  return (
    <div
      style={{
        width: '100%',
        height: 420,
        position: 'relative',
        background: 'linear-gradient(180deg, #020817 0%, #030712 60%, #0B1020 100%)',
        borderRadius: 16,
        overflow: 'hidden',
        border: '1px solid rgba(79,124,255,0.12)',
        boxShadow: '0 0 80px rgba(79,124,255,0.05)',
      }}
    >
      {/* Nebula radials */}
      <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }}>
        <div style={{ position: 'absolute', top: '10%', left: '15%', width: 400, height: 300, background: 'radial-gradient(ellipse, rgba(79,124,255,0.08) 0%, transparent 70%)', borderRadius: '50%' }} />
        <div style={{ position: 'absolute', top: '30%', right: '10%', width: 300, height: 250, background: 'radial-gradient(ellipse, rgba(139,92,246,0.07) 0%, transparent 70%)', borderRadius: '50%' }} />
        <div style={{ position: 'absolute', bottom: 0, left: '40%', width: 350, height: 200, background: 'radial-gradient(ellipse, rgba(34,197,94,0.04) 0%, transparent 70%)', borderRadius: '50%' }} />
      </div>

      {/* Star field */}
      {stars.map(star => (
        <motion.div
          key={star.id}
          style={{
            position: 'absolute',
            left: `${star.x}%`,
            top: `${star.y}%`,
            width: star.size,
            height: star.size,
            borderRadius: '50%',
            background: 'white',
            opacity: star.opacity,
          }}
          animate={{ opacity: [star.opacity * 0.4, star.opacity, star.opacity * 0.4], scale: [1, 1.4, 1] }}
          transition={{ duration: star.duration, repeat: Infinity, delay: star.delay, ease: 'easeInOut' }}
        />
      ))}

      {/* Planet container */}
      <div
        style={{
          position: 'absolute',
          left: '50%',
          top: '50%',
          transform: 'translate(-50%, -52%)',
          width: 280,
          height: 280,
        }}
      >
        {/* Outer atmospheric glow rings */}
        <motion.div
          animate={{ opacity: [0.4, 0.15, 0.4], scale: [1, 1.06, 1] }}
          transition={{ duration: 4, repeat: Infinity, ease: 'easeInOut' }}
          style={{
            position: 'absolute',
            inset: -32,
            borderRadius: '50%',
            background: 'radial-gradient(circle, rgba(79,124,255,0.12) 40%, transparent 72%)',
          }}
        />
        <motion.div
          animate={{ opacity: [0.3, 0.1, 0.3], scale: [1, 1.12, 1] }}
          transition={{ duration: 6, repeat: Infinity, ease: 'easeInOut', delay: 1 }}
          style={{
            position: 'absolute',
            inset: -64,
            borderRadius: '50%',
            background: 'radial-gradient(circle, rgba(79,124,255,0.06) 40%, transparent 70%)',
          }}
        />

        {/* Planet sphere */}
        <div
          style={{
            width: 280,
            height: 280,
            borderRadius: '50%',
            background: 'radial-gradient(circle at 35% 35%, #4a90d9 0%, #2060a8 20%, #1a3a6b 50%, #0a1a3a 80%, #050d1a 100%)',
            boxShadow:
              '0 0 60px 20px rgba(79,124,255,0.3), 0 0 120px 40px rgba(79,124,255,0.15), inset -30px -20px 60px rgba(0,0,30,0.8), inset 10px 8px 30px rgba(100,160,255,0.15)',
            position: 'relative',
            overflow: 'hidden',
          }}
        >
          {/* Continent shapes */}
          <ContinentBlob style={{ top: '18%', left: '22%', width: 70, height: 45, borderRadius: '60% 40% 55% 45%', opacity: 0.85 }} />
          <ContinentBlob style={{ top: '40%', left: '50%', width: 55, height: 38, borderRadius: '45% 55% 40% 60%', opacity: 0.8 }} />
          <ContinentBlob style={{ top: '58%', left: '20%', width: 45, height: 30, borderRadius: '50% 50% 45% 55%', opacity: 0.75 }} />
          <ContinentBlob style={{ top: '25%', left: '60%', width: 40, height: 28, borderRadius: '55% 45% 60% 40%', opacity: 0.7 }} />
          {/* Atmospheric highlight */}
          <div style={{ position: 'absolute', top: '8%', left: '10%', width: '35%', height: '25%', borderRadius: '50%', background: 'radial-gradient(circle, rgba(180,210,255,0.18) 0%, transparent 70%)' }} />
          {/* Shadow side */}
          <div style={{ position: 'absolute', inset: 0, borderRadius: '50%', background: 'linear-gradient(135deg, transparent 40%, rgba(0,0,15,0.6) 100%)' }} />
        </div>

        {/* Orbital ring (SVG) */}
        <div
          style={{
            position: 'absolute',
            top: '50%',
            left: '50%',
            width: 360,
            height: 100,
            transform: 'translate(-50%, -50%)',
            zIndex: 5,
          }}
        >
          <motion.svg
            viewBox="0 0 360 100"
            style={{ width: '100%', height: '100%', overflow: 'visible' }}
            animate={{ rotate: 360 }}
            transition={{ duration: 30, repeat: Infinity, ease: 'linear' }}
          >
            <ellipse
              cx="180"
              cy="50"
              rx="170"
              ry="44"
              fill="none"
              stroke="rgba(79,124,255,0.3)"
              strokeWidth="1.5"
              strokeDasharray="8 6"
            />
            {/* Satellite dot on ring */}
            <circle cx="10" cy="50" r="4" fill="rgba(79,124,255,0.9)" />
            <circle cx="10" cy="50" r="6" fill="none" stroke="rgba(79,124,255,0.4)" strokeWidth="1" />
          </motion.svg>
        </div>
      </div>

      {/* Stat orbs — positioned relative to center */}
      <StatOrb
        label="BTC Price"
        value={`$${btcPrice.toLocaleString()}`}
        color="#4F7CFF"
        delay={0.2}
        style={{ top: '8%', left: '8%' }}
      />
      <StatOrb
        label="24h Change"
        value={`${changePrefix}${priceChange}%`}
        color={changeColor}
        delay={0.35}
        style={{ top: '8%', right: '8%' }}
      />
      <StatOrb
        label="AI Agents"
        value="40 Active"
        color="#8B5CF6"
        delay={0.5}
        style={{ bottom: '22%', left: '6%' }}
      />
      <StatOrb
        label="Market Regime"
        value="TRENDING"
        color="#F59E0B"
        delay={0.65}
        style={{ bottom: '22%', right: '6%' }}
      />

      {/* Bottom text */}
      <div
        style={{
          position: 'absolute',
          bottom: 0,
          left: 0,
          right: 0,
          textAlign: 'center',
          padding: '0 24px 28px',
        }}
      >
        <motion.h1
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.8, duration: 0.7 }}
          style={{
            fontSize: 22,
            fontWeight: 800,
            letterSpacing: '0.18em',
            background: 'linear-gradient(90deg, #4F7CFF 0%, #818CF8 50%, #22C55E 100%)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
            backgroundClip: 'text',
            marginBottom: 6,
            textTransform: 'uppercase',
          }}
        >
          Hedge-AI Mission Control
        </motion.h1>
        <motion.p
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 1, duration: 0.6 }}
          style={{ fontSize: 12, color: '#64748B', letterSpacing: '0.06em' }}
        >
          40 AI agents working 24/7 to find the perfect trade
        </motion.p>
      </div>
    </div>
  );
}
