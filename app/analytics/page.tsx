"use client"

import { useEffect, useMemo, useState } from "react"
import {
  BarChart3,
  Bell,
  Calendar,
  Filter,
  Layers,
  LineChart,
  PieChart,
  Plus,
  Settings,
  Table2,
  Trash2,
  TrendingUp,
} from "lucide-react"
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart as RechartsLineChart,
  Pie,
  PieChart as RechartsPieChart,
  XAxis,
  YAxis,
} from "recharts"

import {
  createCustomKPI,
  deleteCustomKPI,
  getCustomKPIs,
  getJob,
  getJobs,
  getSessionState,
  type CustomKPI,
  type JobResult,
  type JobSummary,
} from "@/lib/api"
import { AppShell } from "@/components/app-shell"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import {
  ChartContainer,
  ChartLegend,
  ChartLegendContent,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import dynamic from "next/dynamic"

const PivotExplorer = dynamic(
  () => import("@/components/pivot-explorer").then((m) => ({ default: m.PivotExplorer })),
  { ssr: false, loading: () => <div className="flex h-[400px] items-center justify-center text-sm text-muted-foreground">Chargement de l&apos;explorateur...</div> }
)

const EXPLORER_SOURCES = [
  { id: "flights",    label: "Vols" },
  { id: "unassigned", label: "Non assignes" },
  { id: "extras",     label: "Make-ups extras" },
  { id: "terminal",   label: "Par terminal" },
  { id: "category",   label: "Par categorie" },
  { id: "carousel",   label: "Par carrousel" },
  { id: "peak_hours", label: "Par heure" },
  { id: "occupancy",  label: "Occupation carousels" },
  { id: "history",    label: "Historique" },
]
const EXPLORER_PAGE_SIZE = 50

const AVAILABLE_METRICS: { value: string; label: string; type: "percentage" | "counter" }[] = [
  { value: "assigned_pct", label: "Taux d'assignation (%)", type: "percentage" },
  { value: "unassigned_count", label: "Vols non assignes", type: "counter" },
  { value: "total_flights", label: "Total vols", type: "counter" },
  { value: "split_count", label: "Vols splittes", type: "counter" },
  { value: "split_pct", label: "Taux de splits (%)", type: "percentage" },
  { value: "narrow_wide_count", label: "Reassignations narrow/wide", type: "counter" },
  { value: "narrow_wide_pct", label: "Taux reassignations (%)", type: "percentage" },
  { value: "extras_count", label: "Make-ups supplementaires", type: "counter" },
]

function resolveMetricValue(metric: string, job: JobResult | null): string {
  if (!job) return "—"
  switch (metric) {
    case "assigned_pct": return `${job.kpis.assignedPct}%`
    case "unassigned_count": return `${job.kpis.unassignedCount}`
    case "total_flights": return `${job.kpis.totalFlights}`
    case "split_count": return `${job.kpis.splitCount}`
    case "split_pct": return `${job.kpis.splitPct}%`
    case "narrow_wide_count": return `${job.kpis.narrowWideCount}`
    case "narrow_wide_pct": return `${job.kpis.narrowWidePct}%`
    case "extras_count": return `${job.tables.extrasNeeded?.length || 0}`
    default: return "—"
  }
}

function resolveMetricNumber(metric: string, job: JobResult | null): number | null {
  if (!job) return null
  switch (metric) {
    case "assigned_pct": return job.kpis.assignedPct
    case "unassigned_count": return job.kpis.unassignedCount
    case "total_flights": return job.kpis.totalFlights
    case "split_count": return job.kpis.splitCount
    case "split_pct": return job.kpis.splitPct
    case "narrow_wide_count": return job.kpis.narrowWideCount
    case "narrow_wide_pct": return job.kpis.narrowWidePct
    case "extras_count": return job.tables.extrasNeeded?.length || 0
    default: return null
  }
}

const TERMINAL_COLORS = [
  "hsl(var(--primary))",
  "hsl(var(--chart-2))",
  "hsl(var(--chart-3))",
  "hsl(var(--chart-4))",
  "hsl(var(--chart-5))",
]

const COLOR_PALETTES: Record<string, string[]> = {
  default: ["hsl(var(--primary))", "hsl(var(--chart-2))", "hsl(var(--chart-3))", "hsl(var(--chart-4))", "hsl(var(--chart-5))", "#f97316", "#8b5cf6", "#06b6d4"],
  warm:    ["#ef4444", "#f97316", "#f59e0b", "#eab308", "#dc2626", "#ea580c", "#d97706", "#ca8a04"],
  cool:    ["#3b82f6", "#06b6d4", "#10b981", "#6366f1", "#2563eb", "#0891b2", "#059669", "#4f46e5"],
  pastel:  ["#fca5a5", "#fdba74", "#fde68a", "#a7f3d0", "#bfdbfe", "#c4b5fd", "#f9a8d4", "#86efac"],
  mono:    ["#1e293b", "#334155", "#475569", "#64748b", "#94a3b8", "#cbd5e1", "#0f172a", "#e2e8f0"],
}

type ExplorerAgg = "count" | "sum" | "avg" | "value"
type ExplorerFieldKind = "numeric" | "temporal" | "text"

function pad2(value: number): string {
  return value.toString().padStart(2, "0")
}

function parseDateValue(value: unknown): number | null {
  if (value instanceof Date) {
    const time = value.getTime()
    return isNaN(time) ? null : time
  }
  const text = String(value ?? "").trim()
  if (!text) return null
  const time = new Date(text).getTime()
  return isNaN(time) ? null : time
}

function formatLocalDayKey(date: Date): string {
  return `${date.getFullYear()}-${pad2(date.getMonth() + 1)}-${pad2(date.getDate())}`
}

function formatLocalDay(date: Date): string {
  return `${pad2(date.getDate())}/${pad2(date.getMonth() + 1)}`
}

function formatLocalTime(date: Date): string {
  return `${pad2(date.getHours())}:${pad2(date.getMinutes())}`
}

function formatTimeChartValue(value: number, includeDate: boolean): string {
  const date = new Date(value)
  if (isNaN(date.getTime())) return String(value)
  return includeDate ? `${formatLocalDay(date)} ${formatLocalTime(date)}` : formatLocalTime(date)
}

function isBlankValue(value: unknown): boolean {
  if (value === null || value === undefined) return true
  if (Array.isArray(value)) return value.length === 0
  return String(value).trim() === ""
}

function isNumericValue(value: unknown): boolean {
  if (typeof value === "number") return Number.isFinite(value)
  if (typeof value === "string") {
    const s = value.trim()
    if (!s) return false
    return !isNaN(Number(s))
  }
  return false
}

function getExplorerFieldKind(data: Record<string, unknown>[], field: string): ExplorerFieldKind {
  const values = data.map(row => row[field]).filter(v => !isBlankValue(v)).slice(0, 200)
  if (values.length === 0) return "text"
  if (isTimeField(field) && values.some(v => parseDateValue(v) !== null)) return "temporal"
  const numericCount = values.filter(isNumericValue).length
  return numericCount / values.length >= 0.7 ? "numeric" : "text"
}

function getDefaultExplorerAgg(data: Record<string, unknown>[], field: string): ExplorerAgg {
  const kind = getExplorerFieldKind(data, field)
  if (kind === "numeric") return "sum"
  if (kind === "temporal") return "value"
  return "count"
}

function hasMultipleTimeDays(data: Record<string, unknown>[], field: string): boolean {
  const days = new Set<string>()
  for (const row of data) {
    const time = parseDateValue(row[field])
    if (time === null) continue
    days.add(formatLocalDayKey(new Date(time)))
    if (days.size > 1) return true
  }
  return false
}

function buildTimeBucketInfo(val: string, granularityMin: number | null, includeDate: boolean): {
  key: string
  label: string
  sortValue: number
} {
  const time = parseDateValue(val)
  if (time === null) {
    return {
      key: val,
      label: val,
      sortValue: Number.MAX_SAFE_INTEGER,
    }
  }

  if (granularityMin === null) {
    const date = new Date(time)
    return {
      key: String(time),
      label: formatTimeChartValue(time, includeDate),
      sortValue: time,
    }
  }

  const bucketDate = new Date(time)
  const totalMin = bucketDate.getHours() * 60 + bucketDate.getMinutes()
  const bucketed = Math.floor(totalMin / granularityMin) * granularityMin
  bucketDate.setHours(0, 0, 0, 0)
  bucketDate.setMinutes(bucketed)

  return {
    key: `${formatLocalDayKey(bucketDate)} ${formatLocalTime(bucketDate)}`,
    label: formatTimeChartValue(bucketDate.getTime(), includeDate),
    sortValue: bucketDate.getTime(),
  }
}

function toPlottableValue(value: unknown, fieldKind: ExplorerFieldKind): number | null {
  if (fieldKind === "numeric") return isNumericValue(value) ? Number(value) : null
  if (fieldKind === "temporal") return parseDateValue(value)
  return null
}

function aggregateExplorerValues(
  rawVals: unknown[],
  yField: string,
  agg: ExplorerAgg,
  fieldKind: ExplorerFieldKind,
): number {
  if (yField === "_count") return rawVals.length
  if (agg === "count") {
    return rawVals.filter(v => !isBlankValue(v)).length
  }
  if (agg === "value") {
    return rawVals.map(v => toPlottableValue(v, fieldKind)).find((v): v is number => v !== null) ?? 0
  }
  const scalars = rawVals
    .map(v => toPlottableValue(v, fieldKind))
    .filter((v): v is number => v !== null)
  if (agg === "sum") {
    return scalars.reduce((acc, v) => acc + v, 0)
  }
  return scalars.length > 0 ? scalars.reduce((a, b) => a + b, 0) / scalars.length : 0
}

function isTimeField(field: string): boolean {
  return /time|opening|closing|date/i.test(field)
}

function formatDate(iso?: string) {
  if (!iso) return "—"
  try {
    return new Date(iso).toLocaleString("fr-FR", {
      day: "2-digit",
      month: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    })
  } catch {
    return iso
  }
}

export default function AnalyticsPage() {
  const [terminalFilter, setTerminalFilter] = useState("all")
  const [job, setJob] = useState<JobResult | null>(null)
  const [allJobs, setAllJobs] = useState<JobSummary[]>([])
  const [isLoading, setIsLoading] = useState(true)

  // KPI Builder state
  const [customKPIs, setCustomKPIs] = useState<CustomKPI[]>([])
  const [dialogOpen, setDialogOpen] = useState(false)
  const [kpiName, setKpiName] = useState("")
  const [kpiMetric, setKpiMetric] = useState("assigned_pct")
  const [kpiDescription, setKpiDescription] = useState("")
  const [kpiAlertEnabled, setKpiAlertEnabled] = useState(false)
  const [kpiAlertOperator, setKpiAlertOperator] = useState<"lt" | "gt">("lt")
  const [kpiAlertThreshold, setKpiAlertThreshold] = useState("")
  const [kpiSaving, setKpiSaving] = useState(false)
  const [kpiError, setKpiError] = useState("")

  // Explorateur
  const [explorerViewMode, setExplorerViewMode] = useState<"table" | "chart">("table")
  const [explorerFilters, setExplorerFilters] = useState<Record<string, string>>({})
  const [explorerHiddenCols, setExplorerHiddenCols] = useState<Record<string, boolean>>({})
  const [explorerSortField, setExplorerSortField] = useState("")
  const [explorerSortDir, setExplorerSortDir] = useState<"asc" | "desc">("asc")
  const [explorerPage, setExplorerPage] = useState(0)
  const [explorerXField, setExplorerXField] = useState("")
  const [explorerYField, setExplorerYField] = useState("")
  const [explorerGroupField, setExplorerGroupField] = useState("")
  const [explorerAgg, setExplorerAgg] = useState<ExplorerAgg>("count")
  const [timelineGranularity, setTimelineGranularity] = useState(15)
  const [explorerGranularity, setExplorerGranularity] = useState<number | null>(null)
  const [colorPalette, setColorPalette] = useState<"default" | "warm" | "cool" | "pastel" | "mono">("default")
  const [explorerCustomTitle, setExplorerCustomTitle] = useState("")
  const [explorerLegendLabel, setExplorerLegendLabel] = useState("")
  const [explorerShowLegend, setExplorerShowLegend] = useState(false)
  const [overviewCustomWidgets, setOverviewCustomWidgets] = useState<{
    id: string; title: string; source: string; xField: string; yField: string; groupField: string; chartType: string
  }[]>([])
  const [addWidgetOpen, setAddWidgetOpen] = useState(false)
  const [newWidgetSource, setNewWidgetSource] = useState("flights")
  const [newWidgetXField, setNewWidgetXField] = useState("")
  const [newWidgetYField, setNewWidgetYField] = useState("_count")
  const [newWidgetGroupField, setNewWidgetGroupField] = useState("")
  const [newWidgetChartType, setNewWidgetChartType] = useState("bar")
  const [newWidgetTitle, setNewWidgetTitle] = useState("")
  const [explorerChartType, setExplorerChartType] = useState("bar")

  // Chart type state for each chart panel
  const [chartTypes, setChartTypes] = useState<Record<string, string>>({
    assignmentRate: "area",
    terminalDist: "pie",
    categoryBreakdown: "bar_h",
    peakHours: "bar",
    carouselLoad: "bar",
    carouselTimeline: "area",
  })

  function setChartType(panel: string, type: string) {
    setChartTypes((prev) => ({ ...prev, [panel]: type }))
  }

  type ChartTypeBtn = { key: string; icon: React.ReactNode; label: string }
  function ChartTypeToggle({ panel, options }: { panel: string; options: ChartTypeBtn[] }) {
    return (
      <div className="flex items-center gap-1">
        {options.map((opt) => (
          <button
            key={opt.key}
            title={opt.label}
            onClick={() => setChartType(panel, opt.key)}
            className={`rounded p-1 transition-colors ${
              chartTypes[panel] === opt.key
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:bg-muted hover:text-foreground"
            }`}
          >
            {opt.icon}
          </button>
        ))}
      </div>
    )
  }

  useEffect(() => {
    let active = true

    async function loadData() {
      setIsLoading(true)
      try {
        const [session, jobs, kpis] = await Promise.all([
          getSessionState(),
          getJobs(100),
          getCustomKPIs(),
        ])
        if (active) setCustomKPIs(kpis)
        if (!active) return

        setAllJobs(jobs)

        const lastJobId = session?.lastJobId
        if (lastJobId) {
          try {
            const result = await getJob(lastJobId)
            if (active) setJob(result)
          } catch {
            // job not found — try first from list
            if (active && jobs.length > 0) {
              const first = await getJob(jobs[0].jobId)
              if (active) setJob(first)
            }
          }
        } else if (jobs.length > 0) {
          const first = await getJob(jobs[0].jobId)
          if (active) setJob(first)
        }
      } catch {
        if (active) setJob(null)
      } finally {
        if (active) setIsLoading(false)
      }
    }

    loadData()

    return () => { active = false }
  }, [])

  const hasJob = Boolean(job)

  // ── Trend data (all runs sorted oldest → newest) ───────────────────────
  const trendsData = useMemo(() => {
    const sorted = [...allJobs].sort((a, b) =>
      (a.createdAt || "").localeCompare(b.createdAt || "")
    )
    return sorted.map((j, i) => ({
      run: `#${i + 1}`,
      date: formatDate(j.createdAt),
      assignmentRate: j.kpis.assignedPct,
      totalFlights: j.kpis.totalFlights,
      unassigned: j.kpis.unassignedCount,
    }))
  }, [allJobs])

  // ── Current job analytics ──────────────────────────────────────────────
  const terminalDistribution = useMemo(() => {
    const items = job?.analytics?.terminalDistribution || []
    const total = items.reduce((s, i) => s + i.count, 0)
    return items.map((item, index) => ({
      name: item.terminal,
      value: item.count,
      pct: total > 0 ? Math.round((item.count / total) * 100) : 0,
      color: TERMINAL_COLORS[index % TERMINAL_COLORS.length],
    }))
  }, [job])

  const filteredTerminalDistribution = useMemo(() => {
    if (terminalFilter === "all") return terminalDistribution
    return terminalDistribution.filter((item) => item.name === terminalFilter)
  }, [terminalDistribution, terminalFilter])

  const terminalChartConfig: ChartConfig = useMemo(() => {
    const config: ChartConfig = {}
    filteredTerminalDistribution.forEach((item) => {
      config[item.name] = { label: item.name, color: item.color }
    })
    return config
  }, [filteredTerminalDistribution])

  const categoryBreakdown = useMemo(
    () => job?.analytics?.categoryBreakdown || [],
    [job]
  )

  const peakHoursData = useMemo(
    () => job?.analytics?.peakHours || [],
    [job]
  )

  const carouselBreakdown = useMemo(
    () => job?.analytics?.carouselBreakdown || [],
    [job]
  )

  const carouselChartConfig: ChartConfig = {
    count: { label: "Vols", color: "hsl(var(--primary))" },
  }

  const timelineOccupancyData = useMemo(() => {
    const flights = job?.tables?.flightsPreview || []
    const windows: { carousel: string; open: number; close: number }[] = []
    flights.forEach(f => {
      const carouselRaw = String(f["AssignedCarousel"] ?? f["AssignedCarousels"] ?? "").trim()
      if (!carouselRaw || carouselRaw.toUpperCase() === "UNASSIGNED") return
      const open = new Date(String(f["MakeupOpening"] ?? "")).getTime()
      const close = new Date(String(f["MakeupClosing"] ?? "")).getTime()
      if (isNaN(open) || isNaN(close) || close <= open) return
      carouselRaw.split("+").map(c => c.trim()).filter(Boolean).forEach(c => {
        windows.push({ carousel: c, open, close })
      })
    })
    if (windows.length === 0) return []
    const minTime = Math.min(...windows.map(w => w.open))
    const maxTime = Math.max(...windows.map(w => w.close))
    const stepMs = timelineGranularity * 60 * 1000
    const slots: { time: string; occupied: number }[] = []
    for (let t = minTime; t <= maxTime; t += stepMs) {
      const active = new Set<string>()
      windows.forEach(w => { if (w.open <= t && w.close > t) active.add(w.carousel) })
      slots.push({
        time: new Date(t).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" }),
        occupied: active.size,
      })
    }
    return slots
  }, [job, timelineGranularity])

  const timelineChartConfig: ChartConfig = {
    occupied: { label: "Carousels actifs", color: "hsl(var(--primary))" },
  }

  const kpiWidgets = useMemo(() => {
    if (!job) return []
    const assignedCount = Math.max(job.kpis.totalFlights - job.kpis.unassignedCount, 0)
    const extrasCount = job.tables.extrasNeeded?.length || 0
    return [
      {
        id: "rate",
        title: "Taux d'assignation",
        value: `${job.kpis.assignedPct}%`,
        sub: `${assignedCount} / ${job.kpis.totalFlights} vols`,
        icon: TrendingUp,
        highlight: job.kpis.assignedPct >= 90,
      },
      {
        id: "flights",
        title: "Vols assignes",
        value: `${assignedCount}`,
        sub: `sur ${job.kpis.totalFlights} total`,
        icon: Layers,
        highlight: false,
      },
      {
        id: "unassigned",
        title: "Vols non assignes",
        value: `${job.kpis.unassignedCount}`,
        sub: `${job.kpis.assignedPct < 100 ? 100 - job.kpis.assignedPct : 0}% non couverts`,
        icon: Calendar,
        highlight: false,
      },
      {
        id: "extras",
        title: "Extras necessaires",
        value: `${extrasCount}`,
        sub: `makeups supplementaires`,
        icon: BarChart3,
        highlight: false,
      },
    ]
  }, [job])

  const terminalOptions = useMemo(() => {
    return terminalDistribution.map((item) => item.name)
  }, [terminalDistribution])

  useEffect(() => {
    if (terminalFilter !== "all" && !terminalOptions.includes(terminalFilter)) {
      setTerminalFilter("all")
    }
  }, [terminalFilter, terminalOptions])

  const areaChartConfig: ChartConfig = {
    assignmentRate: { label: "Taux d'assignation (%)", color: "hsl(var(--primary))" },
  }

  const barChartConfig: ChartConfig = {
    assigned: { label: "Assignes", color: "hsl(var(--primary))" },
    unassigned: { label: "Non assignes", color: "hsl(var(--destructive))" },
  }

  const peakChartConfig: ChartConfig = {
    flights: { label: "Vols", color: "hsl(var(--primary))" },
  }

  const trendsChartConfig: ChartConfig = {
    assignmentRate: { label: "Taux d'assignation (%)", color: "hsl(var(--primary))" },
    unassigned: { label: "Non assignes", color: "hsl(var(--destructive))" },
  }

  // ── Explorateur helpers ───────────────────────────────────────────────
  function getExplorerColumns(data: Record<string, unknown>[]): string[] {
    if (data.length === 0) return []
    return Object.keys(data[0])
  }

  function applyExplorerFilters(data: Record<string, unknown>[]): Record<string, unknown>[] {
    return data.filter(row =>
      Object.entries(explorerFilters).every(([col, val]) => {
        if (!val) return true
        return String(row[col] ?? "").toLowerCase().includes(val.toLowerCase())
      })
    )
  }

  function applyExplorerSort(data: Record<string, unknown>[]): Record<string, unknown>[] {
    if (!explorerSortField) return data
    return [...data].sort((a, b) => {
      const va = a[explorerSortField], vb = b[explorerSortField]
      const na = Number(va), nb = Number(vb)
      const cmp = !isNaN(na) && !isNaN(nb) ? na - nb : String(va ?? "").localeCompare(String(vb ?? ""))
      return explorerSortDir === "asc" ? cmp : -cmp
    })
  }

  function buildExplorerChartData(data: Record<string, unknown>[]): { name: string; value: number }[] {
    if (!explorerXField || !explorerYField) return []
    const isTimeX = isTimeField(explorerXField)
    const showDateOnX = isTimeX && hasMultipleTimeDays(data, explorerXField)
    const yFieldKind = explorerYField === "_count" ? "numeric" : getExplorerFieldKind(data, explorerYField)
    const groups: Record<string, { label: string; sortValue: number; values: unknown[] }> = {}
    data.forEach(row => {
      const rawX = explorerXField === "_count" ? "1" : String(row[explorerXField] ?? "(vide)")
      const bucket = isTimeX
        ? buildTimeBucketInfo(rawX, explorerGranularity, showDateOnX)
        : { key: rawX, label: rawX, sortValue: Number.MAX_SAFE_INTEGER }
      if (!groups[bucket.key]) groups[bucket.key] = { label: bucket.label, sortValue: bucket.sortValue, values: [] }
      groups[bucket.key].values.push(explorerYField === "_count" ? 1 : row[explorerYField])
    })
    const entries = Object.values(groups).map(group => {
      const value = aggregateExplorerValues(group.values, explorerYField, explorerAgg, yFieldKind)
      return {
        name: group.label,
        value: Math.round(value * 100) / 100,
        sortValue: group.sortValue,
      }
    })
    if (isTimeX) {
      return entries.sort((a, b) => a.sortValue - b.sortValue).map(({ name, value }) => ({ name, value }))
    }
    return entries.sort((a, b) => b.value - a.value).map(({ name, value }) => ({ name, value }))
  }

  function buildExplorerStackedData(data: Record<string, unknown>[]): {
    rows: Record<string, string | number>[]
    groupKeys: string[]
  } {
    if (!explorerXField || !explorerGroupField) return { rows: [], groupKeys: [] }
    const isTimeX = isTimeField(explorerXField)
    const showDateOnX = isTimeX && hasMultipleTimeDays(data, explorerXField)
    const yFieldKind = explorerYField === "_count" ? "numeric" : getExplorerFieldKind(data, explorerYField)
    const matrix: Record<string, { label: string; sortValue: number; groups: Record<string, unknown[]> }> = {}
    const allGroupVals = new Set<string>()
    data.forEach(row => {
      const rawX = explorerXField === "_count" ? "Vols" : String(row[explorerXField] ?? "(vide)")
      const bucket = isTimeX
        ? buildTimeBucketInfo(rawX, explorerGranularity, showDateOnX)
        : { key: rawX, label: rawX, sortValue: Number.MAX_SAFE_INTEGER }
      const gKey = explorerGroupField === "_count" ? "Vols" : (String(row[explorerGroupField] ?? "(vide)").trim() || "(vide)")
      allGroupVals.add(gKey)
      if (!matrix[bucket.key]) {
        matrix[bucket.key] = { label: bucket.label, sortValue: bucket.sortValue, groups: {} }
      }
      if (!matrix[bucket.key].groups[gKey]) matrix[bucket.key].groups[gKey] = []
      matrix[bucket.key].groups[gKey].push(explorerYField === "_count" ? 1 : row[explorerYField])
    })
    const groupKeys = Array.from(allGroupVals).sort()
    const rows = Object.entries(matrix)
      .map(([_, bucket]) => {
        const row: Record<string, string | number> = { name: bucket.label, __sortValue: bucket.sortValue }
        groupKeys.forEach(g => {
          const rawVals = bucket.groups[g] || []
          row[g] = Math.round(aggregateExplorerValues(rawVals, explorerYField, explorerAgg, yFieldKind) * 100) / 100
        })
        return row
      })
      .sort((a, b) => isTimeX ? Number(a.__sortValue) - Number(b.__sortValue) : String(a.name).localeCompare(String(b.name)))
      .map(({ __sortValue, ...row }) => row)
    return { rows, groupKeys }
  }

  function openNewKPIDialog() {
    setKpiName("")
    setKpiMetric("assigned_pct")
    setKpiDescription("")
    setKpiAlertEnabled(false)
    setKpiAlertOperator("lt")
    setKpiAlertThreshold("")
    setKpiError("")
    setDialogOpen(true)
  }

  async function handleSaveKPI() {
    if (!kpiName.trim()) {
      setKpiError("Le nom est requis.")
      return
    }
    setKpiSaving(true)
    setKpiError("")
    try {
      const metaInfo = AVAILABLE_METRICS.find((m) => m.value === kpiMetric)
      const created = await createCustomKPI({
        name: kpiName.trim(),
        metric: kpiMetric,
        displayType: metaInfo?.type || "counter",
        description: kpiDescription.trim(),
        alertEnabled: kpiAlertEnabled,
        alertOperator: kpiAlertOperator,
        alertThreshold: kpiAlertEnabled ? parseFloat(kpiAlertThreshold) || 0 : 0,
      })
      setCustomKPIs((prev) => [...prev, created])
      setDialogOpen(false)
    } catch (e: unknown) {
      setKpiError(e instanceof Error ? e.message : "Erreur lors de la sauvegarde.")
    } finally {
      setKpiSaving(false)
    }
  }

  async function handleDeleteKPI(kpiId: string) {
    try {
      await deleteCustomKPI(kpiId)
      setCustomKPIs((prev) => prev.filter((k) => k.kpiId !== kpiId))
    } catch {
      // ignore
    }
  }

  return (
    <AppShell>
      <div className="container mx-auto max-w-7xl px-4 py-8">
        {/* Header */}
        <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-2xl font-bold">Analytics</h1>
            <p className="mt-1 text-muted-foreground">
              Tableau de bord analytique et KPIs personnalisables
            </p>
            {allJobs.length > 0 && (
              <p className="mt-1 text-sm text-muted-foreground">
                {allJobs.length} scenario{allJobs.length > 1 ? "s" : ""} disponible{allJobs.length > 1 ? "s" : ""}
              </p>
            )}
          </div>
          <div className="flex flex-wrap gap-2">
            <Select value={terminalFilter} onValueChange={setTerminalFilter}>
              <SelectTrigger className="w-44">
                <Filter className="mr-2 h-4 w-4" />
                <SelectValue placeholder="Tous les terminaux" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Tous les terminaux</SelectItem>
                {terminalOptions.map((terminal) => (
                  <SelectItem key={terminal} value={terminal}>
                    {terminal}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        {isLoading && (
          <Alert className="mb-6">
            <AlertDescription>Chargement des scenarios...</AlertDescription>
          </Alert>
        )}

        {!isLoading && !hasJob && (
          <Alert className="mb-6">
            <AlertDescription>
              Aucun scenario disponible. Lancez une allocation pour alimenter les analytics.
            </AlertDescription>
          </Alert>
        )}

        {/* KPI Widgets */}
        {hasJob && (
          <div className="mb-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {kpiWidgets.map((kpi) => (
              <Card key={kpi.id}>
                <CardHeader className="flex flex-row items-center justify-between pb-2">
                  <CardTitle className="text-sm font-medium text-muted-foreground">
                    {kpi.title}
                  </CardTitle>
                  <kpi.icon className="h-4 w-4 text-muted-foreground" />
                </CardHeader>
                <CardContent>
                  <div className="flex items-baseline gap-2">
                    <span className={`text-2xl font-bold ${kpi.highlight ? "text-primary" : ""}`}>
                      {kpi.value}
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">{kpi.sub}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        )}

        {/* Charts Grid */}
        <Tabs defaultValue="overview" className="space-y-4">
          <TabsList>
            <TabsTrigger value="overview">Vue d{"'"}ensemble</TabsTrigger>
            <TabsTrigger value="trends">
              Tendances
              {allJobs.length > 1 && (
                <Badge variant="secondary" className="ml-2 text-xs">
                  {allJobs.length}
                </Badge>
              )}
            </TabsTrigger>
            <TabsTrigger value="builder">KPI Builder</TabsTrigger>
            <TabsTrigger value="explorer">Explorateur</TabsTrigger>
          </TabsList>

          {/* ── OVERVIEW TAB ── */}
          <TabsContent value="overview" className="space-y-4">
            {!hasJob && !isLoading && (
              <p className="text-center text-muted-foreground py-12">
                Lancez une allocation pour voir les graphiques.
              </p>
            )}
            {hasJob && (
              <>
              <div className="flex justify-end">
                <Button variant="outline" size="sm" onClick={() => {
                  setNewWidgetTitle(""); setNewWidgetSource("flights"); setNewWidgetXField(""); setNewWidgetYField("_count"); setNewWidgetGroupField(""); setNewWidgetChartType("bar"); setAddWidgetOpen(true)
                }}>
                  <Plus className="mr-1.5 h-4 w-4" />
                  Ajouter un graphique
                </Button>
              </div>
              <div className="grid gap-4 lg:grid-cols-2">
                {/* Assignment Rate */}
                <Card>
                  <CardHeader>
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <CardTitle className="flex items-center gap-2">
                          <LineChart className="h-5 w-5" />
                          Evolution du taux d{"'"}assignation
                        </CardTitle>
                        <CardDescription>
                          {allJobs.length > 1
                            ? `${allJobs.length} scenarios`
                            : "Dernier scenario — " + formatDate(job?.createdAt)}
                        </CardDescription>
                      </div>
                      <ChartTypeToggle panel="assignmentRate" options={[
                        { key: "area", icon: <TrendingUp className="h-3.5 w-3.5" />, label: "Aire" },
                        { key: "line", icon: <LineChart className="h-3.5 w-3.5" />, label: "Ligne" },
                        { key: "bar", icon: <BarChart3 className="h-3.5 w-3.5" />, label: "Barres" },
                        { key: "table", icon: <Table2 className="h-3.5 w-3.5" />, label: "Tableau" },
                      ]} />
                    </div>
                  </CardHeader>
                  <CardContent>
                    {(() => {
                      const data = trendsData.length > 0 ? trendsData : [{ run: "1", date: formatDate(job?.createdAt), assignmentRate: job?.kpis.assignedPct ?? 0, totalFlights: job?.kpis.totalFlights ?? 0, unassigned: job?.kpis.unassignedCount ?? 0 }]
                      if (chartTypes.assignmentRate === "table") {
                        return (
                          <div className="overflow-x-auto">
                            <table className="w-full text-sm">
                              <thead>
                                <tr className="border-b text-left text-muted-foreground">
                                  <th className="pb-2 pr-4 font-medium">Run</th>
                                  <th className="pb-2 pr-4 font-medium">Date</th>
                                  <th className="pb-2 pr-4 font-medium">Taux assignation</th>
                                  <th className="pb-2 pr-4 font-medium">Total vols</th>
                                  <th className="pb-2 font-medium">Non assignes</th>
                                </tr>
                              </thead>
                              <tbody>
                                {data.map((row) => (
                                  <tr key={row.run} className="border-b last:border-0 hover:bg-muted/50">
                                    <td className="py-2 pr-4 font-mono text-xs text-muted-foreground">{row.run}</td>
                                    <td className="py-2 pr-4">{row.date}</td>
                                    <td className="py-2 pr-4 font-semibold">{row.assignmentRate}%</td>
                                    <td className="py-2 pr-4">{row.totalFlights}</td>
                                    <td className="py-2">{row.unassigned}</td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        )
                      }
                      return (
                        <ChartContainer config={areaChartConfig} className="h-[300px]">
                          {chartTypes.assignmentRate === "bar" ? (
                            <BarChart data={data}>
                              <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                              <XAxis dataKey="run" className="text-xs" />
                              <YAxis domain={[0, 100]} className="text-xs" unit="%" />
                              <ChartTooltip content={<ChartTooltipContent />} />
                              <Bar dataKey="assignmentRate" fill="var(--color-assignmentRate)" radius={[4, 4, 0, 0]} />
                            </BarChart>
                          ) : chartTypes.assignmentRate === "line" ? (
                            <RechartsLineChart data={data}>
                              <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                              <XAxis dataKey="run" className="text-xs" />
                              <YAxis domain={[0, 100]} className="text-xs" unit="%" />
                              <ChartTooltip content={<ChartTooltipContent />} />
                              <Line type="monotone" dataKey="assignmentRate" stroke="var(--color-assignmentRate)" strokeWidth={2} dot={{ r: 4 }} />
                            </RechartsLineChart>
                          ) : (
                            <AreaChart data={data}>
                              <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                              <XAxis dataKey="run" className="text-xs" />
                              <YAxis domain={[0, 100]} className="text-xs" unit="%" />
                              <ChartTooltip content={<ChartTooltipContent />} />
                              <Area type="monotone" dataKey="assignmentRate" stroke="var(--color-assignmentRate)" fill="var(--color-assignmentRate)" fillOpacity={0.2} strokeWidth={2} />
                            </AreaChart>
                          )}
                        </ChartContainer>
                      )
                    })()}
                  </CardContent>
                </Card>

                {/* Terminal Distribution */}
                <Card>
                  <CardHeader>
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <CardTitle className="flex items-center gap-2">
                          <PieChart className="h-5 w-5" />
                          Repartition par terminal
                        </CardTitle>
                        <CardDescription>Distribution des vols</CardDescription>
                      </div>
                      <ChartTypeToggle panel="terminalDist" options={[
                        { key: "pie", icon: <PieChart className="h-3.5 w-3.5" />, label: "Camembert" },
                        { key: "bar", icon: <BarChart3 className="h-3.5 w-3.5" />, label: "Barres" },
                        { key: "table", icon: <Table2 className="h-3.5 w-3.5" />, label: "Tableau" },
                      ]} />
                    </div>
                  </CardHeader>
                  <CardContent>
                    {filteredTerminalDistribution.length === 0 ? (
                      <div className="flex h-[300px] items-center justify-center text-muted-foreground text-sm">
                        Aucune donnee de terminal disponible
                      </div>
                    ) : chartTypes.terminalDist === "table" ? (
                      <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                          <thead>
                            <tr className="border-b text-left text-muted-foreground">
                              <th className="pb-2 pr-4 font-medium">Terminal</th>
                              <th className="pb-2 pr-4 font-medium">Vols</th>
                              <th className="pb-2 font-medium">Pourcentage</th>
                            </tr>
                          </thead>
                          <tbody>
                            {filteredTerminalDistribution.map((item) => (
                              <tr key={item.name} className="border-b last:border-0 hover:bg-muted/50">
                                <td className="py-2 pr-4 flex items-center gap-2">
                                  <div className="h-3 w-3 rounded-full shrink-0" style={{ backgroundColor: item.color }} />
                                  {item.name}
                                </td>
                                <td className="py-2 pr-4 font-semibold">{item.value}</td>
                                <td className="py-2">{item.pct}%</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    ) : chartTypes.terminalDist === "bar" ? (
                      <ChartContainer config={terminalChartConfig} className="h-[300px]">
                        <BarChart data={filteredTerminalDistribution}>
                          <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                          <XAxis dataKey="name" className="text-xs" />
                          <YAxis className="text-xs" />
                          <ChartTooltip content={<ChartTooltipContent />} />
                          <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                            {filteredTerminalDistribution.map((entry, index) => (
                              <Cell key={`cell-${index}`} fill={entry.color} />
                            ))}
                          </Bar>
                        </BarChart>
                      </ChartContainer>
                    ) : (
                      <>
                        <div className="flex h-[260px] items-center justify-center">
                          <ChartContainer config={terminalChartConfig} className="h-[240px] w-[240px]">
                            <RechartsPieChart>
                              <ChartTooltip content={<ChartTooltipContent />} />
                              <Pie
                                data={filteredTerminalDistribution}
                                dataKey="value"
                                nameKey="name"
                                cx="50%"
                                cy="50%"
                                innerRadius={60}
                                outerRadius={100}
                                strokeWidth={2}
                              >
                                {filteredTerminalDistribution.map((entry, index) => (
                                  <Cell key={`cell-${index}`} fill={entry.color} />
                                ))}
                              </Pie>
                            </RechartsPieChart>
                          </ChartContainer>
                        </div>
                        <div className="mt-2 flex flex-wrap justify-center gap-4">
                          {filteredTerminalDistribution.map((item) => (
                            <div key={item.name} className="flex items-center gap-2">
                              <div className="h-3 w-3 rounded-full" style={{ backgroundColor: item.color }} />
                              <span className="text-sm">{item.name}: {item.value} vols ({item.pct}%)</span>
                            </div>
                          ))}
                        </div>
                      </>
                    )}
                  </CardContent>
                </Card>

                {/* Category Breakdown */}
                <Card>
                  <CardHeader>
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <CardTitle className="flex items-center gap-2">
                          <BarChart3 className="h-5 w-5" />
                          Assignation par categorie
                        </CardTitle>
                        <CardDescription>Wide vs Narrow — assignes et non assignes</CardDescription>
                      </div>
                      <ChartTypeToggle panel="categoryBreakdown" options={[
                        { key: "bar_h", icon: <BarChart3 className="h-3.5 w-3.5 rotate-90" />, label: "Barres horizontales" },
                        { key: "bar_v", icon: <BarChart3 className="h-3.5 w-3.5" />, label: "Barres verticales" },
                        { key: "table", icon: <Table2 className="h-3.5 w-3.5" />, label: "Tableau" },
                      ]} />
                    </div>
                  </CardHeader>
                  <CardContent>
                    {categoryBreakdown.length === 0 ? (
                      <div className="flex h-[300px] items-center justify-center text-muted-foreground text-sm">
                        Aucune donnee de categorie disponible
                      </div>
                    ) : chartTypes.categoryBreakdown === "table" ? (
                      <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                          <thead>
                            <tr className="border-b text-left text-muted-foreground">
                              <th className="pb-2 pr-4 font-medium">Categorie</th>
                              <th className="pb-2 pr-4 font-medium">Assignes</th>
                              <th className="pb-2 pr-4 font-medium">Non assignes</th>
                              <th className="pb-2 font-medium">Total</th>
                            </tr>
                          </thead>
                          <tbody>
                            {categoryBreakdown.map((row) => (
                              <tr key={row.category} className="border-b last:border-0 hover:bg-muted/50">
                                <td className="py-2 pr-4 font-medium">{row.category}</td>
                                <td className="py-2 pr-4 text-primary font-semibold">{row.assigned}</td>
                                <td className="py-2 pr-4 text-destructive">{row.unassigned}</td>
                                <td className="py-2">{row.assigned + row.unassigned}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    ) : chartTypes.categoryBreakdown === "bar_v" ? (
                      <ChartContainer config={barChartConfig} className="h-[300px]">
                        <BarChart data={categoryBreakdown}>
                          <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                          <XAxis dataKey="category" className="text-xs" />
                          <YAxis className="text-xs" />
                          <ChartTooltip content={<ChartTooltipContent />} />
                          <Bar dataKey="assigned" stackId="a" fill="var(--color-assigned)" />
                          <Bar dataKey="unassigned" stackId="a" fill="var(--color-unassigned)" radius={[4, 4, 0, 0]} />
                        </BarChart>
                      </ChartContainer>
                    ) : (
                      <ChartContainer config={barChartConfig} className="h-[300px]">
                        <BarChart data={categoryBreakdown} layout="vertical">
                          <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                          <XAxis type="number" className="text-xs" />
                          <YAxis dataKey="category" type="category" className="text-xs" width={60} />
                          <ChartTooltip content={<ChartTooltipContent />} />
                          <Bar dataKey="assigned" stackId="a" fill="var(--color-assigned)" />
                          <Bar dataKey="unassigned" stackId="a" fill="var(--color-unassigned)" radius={[0, 4, 4, 0]} />
                        </BarChart>
                      </ChartContainer>
                    )}
                  </CardContent>
                </Card>

                {/* Carousel Load */}
                <Card className="lg:col-span-2">
                  <CardHeader>
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <CardTitle className="flex items-center gap-2">
                          <Layers className="h-5 w-5" />
                          Charge par carrousel
                        </CardTitle>
                        <CardDescription>Nombre de vols assignes a chaque carrousel</CardDescription>
                      </div>
                      <ChartTypeToggle panel="carouselLoad" options={[
                        { key: "bar", icon: <BarChart3 className="h-3.5 w-3.5" />, label: "Barres" },
                        { key: "bar_h", icon: <BarChart3 className="h-3.5 w-3.5 rotate-90" />, label: "Barres horizontales" },
                        { key: "table", icon: <Table2 className="h-3.5 w-3.5" />, label: "Tableau" },
                      ]} />
                    </div>
                  </CardHeader>
                  <CardContent>
                    {carouselBreakdown.length === 0 ? (
                      <div className="flex h-[300px] items-center justify-center text-muted-foreground text-sm">
                        Aucune donnee de carrousel disponible
                      </div>
                    ) : chartTypes.carouselLoad === "table" ? (
                      <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                          <thead>
                            <tr className="border-b text-left text-muted-foreground">
                              <th className="pb-2 pr-4 font-medium">Carrousel</th>
                              <th className="pb-2 pr-4 font-medium">Terminal</th>
                              <th className="pb-2 font-medium">Vols</th>
                            </tr>
                          </thead>
                          <tbody>
                            {carouselBreakdown.map((row) => (
                              <tr key={`${row.terminal}-${row.carousel}`} className="border-b last:border-0 hover:bg-muted/50">
                                <td className="py-2 pr-4 font-medium">{row.carousel}</td>
                                <td className="py-2 pr-4 text-muted-foreground">{row.terminal}</td>
                                <td className="py-2 font-semibold">{row.count}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    ) : chartTypes.carouselLoad === "bar_h" ? (
                      <ChartContainer config={carouselChartConfig} className="h-[300px]">
                        <BarChart data={carouselBreakdown.map(d => ({ name: d.carousel, count: d.count }))} layout="vertical">
                          <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                          <XAxis type="number" className="text-xs" />
                          <YAxis dataKey="name" type="category" className="text-xs" width={80} />
                          <ChartTooltip content={<ChartTooltipContent />} />
                          <Bar dataKey="count" fill="var(--color-count)" radius={[0, 4, 4, 0]} />
                        </BarChart>
                      </ChartContainer>
                    ) : (
                      <ChartContainer config={carouselChartConfig} className="h-[300px]">
                        <BarChart data={carouselBreakdown.map(d => ({ name: d.carousel, count: d.count }))}>
                          <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                          <XAxis dataKey="name" className="text-xs" />
                          <YAxis className="text-xs" />
                          <ChartTooltip content={<ChartTooltipContent />} />
                          <Bar dataKey="count" fill="var(--color-count)" radius={[4, 4, 0, 0]} />
                        </BarChart>
                      </ChartContainer>
                    )}
                  </CardContent>
                </Card>

                {/* Timeline Occupation des Carousels */}
                <Card className="lg:col-span-2">
                  <CardHeader>
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <CardTitle className="flex items-center gap-2">
                          <TrendingUp className="h-5 w-5" />
                          Occupation des carousels dans le temps
                        </CardTitle>
                        <CardDescription>
                          Nombre de carousels actifs a chaque instant (fenetres MakeupOpening → MakeupClosing)
                        </CardDescription>
                      </div>
                      <div className="flex items-center gap-2">
                        {/* Granularity selector */}
                        <div className="flex items-center gap-1 rounded border p-0.5">
                          {[5, 10, 15, 30].map(g => (
                            <button
                              key={g}
                              onClick={() => setTimelineGranularity(g)}
                              className={`rounded px-2 py-1 text-xs transition-colors ${
                                timelineGranularity === g
                                  ? "bg-primary text-primary-foreground"
                                  : "text-muted-foreground hover:bg-muted"
                              }`}
                            >
                              {g}min
                            </button>
                          ))}
                        </div>
                        <ChartTypeToggle panel="carouselTimeline" options={[
                          { key: "area", icon: <TrendingUp className="h-3.5 w-3.5" />, label: "Aire" },
                          { key: "line", icon: <LineChart className="h-3.5 w-3.5" />, label: "Ligne" },
                          { key: "bar", icon: <BarChart3 className="h-3.5 w-3.5" />, label: "Barres" },
                          { key: "table", icon: <Table2 className="h-3.5 w-3.5" />, label: "Tableau" },
                        ]} />
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent>
                    {timelineOccupancyData.length === 0 ? (
                      <div className="flex h-[300px] items-center justify-center text-muted-foreground text-sm">
                        Aucune donnee d{"'"}occupation disponible (MakeupOpening/MakeupClosing requis)
                      </div>
                    ) : chartTypes.carouselTimeline === "table" ? (
                      <div className="overflow-x-auto max-h-[300px]">
                        <table className="w-full text-sm">
                          <thead>
                            <tr className="border-b text-left text-muted-foreground">
                              <th className="pb-2 pr-4 font-medium">Heure</th>
                              <th className="pb-2 font-medium">Carousels actifs</th>
                            </tr>
                          </thead>
                          <tbody>
                            {timelineOccupancyData.map((row, i) => (
                              <tr key={i} className="border-b last:border-0 hover:bg-muted/50">
                                <td className="py-1.5 pr-4 font-mono text-xs">{row.time}</td>
                                <td className="py-1.5 font-semibold">{row.occupied}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    ) : (
                      <ChartContainer config={timelineChartConfig} className="h-[300px]">
                        {chartTypes.carouselTimeline === "bar" ? (
                          <BarChart data={timelineOccupancyData}>
                            <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                            <XAxis dataKey="time" className="text-xs" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
                            <YAxis className="text-xs" allowDecimals={false} />
                            <ChartTooltip content={<ChartTooltipContent />} />
                            <Bar dataKey="occupied" fill="var(--color-occupied)" radius={[4, 4, 0, 0]} />
                          </BarChart>
                        ) : chartTypes.carouselTimeline === "line" ? (
                          <RechartsLineChart data={timelineOccupancyData}>
                            <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                            <XAxis dataKey="time" className="text-xs" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
                            <YAxis className="text-xs" allowDecimals={false} />
                            <ChartTooltip content={<ChartTooltipContent />} />
                            <Line type="stepAfter" dataKey="occupied" stroke="var(--color-occupied)" strokeWidth={2} dot={false} />
                          </RechartsLineChart>
                        ) : (
                          <AreaChart data={timelineOccupancyData}>
                            <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                            <XAxis dataKey="time" className="text-xs" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
                            <YAxis className="text-xs" allowDecimals={false} />
                            <ChartTooltip content={<ChartTooltipContent />} />
                            <Area type="stepAfter" dataKey="occupied" stroke="var(--color-occupied)" fill="var(--color-occupied)" fillOpacity={0.2} strokeWidth={2} />
                          </AreaChart>
                        )}
                      </ChartContainer>
                    )}
                  </CardContent>
                </Card>

                {/* Peak Hours */}
                <Card>
                  <CardHeader>
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <CardTitle className="flex items-center gap-2">
                          <Calendar className="h-5 w-5" />
                          Distribution horaire des vols
                        </CardTitle>
                        <CardDescription>Heures de pointe</CardDescription>
                      </div>
                      <ChartTypeToggle panel="peakHours" options={[
                        { key: "bar", icon: <BarChart3 className="h-3.5 w-3.5" />, label: "Barres" },
                        { key: "line", icon: <LineChart className="h-3.5 w-3.5" />, label: "Ligne" },
                        { key: "area", icon: <TrendingUp className="h-3.5 w-3.5" />, label: "Aire" },
                        { key: "table", icon: <Table2 className="h-3.5 w-3.5" />, label: "Tableau" },
                      ]} />
                    </div>
                  </CardHeader>
                  <CardContent>
                    {peakHoursData.length === 0 ? (
                      <div className="flex h-[300px] items-center justify-center text-muted-foreground text-sm">
                        Aucune donnee horaire disponible
                      </div>
                    ) : chartTypes.peakHours === "table" ? (
                      <div className="overflow-x-auto max-h-[300px]">
                        <table className="w-full text-sm">
                          <thead>
                            <tr className="border-b text-left text-muted-foreground">
                              <th className="pb-2 pr-4 font-medium">Heure</th>
                              <th className="pb-2 font-medium">Vols</th>
                            </tr>
                          </thead>
                          <tbody>
                            {peakHoursData.map((row) => (
                              <tr key={row.hour} className="border-b last:border-0 hover:bg-muted/50">
                                <td className="py-2 pr-4">{row.hour}</td>
                                <td className="py-2 font-semibold">{row.flights}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    ) : (
                      <ChartContainer config={peakChartConfig} className="h-[300px]">
                        {chartTypes.peakHours === "line" ? (
                          <RechartsLineChart data={peakHoursData}>
                            <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                            <XAxis dataKey="hour" className="text-xs" interval={1} />
                            <YAxis className="text-xs" />
                            <ChartTooltip content={<ChartTooltipContent />} />
                            <Line type="monotone" dataKey="flights" stroke="var(--color-flights)" strokeWidth={2} dot={{ r: 3 }} />
                          </RechartsLineChart>
                        ) : chartTypes.peakHours === "area" ? (
                          <AreaChart data={peakHoursData}>
                            <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                            <XAxis dataKey="hour" className="text-xs" interval={1} />
                            <YAxis className="text-xs" />
                            <ChartTooltip content={<ChartTooltipContent />} />
                            <Area type="monotone" dataKey="flights" stroke="var(--color-flights)" fill="var(--color-flights)" fillOpacity={0.2} strokeWidth={2} />
                          </AreaChart>
                        ) : (
                          <BarChart data={peakHoursData}>
                            <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                            <XAxis dataKey="hour" className="text-xs" interval={1} />
                            <YAxis className="text-xs" />
                            <ChartTooltip content={<ChartTooltipContent />} />
                            <Bar dataKey="flights" fill="var(--color-flights)" radius={[4, 4, 0, 0]} />
                          </BarChart>
                        )}
                      </ChartContainer>
                    )}
                  </CardContent>
                </Card>
              </div>

              {/* ── Custom widgets added by user ── */}
              {overviewCustomWidgets.length > 0 && (
                <div className="grid gap-4 lg:grid-cols-2">
                  {overviewCustomWidgets.map(w => {
                    const wRaw = (() => {
                      if (!job) return []
                      switch (w.source) {
                        case "flights":    return job.tables.flightsPreview || []
                        case "unassigned": return job.tables.unassigned || []
                        case "extras":     return job.tables.extrasNeeded || []
                        case "terminal":   return (job.analytics?.terminalDistribution || []).map(d => ({ Terminal: d.terminal, Vols: d.count }))
                        case "category":   return (job.analytics?.categoryBreakdown || []).map(d => ({ Categorie: d.category, Assignes: d.assigned, "Non assignes": d.unassigned }))
                        case "carousel":   return (job.analytics?.carouselBreakdown || []).map(d => ({ Carrousel: d.carousel, Terminal: d.terminal, Vols: d.count }))
                        case "peak_hours": return (job.analytics?.peakHours || []).map(d => ({ Heure: d.hour, Vols: d.flights }))
                        case "occupancy":  return timelineOccupancyData.map(d => ({ Heure: d.time, "Carousels actifs": d.occupied }))
                        default: return []
                      }
                    })()
                    const wColors = COLOR_PALETTES[colorPalette] ?? COLOR_PALETTES.default
                    const wCfg: ChartConfig = { value: { label: w.yField === "_count" ? "Nombre" : w.yField, color: wColors[0] } }
                    // Simple aggregation
                    const wGroups: Record<string, number> = {}
                    wRaw.forEach(row => {
                      const xKey = w.xField ? String(row[w.xField] ?? "(vide)") : "(tout)"
                      const val = w.yField === "_count" ? 1 : Number(row[w.yField] ?? 0)
                      wGroups[xKey] = (wGroups[xKey] || 0) + val
                    })
                    const wData = Object.entries(wGroups).map(([name, value]) => ({ name, value })).sort((a, b) => b.value - a.value).slice(0, 20)
                    return (
                      <Card key={w.id}>
                        <CardHeader>
                          <div className="flex items-start justify-between gap-2">
                            <div>
                              <CardTitle className="text-sm font-medium flex items-center gap-2">
                                <BarChart3 className="h-4 w-4" />
                                {w.title || `${w.xField} → ${w.yField === "_count" ? "Nombre" : w.yField}`}
                              </CardTitle>
                              <CardDescription className="text-xs">{wData.length} groupes — source: {w.source}</CardDescription>
                            </div>
                            <button onClick={() => setOverviewCustomWidgets(prev => prev.filter(x => x.id !== w.id))} className="text-muted-foreground hover:text-destructive text-xs" title="Supprimer">✕</button>
                          </div>
                        </CardHeader>
                        <CardContent>
                          {wData.length === 0 ? (
                            <div className="flex h-[240px] items-center justify-center text-muted-foreground text-sm">Aucune donnee</div>
                          ) : w.chartType === "table" ? (
                            <div className="overflow-x-auto max-h-[240px]">
                              <table className="w-full text-sm">
                                <thead><tr className="border-b text-left text-muted-foreground"><th className="pb-2 pr-4 font-medium">{w.xField || "Groupe"}</th><th className="pb-2 font-medium">{w.yField === "_count" ? "Nombre" : w.yField}</th></tr></thead>
                                <tbody>{wData.map((r, i) => <tr key={i} className="border-b last:border-0 hover:bg-muted/50"><td className="py-1.5 pr-4 truncate max-w-[160px]">{r.name}</td><td className="py-1.5 font-semibold">{r.value}</td></tr>)}</tbody>
                              </table>
                            </div>
                          ) : w.chartType === "line" ? (
                            <ChartContainer config={wCfg} className="h-[240px]">
                              <RechartsLineChart data={wData}><CartesianGrid strokeDasharray="3 3" className="stroke-muted" /><XAxis dataKey="name" tick={{ fontSize: 10 }} /><YAxis className="text-xs" /><ChartTooltip content={<ChartTooltipContent />} /><Line type="monotone" dataKey="value" stroke={wColors[0]} strokeWidth={2} dot={{ r: 3 }} /></RechartsLineChart>
                            </ChartContainer>
                          ) : w.chartType === "area" ? (
                            <ChartContainer config={wCfg} className="h-[240px]">
                              <AreaChart data={wData}><CartesianGrid strokeDasharray="3 3" className="stroke-muted" /><XAxis dataKey="name" tick={{ fontSize: 10 }} /><YAxis className="text-xs" /><ChartTooltip content={<ChartTooltipContent />} /><Area type="monotone" dataKey="value" stroke={wColors[0]} fill={wColors[0]} fillOpacity={0.2} strokeWidth={2} /></AreaChart>
                            </ChartContainer>
                          ) : (
                            <ChartContainer config={wCfg} className="h-[240px]">
                              <BarChart data={wData}><CartesianGrid strokeDasharray="3 3" className="stroke-muted" /><XAxis dataKey="name" tick={{ fontSize: 10 }} /><YAxis className="text-xs" /><ChartTooltip content={<ChartTooltipContent />} /><Bar dataKey="value" fill={wColors[0]} radius={[4,4,0,0]} /></BarChart>
                            </ChartContainer>
                          )}
                        </CardContent>
                      </Card>
                    )
                  })}
                </div>
              )}
              </>
            )}
          </TabsContent>

          {/* ── TRENDS TAB ── */}
          <TabsContent value="trends">
            {allJobs.length === 0 && !isLoading && (
              <Card>
                <CardContent className="flex h-[300px] items-center justify-center">
                  <div className="text-center">
                    <LineChart className="mx-auto h-12 w-12 text-muted-foreground" />
                    <p className="mt-4 text-lg font-medium">Aucun historique disponible</p>
                    <p className="text-muted-foreground">Lancez plusieurs allocations pour voir les tendances.</p>
                  </div>
                </CardContent>
              </Card>
            )}
            {allJobs.length > 0 && (
              <div className="space-y-4">
                {/* Trend chart */}
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <TrendingUp className="h-5 w-5" />
                      Evolution du taux d{"'"}assignation
                    </CardTitle>
                    <CardDescription>
                      {allJobs.length} scenario{allJobs.length > 1 ? "s" : ""} — du plus ancien au plus recent
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <ChartContainer config={trendsChartConfig} className="h-[320px]">
                      <RechartsLineChart data={trendsData}>
                        <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                        <XAxis dataKey="run" className="text-xs" />
                        <YAxis yAxisId="left" domain={[0, 100]} className="text-xs" unit="%" />
                        <YAxis yAxisId="right" orientation="right" className="text-xs" />
                        <ChartTooltip
                          content={({ active, payload, label }) => {
                            if (!active || !payload?.length) return null
                            const d = trendsData.find((t) => t.run === label)
                            return (
                              <div className="rounded-lg border bg-background p-3 text-sm shadow-md">
                                <p className="font-semibold">{label} — {d?.date}</p>
                                {payload.map((p) => (
                                  <p key={p.name} style={{ color: p.color }}>
                                    {p.name === "assignmentRate" ? "Taux d'assignation" : "Non assignes"}: {p.value}
                                    {p.name === "assignmentRate" ? "%" : ""}
                                  </p>
                                ))}
                                <p className="text-muted-foreground mt-1">Total vols: {d?.totalFlights}</p>
                              </div>
                            )
                          }}
                        />
                        <Line
                          yAxisId="left"
                          type="monotone"
                          dataKey="assignmentRate"
                          stroke="var(--color-assignmentRate)"
                          strokeWidth={2}
                          dot={{ r: 4 }}
                          activeDot={{ r: 6 }}
                        />
                        <Line
                          yAxisId="right"
                          type="monotone"
                          dataKey="unassigned"
                          stroke="var(--color-unassigned)"
                          strokeWidth={2}
                          strokeDasharray="4 2"
                          dot={{ r: 3 }}
                        />
                      </RechartsLineChart>
                    </ChartContainer>
                    <div className="mt-3 flex gap-6 justify-center text-sm">
                      <span className="flex items-center gap-2">
                        <span className="inline-block h-0.5 w-5 bg-primary" />
                        Taux d{"'"}assignation (axe gauche, %)
                      </span>
                      <span className="flex items-center gap-2">
                        <span className="inline-block h-0.5 w-5 bg-destructive border-dashed" style={{ borderTop: "2px dashed" }} />
                        Vols non assignes (axe droit)
                      </span>
                    </div>
                  </CardContent>
                </Card>

                {/* History table */}
                <Card>
                  <CardHeader>
                    <CardTitle>Historique des scenarios</CardTitle>
                    <CardDescription>{allJobs.length} execution{allJobs.length > 1 ? "s" : ""}</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b text-left text-muted-foreground">
                            <th className="pb-2 pr-4 font-medium">Run</th>
                            <th className="pb-2 pr-4 font-medium">Date</th>
                            <th className="pb-2 pr-4 font-medium">Total vols</th>
                            <th className="pb-2 pr-4 font-medium">Taux assignation</th>
                            <th className="pb-2 pr-4 font-medium">Non assignes</th>
                            <th className="pb-2 font-medium">Splits</th>
                          </tr>
                        </thead>
                        <tbody>
                          {[...allJobs]
                            .sort((a, b) => (b.createdAt || "").localeCompare(a.createdAt || ""))
                            .map((j, i) => (
                              <tr key={j.jobId} className="border-b last:border-0 hover:bg-muted/50">
                                <td className="py-2 pr-4 font-mono text-xs text-muted-foreground">
                                  #{allJobs.length - i}
                                </td>
                                <td className="py-2 pr-4">{formatDate(j.createdAt)}</td>
                                <td className="py-2 pr-4">{j.kpis.totalFlights}</td>
                                <td className="py-2 pr-4">
                                  <span
                                    className={`font-semibold ${
                                      j.kpis.assignedPct >= 95
                                        ? "text-green-600"
                                        : j.kpis.assignedPct >= 80
                                        ? "text-yellow-600"
                                        : "text-destructive"
                                    }`}
                                  >
                                    {j.kpis.assignedPct}%
                                  </span>
                                </td>
                                <td className="py-2 pr-4">{j.kpis.unassignedCount}</td>
                                <td className="py-2">{j.kpis.splitCount}</td>
                              </tr>
                            ))}
                        </tbody>
                      </table>
                    </div>
                  </CardContent>
                </Card>
              </div>
            )}
          </TabsContent>

          {/* ── KPI BUILDER TAB ── */}
          <TabsContent value="builder" className="space-y-6">

            {/* ── KPI section ── */}
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-lg font-semibold">Indicateurs (KPI)</h2>
                  <p className="text-sm text-muted-foreground">Valeurs numeriques avec alertes optionnelles</p>
                </div>
                <Button onClick={openNewKPIDialog}>
                  <Plus className="mr-2 h-4 w-4" />
                  Nouveau KPI
                </Button>
              </div>

            {/* Custom KPIs grid with live values */}
            {customKPIs.length === 0 ? (
              <Card>
                <CardContent className="flex h-[160px] flex-col items-center justify-center gap-3 text-center">
                  <div className="flex h-14 w-14 items-center justify-center rounded-full bg-muted">
                    <Settings className="h-7 w-7 text-muted-foreground" />
                  </div>
                  <p className="font-medium">Aucun KPI personnalise</p>
                  <p className="max-w-xs text-sm text-muted-foreground">
                    Cliquez sur <strong>Nouveau KPI</strong> pour creer votre premier indicateur.
                  </p>
                </CardContent>
              </Card>
            ) : (
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {customKPIs.map((kpi) => {
                  const currentValue = resolveMetricValue(kpi.metric, job)
                  const numValue = resolveMetricNumber(kpi.metric, job)
                  const isAlert =
                    kpi.alertEnabled &&
                    numValue !== null &&
                    (kpi.alertOperator === "lt"
                      ? numValue < kpi.alertThreshold
                      : numValue > kpi.alertThreshold)
                  return (
                    <Card key={kpi.kpiId} className={isAlert ? "border-destructive" : ""}>
                      <CardHeader className="flex flex-row items-start justify-between pb-1">
                        <div className="flex-1 min-w-0">
                          <CardTitle className="flex items-center gap-2 text-sm font-medium truncate">
                            {isAlert && <Bell className="h-3.5 w-3.5 shrink-0 text-destructive" />}
                            {kpi.name}
                          </CardTitle>
                          {kpi.description && (
                            <CardDescription className="text-xs mt-0.5 truncate">
                              {kpi.description}
                            </CardDescription>
                          )}
                        </div>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7 shrink-0 text-muted-foreground hover:text-destructive"
                          onClick={() => handleDeleteKPI(kpi.kpiId)}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </CardHeader>
                      <CardContent>
                        <p className={`text-2xl font-bold ${isAlert ? "text-destructive" : ""}`}>
                          {currentValue}
                        </p>
                        {kpi.alertEnabled && (
                          <p className="mt-1 text-xs text-muted-foreground">
                            Alerte si {kpi.alertOperator === "lt" ? "<" : ">"} {kpi.alertThreshold}
                            {kpi.displayType === "percentage" ? "%" : ""}
                          </p>
                        )}
                        {!hasJob && (
                          <p className="mt-1 text-xs text-muted-foreground italic">
                            Lancez une allocation pour voir la valeur
                          </p>
                        )}
                      </CardContent>
                    </Card>
                  )
                })}
              </div>
            )}

            {/* Available metrics reference */}
            <Card>
              <CardHeader>
                <CardTitle className="text-sm font-medium">Metriques disponibles</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
                  {AVAILABLE_METRICS.map((m) => (
                    <div key={m.value} className="rounded-md border px-3 py-2 text-sm">
                      <p className="font-medium">{m.label}</p>
                      <p className="text-xs text-muted-foreground">
                        {m.type === "percentage" ? "Pourcentage" : "Compteur"}
                        {hasJob ? ` — ${resolveMetricValue(m.value, job)}` : ""}
                      </p>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
            </div>{/* end KPI section */}
          </TabsContent>

          {/* ── EXPLORATEUR TAB ── */}
          <TabsContent value="explorer" className="space-y-4">
            {/* TODO_EXPLORER_CONTENT */}
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold">Explorateur de donnees</h2>
                <p className="text-sm text-muted-foreground">Explorez toutes les donnees, filtrez et construisez vos graphiques</p>
              </div>
              <div className="flex items-center gap-2">
                <button onClick={() => setExplorerViewMode("table")} className={`rounded-md border px-3 py-1.5 text-sm transition-colors ${explorerViewMode === "table" ? "bg-primary text-primary-foreground border-primary" : "hover:bg-muted"}`}>
                  <Table2 className="inline mr-1.5 h-3.5 w-3.5" />Tableau
                </button>
                <button onClick={() => setExplorerViewMode("chart")} className={`rounded-md border px-3 py-1.5 text-sm transition-colors ${explorerViewMode === "chart" ? "bg-primary text-primary-foreground border-primary" : "hover:bg-muted"}`}>
                  <BarChart3 className="inline mr-1.5 h-3.5 w-3.5" />Pivot
                </button>
              </div>
            </div>

            {!hasJob && (
              <Card><CardContent className="py-12 text-center text-muted-foreground text-sm">Lancez une allocation pour explorer les donnees.</CardContent></Card>
            )}

            {hasJob && (() => {
              // Source unique : toujours tous les vols avec tous les champs
              const raw = job?.tables?.flightsPreview || []
              const cols = getExplorerColumns(raw)
              const filtered = applyExplorerFilters(raw)
              const sorted = applyExplorerSort(filtered)
              const visibleCols = cols.filter(c => !explorerHiddenCols[c])
              const totalPages = Math.ceil(sorted.length / EXPLORER_PAGE_SIZE)
              const pageData = sorted.slice(explorerPage * EXPLORER_PAGE_SIZE, (explorerPage + 1) * EXPLORER_PAGE_SIZE)

              if (explorerViewMode === "table") {
                return (
                  <Card>
                    <CardContent className="pt-4 px-0">
                      {/* Column visibility + global info */}
                      <div className="flex flex-wrap items-center gap-2 px-4 pb-3 border-b">
                        <span className="text-sm text-muted-foreground">{filtered.length} lignes</span>
                        <div className="ml-auto flex flex-wrap gap-1 max-h-20 overflow-y-auto">
                          {cols.map(c => (
                            <button
                              key={c}
                              onClick={() => setExplorerHiddenCols(prev => ({ ...prev, [c]: !prev[c] }))}
                              className={`rounded border px-2 py-0.5 text-xs transition-colors ${explorerHiddenCols[c] ? "opacity-40 line-through" : "bg-muted"}`}
                              title={explorerHiddenCols[c] ? "Afficher la colonne" : "Masquer la colonne"}
                            >
                              {c}
                            </button>
                          ))}
                        </div>
                      </div>

                      {/* Filter row */}
                      <div className="flex items-center gap-2 px-4 py-2 border-b bg-muted/30 overflow-x-auto">
                        {visibleCols.map(c => (
                          <input
                            key={c}
                            value={explorerFilters[c] ?? ""}
                            onChange={e => { setExplorerFilters(prev => ({ ...prev, [c]: e.target.value })); setExplorerPage(0) }}
                            placeholder={`Filtrer ${c}...`}
                            className="min-w-[100px] flex-1 rounded border bg-background px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-primary"
                          />
                        ))}
                        {Object.values(explorerFilters).some(Boolean) && (
                          <button onClick={() => setExplorerFilters({})} className="shrink-0 text-xs text-muted-foreground hover:text-destructive">✕ Effacer</button>
                        )}
                      </div>

                      {/* Table */}
                      <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                          <thead>
                            <tr className="border-b text-left bg-muted/20">
                              {visibleCols.map(c => (
                                <th
                                  key={c}
                                  className="px-3 py-2 font-medium cursor-pointer select-none whitespace-nowrap hover:bg-muted/50"
                                  onClick={() => {
                                    if (explorerSortField === c) setExplorerSortDir(d => d === "asc" ? "desc" : "asc")
                                    else { setExplorerSortField(c); setExplorerSortDir("asc") }
                                  }}
                                >
                                  {c}
                                  {explorerSortField === c && <span className="ml-1 text-primary">{explorerSortDir === "asc" ? "↑" : "↓"}</span>}
                                </th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {pageData.length === 0 ? (
                              <tr><td colSpan={visibleCols.length} className="px-3 py-8 text-center text-muted-foreground">Aucun resultat</td></tr>
                            ) : pageData.map((row, i) => (
                              <tr key={i} className="border-b last:border-0 hover:bg-muted/40">
                                {visibleCols.map(c => (
                                  <td key={c} className="px-3 py-1.5 text-xs whitespace-nowrap max-w-[200px] truncate">{String(row[c] ?? "")}</td>
                                ))}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>

                      {/* Pagination */}
                      {totalPages > 1 && (
                        <div className="flex items-center justify-between px-4 pt-3 border-t">
                          <span className="text-xs text-muted-foreground">Page {explorerPage + 1} / {totalPages}</span>
                          <div className="flex gap-2">
                            <Button variant="outline" size="sm" disabled={explorerPage === 0} onClick={() => setExplorerPage(p => p - 1)}>Precedent</Button>
                            <Button variant="outline" size="sm" disabled={explorerPage >= totalPages - 1} onClick={() => setExplorerPage(p => p + 1)}>Suivant</Button>
                          </div>
                        </div>
                      )}
                    </CardContent>
                  </Card>
                )
              }

              // ── Pivot mode ──
              return <PivotExplorer data={filtered} rowCount={filtered.length} />
            })()}
          </TabsContent>

        </Tabs>
      </div>

      {/* ── Add Widget Dialog ── */}
      <Dialog open={addWidgetOpen} onOpenChange={setAddWidgetOpen}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>Ajouter un graphique a la vue d{"'"}ensemble</DialogTitle>
            <DialogDescription>Configurez votre graphique puis cliquez sur Ajouter.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-1.5">
              <Label>Titre (optionnel)</Label>
              <Input placeholder="Mon graphique..." value={newWidgetTitle} onChange={e => setNewWidgetTitle(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label>Source de donnees</Label>
              <div className="flex flex-wrap gap-1">
                {EXPLORER_SOURCES.filter(s => s.id !== "history").map(s => (
                  <button key={s.id} onClick={() => { setNewWidgetSource(s.id); setNewWidgetXField(""); setNewWidgetYField("_count"); setNewWidgetGroupField("") }}
                    className={`rounded border px-2 py-1 text-xs transition-colors ${newWidgetSource === s.id ? "bg-primary text-primary-foreground border-primary" : "hover:bg-muted"}`}>
                    {s.label}
                  </button>
                ))}
              </div>
            </div>
            {(() => {
              const wRaw = (() => {
                if (!job) return []
                switch (newWidgetSource) {
                  case "flights":    return job.tables.flightsPreview || []
                  case "unassigned": return job.tables.unassigned || []
                  case "extras":     return job.tables.extrasNeeded || []
                  case "terminal":   return (job.analytics?.terminalDistribution || []).map(d => ({ Terminal: d.terminal, Vols: d.count }))
                  case "category":   return (job.analytics?.categoryBreakdown || []).map(d => ({ Categorie: d.category, Assignes: d.assigned, "Non assignes": d.unassigned }))
                  case "carousel":   return (job.analytics?.carouselBreakdown || []).map(d => ({ Carrousel: d.carousel, Terminal: d.terminal, Vols: d.count }))
                  case "peak_hours": return (job.analytics?.peakHours || []).map(d => ({ Heure: d.hour, Vols: d.flights }))
                  case "occupancy":  return timelineOccupancyData.map(d => ({ Heure: d.time, "Carousels actifs": d.occupied }))
                  default: return []
                }
              })()
              const wCols = wRaw.length > 0 ? Object.keys(wRaw[0]) : []
              return (
                <div className="space-y-3">
                  <div className="space-y-1.5">
                    <Label>Champ X (grouper par)</Label>
                    <div className="flex flex-wrap gap-1">
                      {wCols.map(c => (
                        <button key={c} onClick={() => setNewWidgetXField(c)}
                          className={`rounded border px-2 py-0.5 text-xs transition-colors ${newWidgetXField === c ? "bg-blue-500 text-white border-blue-500" : "hover:bg-blue-50 text-blue-700"}`}>
                          {c}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div className="space-y-1.5">
                    <Label>Valeur Y</Label>
                    <div className="flex flex-wrap gap-1">
                      <button onClick={() => setNewWidgetYField("_count")}
                        className={`rounded border px-2 py-0.5 text-xs transition-colors ${newWidgetYField === "_count" ? "bg-green-500 text-white border-green-500" : "hover:bg-green-50 text-green-700"}`}>
                        Nombre de lignes
                      </button>
                      {wCols.map(c => (
                        <button key={c} onClick={() => setNewWidgetYField(c)}
                          className={`rounded border px-2 py-0.5 text-xs transition-colors ${newWidgetYField === c ? "bg-green-500 text-white border-green-500" : "hover:bg-green-50 text-green-700"}`}>
                          {c}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div className="space-y-1.5">
                    <Label>Type de graphique</Label>
                    <div className="flex gap-1 flex-wrap">
                      {[
                        { key: "bar", label: "Barres" }, { key: "line", label: "Ligne" },
                        { key: "area", label: "Aire" }, { key: "table", label: "Tableau" },
                      ].map(t => (
                        <button key={t.key} onClick={() => setNewWidgetChartType(t.key)}
                          className={`rounded border px-2 py-1 text-xs transition-colors ${newWidgetChartType === t.key ? "bg-primary text-primary-foreground border-primary" : "hover:bg-muted"}`}>
                          {t.label}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              )
            })()}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setAddWidgetOpen(false)}>Annuler</Button>
            <Button onClick={() => {
              if (!newWidgetXField) return
              setOverviewCustomWidgets(prev => [...prev, {
                id: `w-${Date.now()}`, title: newWidgetTitle,
                source: newWidgetSource, xField: newWidgetXField,
                yField: newWidgetYField, groupField: newWidgetGroupField,
                chartType: newWidgetChartType,
              }])
              setAddWidgetOpen(false)
            }} disabled={!newWidgetXField}>
              Ajouter
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── New KPI Dialog ── */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Nouveau KPI personnalise</DialogTitle>
            <DialogDescription>
              Choisissez une metrique, donnez-lui un nom et configurez une alerte optionnelle.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2">
            {/* Name */}
            <div className="space-y-1.5">
              <Label htmlFor="kpi-name">Nom *</Label>
              <Input
                id="kpi-name"
                placeholder="Ex : Taux de remplissage T1"
                value={kpiName}
                onChange={(e) => setKpiName(e.target.value)}
              />
            </div>

            {/* Metric */}
            <div className="space-y-1.5">
              <Label htmlFor="kpi-metric">Metrique *</Label>
              <Select value={kpiMetric} onValueChange={setKpiMetric}>
                <SelectTrigger id="kpi-metric">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {AVAILABLE_METRICS.map((m) => (
                    <SelectItem key={m.value} value={m.value}>
                      {m.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {hasJob && (
                <p className="text-xs text-muted-foreground">
                  Valeur actuelle : <strong>{resolveMetricValue(kpiMetric, job)}</strong>
                </p>
              )}
            </div>

            {/* Description */}
            <div className="space-y-1.5">
              <Label htmlFor="kpi-desc">Description (optionnel)</Label>
              <Input
                id="kpi-desc"
                placeholder="Courte description du KPI"
                value={kpiDescription}
                onChange={(e) => setKpiDescription(e.target.value)}
              />
            </div>

            {/* Alert toggle */}
            <div className="flex items-center justify-between rounded-lg border p-3">
              <div>
                <p className="text-sm font-medium">Activer une alerte</p>
                <p className="text-xs text-muted-foreground">
                  Affiche un indicateur visuel quand le seuil est depasse
                </p>
              </div>
              <Switch
                checked={kpiAlertEnabled}
                onCheckedChange={setKpiAlertEnabled}
              />
            </div>

            {/* Alert config */}
            {kpiAlertEnabled && (
              <div className="flex gap-2">
                <div className="w-32">
                  <Label className="text-xs">Condition</Label>
                  <Select
                    value={kpiAlertOperator}
                    onValueChange={(v) => setKpiAlertOperator(v as "lt" | "gt")}
                  >
                    <SelectTrigger className="mt-1">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="lt">Inferieur a (&lt;)</SelectItem>
                      <SelectItem value="gt">Superieur a (&gt;)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="flex-1">
                  <Label className="text-xs">Seuil</Label>
                  <Input
                    className="mt-1"
                    type="number"
                    placeholder="Ex : 95"
                    value={kpiAlertThreshold}
                    onChange={(e) => setKpiAlertThreshold(e.target.value)}
                  />
                </div>
              </div>
            )}

            {kpiError && (
              <p className="text-sm text-destructive">{kpiError}</p>
            )}
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)} disabled={kpiSaving}>
              Annuler
            </Button>
            <Button onClick={handleSaveKPI} disabled={kpiSaving}>
              {kpiSaving ? "Sauvegarde..." : "Creer le KPI"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </AppShell>
  )
}
