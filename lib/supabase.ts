import { createClient } from "@supabase/supabase-js"

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!

export const supabase = createClient(supabaseUrl, supabaseAnonKey)

export interface SupabaseJob {
  job_id: string
  scenario_name: string | null
  status: string
  created_at: string | null
  finished_at: string | null
  kpis: {
    total_flights?: number
    assigned_pct?: number
    unassigned_count?: number
    split_count?: number
    split_pct?: number
    narrow_wide_count?: number
    narrow_wide_pct?: number
  }
  storage_size_bytes: number
}
