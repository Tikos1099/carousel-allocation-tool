import { createClient } from "@supabase/supabase-js"

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!

export const supabase = createClient(supabaseUrl, supabaseAnonKey)

// ─── Hierarchy Types ───────────────────────────────────────────────────────────

export interface Entreprise {
  id: string
  name: string
  background_url: string | null
  created_at: string | null
}

export interface Secteur {
  id: string
  entreprise_id: string
  name: string
  background_url: string | null
  created_at: string | null
}

export interface Projet {
  id: string
  secteur_id: string | null      // nullable — projet peut exister sans secteur
  entreprise_id: string | null   // renseigné quand projet est direct sous une entreprise
  name: string
  code: string | null            // code optionnel du projet
  background_url: string | null
  created_at: string | null
}

export interface Scenario {
  id: string
  projet_id: string
  name: string
  background_url: string | null
  created_at: string | null
}

export interface AllocationRun {
  id: string
  scenario_id: string
  name: string | null
  status: "pending" | "running" | "done" | "error"
  config: Record<string, unknown> | null
  kpis: {
    total_flights?: number
    assigned_pct?: number
    unassigned_count?: number
    split_count?: number
    split_pct?: number
    narrow_wide_count?: number
    narrow_wide_pct?: number
  } | null
  analytics: Record<string, unknown> | null
  warnings: string[] | null
  storage_size_bytes: number
  created_at: string | null
  finished_at: string | null
}

// ─── Mapping Types ─────────────────────────────────────────────────────────────

export interface JoinSavedConfig {
  alias: string
  on_primary: string
  on_secondary: string
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

export interface Mapping {
  id: string
  scenario_id: string
  name: string
  rows: MappingRow[]
  filters: FilterRule[]
  output_filters: FilterRule[]
  dedup_by_pk: boolean
  joins: JoinSavedConfig[]
  created_at: string | null
}

// Alias used by mapping page
export type MappingConfig = Omit<Mapping, "scenario_id">

// ─── Legacy Types (kept for backward compatibility) ────────────────────────────

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
