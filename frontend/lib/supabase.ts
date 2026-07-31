import { createClient } from '@supabase/supabase-js'

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL ?? 'https://hugpspsssckbepyofcnt.supabase.co'
const supabaseAnonKey =
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ??
  'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imh1Z3BzcHNzc2NrYmVweW9mY250Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODU0Mjk5OTMsImV4cCI6MjEwMTAwNTk5M30.DF3DCBllgTpQ9XCy4V_N0UiTljq-GDaJkoyu0TEsUhY'

export const supabase = createClient(supabaseUrl, supabaseAnonKey)
