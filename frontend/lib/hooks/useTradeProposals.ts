import { useEffect, useState, useCallback, useRef } from 'react'
import { supabase } from '../supabase'

export interface TradeProposal {
  id: string
  symbol: string
  direction: string
  timeframe: string
  proposed_at: string
  consensus_score: number | null
  confidence_pct: number | null
  debate_summary: unknown | null
  agent_signals: unknown | null
  risk_assessment: unknown | null
  status: 'pending' | 'approved' | 'rejected' | 'expired' | 'cancelled'
  human_decision: string | null
  human_reason: string | null
  decided_at: string | null
  expires_at: string | null
}

const POLL_INTERVAL = 10_000 // 10 seconds

export function useTradeProposals() {
  const [proposals, setProposals] = useState<TradeProposal[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const cancelledRef = useRef(false)

  const fetchPending = useCallback(async () => {
    try {
      const { data, error: fetchError } = await supabase
        .from('trade_proposals')
        .select('*')
        .eq('status', 'pending')
        .order('proposed_at', { ascending: false })

      if (fetchError) throw fetchError
      if (!cancelledRef.current) {
        setProposals(data as TradeProposal[])
        setLoading(false)
        setError(null)
      }
    } catch (err: unknown) {
      if (!cancelledRef.current) {
        setError(err instanceof Error ? err.message : String(err))
        setLoading(false)
      }
    }
  }, [])

  useEffect(() => {
    cancelledRef.current = false

    // Initial fetch
    fetchPending()

    // Poll every 10s as primary update mechanism
    const timer = setInterval(fetchPending, POLL_INTERVAL)

    // Try realtime as an enhancement — silently ignore if not enabled
    let channel: ReturnType<typeof supabase.channel> | null = null
    try {
      channel = supabase
        .channel('trade_proposals_changes')
        .on(
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          'postgres_changes' as any,
          { event: '*', schema: 'public', table: 'trade_proposals' },
          () => { fetchPending() },
        )
        .subscribe((status: string) => {
          if (status === 'CHANNEL_ERROR' || status === 'TIMED_OUT') {
            // Realtime not available — polling covers us
          }
        })
    } catch {
      // Realtime not available on this project — polling covers us
    }

    return () => {
      cancelledRef.current = true
      clearInterval(timer)
      if (channel) supabase.removeChannel(channel)
    }
  }, [fetchPending])

  return { proposals, loading, error, refetch: fetchPending }
}
