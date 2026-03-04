export interface AllocationConfig {
  columnMapping: {
    departureTime: string
    flightNumber: string
    category: string
    positions: string
    terminal?: string
    makeupOpening?: string
    makeupClosing?: string
  }
  categoryMapping: Record<string, "Wide" | "Narrow" | "Ignore">
  terminalMapping: Record<string, string>
  makeupRules: {
    useFileColumns: boolean
    wideOffsetOpen?: number
    wideOffsetClose?: number
    narrowOffsetOpen?: number
    narrowOffsetClose?: number
  }
  timelineStep: number
  carousels: {
    terminal: string
    carouselName: string
    wideCapacity: number
    narrowCapacity: number
  }[]
  rules: {
    applyReadjustment: boolean
    ruleMulti: boolean
    ruleNarrowWide: boolean
    ruleExtras: boolean
    maxCarouselsNarrow: number
    maxCarouselsWide: number
    ruleOrder: Array<"multi" | "narrow_wide" | "extras">
  }
  extrasByTerminal: Record<string, { wide: number; narrow: number }>
}

export interface WizardStateSnapshot {
  fileMeta?: { name: string; size: number } | null
  filePreview: Record<string, unknown>[]
  fileColumns: string[]
  suggestedMapping: AllocationConfig["columnMapping"] | null
  categoryValues: string[]
  terminalValues: string[]
  columnMapping: AllocationConfig["columnMapping"]
  mappingLocked: boolean
  categoryMapping: Record<string, "Wide" | "Narrow" | "Ignore">
  terminalMapping: Record<string, string>
  makeupRules: AllocationConfig["makeupRules"]
  timelineStep: number
  carousels: AllocationConfig["carousels"]
  rules: AllocationConfig["rules"]
  extrasByTerminal: AllocationConfig["extrasByTerminal"]
}

export interface SessionState {
  currentStep: number
  wizardState: WizardStateSnapshot
  lastJobId?: string | null
  fileMeta?: { name: string; size: number } | null
  updatedAt?: string
}

export interface JobResult {
  jobId: string
  status: "queued" | "running" | "done" | "error"
  createdAt?: string
  finishedAt?: string
  kpis: {
    totalFlights: number
    assignedPct: number
    unassignedCount: number
    splitCount: number
    splitPct: number
    narrowWideCount: number
    narrowWidePct: number
  }
  warnings: Record<string, unknown>[]
  downloads: Record<string, string>
  tables: {
    flightsPreview: Record<string, unknown>[]
    unassigned: Record<string, unknown>[]
    extrasNeeded: Record<string, unknown>[]
  }
  analytics?: {
    terminalDistribution?: { terminal: string; count: number }[]
    categoryBreakdown?: { category: string; assigned: number; unassigned: number }[]
    peakHours?: { hour: string; flights: number }[]
  }
  error?: string
}

export interface PreviewResult {
  success: boolean
  preview: Record<string, unknown>[]
  columns: string[]
  suggestedMapping: AllocationConfig["columnMapping"]
  fileMeta?: { name: string; size: number }
}

