'use client';

import { useEffect, useRef, useState, useCallback } from 'react';

export type WSStatus = 'connecting' | 'connected' | 'disconnected' | 'error';

export interface AgentActivityMessage {
  type: 'agent_update' | 'debate_message' | 'trade_signal' | 'system';
  agent_id?: string;
  agent_name?: string;
  department?: string;
  status?: 'idle' | 'analyzing' | 'debating';
  signal?: 'bullish' | 'bearish' | 'neutral';
  confidence?: number;
  message?: string;
  timestamp?: string;
  payload?: Record<string, unknown>;
}

export interface MarketDataMessage {
  type: 'price' | 'prediction' | 'snapshot';
  symbol?: string;
  price?: number;
  change?: number;
  change_pct?: number;
  predictions?: Record<string, unknown>;
  timestamp?: string;
}

interface UseWebSocketOptions {
  onMessage?: (data: AgentActivityMessage | MarketDataMessage) => void;
  reconnectInterval?: number;
  maxReconnectAttempts?: number;
}

export function useWebSocket(url: string, options: UseWebSocketOptions = {}) {
  const { onMessage, reconnectInterval = 3000, maxReconnectAttempts = 10 } = options;

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectCountRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef(true);

  const [status, setStatus] = useState<WSStatus>('disconnected');
  const [lastMessage, setLastMessage] = useState<AgentActivityMessage | MarketDataMessage | null>(null);
  const [error, setError] = useState<string | null>(null);

  const connect = useCallback(() => {
    if (!mountedRef.current) return;
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    try {
      setStatus('connecting');
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        if (!mountedRef.current) return;
        setStatus('connected');
        setError(null);
        reconnectCountRef.current = 0;
      };

      ws.onmessage = (event) => {
        if (!mountedRef.current) return;
        try {
          const data = JSON.parse(event.data) as AgentActivityMessage | MarketDataMessage;
          setLastMessage(data);
          onMessage?.(data);
        } catch {
          // silently ignore parse errors
        }
      };

      ws.onerror = () => {
        if (!mountedRef.current) return;
        setStatus('error');
        setError('WebSocket connection error');
      };

      ws.onclose = () => {
        if (!mountedRef.current) return;
        setStatus('disconnected');
        wsRef.current = null;

        if (reconnectCountRef.current < maxReconnectAttempts) {
          reconnectCountRef.current++;
          reconnectTimerRef.current = setTimeout(() => {
            if (mountedRef.current) connect();
          }, reconnectInterval);
        }
      };
    } catch (err) {
      setStatus('error');
      setError(err instanceof Error ? err.message : 'Failed to connect');
    }
  }, [url, onMessage, reconnectInterval, maxReconnectAttempts]);

  const disconnect = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setStatus('disconnected');
  }, []);

  const send = useCallback((data: unknown) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    connect();

    return () => {
      mountedRef.current = false;
      disconnect();
    };
  }, [connect, disconnect]);

  return { status, lastMessage, error, send, connect, disconnect };
}

export function useAgentActivityWS(onMessage?: (data: AgentActivityMessage) => void) {
  return useWebSocket('ws://localhost:8000/ws/agent-activity', {
    onMessage: onMessage as (data: AgentActivityMessage | MarketDataMessage) => void,
  });
}

export function useMarketDataWS(onMessage?: (data: MarketDataMessage) => void) {
  return useWebSocket('ws://localhost:8000/ws/market-data', {
    onMessage: onMessage as (data: AgentActivityMessage | MarketDataMessage) => void,
  });
}
