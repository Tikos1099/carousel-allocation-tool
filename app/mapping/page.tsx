"use client"

import { useState, useEffect, useRef } from "react"
import {
  Upload, Plus, Trash2, Save, FolderOpen, X,
  ArrowUp, ArrowDown, FileSpreadsheet, FileText,
  AlertCircle, CheckCircle, GitMerge,
  Download, Eye, EyeOff, HelpCircle, ChevronRight,
  MoreHorizontal, ArrowRight, Filter,
} from "lucide-react"
import { AppShell } from "@/components/app-shell"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { Checkbox } from "@/components/ui/checkbox"
import { Switch } from "@/components/ui/switch"
import { Separator } from "@/components/ui/separator"
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from "@/components/ui/dialog"
import {
  Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription,
} from "@/components/ui/sheet"
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem,
  DropdownMenuSeparator, DropdownMenuTrigger, DropdownMenuLabel,
} from "@/components/ui/dropdown-menu"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { toast } from "sonner"
import { supabase, type MappingConfig, type MappingRow, type FilterRule, type FilterOp } from "@/lib/supabase"

// ─── Types ────────────────────────────────────────────────────────────────────

type Aggregation = "First" | "Last" | "Sum" | "Count" | "Max" | "Min" | "Average" | "Concat"
type ColFormat =
  | "Auto" | "General" | "Number" | "Number (2dp)"
  | "Text" | "Date" | "Time" | "DateTime" | "Percentage"

const AGGREGATIONS: Aggregation[] = ["First", "Last", "Sum", "Count", "Max", "Min", "Average", "Concat"]
const FORMATS: ColFormat[] = [
  "Auto", "General", "Number", "Number (2dp)",
  "Text", "Date", "Time", "DateTime", "Percentage",
]

interface PreviewResult {
  columns: string[]
  rows: Record<string, unknown>[]
  total_rows: number
  preview_rows: number
}

const FILTER_OPS: { value: FilterOp; label: string; noVal?: boolean }[] = [
  { value: "=",            label: "= égal à" },
  { value: "<>",           label: "≠ différent de" },
  { value: ">",            label: "> supérieur à" },
  { value: "<",            label: "< inférieur à" },
  { value: ">=",           label: "≥ supérieur ou égal" },
  { value: "<=",           label: "≤ inférieur ou égal" },
  { value: "contains",     label: "contient" },
  { value: "not_contains", label: "ne contient pas" },
  { value: "starts_with",  label: "commence par" },
  { value: "ends_with",    label: "finit par" },
  { value: "is_empty",     label: "est vide", noVal: true },
  { value: "is_not_empty", label: "n'est pas vide", noVal: true },
]

function newFilterRule(col = ""): FilterRule {
  return { id: crypto.randomUUID(), col, op: "=", val: "" }
}

function newRow(targetName = ""): MappingRow {
  return {
    id: crypto.randomUUID(),
    targetName,
    sourceCol: "",
    formula: "",
    isPK: false,
    aggregation: "First",
    format: "Auto",
    includeInOutput: true,
  }
}

// ─── API ─────────────────────────────────────────────────────────────────────

