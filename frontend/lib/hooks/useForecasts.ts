import { useEffect, useState, useCallback, useRef } from 'react'
import { supabase } from '../supabase'

export interface Forecast {
  id: string
  symbol: string
  timeframe: string
  created_at: string
  expiry_at: string
  direction: 'bullish' | 'bearish' | 'neutral'
  confidence_pct: number | null
  bull_probability: number | null
  bear_probability: number | null
  neutral_probability: number | null
  price_at_creation: number | null
  predicted_low: number | null
  predicted_high: number | null
  risk_score: number | null
  market_regime: string | null
  model_contributions: unknown | null
  supporting_evidence: unknown | null
  contradicting_evidence: unknown | null
  evaluated: boolean
  actual_price_at_expiry: number | null
  actual_direction: string | null
  direction_correct: boolean | null
  range_hit: boolean | null
  absolute_error_pct: number | null
  mfe: number | null
  mae: number | null
}

const POLL_INTERVAL = 15_000 // 15 seconds

export function useForecasts(symbol?: string, limit = 50) {
  const [forecasts, setForecasts] = useState<Forecast[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const cancelledRef = useRef(false)

  const fetchForecasts = useCallback(async () => {
    try {
      let query = supabase
        .from('forecasts')
        .select('*')
        .order('created_at', { ascending: false })
        .limit(limit)

      if (symbol) {
        query = query.eq('symbol', symbol)
      }

      const { data, error: fetchError } = await query
      if (fetchError) throw fetchError
      if (!cancelledRef.current) {
        setForecasts(data as Forecast[])
        setLoading(false)
        setError(null)
      }
    } catch (err: unknown) {
      if (!cancelledRef.current) {
        setError(err instanceof Error ? err.message : String(err))
        setLoading(false)
      }
    }
  }, [symbol, limit])

  useEffect(() => {
    cancelledRef.current = false

    fetchForecasts()

    const timer = setInterval(fetchForecasts, POLL_INTERVAL)

    // Try realtime as enhancement — silently ignore errors
    let channel: ReturnType<typeof supabase.channel> | null = null
    try {
      channel = supabase
        .channel('forecasts_changes')
        .on(
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          'postgres_changes' as any,
          { event: 'INSERT', schema: 'public', table: 'forecasts' },
          () => { fetchForecasts() },
        )
        .subscribe((status: string) => {
          if (status === 'CHANNEL_ERROR' || status === 'TIMED_OUT') {
            // Polling covers us
          }
        })
    } catch {
      // Realtime not available — polling covers us
    }

    return () => {
      cancelledRef.current = true
      clearInterval(timer)
      if (channel) supabase.removeChannel(channel)
    }
  }, [fetchForecasts])

  return { forecasts, loading, error, refetch: fetchForecasts }
}
