import { useEffect, useState, useCallback, useRef } from 'react'
import { supabase } from '../supabase'

export interface AgentDecision {
  id: string
  agent_id: string
  symbol: string
  decided_at: string
  signal: string
  confidence: number | null
  reasoning: string | null
  outcome: 'correct' | 'incorrect' | 'neutral' | 'pending'
  pnl_attribution: number | null
}

const MAX_DECISIONS = 50
const POLL_INTERVAL = 15_000 // 15 seconds

export function useAgentDecisions(agentId?: string) {
  const [decisions, setDecisions] = useState<AgentDecision[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const cancelledRef = useRef(false)

  const fetchRecent = useCallback(async () => {
    try {
      let query = supabase
        .from('agent_decisions')
        .select('*')
        .order('decided_at', { ascending: false })
        .limit(MAX_DECISIONS)

      if (agentId) {
        query = query.eq('agent_id', agentId)
      }

      const { data, error: fetchError } = await query
      if (fetchError) throw fetchError
      if (!cancelledRef.current) {
        setDecisions(data as AgentDecision[])
        setLoading(false)
        setError(null)
      }
    } catch (err: unknown) {
      if (!cancelledRef.current) {
        setError(err instanceof Error ? err.message : String(err))
        setLoading(false)
      }
    }
  }, [agentId])

  useEffect(() => {
    cancelledRef.current = false

    fetchRecent()

    const timer = setInterval(fetchRecent, POLL_INTERVAL)

    // Try realtime as enhancement — silently ignore if not enabled
    let channel: ReturnType<typeof supabase.channel> | null = null
    try {
      const channelName = agentId ? `agent_decisions_${agentId}` : 'agent_decisions_all'
      const filter = agentId
        ? { event: 'INSERT' as const, schema: 'public', table: 'agent_decisions', filter: `agent_id=eq.${agentId}` }
        : { event: 'INSERT' as const, schema: 'public', table: 'agent_decisions' }

      channel = supabase
        .channel(channelName)
        .on(
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          'postgres_changes' as any,
          filter,
          (payload: { new: unknown }) => {
            const newDecision = payload.new as AgentDecision
            if (!cancelledRef.current) {
              setDecisions((prev) => [newDecision, ...prev].slice(0, MAX_DECISIONS))
            }
          },
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
  }, [agentId, fetchRecent])

  return { decisions, loading, error }
}
