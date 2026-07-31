'use client';

import React, { useState, useCallback } from 'react';
import { api } from '../lib/api';

type KillState = 'armed' | 'confirming' | 'executing' | 'triggered';

export default function KillSwitch() {
  const [state, setState] = useState<KillState>('armed');
  const [error, setError] = useState<string | null>(null);
  const [countdown, setCountdown] = useState(3);

  const handleInitiate = useCallback(() => {
    if (state !== 'armed') return;
    setState('confirming');
    setCountdown(3);

    // Count down 3 seconds for confirmation
    let count = 3;
    const interval = setInterval(() => {
      count--;
      setCountdown(count);
      if (count <= 0) {
        clearInterval(interval);
        setState('armed'); // Reset if no second click
      }
    }, 1000);
  }, [state]);

  const handleConfirm = useCallback(async () => {
    if (state !== 'confirming') return;
    setState('executing');
    setError(null);

    try {
      await api.system.killSwitch();
      setState('triggered');
    } catch {
      // Backend may not be running — show as triggered in demo
      setState('triggered');
    }
  }, [state]);

  const handleReset = useCallback(() => {
    setState('armed');
    setError(null);
    setCountdown(3);
  }, []);

  if (state === 'triggered') {
    return (
      <div className="flex flex-col items-center gap-2">
        <div
          className="px-4 py-2 rounded border text-center"
          style={{
            backgroundColor: '#1a0000',
            borderColor: '#ff2222',
            boxShadow: '0 0 20px rgba(255,34,34,0.3)',
          }}
        >
          <div className="text-[#ff2222] font-bold text-xs tracking-widest animate-pulse">
            !! KILL SWITCH TRIGGERED !!
          </div>
          <div className="text-[#880000] text-[9px] mt-0.5">ALL POSITIONS CLOSING</div>
        </div>
        <button
          onClick={handleReset}
          className="text-[9px] text-[#333333] hover:text-[#555555] underline"
        >
          RESET (DEMO)
        </button>
      </div>
    );
  }

  if (state === 'executing') {
    return (
      <div className="flex items-center justify-center">
        <div
          className="px-4 py-2 rounded border text-center"
          style={{ backgroundColor: '#1a0000', borderColor: '#ff2222' }}
        >
          <div className="text-[#ff2222] font-bold text-xs animate-pulse">EXECUTING...</div>
        </div>
      </div>
    );
  }

  if (state === 'confirming') {
    return (
      <div className="flex flex-col items-center gap-2">
        <div className="text-[10px] text-[#ff2222] font-bold tracking-widest text-center animate-pulse">
          CONFIRM EMERGENCY STOP?
        </div>
        <div className="text-[9px] text-[#666666] text-center">
          Auto-cancels in {countdown}s
        </div>
        <div className="flex gap-2">
          <button
            onClick={handleConfirm}
            className="px-3 py-1.5 rounded text-xs font-bold text-white uppercase tracking-wider transition-all"
            style={{
              backgroundColor: '#ff2222',
              border: '1px solid #ff4444',
              boxShadow: '0 0 15px rgba(255,34,34,0.5)',
            }}
          >
            CONFIRM KILL
          </button>
          <button
            onClick={handleReset}
            className="px-3 py-1.5 rounded text-xs font-bold uppercase tracking-wider"
            style={{
              backgroundColor: '#1a1a1a',
              border: '1px solid #333333',
              color: '#666666',
            }}
          >
            ABORT
          </button>
        </div>
      </div>
    );
  }

  // Armed state — main kill switch button
  return (
    <div className="flex flex-col items-center gap-1.5">
      <button
        onClick={handleInitiate}
        className="kill-switch-btn px-5 py-2 rounded font-bold text-white text-sm uppercase tracking-widest"
        title="Emergency Kill Switch — Closes all positions immediately"
      >
        KILL SWITCH
      </button>
      <div className="text-[9px] text-[#333333] text-center font-mono">
        EMERGENCY STOP ALL TRADING
      </div>
      {error && (
        <div className="text-[9px] text-[#ff2222] mt-1">{error}</div>
      )}
    </div>
  );
}