const API_BASE = (() => {
  const env = process.env.NEXT_PUBLIC_API_BASE_URL
  if (env) return env.replace(/\/$/, "")
  if (typeof window !== "undefined" &&
    (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1"))
    return "http://127.0.0.1:8000"
  return "https://carousel-allocation-tool-production.up.railway.app"
})()

async function getMappingColumns(file: File): Promise<{ columns: string[]; row_count: number }> {
  const form = new FormData()
  form.append("file", file)
  const res = await fetch(`${API_BASE}/api/mapping/columns`, { method: "POST", body: form })
  if (!res.ok) { const e = await res.json().catch(() => ({ detail: res.statusText })); throw new Error(e.detail) }
  return res.json()
}

async function getMappingPreview(file: File, config: object): Promise<PreviewResult> {
  const form = new FormData()
  form.append("file", file)
  form.append("config_json", JSON.stringify(config))
  const res = await fetch(`${API_BASE}/api/mapping/preview`, { method: "POST", body: form })
  if (!res.ok) { const e = await res.json().catch(() => ({ detail: res.statusText })); throw new Error(e.detail) }
  return res.json()
}

async function downloadMapping(file: File, config: object): Promise<{ blob: Blob; filename: string }> {
  const form = new FormData()
  form.append("file", file)
  form.append("config_json", JSON.stringify(config))
  const res = await fetch(`${API_BASE}/api/mapping/execute`, { method: "POST", body: form })
  if (!res.ok) { const e = await res.json().catch(() => ({ detail: res.statusText })); throw new Error(e.detail) }
  const blob = await res.blob()
  const cd = res.headers.get("content-disposition") || ""
  const match = cd.match(/filename=([^\s;]+)/)
  return { blob, filename: match ? match[1] : "mapping_output" }
}

// ─── Formula reference ────────────────────────────────────────────────────────

const FORMULA_GROUPS = [
  {
    label: "Références",
    items: [
      { formula: "=NomColonne", desc: "Copie la valeur de la colonne source" },
      { formula: '="texte"', desc: "Valeur constante (texte)" },
      { formula: "=42", desc: "Valeur constante (nombre)" },
    ],
  },
  {
    label: "Séquences (index de ligne)",
    items: [
      { formula: "=ROW()", desc: "Index 0-based : 0, 1, 2, 3…" },
      { formula: "=ROW(1)", desc: "Index 1-based : 1, 2, 3, 4…" },
      { formula: "=ROW()+1", desc: "Commence à 1 (équivalent à ROW(1))" },
      { formula: "=ROW()**2", desc: "Carré de l'index : 0, 1, 4, 9, 16…" },
      { formula: "=ROW(1)**2", desc: "Carré 1-based : 1, 4, 9, 16, 25…" },
      { formula: "=ROW()*2+1", desc: "Impairs : 1, 3, 5, 7, 9…" },
      { formula: "=ROW()*10", desc: "Multiples de 10 : 0, 10, 20, 30…" },
      { formula: "=ROW(100)", desc: "Commence à 100 : 100, 101, 102…" },
    ],
  },
  {
    label: "Texte",
    items: [
      { formula: "=LEFT(Col, 3)", desc: "3 premiers caractères" },
      { formula: "=RIGHT(Col, 4)", desc: "4 derniers caractères" },
      { formula: "=MID(Col, 2, 5)", desc: "Substring : pos 2, longueur 5" },
      { formula: "=UPPER(Col)", desc: "Majuscules" },
      { formula: "=LOWER(Col)", desc: "Minuscules" },
      { formula: "=TRIM(Col)", desc: "Supprime les espaces en début/fin" },
    ],
  },
  {
    label: "Découpe",
    items: [
      { formula: '=TEXTBEFORE(Col, "/")', desc: 'Texte avant le séparateur "/"' },
      { formula: '=TEXTAFTER(Col, "-")', desc: 'Texte après le séparateur "-"' },
    ],
  },
  {
    label: "Combinaison",
    items: [
      { formula: '=ColA & "-" & ColB', desc: "Concaténation de deux colonnes" },
      { formula: '=LEFT(Col,3) & "_" & ColB', desc: "Formule + concaténation" },
    ],
  },
  {
    label: "Condition (IF / AND / OR)",
    items: [
      { formula: '=IF(Col="val", "oui", "non")', desc: 'Si Col vaut "val" → "oui", sinon "non"' },
      { formula: "=IF(Col>100, \"Heavy\", \"Light\")", desc: "Comparaison numérique" },
      { formula: '=IF(Col<>"", Col, "vide")', desc: "Si non vide, garde la valeur, sinon « vide »" },
      { formula: '=IF(AND(A="X", B>5), "ok", "ko")', desc: "ET : les deux conditions doivent être vraies" },
      { formula: '=IF(OR(A="X", A="Y"), "match", "no")', desc: "OU : au moins une condition vraie" },
    ],
  },
]

// ─── Step indicator ───────────────────────────────────────────────────────────

function StepBadge({ n, label, done }: { n: number; label: string; done: boolean }) {
  return (
    <div className="flex items-center gap-2">
      <div className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold
        ${done ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"}`}>
        {done ? <CheckCircle className="h-3.5 w-3.5" /> : n}
      </div>
      <span className={`text-sm font-medium ${done ? "text-foreground" : "text-muted-foreground"}`}>
        {label}
      </span>
    </div>
  )
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function MappingPage() {
  // Source
  const [sourceFile, setSourceFile] = useState<File | null>(null)
  const [sourceColumns, setSourceColumns] = useState<string[]>([])
  const [sourceRowCount, setSourceRowCount] = useState<number | null>(null)
  const [isLoadingSource, setIsLoadingSource] = useState(false)
  const sourceInputRef = useRef<HTMLInputElement>(null)

  // Target
  const targetInputRef = useRef<HTMLInputElement>(null)
  const [isLoadingTarget, setIsLoadingTarget] = useState(false)
  const [newColName, setNewColName] = useState("")

  // Rows
  const [rows, setRows] = useState<MappingRow[]>([])

  // Source filters
  const [filters, setFilters] = useState<FilterRule[]>([])

  // Output filters (applied after mapping on computed columns)
  const [outputFilters, setOutputFilters] = useState<FilterRule[]>([])

  // Options
  const [dedupByPK, setDedupByPK] = useState(false)

  // Formula help sheet
  const [showFormulaSheet, setShowFormulaSheet] = useState(false)

  // Preview dialog
  const [isPreviewing, setIsPreviewing] = useState(false)
  const [previewData, setPreviewData] = useState<PreviewResult | null>(null)
  const [showPreviewDialog, setShowPreviewDialog] = useState(false)
  const [outputFormat, setOutputFormat] = useState<"csv" | "excel">("csv")
  const [outputFilename, setOutputFilename] = useState("mapping_output")
  const [isDownloading, setIsDownloading] = useState(false)

  // Configs (Supabase)
  const [savedConfigs, setSavedConfigs] = useState<MappingConfig[]>([])
  const [configName, setConfigName] = useState("")
  const [showSaveDialog, setShowSaveDialog] = useState(false)
  const [showLoadDialog, setShowLoadDialog] = useState(false)
  const [showDeleteDialog, setShowDeleteDialog] = useState(false)
  const [selectedToDelete, setSelectedToDelete] = useState<MappingConfig | null>(null)
  const [isSaving, setIsSaving] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)
  const [isLoadingConfigs, setIsLoadingConfigs] = useState(false)

  useEffect(() => { loadConfigs() }, [])

  async function loadConfigs() {
    setIsLoadingConfigs(true)
    try {
      const { data, error } = await supabase
        .from("mapping_configs")
        .select("*")
        .order("created_at", { ascending: false })
      if (error) throw error
      setSavedConfigs((data as MappingConfig[]) || [])
    } catch (e) {
      console.error("Failed to load configs:", e)
    } finally {
      setIsLoadingConfigs(false)
    }
  }

  // ── Source file ──────────────────────────────────────────────────────────

  async function handleSourceFile(file: File) {
    setIsLoadingSource(true)
    setSourceFile(file)
    setSourceColumns([])
    setSourceRowCount(null)
    try {
      const result = await getMappingColumns(file)
      setSourceColumns(result.columns)
      setSourceRowCount(result.row_count)
      toast.success(`${result.columns.length} colonnes · ${result.row_count.toLocaleString()} lignes`)
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Impossible de lire le fichier")
      setSourceFile(null)
    } finally {
      setIsLoadingSource(false)
    }
  }

  // ── Target schema ────────────────────────────────────────────────────────

  async function handleTargetFile(file: File) {
    setIsLoadingTarget(true)
    try {
      const result = await getMappingColumns(file)
      setRows(result.columns.map(col => newRow(col)))
      toast.success(`${result.columns.length} colonnes cibles chargées`)
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Impossible de lire le fichier")
    } finally {
      setIsLoadingTarget(false)
    }
  }

  function handleAddColumn() {
    const name = newColName.trim()
    if (!name) return
    setRows(r => [...r, newRow(name)])
    setNewColName("")
  }

  // ── Row management ───────────────────────────────────────────────────────

  function removeRow(id: string) {
    setRows(r => r.filter(row => row.id !== id))
  }

  function moveRow(id: string, dir: -1 | 1) {
    setRows(r => {
      const idx = r.findIndex(row => row.id === id)
      if (idx < 0) return r
      const ni = idx + dir
      if (ni < 0 || ni >= r.length) return r
      const copy = [...r]
      ;[copy[idx], copy[ni]] = [copy[ni], copy[idx]]
      return copy
    })
  }

  function updateRow(id: string, field: keyof MappingRow, value: unknown) {
    setRows(r =>
      r.map(row => {
        if (row.id !== id) return row
        if (field === "sourceCol") {
          const newSrc = value as string
          const isSimple =
            !row.formula ||
            (row.formula.startsWith("=") &&
              !row.formula.includes("&") &&
              !row.formula.includes("+") &&
              !row.formula.includes("(") &&
              !row.formula.includes("-") &&
              !row.formula.includes("*") &&
              !row.formula.includes("/"))
          return {
            ...row,
            sourceCol: newSrc,
            formula: isSimple ? (newSrc ? `=${newSrc}` : "") : row.formula,
          }
        }
        return { ...row, [field]: value }
      })
    )
  }

  function togglePK(id: string, checked: boolean) {
    setRows(r =>
      r.map(row => ({
        ...row,
        isPK: row.id === id ? checked : checked ? false : row.isPK,
      }))
    )
  }

  // ── Preview & Download ───────────────────────────────────────────────────

  function buildConfig(format: "csv" | "excel", filename: string) {
    const ext = format === "excel" ? ".xlsx" : ".csv"
    const baseName = filename.trim() || "mapping_output"
    const finalName = baseName.endsWith(ext) ? baseName : `${baseName}${ext}`
    return {
      columns: rows.map(r => ({
        target_name: r.targetName,
        source_col: r.sourceCol,
        formula: r.formula,
        is_pk: r.isPK,
        aggregation: r.aggregation,
        format: r.format,
        include_in_output: r.includeInOutput ?? true,
      })),
      filters: filters.map(f => ({ col: f.col, op: f.op, val: f.val })),
      output_filters: outputFilters.map(f => ({ col: f.col, op: f.op, val: f.val })),
      dedup_by_pk: dedupByPK,
      output_format: format,
      output_filename: finalName,
    }
  }

  async function handlePreview() {
    if (!sourceFile) { toast.error("Veuillez charger un fichier source"); return }
    if (rows.length === 0) { toast.error("Aucune colonne définie"); return }
    setIsPreviewing(true)
    try {
      const config = buildConfig(outputFormat, outputFilename)
      const result = await getMappingPreview(sourceFile, config)
      setPreviewData(result)
      setShowPreviewDialog(true)
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Erreur lors de la prévisualisation")
    } finally {
      setIsPreviewing(false)
    }
  }

  async function handleDownload() {
    if (!sourceFile) return
    setIsDownloading(true)
    try {
      const config = buildConfig(outputFormat, outputFilename)
      const { blob, filename } = await downloadMapping(sourceFile, config)
      const url = URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      a.download = filename
      a.click()
      URL.revokeObjectURL(url)
      toast.success("Fichier téléchargé !")
      setShowPreviewDialog(false)
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Erreur lors du téléchargement")
    } finally {
      setIsDownloading(false)
    }
  }

  // ── Configs ──────────────────────────────────────────────────────────────

  async function handleSaveConfig() {
    const name = configName.trim()
    if (!name) return
    setIsSaving(true)
    try {
      const existing = savedConfigs.find(c => c.name === name)
      if (existing) {
        const { error } = await supabase
          .from("mapping_configs")
          .update({ rows, filters, output_filters: outputFilters, dedup_by_pk: dedupByPK })
          .eq("id", existing.id)
        if (error) throw error
      } else {
        const { error } = await supabase
          .from("mapping_configs")
          .insert({ name, rows, filters, output_filters: outputFilters, dedup_by_pk: dedupByPK })
        if (error) throw error
      }
      toast.success(`Configuration "${name}" sauvegardée`)
      setShowSaveDialog(false)
      setConfigName("")
      await loadConfigs()
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Erreur lors de la sauvegarde")
    } finally {
      setIsSaving(false)
    }
  }

  function handleLoadConfig(cfg: MappingConfig) {
    setRows(cfg.rows.map(r => ({ ...r, includeInOutput: r.includeInOutput ?? true, id: crypto.randomUUID() })))
    setFilters((cfg.filters ?? []).map(f => ({ ...f, id: crypto.randomUUID() })))
    setOutputFilters((cfg.output_filters ?? []).map(f => ({ ...f, id: crypto.randomUUID() })))
    setDedupByPK(cfg.dedup_by_pk)
    setShowLoadDialog(false)
    toast.success(`Configuration "${cfg.name}" chargée`)
  }

  async function handleDeleteConfig() {
    if (!selectedToDelete) return
    setIsDeleting(true)
    try {
      const { error } = await supabase
        .from("mapping_configs")
        .delete()
        .eq("id", selectedToDelete.id)
      if (error) throw error
      toast.success(`"${selectedToDelete.name}" supprimée`)
      setShowDeleteDialog(false)
      setSelectedToDelete(null)
      await loadConfigs()
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Erreur lors de la suppression")
    } finally {
      setIsDeleting(false)
    }
  }

  const pkExists = rows.some(r => r.isPK)
  const step1Done = !!sourceFile && sourceColumns.length > 0
  const step2Done = rows.length > 0
  const canPreview = step1Done && step2Done

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <AppShell>
      <div className="mx-auto max-w-6xl px-6 py-6 space-y-6">

        {/* ── Page header ──────────────────────────────────────────────────── */}
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 text-sm text-muted-foreground mb-1">
              <span>Accueil</span>
              <ChevronRight className="h-3.5 w-3.5" />
              <span className="text-foreground font-medium">Mapping Tool</span>
            </div>
            <h1 className="text-2xl font-bold">Mapping Tool</h1>
            <p className="text-sm text-muted-foreground mt-0.5">
              Transformez vos données entre fichiers Excel ou CSV
            </p>
          </div>

          {/* Config actions — dropdown */}
          <div className="flex items-center gap-2 shrink-0">
            {/* Steps summary */}
            <div className="hidden lg:flex items-center gap-4 mr-4">
              <StepBadge n={1} label="Source" done={step1Done} />
              <ArrowRight className="h-3.5 w-3.5 text-muted-foreground" />
              <StepBadge n={2} label="Mapping" done={step2Done} />
              <ArrowRight className="h-3.5 w-3.5 text-muted-foreground" />
              <StepBadge n={3} label="Export" done={false} />
            </div>

            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" size="sm">
                  <MoreHorizontal className="h-4 w-4 mr-1.5" />
                  Configurations
                  {savedConfigs.length > 0 && (
                    <Badge variant="secondary" className="ml-1.5 text-xs px-1.5 py-0">
                      {savedConfigs.length}
                    </Badge>
                  )}
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-56">
                <DropdownMenuLabel className="text-xs text-muted-foreground font-normal">
                  Gestion des configurations
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={() => { loadConfigs(); setShowLoadDialog(true) }}>
                  <FolderOpen className="h-4 w-4 mr-2 text-muted-foreground" />
                  Charger une configuration
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => setShowSaveDialog(true)} disabled={rows.length === 0}>
                  <Save className="h-4 w-4 mr-2 text-muted-foreground" />
                  Sauvegarder la configuration
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  onClick={() => { loadConfigs(); setShowDeleteDialog(true) }}
                  className="text-destructive focus:text-destructive"
                  disabled={savedConfigs.length === 0}
                >
                  <Trash2 className="h-4 w-4 mr-2" />
                  Supprimer une configuration
                </DropdownMenuItem>

                {savedConfigs.length > 0 && (
                  <>
                    <DropdownMenuSeparator />
                    <DropdownMenuLabel className="text-xs text-muted-foreground font-normal">
                      Accès rapide
                    </DropdownMenuLabel>
                    {savedConfigs.slice(0, 4).map(cfg => (
                      <DropdownMenuItem
                        key={cfg.id}
                        onClick={() => handleLoadConfig(cfg)}
                        className="text-sm"
                      >
                        <CheckCircle className="h-3.5 w-3.5 mr-2 text-muted-foreground" />
                        <span className="truncate">{cfg.name}</span>
                        <span className="ml-auto text-xs text-muted-foreground shrink-0">
                          {cfg.rows.length}c
                        </span>
                      </DropdownMenuItem>
                    ))}
                  </>
                )}
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>

        {/* ── Step 1 : Files ───────────────────────────────────────────────── */}
        <section className="space-y-3">
          <div className="flex items-center gap-2">
            <div className="flex h-6 w-6 items-center justify-center rounded-full bg-primary text-primary-foreground text-xs font-bold shrink-0">
              1
            </div>
            <h2 className="text-sm font-semibold">Fichiers</h2>
            <Separator className="flex-1" />
          </div>

          <div className="grid grid-cols-2 gap-4">
            {/* Source */}
            <Card className={`transition-colors ${step1Done ? "border-primary/30 bg-primary/[0.02]" : ""}`}>
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="text-sm">Fichier source</CardTitle>
                    <CardDescription className="text-xs mt-0.5">Excel ou CSV à lire</CardDescription>
                  </div>
                  {step1Done && (
                    <Badge variant="secondary" className="text-xs gap-1">
                      <CheckCircle className="h-3 w-3" />
                      Chargé
                    </Badge>
                  )}
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                <input
                  ref={sourceInputRef}
                  type="file"
                  accept=".xlsx,.xls,.csv"
                  className="hidden"
                  onChange={e => { const f = e.target.files?.[0]; if (f) handleSourceFile(f); e.target.value = "" }}
                />
                {!sourceFile ? (
                  <div
                    onClick={() => sourceInputRef.current?.click()}
                    onDragOver={e => e.preventDefault()}
                    onDrop={e => { e.preventDefault(); const f = e.dataTransfer.files[0]; if (f) handleSourceFile(f) }}
                    className="border-2 border-dashed rounded-lg p-6 text-center cursor-pointer hover:border-primary hover:bg-primary/5 transition-all"
                  >
                    <Upload className="h-7 w-7 mx-auto mb-2 text-muted-foreground" />
                    <p className="text-sm font-medium">Glissez votre fichier ici</p>
                    <p className="text-xs text-muted-foreground mt-1">ou cliquez · .xlsx .xls .csv</p>
                  </div>
                ) : (
                  <div className="space-y-2.5">
                    <div className="flex items-center gap-3 p-3 bg-muted/60 rounded-lg">
                      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary/10">
                        <FileSpreadsheet className="h-4 w-4 text-primary" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-medium truncate">{sourceFile.name}</p>
                        {sourceRowCount !== null
                          ? <p className="text-xs text-muted-foreground">{sourceRowCount.toLocaleString()} lignes · {sourceColumns.length} colonnes</p>
                          : isLoadingSource && <p className="text-xs text-muted-foreground">Analyse en cours…</p>
                        }
                      </div>
                      <Button variant="ghost" size="icon" className="h-7 w-7 shrink-0"
                        onClick={() => { setSourceFile(null); setSourceColumns([]); setSourceRowCount(null) }}>
                        <X className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                    {sourceColumns.length > 0 && (
                      <div className="flex flex-wrap gap-1">
                        {sourceColumns.slice(0, 8).map(col => (
                          <Badge key={col} variant="secondary" className="text-xs py-0 font-normal">{col}</Badge>
                        ))}
                        {sourceColumns.length > 8 && (
                          <Badge variant="outline" className="text-xs py-0">+{sourceColumns.length - 8} autres</Badge>
                        )}
                      </div>
                    )}
                    <Button variant="ghost" size="sm" className="w-full h-7 text-xs text-muted-foreground"
                      onClick={() => sourceInputRef.current?.click()}>
                      Changer de fichier
                    </Button>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Target Schema */}
            <Card className={`transition-colors ${step2Done ? "border-primary/30 bg-primary/[0.02]" : ""}`}>
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="text-sm">Schéma cible</CardTitle>
                    <CardDescription className="text-xs mt-0.5">Colonnes de sortie</CardDescription>
                  </div>
                  {step2Done && (
                    <Badge variant="secondary" className="text-xs gap-1">
                      <CheckCircle className="h-3 w-3" />
                      {rows.filter(r => r.includeInOutput).length}/{rows.length} colonnes
                    </Badge>
                  )}
                </div>
              </CardHeader>
              <CardContent>
                <Tabs defaultValue="manual">
                  <TabsList className="grid grid-cols-2 h-8 mb-3">
                    <TabsTrigger value="manual" className="text-xs">Manuel</TabsTrigger>
                    <TabsTrigger value="file" className="text-xs">Depuis fichier</TabsTrigger>
                  </TabsList>
                  <TabsContent value="manual" className="space-y-2">
                    <div className="flex gap-2">
                      <Input
                        placeholder="Nom de la colonne cible…"
                        value={newColName}
                        onChange={e => setNewColName(e.target.value)}
                        onKeyDown={e => e.key === "Enter" && handleAddColumn()}
                        className="h-8 text-sm"
                      />
                      <Button size="sm" onClick={handleAddColumn} className="h-8 px-3 shrink-0">
                        <Plus className="h-4 w-4" />
                      </Button>
                    </div>
                    {rows.length === 0 && (
                      <p className="text-xs text-muted-foreground">
                        Tapez un nom et appuyez sur Entrée pour ajouter une colonne.
                      </p>
                    )}
                  </TabsContent>
                  <TabsContent value="file" className="space-y-2">
                    <input
                      ref={targetInputRef}
                      type="file"
                      accept=".xlsx,.xls,.csv"
                      className="hidden"
                      onChange={e => { const f = e.target.files?.[0]; if (f) handleTargetFile(f); e.target.value = "" }}
                    />
                    <Button variant="outline" className="w-full h-9 text-sm"
                      onClick={() => targetInputRef.current?.click()}
                      disabled={isLoadingTarget}>
                      <Upload className="h-3.5 w-3.5 mr-1.5" />
                      {isLoadingTarget ? "Chargement…" : "Importer les en-têtes"}
                    </Button>
                    <p className="text-xs text-muted-foreground">
                      Les en-têtes du fichier deviendront les colonnes cibles.
                    </p>
                  </TabsContent>
                </Tabs>
              </CardContent>
            </Card>
          </div>
        </section>

        {/* ── Row Filters ─────────────────────────────────────────────────── */}
        <section className="space-y-3">
          <div className="flex items-center gap-2">
            <Filter className="h-4 w-4 text-muted-foreground shrink-0" />
            <h2 className="text-sm font-semibold">Filtres de lignes</h2>
            {filters.length > 0 && (
              <Badge variant="secondary" className="text-xs">{filters.length} actif{filters.length > 1 ? "s" : ""}</Badge>
            )}
            <Separator className="flex-1" />
            <Button
              variant="ghost" size="sm"
              className="h-7 px-2 text-xs gap-1 shrink-0"
              onClick={() => setFilters(f => [...f, newFilterRule(sourceColumns[0] ?? "")])}
              disabled={sourceColumns.length === 0}
            >
              <Plus className="h-3.5 w-3.5" />
              Ajouter un filtre
            </Button>
          </div>

          {filters.length === 0 ? (
            <p className="text-xs text-muted-foreground px-1">
              Aucun filtre — toutes les lignes source seront traitées.
              {sourceColumns.length === 0 && " Chargez d'abord un fichier source."}
            </p>
          ) : (
            <Card>
              <CardContent className="p-0">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b bg-muted/40 text-xs text-muted-foreground">
                      <th className="px-3 py-2 text-left font-medium w-[200px]">Colonne</th>
                      <th className="px-3 py-2 text-left font-medium w-[200px]">Condition</th>
                      <th className="px-3 py-2 text-left font-medium">Valeur</th>
                      <th className="px-3 py-2 w-8" />
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {filters.map((f, idx) => {
                      const opDef = FILTER_OPS.find(o => o.value === f.op)
                      return (
                        <tr key={f.id} className="hover:bg-muted/20 transition-colors">
                          <td className="px-3 py-1.5">
                            <Select
                              value={f.col || "__none__"}
                              onValueChange={v => setFilters(fs => fs.map((r, i) =>
                                i === idx ? { ...r, col: v === "__none__" ? "" : v } : r
                              ))}
                            >
                              <SelectTrigger className="h-7 text-xs">
                                <SelectValue placeholder="(colonne)" />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value="__none__" className="italic text-muted-foreground">(choisir)</SelectItem>
                                {sourceColumns.map(c => (
                                  <SelectItem key={c} value={c}>{c}</SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          </td>
                          <td className="px-3 py-1.5">
                            <Select
                              value={f.op}
                              onValueChange={v => setFilters(fs => fs.map((r, i) =>
                                i === idx ? { ...r, op: v as FilterOp, val: "" } : r
                              ))}
                            >
                              <SelectTrigger className="h-7 text-xs">
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                {FILTER_OPS.map(o => (
                                  <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          </td>
                          <td className="px-3 py-1.5">
                            {opDef?.noVal ? (
                              <span className="text-xs text-muted-foreground italic px-2">—</span>
                            ) : (
                              <Input
                                value={f.val}
                                onChange={e => setFilters(fs => fs.map((r, i) =>
                                  i === idx ? { ...r, val: e.target.value } : r
                                ))}
                                placeholder="valeur…"
                                className="h-7 text-xs border-transparent bg-transparent hover:border-input focus:border-input px-2"
                              />
                            )}
                          </td>
                          <td className="px-2 py-1.5">
                            <Button
                              variant="ghost" size="icon"
                              className="h-6 w-6 text-muted-foreground hover:text-destructive"
                              onClick={() => setFilters(fs => fs.filter((_, i) => i !== idx))}
                            >
                              <X className="h-3 w-3" />
                            </Button>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
                <div className="px-3 py-2 border-t bg-muted/20">
                  <p className="text-xs text-muted-foreground">
                    Les filtres sont combinés avec <strong>ET</strong> — une ligne doit satisfaire <strong>toutes</strong> les conditions pour être incluse.
                  </p>
                </div>
              </CardContent>
            </Card>
          )}
        </section>

        {/* ── Output Filters ───────────────────────────────────────────────── */}
        <section className="space-y-3">
          <div className="flex items-center gap-2">
            <Filter className="h-4 w-4 text-primary shrink-0" />
            <h2 className="text-sm font-semibold">Filtres sur l&apos;output</h2>
            {outputFilters.length > 0 && (
              <Badge variant="secondary" className="text-xs">{outputFilters.length} actif{outputFilters.length > 1 ? "s" : ""}</Badge>
            )}
            <Separator className="flex-1" />
            <Button
              variant="ghost" size="sm"
              className="h-7 px-2 text-xs gap-1 shrink-0"
              onClick={() => {
                const firstCol = rows.find(r => r.targetName.trim())?.targetName ?? ""
                setOutputFilters(f => [...f, newFilterRule(firstCol)])
              }}
              disabled={rows.length === 0}
            >
              <Plus className="h-3.5 w-3.5" />
              Ajouter un filtre output
            </Button>
          </div>

          {outputFilters.length === 0 ? (
            <p className="text-xs text-muted-foreground px-1">
              Aucun filtre output — toutes les lignes calculées seront conservées.
              {rows.length === 0 && " Définissez d'abord les colonnes cibles (étape 2)."}
            </p>
          ) : (
            <Card>
              <CardContent className="p-0">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b bg-muted/40 text-xs text-muted-foreground">
                      <th className="px-3 py-2 text-left font-medium w-[200px]">Colonne output</th>
                      <th className="px-3 py-2 text-left font-medium w-[200px]">Condition</th>
                      <th className="px-3 py-2 text-left font-medium">Valeur</th>
                      <th className="px-3 py-2 w-8" />
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {outputFilters.map((f, idx) => {
                      const opDef = FILTER_OPS.find(o => o.value === f.op)
                      const outputCols = rows.map(r => r.targetName).filter(n => n.trim())
                      return (
                        <tr key={f.id} className="hover:bg-muted/20 transition-colors">
                          <td className="px-3 py-1.5">
                            <Select
                              value={f.col || "__none__"}
                              onValueChange={v => setOutputFilters(fs => fs.map((r, i) =>
                                i === idx ? { ...r, col: v === "__none__" ? "" : v } : r
                              ))}
                            >
                              <SelectTrigger className="h-7 text-xs">
                                <SelectValue placeholder="(colonne)" />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value="__none__" className="italic text-muted-foreground">(choisir)</SelectItem>
                                {outputCols.map(c => (
                                  <SelectItem key={c} value={c}>{c}</SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          </td>
                          <td className="px-3 py-1.5">
                            <Select
                              value={f.op}
                              onValueChange={v => setOutputFilters(fs => fs.map((r, i) =>
                                i === idx ? { ...r, op: v as FilterOp, val: "" } : r
                              ))}
                            >
                              <SelectTrigger className="h-7 text-xs">
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                {FILTER_OPS.map(o => (
                                  <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          </td>
                          <td className="px-3 py-1.5">
                            {opDef?.noVal ? (
                              <span className="text-xs text-muted-foreground italic px-2">—</span>
                            ) : (
                              <Input
                                value={f.val}
                                onChange={e => setOutputFilters(fs => fs.map((r, i) =>
                                  i === idx ? { ...r, val: e.target.value } : r
                                ))}
                                placeholder="valeur…"
                                className="h-7 text-xs border-transparent bg-transparent hover:border-input focus:border-input px-2"
                              />
                            )}
                          </td>
                          <td className="px-2 py-1.5">
                            <Button
                              variant="ghost" size="icon"
                              className="h-6 w-6 text-muted-foreground hover:text-destructive"
                              onClick={() => setOutputFilters(fs => fs.filter((_, i) => i !== idx))}
                            >
                              <X className="h-3 w-3" />
                            </Button>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
                <div className="px-3 py-2 border-t bg-muted/20">
                  <p className="text-xs text-muted-foreground">
                    Appliqués <strong>après</strong> le mapping et la déduplication — filtrent sur les valeurs calculées.
                    Combinés avec <strong>ET</strong>.
                  </p>
                </div>
              </CardContent>
            </Card>
          )}
        </section>

        {/* ── Step 2 : Mapping table ───────────────────────────────────────── */}
        <section className="space-y-3">
          <div className="flex items-center gap-2">
            <div className={`flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold shrink-0
              ${step2Done ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"}`}>
              2
            </div>
            <h2 className="text-sm font-semibold">Mapping des colonnes</h2>
            <Separator className="flex-1" />
            <div className="flex items-center gap-3 shrink-0">
              {/* Dedup toggle */}
              <div className="flex items-center gap-2">
                <Switch id="dedup" checked={dedupByPK} onCheckedChange={setDedupByPK} />
                <Label htmlFor="dedup" className="text-xs cursor-pointer select-none text-muted-foreground">
                  Dédupliquer par PK
                </Label>
              </div>
              {dedupByPK && !pkExists && (
                <Badge variant="destructive" className="text-xs gap-1">
                  <AlertCircle className="h-3 w-3" />Aucune PK
                </Badge>
              )}
              {/* Formula help trigger */}
              <Button
                variant="ghost"
                size="sm"
                className="h-7 px-2 text-xs text-muted-foreground gap-1"
                onClick={() => setShowFormulaSheet(true)}
              >
                <HelpCircle className="h-3.5 w-3.5" />
                Formules
              </Button>
            </div>
          </div>

          <Card>
            <CardContent className="p-0">
              {rows.length === 0 ? (
                <div className="py-14 text-center text-muted-foreground">
                  <GitMerge className="h-10 w-10 mx-auto mb-3 opacity-20" />
                  <p className="text-sm font-medium">Aucune colonne définie</p>
                  <p className="text-xs mt-1 text-muted-foreground/70">
                    Ajoutez des colonnes dans le schéma cible ci-dessus
                  </p>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b bg-muted/40 text-xs text-muted-foreground">
                        <th className="px-3 py-2.5 text-left font-medium w-[160px]">Colonne cible</th>
                        <th className="px-3 py-2.5 text-left font-medium w-[180px]">Source</th>
                        <th className="px-3 py-2.5 text-left font-medium">
                          <div className="flex items-center gap-1">
                            Formule
                            <button
                              onClick={() => setShowFormulaSheet(true)}
                              className="text-muted-foreground/60 hover:text-muted-foreground transition-colors"
                            >
                              <HelpCircle className="h-3 w-3" />
                            </button>
                          </div>
                        </th>
                        <th className="px-3 py-2.5 text-center font-medium w-[42px]" title="Clé primaire">PK</th>
                        <th className="px-3 py-2.5 text-left font-medium w-[120px]">Agrégation</th>
                        <th className="px-3 py-2.5 text-left font-medium w-[130px]">Format</th>
                        <th className="px-3 py-2.5 text-center font-medium w-[42px]" title="Inclure dans l'output">Incl.</th>
                        <th className="px-3 py-2.5 w-[80px]" />
                      </tr>
                    </thead>
                    <tbody className="divide-y">
                      {rows.map((row, idx) => (
                        <tr
                          key={row.id}
                          className={`transition-colors hover:bg-muted/20 ${
                            !row.includeInOutput
                              ? "opacity-50 bg-muted/30"
                              : row.isPK ? "bg-primary/[0.03] border-l-2 border-l-primary" : ""
                          }`}
                        >
                          <td className="px-3 py-1.5">
                            <Input
                              value={row.targetName}
                              onChange={e => updateRow(row.id, "targetName", e.target.value)}
                              className="h-7 text-xs font-medium border-transparent bg-transparent hover:border-input focus:border-input px-2"
                            />
                          </td>
                          <td className="px-3 py-1.5">
                            <Select
                              value={row.sourceCol || "__none__"}
                              onValueChange={v => updateRow(row.id, "sourceCol", v === "__none__" ? "" : v)}
                            >
                              <SelectTrigger className="h-7 text-xs">
                                <SelectValue placeholder="(aucune)" />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value="__none__" className="text-muted-foreground italic">(aucune)</SelectItem>
                                {sourceColumns.map(col => (
                                  <SelectItem key={col} value={col}>{col}</SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          </td>
                          <td className="px-3 py-1.5">
                            <Input
                              value={row.formula}
                              onChange={e => updateRow(row.id, "formula", e.target.value)}
                              placeholder={'=Colonne ou ="constante"'}
                              className="h-7 text-xs font-mono border-transparent bg-transparent hover:border-input focus:border-input px-2"
                            />
                          </td>
                          <td className="px-3 py-1.5 text-center">
                            <Checkbox
                              checked={row.isPK}
                              onCheckedChange={checked => togglePK(row.id, !!checked)}
                            />
                          </td>
                          <td className="px-3 py-1.5">
                            <Select
                              value={row.aggregation}
                              onValueChange={v => updateRow(row.id, "aggregation", v)}
                              disabled={!dedupByPK}
                            >
                              <SelectTrigger className="h-7 text-xs">
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                {AGGREGATIONS.map(a => (
                                  <SelectItem key={a} value={a}>{a}</SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          </td>
                          <td className="px-3 py-1.5">
                            <Select
                              value={row.format}
                              onValueChange={v => updateRow(row.id, "format", v)}
                            >
                              <SelectTrigger className="h-7 text-xs">
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                {FORMATS.map(f => (
                                  <SelectItem key={f} value={f}>{f}</SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          </td>
                          <td className="px-3 py-1.5 text-center">
                            <Button
                              variant="ghost"
                              size="icon"
                              className={`h-6 w-6 ${row.includeInOutput ? "text-primary" : "text-muted-foreground/40"}`}
                              title={row.includeInOutput ? "Inclus dans l'output (cliquer pour masquer)" : "Colonne intermédiaire — absente de l'output (cliquer pour inclure)"}
                              onClick={() => updateRow(row.id, "includeInOutput", !row.includeInOutput)}
                            >
                              {row.includeInOutput
                                ? <Eye className="h-3.5 w-3.5" />
                                : <EyeOff className="h-3.5 w-3.5" />}
                            </Button>
                          </td>
                          <td className="px-3 py-1.5">
                            <div className="flex items-center gap-0.5">
                              <Button variant="ghost" size="icon" className="h-6 w-6 text-muted-foreground"
                                onClick={() => moveRow(row.id, -1)} disabled={idx === 0}>
                                <ArrowUp className="h-3 w-3" />
                              </Button>
                              <Button variant="ghost" size="icon" className="h-6 w-6 text-muted-foreground"
                                onClick={() => moveRow(row.id, 1)} disabled={idx === rows.length - 1}>
                                <ArrowDown className="h-3 w-3" />
                              </Button>
                              <Button variant="ghost" size="icon"
                                className="h-6 w-6 text-muted-foreground hover:text-destructive"
                                onClick={() => removeRow(row.id)}>
                                <X className="h-3 w-3" />
                              </Button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>
        </section>

        {/* ── Step 3 : Export ──────────────────────────────────────────────── */}
        <section className="space-y-3">
          <div className="flex items-center gap-2">
            <div className="flex h-6 w-6 items-center justify-center rounded-full bg-muted text-muted-foreground text-xs font-bold shrink-0">
              3
            </div>
            <h2 className="text-sm font-semibold">Export</h2>
            <Separator className="flex-1" />
          </div>

          <div className="flex items-center justify-between rounded-xl border bg-card p-4">
            <div className="space-y-0.5">
              <p className="text-sm font-medium">
                {canPreview
                  ? (() => {
                      const included = rows.filter(r => r.includeInOutput).length
                      const hidden = rows.length - included
                      return `Prêt · ${included} colonne${included > 1 ? "s" : ""}${hidden > 0 ? ` (+${hidden} intermédiaire${hidden > 1 ? "s" : ""})` : ""} · ${sourceRowCount?.toLocaleString() ?? "?"} lignes source${filters.length > 0 ? ` · ${filters.length} filtre source` : ""}${outputFilters.length > 0 ? ` · ${outputFilters.length} filtre output` : ""}`
                    })()
                  : "Complétez les étapes 1 et 2 pour continuer"
                }
              </p>
              <p className="text-xs text-muted-foreground">
                Prévisualisez le résultat avant de télécharger
              </p>
            </div>
            <Button
              size="default"
              onClick={handlePreview}
              disabled={isPreviewing || !canPreview}
              className="gap-2"
            >
              <Eye className="h-4 w-4" />
              {isPreviewing ? "Analyse…" : "Prévisualiser"}
            </Button>
          </div>
        </section>
      </div>

      {/* ── Formula Help Sheet ──────────────────────────────────────────────── */}
      <Sheet open={showFormulaSheet} onOpenChange={setShowFormulaSheet}>
        <SheetContent className="w-[420px] sm:w-[480px] overflow-y-auto">
          <SheetHeader className="mb-4">
            <SheetTitle className="flex items-center gap-2">
              <HelpCircle className="h-5 w-5" />
              Référence des formules
            </SheetTitle>
            <SheetDescription>
              Toute formule commence par <code className="bg-muted px-1 rounded text-xs">=</code>.
              Les noms de colonnes sont sensibles à la casse.
            </SheetDescription>
          </SheetHeader>
          <div className="space-y-5">
            {FORMULA_GROUPS.map(group => (
              <div key={group.label}>
                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">
                  {group.label}
                </p>
                <div className="space-y-2">
                  {group.items.map(({ formula, desc }) => (
                    <div key={formula} className="flex items-start gap-3 p-2.5 rounded-lg bg-muted/50">
                      <code className="text-xs bg-background border px-2 py-1 rounded font-mono shrink-0 whitespace-nowrap">
                        {formula}
                      </code>
                      <span className="text-xs text-muted-foreground pt-0.5">{desc}</span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
            <div className="p-3 bg-amber-50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-800 rounded-lg">
              <p className="text-xs font-medium text-amber-800 dark:text-amber-300 mb-1">Concaténation</p>
              <code className="text-xs text-amber-700 dark:text-amber-400 font-mono block">
                =LEFT(FlightNum,2) &amp; &quot;-&quot; &amp; Route
              </code>
              <p className="text-xs text-amber-600 dark:text-amber-500 mt-1">
                Utilisez <code className="bg-amber-100 dark:bg-amber-900 px-1 rounded">&amp;</code> pour joindre plusieurs valeurs.
              </p>
            </div>
          </div>
        </SheetContent>
      </Sheet>

      {/* ── Preview Dialog ──────────────────────────────────────────────────── */}
      <Dialog open={showPreviewDialog} onOpenChange={setShowPreviewDialog}>
        <DialogContent className="max-w-5xl max-h-[90vh] flex flex-col">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              Résultat du mapping
            </DialogTitle>
          </DialogHeader>

          {previewData && (
            <div className="flex flex-col gap-4 flex-1 min-h-0">
              {/* Stats bar */}
              <div className="flex items-center gap-3">
                <Badge variant="secondary" className="gap-1">
                  {previewData.total_rows.toLocaleString()} lignes
                </Badge>
                <Badge variant="outline" className="gap-1">
                  {previewData.columns.length} colonnes
                </Badge>
                {previewData.total_rows > previewData.preview_rows && (
                  <span className="text-xs text-muted-foreground">
                    · aperçu des {previewData.preview_rows} premières lignes
                  </span>
                )}
              </div>

              {/* Preview table */}
              <div className="border rounded-lg overflow-auto" style={{ maxHeight: "42vh" }}>
                <table className="w-full text-xs">
                  <thead className="sticky top-0 z-10">
                    <tr>
                      {previewData.columns.map(col => (
                        <th key={col}
                          className="px-3 py-2 text-left font-medium text-muted-foreground whitespace-nowrap bg-muted/90 border-b">
                          {col}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {previewData.rows.map((row, i) => (
                      <tr key={i} className="hover:bg-muted/30 transition-colors">
                        {previewData.columns.map(col => (
                          <td key={col}
                            className="px-3 py-1.5 whitespace-nowrap max-w-[200px] truncate"
                            title={String(row[col] ?? "")}>
                            {row[col] === null || row[col] === undefined
                              ? <span className="text-muted-foreground/40 italic">—</span>
                              : String(row[col])}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Download options */}
              <div className="border rounded-xl p-4 bg-muted/30 space-y-3">
                <p className="text-sm font-medium">Options de téléchargement</p>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <Label htmlFor="filename" className="text-xs text-muted-foreground">Nom du fichier</Label>
                    <Input
                      id="filename"
                      value={outputFilename}
                      onChange={e => setOutputFilename(e.target.value)}
                      placeholder="mapping_output"
                      className="h-8 text-sm"
                    />
                    <p className="text-xs text-muted-foreground">L&apos;extension sera ajoutée automatiquement</p>
                  </div>
                  <div className="space-y-1.5">
                    <Label className="text-xs text-muted-foreground">Format</Label>
                    <div className="flex gap-2">
                      <Button
                        variant={outputFormat === "csv" ? "default" : "outline"}
                        size="sm" className="flex-1"
                        onClick={() => setOutputFormat("csv")}
                      >
                        <FileText className="h-3.5 w-3.5 mr-1.5" />CSV
                      </Button>
                      <Button
                        variant={outputFormat === "excel" ? "default" : "outline"}
                        size="sm" className="flex-1"
                        onClick={() => setOutputFormat("excel")}
                      >
                        <FileSpreadsheet className="h-3.5 w-3.5 mr-1.5" />Excel
                      </Button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setShowPreviewDialog(false)}>Fermer</Button>
            <Button onClick={handleDownload} disabled={isDownloading} className="gap-2">
              <Download className="h-4 w-4" />
              {isDownloading ? "Téléchargement…" : `Télécharger en ${outputFormat.toUpperCase()}`}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Save Dialog ─────────────────────────────────────────────────────── */}
      <Dialog open={showSaveDialog} onOpenChange={setShowSaveDialog}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>Sauvegarder la configuration</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 py-1">
            <div className="space-y-1.5">
              <Label htmlFor="cfg-name" className="text-sm">Nom</Label>
              <Input
                id="cfg-name"
                value={configName}
                onChange={e => setConfigName(e.target.value)}
                placeholder="Ex : FPD_from_Generated"
                onKeyDown={e => e.key === "Enter" && handleSaveConfig()}
                autoFocus
              />
            </div>
            {savedConfigs.some(c => c.name === configName.trim()) && configName.trim() && (
              <p className="text-xs text-amber-500 flex items-center gap-1">
                <AlertCircle className="h-3 w-3" />
                Une config portant ce nom existe déjà — elle sera mise à jour.
              </p>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowSaveDialog(false)}>Annuler</Button>
            <Button onClick={handleSaveConfig} disabled={!configName.trim() || isSaving}>
              <Save className="h-4 w-4 mr-1.5" />
              {isSaving ? "Sauvegarde…" : "Sauvegarder"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Load Dialog ─────────────────────────────────────────────────────── */}
      <Dialog open={showLoadDialog} onOpenChange={setShowLoadDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Charger une configuration</DialogTitle>
          </DialogHeader>
          <div className="py-1">
            {isLoadingConfigs ? (
              <p className="py-4 text-sm text-center text-muted-foreground">Chargement…</p>
            ) : savedConfigs.length === 0 ? (
              <p className="py-4 text-sm text-center text-muted-foreground">Aucune configuration sauvegardée.</p>
            ) : (
              <div className="space-y-1.5 max-h-72 overflow-y-auto">
                {savedConfigs.map(cfg => (
                  <button
                    key={cfg.id}
                    onClick={() => handleLoadConfig(cfg)}
                    className="w-full flex items-center justify-between p-3 border rounded-lg hover:bg-muted hover:border-primary/30 transition-all text-left"
                  >
                    <div>
                      <p className="text-sm font-medium">{cfg.name}</p>
                      <p className="text-xs text-muted-foreground">
                        {cfg.rows.length} colonne{cfg.rows.length !== 1 ? "s" : ""}
                        {" · "}{cfg.dedup_by_pk ? "Dédup PK" : "Sans dédup"}
                        {cfg.created_at && ` · ${new Date(cfg.created_at).toLocaleDateString("fr-FR")}`}
                      </p>
                    </div>
                    <ArrowRight className="h-4 w-4 text-muted-foreground shrink-0" />
                  </button>
                ))}
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowLoadDialog(false)}>Fermer</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Delete Dialog ────────────────────────────────────────────────────── */}
      <Dialog
        open={showDeleteDialog}
        onOpenChange={open => { setShowDeleteDialog(open); if (!open) setSelectedToDelete(null) }}
      >
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Supprimer une configuration</DialogTitle>
          </DialogHeader>
          <div className="py-1">
            {savedConfigs.length === 0 ? (
              <p className="py-4 text-sm text-center text-muted-foreground">Aucune configuration à supprimer.</p>
            ) : (
              <div className="space-y-1.5 max-h-64 overflow-y-auto">
                {savedConfigs.map(cfg => (
                  <button
                    key={cfg.id}
                    onClick={() => setSelectedToDelete(cfg)}
                    className={`w-full flex items-center justify-between p-3 border rounded-lg transition-all text-left ${
                      selectedToDelete?.id === cfg.id
                        ? "border-destructive bg-destructive/10"
                        : "hover:bg-muted"
                    }`}
                  >
                    <div>
                      <p className="text-sm font-medium">{cfg.name}</p>
                      <p className="text-xs text-muted-foreground">
                        {cfg.rows.length} colonne{cfg.rows.length !== 1 ? "s" : ""}
                      </p>
                    </div>
                    {selectedToDelete?.id === cfg.id && (
                      <Trash2 className="h-4 w-4 text-destructive shrink-0" />
                    )}
                  </button>
                ))}
                {selectedToDelete && (
                  <p className="text-xs text-destructive pt-1 flex items-center gap-1">
                    <AlertCircle className="h-3 w-3" />
                    &ldquo;{selectedToDelete.name}&rdquo; sera supprimée définitivement.
                  </p>
                )}
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => { setShowDeleteDialog(false); setSelectedToDelete(null) }}>
              Annuler
            </Button>
            <Button variant="destructive" onClick={handleDeleteConfig} disabled={!selectedToDelete || isDeleting}>
              <Trash2 className="h-4 w-4 mr-1.5" />
              {isDeleting ? "Suppression…" : "Supprimer"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </AppShell>
  )
}