const devFallbackBase =
  typeof window !== "undefined" &&
  (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1")
    ? "http://127.0.0.1:8000"
    : ""
const prodFallbackBase =
  typeof window !== "undefined" && window.location.hostname.endsWith(".vercel.app")
    ? "https://carousel-allocation-tool-production.up.railway.app"
    : ""
const API_BASE = (
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  devFallbackBase ||
  prodFallbackBase
).replace(/\/$/, "")

const SESSION_KEY = "makeup_session_id"
let sessionIdCache: string | null = null

function getSessionId(): string | null {
  if (typeof window === "undefined") return null
  if (sessionIdCache) return sessionIdCache
  const stored = window.sessionStorage.getItem(SESSION_KEY)
  if (stored) {
    sessionIdCache = stored
    return stored
  }
  const generated =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(16).slice(2)}`
  window.sessionStorage.setItem(SESSION_KEY, generated)
  sessionIdCache = generated
  return generated
}

function captureSessionId(res: Response) {
  if (typeof window === "undefined") return
  const header = res.headers.get("x-session-id")
  if (!header) return
  sessionIdCache = header
  window.sessionStorage.setItem(SESSION_KEY, header)
}

function withSessionHeaders(options: RequestInit = {}): RequestInit {
  const sessionId = getSessionId()
  if (!sessionId) return options
  const headers = new Headers(options.headers || {})
  headers.set("X-Session-Id", sessionId)
  return { ...options, headers }
}

function buildUrl(path: string): string {
  if (!path) return path
  if (path.startsWith("http://") || path.startsWith("https://")) return path
  const normalized = path.startsWith("/") ? path : `/${path}`
  return API_BASE ? `${API_BASE}${normalized}` : normalized
}

async function parseError(res: Response): Promise<string> {
  try {
    const data = await res.json()
    if (typeof data === "string") return data
    if (data && typeof data.detail === "string") return data.detail
    return JSON.stringify(data)
  } catch {
    return res.statusText
  }
}

async function fetchWithTimeout(
  url: string,
  options: RequestInit,
  timeoutMs: number
): Promise<Response> {
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs)
  try {
    return await fetch(url, { ...options, signal: controller.signal })
  } catch (error) {
    if (controller.signal.aborted) {
      throw new Error("Le serveur met trop de temps a repondre. Veuillez reessayer.")
    }
    throw error
  } finally {
    clearTimeout(timeoutId)
  }
}

function mapSuggestedMapping(suggested: Record<string, unknown> | null | undefined): AllocationConfig["columnMapping"] {
  const get = (key: string) => (typeof suggested?.[key] === "string" ? String(suggested?.[key]) : "")
  return {
    departureTime: get("DepartureTime"),
    flightNumber: get("FlightNumber"),
    category: get("Category"),
    positions: get("Positions"),
    terminal: get("Terminal") || "",
    makeupOpening: get("MakeupOpening") || "",
    makeupClosing: get("MakeupClosing") || "",
  }
}

function buildConfigPayload(config: AllocationConfig) {
  const mapping = {
    DepartureTime: config.columnMapping.departureTime || null,
    FlightNumber: config.columnMapping.flightNumber || null,
    Category: config.columnMapping.category || null,
    Positions: config.columnMapping.positions || null,
    Terminal: config.columnMapping.terminal || null,
    MakeupOpening: config.makeupRules.useFileColumns ? (config.columnMapping.makeupOpening || null) : null,
    MakeupClosing: config.makeupRules.useFileColumns ? (config.columnMapping.makeupClosing || null) : null,
  }

  const category_mapping: Record<string, string> = {}
  Object.entries(config.categoryMapping || {}).forEach(([key, value]) => {
    if (!key) return
    if (value === "Ignore") {
      category_mapping[key] = "IGNORER"
    } else {
      category_mapping[key] = value
    }
  })

  const terminal_mapping: Record<string, string> = {}
  Object.entries(config.terminalMapping || {}).forEach(([key, value]) => {
    if (!key) return
    if (!value || value === "Ignore") {
      terminal_mapping[key] = "IGNORER"
    } else {
      terminal_mapping[key] = value
    }
  })

  const carousels_by_terminal: Record<string, { name: string; wide: number; narrow: number }[]> = {}
  config.carousels.forEach((carousel) => {
    if (!carousel.terminal || !carousel.carouselName) return
    if (!carousels_by_terminal[carousel.terminal]) {
      carousels_by_terminal[carousel.terminal] = []
    }
    carousels_by_terminal[carousel.terminal].push({
      name: carousel.carouselName,
      wide: Number(carousel.wideCapacity || 0),
      narrow: Number(carousel.narrowCapacity || 0),
    })
  })

  const extras_by_terminal: Record<string, { wide: number; narrow: number }> = {}
  Object.entries(config.extrasByTerminal || {}).forEach(([terminal, cap]) => {
    if (!terminal || terminal.toLowerCase() === "ignore") return
    extras_by_terminal[terminal] = {
      wide: Number(cap.wide || 0),
      narrow: Number(cap.narrow || 0),
    }
  })

  return {
    mapping,
    category_mapping,
    terminal_mapping,
    makeup_time_mode: config.makeupRules.useFileColumns ? "columns" : "offsets",
    offsets_minutes: {
      Wide: {
        open: Number(config.makeupRules.wideOffsetOpen || 0),
        close: Number(config.makeupRules.wideOffsetClose || 0),
      },
      Narrow: {
        open: Number(config.makeupRules.narrowOffsetOpen || 0),
        close: Number(config.makeupRules.narrowOffsetClose || 0),
      },
    },
    time_step_minutes: Number(config.timelineStep || 5),
    carousels_mode: "by_terminal_file",
    carousels_by_terminal,
    rules: {
      apply_readjustment: config.rules.applyReadjustment,
      rule_multi: config.rules.ruleMulti,
      rule_narrow_wide: config.rules.ruleNarrowWide,
      rule_extras: config.rules.ruleExtras,
      rule_order: config.rules.ruleOrder || [],
      wide_can_use_narrow: true,
      narrow_can_use_wide: config.rules.ruleNarrowWide,
      max_carousels_per_flight: {
        Wide: Number(config.rules.maxCarouselsWide || 1),
        Narrow: Number(config.rules.maxCarouselsNarrow || 1),
      },
    },
    extras_by_terminal,
  }
}

function mapJobResult(payload: Record<string, unknown>): JobResult {
  const kpis = (payload.kpis as Record<string, unknown>) || {}
  const tables = (payload.tables as Record<string, unknown>) || {}
  const analytics = (payload.analytics as Record<string, unknown>) || {}
  return {
    jobId: String(payload.job_id || payload.jobId || ""),
    status: (payload.status as JobResult["status"]) || "error",
    createdAt: (payload.created_at as string) || (payload.createdAt as string),
    finishedAt: (payload.finished_at as string) || (payload.finishedAt as string),
    kpis: {
      totalFlights: Number(kpis.total_flights || 0),
      assignedPct: Number(kpis.assigned_pct || 0),
      unassignedCount: Number(kpis.unassigned_count || 0),
      splitCount: Number(kpis.split_count || 0),
      splitPct: Number(kpis.split_pct || 0),
      narrowWideCount: Number(kpis.narrow_wide_count || 0),
      narrowWidePct: Number(kpis.narrow_wide_pct || 0),
    },
    warnings: (payload.warnings as Record<string, unknown>[]) || [],
    downloads: (payload.downloads as Record<string, string>) || {},
    tables: {
      flightsPreview: (tables.flights_preview as Record<string, unknown>[]) || [],
      unassigned: (tables.unassigned as Record<string, unknown>[]) || [],
      extrasNeeded: (tables.extras_needed as Record<string, unknown>[]) || [],
    },
    analytics: {
      terminalDistribution:
        (analytics.terminal_distribution as { terminal: string; count: number }[]) || [],
      categoryBreakdown:
        (analytics.category_breakdown as {
          category: string
          assigned: number
          unassigned: number
        }[]) || [],
      peakHours:
        (analytics.peak_hours as { hour: string; flights: number }[]) || [],
    },
    error: (payload.error as string) || undefined,
  }
}

export async function runJob(
  file: File | null,
  config: AllocationConfig
): Promise<{ jobId: string }> {
  const formData = new FormData()
  if (file) {
    formData.append("file", file)
  }
  formData.append("config_json", JSON.stringify(buildConfigPayload(config)))

  const res = await fetch(
    buildUrl("/api/run"),
    withSessionHeaders({
      method: "POST",
      body: formData,
    })
  )
  if (!res.ok) {
    const message = await parseError(res)
    throw new Error(message)
  }
  captureSessionId(res)
  const data = (await res.json()) as Record<string, unknown>
  return { jobId: String(data.job_id || data.jobId || "") }
}

export async function getJob(jobId: string): Promise<JobResult> {
  const res = await fetch(
    buildUrl(`/api/jobs/${jobId}`),
    withSessionHeaders({ method: "GET" })
  )
  if (!res.ok) {
    const message = await parseError(res)
    throw new Error(message)
  }
  captureSessionId(res)
  const data = (await res.json()) as Record<string, unknown>
  return mapJobResult(data)
}

export function downloadFile(jobId: string, filenameOrPath: string): string {
  if (!filenameOrPath) return ""
  const path = filenameOrPath.startsWith("/api/")
    ? filenameOrPath
    : `/api/jobs/${jobId}/download/${filenameOrPath}`
  return buildUrl(path)
}

export async function uploadFile(file: File): Promise<PreviewResult> {
  const formData = new FormData()
  formData.append("file", file)

  const res = await fetchWithTimeout(
    buildUrl("/api/preview"),
    withSessionHeaders({
      method: "POST",
      body: formData,
    }),
    60000
  )
  if (!res.ok) {
    const message = await parseError(res)
    throw new Error(message)
  }
  captureSessionId(res)
  const data = (await res.json()) as Record<string, unknown>
  return {
    success: true,
    preview: (data.preview as Record<string, unknown>[]) || [],
    columns: (data.columns as string[]) || [],
    suggestedMapping: mapSuggestedMapping(data.suggested_mapping as Record<string, unknown>),
    fileMeta: (data.file_meta as { name: string; size: number }) || undefined,
  }
}

export async function autoDetectMapping(
  file: File
): Promise<AllocationConfig["columnMapping"]> {
  const preview = await uploadFile(file)
  return preview.suggestedMapping
}

export async function inspectFile(
  file: File | null,
  columnMapping: AllocationConfig["columnMapping"]
): Promise<{ categories: string[]; terminals: string[] }> {
  const formData = new FormData()
  if (file) {
    formData.append("file", file)
  }
  formData.append(
    "config_json",
    JSON.stringify({
      mapping: {
        DepartureTime: columnMapping.departureTime || null,
        FlightNumber: columnMapping.flightNumber || null,
        Category: columnMapping.category || null,
        Positions: columnMapping.positions || null,
        Terminal: columnMapping.terminal || null,
        MakeupOpening: columnMapping.makeupOpening || null,
        MakeupClosing: columnMapping.makeupClosing || null,
      },
    })
  )

  const res = await fetch(
    buildUrl("/api/inspect"),
    withSessionHeaders({
      method: "POST",
      body: formData,
    })
  )
  if (!res.ok) {
    const message = await parseError(res)
    throw new Error(message)
  }
  captureSessionId(res)
  const data = (await res.json()) as Record<string, unknown>
  return {
    categories: (data.categories as string[]) || [],
    terminals: (data.terminals as string[]) || [],
  }
}

export async function validateCarouselsFile(
  file: File
): Promise<{
  valid: boolean
  carousels: { terminal: string; carouselName: string; wideCapacity: number; narrowCapacity: number }[]
  errors: string[]
}> {
  const formData = new FormData()
  formData.append("file", file)

  const res = await fetch(
    buildUrl("/api/carousels/validate"),
    withSessionHeaders({
      method: "POST",
      body: formData,
    })
  )
  if (!res.ok) {
    const message = await parseError(res)
    throw new Error(message)
  }
  captureSessionId(res)
  const data = (await res.json()) as Record<string, unknown>
  return {
    valid: Boolean(data.valid),
    carousels:
      (data.carousels as {
        terminal: string
        carouselName: string
        wideCapacity: number
        narrowCapacity: number
      }[]) || [],
    errors: (data.errors as string[]) || [],
  }
}

export async function getSessionState(): Promise<SessionState | null> {
  const res = await fetch(buildUrl("/api/session/state"), withSessionHeaders({ method: "GET" }))
  if (!res.ok) {
    return null
  }
  captureSessionId(res)
  const data = (await res.json()) as Record<string, unknown>
  return {
    currentStep: Number(data.current_step || 1),
    wizardState: (data.wizard_state as WizardStateSnapshot) || ({} as WizardStateSnapshot),
    lastJobId: (data.last_job_id as string) || null,
    fileMeta: (data.file_meta as { name: string; size: number }) || undefined,
    updatedAt: (data.updated_at as string) || undefined,
  }
}

export async function setSessionState(payload: {
  currentStep: number
  wizardState: WizardStateSnapshot
}): Promise<SessionState | null> {
  const sessionInit = withSessionHeaders()
  const headers = new Headers(sessionInit.headers || {})
  headers.set("Content-Type", "application/json")

  const res = await fetch(buildUrl("/api/session/state"), {
    method: "POST",
    headers,
    body: JSON.stringify({
      current_step: payload.currentStep,
      wizard_state: payload.wizardState,
    }),
  })
  if (!res.ok) {
    return null
  }
  captureSessionId(res)
  const data = (await res.json()) as Record<string, unknown>
  return {
    currentStep: Number(data.current_step || 1),
    wizardState: (data.wizard_state as WizardStateSnapshot) || ({} as WizardStateSnapshot),
    lastJobId: (data.last_job_id as string) || null,
    fileMeta: (data.file_meta as { name: string; size: number }) || undefined,
    updatedAt: (data.updated_at as string) || undefined,
  }
}
