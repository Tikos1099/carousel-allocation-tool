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
  folder_id: string | null
}

export interface Folder {
  id: string
  name: string
  created_at: string | null
}

export interface MappingRow {
  id: string
  targetName: string
  sourceCol: string
  formula: string
  isPK: boolean
  aggregation: string
  format: string
  includeInOutput: boolean
}

export type FilterOp =
  | "=" | "<>" | ">" | "<" | ">=" | "<="
  | "contains" | "not_contains"
  | "starts_with" | "ends_with"
  | "is_empty" | "is_not_empty"

export interface FilterRule {
  id: string
  col: string
  op: FilterOp
  val: string
}

export interface MappingConfig {
  id: string
  name: string
  rows: MappingRow[]
  filters: FilterRule[]
  output_filters: FilterRule[]
  dedup_by_pk: boolean
  created_at: string | null
}
