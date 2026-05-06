"use client"

import { Suspense, useState, useEffect, useRef, useMemo } from "react"
import { useSearchParams } from "next/navigation"
import {
  Upload, Plus, Trash2, Save, FolderOpen, X,
  ArrowUp, ArrowDown, FileSpreadsheet,
  AlertCircle, CheckCircle, GitMerge,
  Download, Eye, EyeOff, HelpCircle, Search,
  LayoutList, LayoutGrid, ArrowRight, ChevronDown,
} from "lucide-react"
import { AppShell } from "@/components/app-shell"
import { toast } from "sonner"
import { supabase, type MappingConfig, type MappingRow, type FilterRule, type FilterOp, type JoinSavedConfig } from "@/lib/supabase"
import s from "./mapping.module.css"

// ─── Types ────────────────────────────────────────────────────────────────────

interface SecondaryFile {
  id: string
  file: File | null
  alias: string
  columns: string[]
  onPrimary: string
  onSecondary: string
  isLoading: boolean
  availableSheets: string[]
  sheetName: string
  skipRows: number
}

interface FilterGroup {
  id: string
  op: "AND" | "OR"
  rules: FilterRule[]
}

function toFilterGroups(data: unknown[]): FilterGroup[] {
  if (!data?.length) return []
  if ((data[0] as FilterGroup).rules !== undefined) {
    return (data as FilterGroup[]).map(g => ({
      ...g,
      id: g.id || crypto.randomUUID(),
      rules: g.rules.map(r => ({ ...r, id: r.id || crypto.randomUUID() })),
    }))
  }
  return (data as FilterRule[]).map(r => ({
    id: crypto.randomUUID(),
    op: "AND" as const,
    rules: [{ ...r, id: r.id || crypto.randomUUID() }],
  }))
}

function newFilterGroup(col = "", op: "AND" | "OR" = "AND"): FilterGroup {
  return { id: crypto.randomUUID(), op, rules: [newFilterRule(col)] }
}

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

async function getMappingSheets(file: File): Promise<{ sheets: string[] }> {
  const form = new FormData()
  form.append("file", file)
  const res = await fetch(`${API_BASE}/api/mapping/sheets`, { method: "POST", body: form })
  if (!res.ok) { const e = await res.json().catch(() => ({ detail: res.statusText })); throw new Error(e.detail) }
  return res.json()
}

async function getMappingColumns(file: File, sheetName?: string, skipRows?: number): Promise<{ columns: string[]; row_count: number }> {
  const form = new FormData()
  form.append("file", file)
  if (sheetName) form.append("sheet_name", sheetName)
  if (skipRows) form.append("skip_rows", String(skipRows))
  const res = await fetch(`${API_BASE}/api/mapping/columns`, { method: "POST", body: form })
  if (!res.ok) { const e = await res.json().catch(() => ({ detail: res.statusText })); throw new Error(e.detail) }
  return res.json()
}

async function getMappingPreview(file: File, secondaryFiles: SecondaryFile[], config: object): Promise<PreviewResult> {
  const form = new FormData()
  form.append("file", file)
  for (const sec of secondaryFiles) {
    if (sec.file) form.append("secondary_files", sec.file)
  }
  form.append("config_json", JSON.stringify(config))
  const res = await fetch(`${API_BASE}/api/mapping/preview`, { method: "POST", body: form })
  if (!res.ok) { const e = await res.json().catch(() => ({ detail: res.statusText })); throw new Error(e.detail) }
  return res.json()
}

async function downloadMapping(file: File, secondaryFiles: SecondaryFile[], config: object): Promise<{ blob: Blob; filename: string }> {
  const form = new FormData()
  form.append("file", file)
  for (const sec of secondaryFiles) {
    if (sec.file) form.append("secondary_files", sec.file)
  }
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
    label: "Séquences",
    items: [
      { formula: "=ROW()", desc: "Index 0-based : 0, 1, 2, 3…" },
      { formula: "=ROW(1)", desc: "Index 1-based : 1, 2, 3, 4…" },
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
    label: "Condition",
    items: [
      { formula: '=IF(Col="val", "oui", "non")', desc: 'Si Col vaut "val" → "oui", sinon "non"' },
      { formula: "=IF(Col>100, \"Heavy\", \"Light\")", desc: "Comparaison numérique" },
      { formula: '=IF(AND(A="X", B>5), "ok", "ko")', desc: "ET : les deux conditions vraies" },
      { formula: '=IF(OR(A="X", A="Y"), "match", "no")', desc: "OU : au moins une vraie" },
    ],
  },
]

// ─── Formula syntax highlighting ─────────────────────────────────────────────

const PAREN_COLORS = ["#1E5BA8", "#B45309", "#15803D", "#7C3AED", "#0369A1"]

function highlightFormula(formula: string): Array<{ type: string; v: string; depth?: number }> {
  if (!formula) return []
  const re = /(=|\bIF|\bSI|\bAND|\bET|\bOR|\bOU|\bNOT|\bLEFT|\bRIGHT|\bMID|\bUPPER|\bLOWER|\bTRIM|\bLEN|\bCONCAT|\bROW|\bROUND|\bABS|\bMIN|\bMAX|\bSUM|\bCOUNT|\bAVERAGE|\bTEXT|\bYEAR|\bMONTH|\bDAY|\bDATEDIFF|\bTODAY|\bVLOOKUP|\bRECHERCHEV|\bMATCH|\bEQUIV|\bINDEX|\bLET|\bCHOOSE|\bRAND|\bALEA|\bSUBSTITUTE|\bSPLIT|\bJOIN|\bTEXTBEFORE|\bTEXTAFTER)\b|"([^"]*)"|(\d+\.?\d*)|([a-zA-Z_][a-zA-Z0-9_.]*)|([+\-*/&<>=!]+)|([(),])/g
  const out: Array<{ type: string; v: string; depth?: number }> = []
  let m: RegExpExecArray | null
  let last = 0
  let depth = 0
  while ((m = re.exec(formula)) !== null) {
    if (m.index > last) out.push({ type: "txt", v: formula.slice(last, m.index) })
    if (m[1]) out.push({ type: "fn", v: m[0] })
    else if (m[2] !== undefined) out.push({ type: "str", v: `"${m[2]}"` })
    else if (m[3]) out.push({ type: "num", v: m[0] })
    else if (m[4]) out.push({ type: "ref", v: m[0] })
    else if (m[5]) out.push({ type: "op", v: m[0] })
    else if (m[6]) {
      const v = m[0]
      if (v === "(") {
        out.push({ type: "paren", v, depth })
        depth++
      } else if (v === ")") {
        depth--
        if (depth < 0) { out.push({ type: "paren_err", v }); depth = 0 }
        else out.push({ type: "paren", v, depth })
      } else {
        // comma — inherit depth of enclosing parens
        out.push({ type: "comma", v, depth: Math.max(0, depth - 1) })
      }
    }
    last = re.lastIndex
  }
  if (last < formula.length) out.push({ type: "txt", v: formula.slice(last) })
  return out
}

function FormulaHighlight({ value }: { value: string }) {
  const tokens = useMemo(() => highlightFormula(value), [value])
  if (!value) return <span style={{ color: "var(--text-disabled)", fontStyle: "italic", fontSize: 11 }}>—</span>
  return (
    <span style={{ fontFamily: "var(--font-mono)", fontSize: 12 }}>
      {tokens.map((t, i) => {
        if (t.type === "fn")       return <span key={i} className={s.tkFn}>{t.v}</span>
        if (t.type === "ref")      return <span key={i} className={s.tkRef}>{t.v}</span>
        if (t.type === "str")      return <span key={i} className={s.tkStr}>{t.v}</span>
        if (t.type === "num")      return <span key={i} className={s.tkNum}>{t.v}</span>
        if (t.type === "op")       return <span key={i} className={s.tkOp}>{t.v}</span>
        if (t.type === "paren") {
          const c = PAREN_COLORS[(t.depth ?? 0) % PAREN_COLORS.length]
          return <span key={i} style={{ color: c, fontWeight: 600 }}>{t.v}</span>
        }
        if (t.type === "paren_err") return <span key={i} className={s.tkParenErr}>{t.v}</span>
        if (t.type === "comma") {
          const c = PAREN_COLORS[(t.depth ?? 0) % PAREN_COLORS.length]
          return <span key={i} style={{ color: c, opacity: 0.75 }}>{t.v}</span>
        }
        return <span key={i}>{t.v}</span>
      })}
    </span>
  )
}

function EditableFormulaCell({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const [editing, setEditing] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  useEffect(() => { if (editing) inputRef.current?.focus() }, [editing])

  if (editing) {
    return (
      <input
        ref={inputRef}
        value={value}
        onChange={e => onChange(e.target.value)}
        onBlur={() => setEditing(false)}
        onKeyDown={e => e.key === "Escape" && setEditing(false)}
        placeholder='=Colonne ou ="constante"'
        className={`${s.formulaCell} ${s.formulaCellEditing}`}
        style={{ cursor: "text" }}
      />
    )
  }
  return (
    <div
      onClick={() => setEditing(true)}
      className={s.formulaCell}
      title="Cliquer pour modifier"
    >
      {value
        ? <FormulaHighlight value={value} />
        : <span style={{ color: "var(--text-disabled)", fontStyle: "italic", fontSize: 11 }}>Cliquer pour éditer…</span>
      }
    </div>
  )
}

// ─── Checkbox ─────────────────────────────────────────────────────────────────

function Cb({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <button
      type="button"
      onClick={() => onChange(!checked)}
      className={`${s.checkbox} ${checked ? s.checkboxChecked : ""}`}
      aria-checked={checked}
    />
  )
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function MappingPageWrapper() {
  return <Suspense><MappingPage /></Suspense>
}

function MappingPage() {
  const searchParams = useSearchParams()
  const scenarioId = searchParams.get("scenarioId")
  const mappingId = searchParams.get("mappingId")

  // Source
  const [sourceFile, setSourceFile] = useState<File | null>(null)
  const [sourceColumns, setSourceColumns] = useState<string[]>([])
  const [sourceRowCount, setSourceRowCount] = useState<number | null>(null)
  const [isLoadingSource, setIsLoadingSource] = useState(false)
  const [sourceSheets, setSourceSheets] = useState<string[]>([])
  const [sourceSheetName, setSourceSheetName] = useState<string>("")
  const [sourceSkipRows, setSourceSkipRows] = useState<number>(0)
  const sourceInputRef = useRef<HTMLInputElement>(null)

  // Secondary files
  const [secondaryFiles, setSecondaryFiles] = useState<SecondaryFile[]>([])
  const secondaryInputRefs = useRef<Map<string, HTMLInputElement>>(new Map())

  // Target
  const targetInputRef = useRef<HTMLInputElement>(null)
  const [isLoadingTarget, setIsLoadingTarget] = useState(false)
  const [newColName, setNewColName] = useState("")
  const [targetTab, setTargetTab] = useState<"manual" | "file">("manual")

  // Rows
  const [rows, setRows] = useState<MappingRow[]>([])

  // Filters
  const [filterGroups, setFilterGroups] = useState<FilterGroup[]>([])
  const [outputFilterGroups, setOutputFilterGroups] = useState<FilterGroup[]>([])

  // Options
  const [dedupByPK, setDedupByPK] = useState(false)

  // UI
  const [showFormulaPanel, setShowFormulaPanel] = useState(false)
  const [formulaSearch, setFormulaSearch] = useState("")
  const [tableLayout, setTableLayout] = useState<"table" | "hybrid" | "cards">("table")
  const [secondaryExpanded, setSecondaryExpanded] = useState(true)
  const [showConfigDropdown, setShowConfigDropdown] = useState(false)
  const configDropdownRef = useRef<HTMLDivElement>(null)

  // Preview
  const [isPreviewing, setIsPreviewing] = useState(false)
  const [previewData, setPreviewData] = useState<PreviewResult | null>(null)
  const [showPreviewModal, setShowPreviewModal] = useState(false)
  const [outputFormat, setOutputFormat] = useState<"csv" | "excel">("csv")
  const [outputFilename, setOutputFilename] = useState("mapping_output")
  const [isDownloading, setIsDownloading] = useState(false)

  // Configs
  const [savedConfigs, setSavedConfigs] = useState<MappingConfig[]>([])
  const [configName, setConfigName] = useState("")
  const [showSaveModal, setShowSaveModal] = useState(false)
  const [showLoadModal, setShowLoadModal] = useState(false)
  const [showDeleteModal, setShowDeleteModal] = useState(false)
  const [selectedToDelete, setSelectedToDelete] = useState<MappingConfig | null>(null)
  const [isSaving, setIsSaving] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)
  const [isLoadingConfigs, setIsLoadingConfigs] = useState(false)

  useEffect(() => {
    loadConfigs()
    if (mappingId) loadMappingFromScenario()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mappingId])

  // Close config dropdown on outside click
  useEffect(() => {
    if (!showConfigDropdown) return
    const handler = (e: MouseEvent) => {
      if (configDropdownRef.current && !configDropdownRef.current.contains(e.target as Node))
        setShowConfigDropdown(false)
    }
    document.addEventListener("mousedown", handler)
    return () => document.removeEventListener("mousedown", handler)
  }, [showConfigDropdown])

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

  async function loadMappingFromScenario() {
    if (!mappingId) return
    const { data, error } = await supabase.from("mappings").select("*").eq("id", mappingId).single()
    if (error || !data) return
    setRows(data.rows || [])
    setFilterGroups(toFilterGroups(data.filters || []))
    setOutputFilterGroups(toFilterGroups(data.output_filters || []))
    setDedupByPK(data.dedup_by_pk || false)
    setConfigName(data.name || "")
    setSecondaryFiles((data.joins || []).map((j: JoinSavedConfig) => ({
      id: crypto.randomUUID(),
      file: null,
      alias: j.alias,
      columns: [],
      onPrimary: j.on_primary,
      onSecondary: j.on_secondary,
      isLoading: false,
      availableSheets: [],
      sheetName: "",
      skipRows: 0,
    })))
  }

  // ── Source file ──────────────────────────────────────────────────────────

  async function handleSourceFile(file: File) {
    setIsLoadingSource(true)
    setSourceFile(file)
    setSourceColumns([])
    setSourceRowCount(null)
    setSourceSheets([])
    setSourceSheetName("")
    setSourceSkipRows(0)
    try {
      const sheetsResult = await getMappingSheets(file)
      const sheets = sheetsResult.sheets
      setSourceSheets(sheets)
      const defaultSheet = sheets[0] ?? ""
      setSourceSheetName(defaultSheet)
      const result = await getMappingColumns(file, defaultSheet, 0)
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

  async function reloadSourceColumns(file: File, sheetName: string, skipRows: number) {
    setIsLoadingSource(true)
    setSourceColumns([])
    setSourceRowCount(null)
    try {
      const result = await getMappingColumns(file, sheetName, skipRows)
      setSourceColumns(result.columns)
      setSourceRowCount(result.row_count)
      toast.success(`${result.columns.length} colonnes · ${result.row_count.toLocaleString()} lignes`)
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Impossible de recharger les colonnes")
    } finally {
      setIsLoadingSource(false)
    }
  }

  async function reloadSecondaryColumns(secId: string, file: File, sheetName: string, skipRows: number) {
    setSecondaryFiles(fs => fs.map(s => s.id === secId ? { ...s, isLoading: true, columns: [], onSecondary: "" } : s))
    try {
      const result = await getMappingColumns(file, sheetName, skipRows)
      setSecondaryFiles(fs => fs.map(s => s.id === secId ? {
        ...s, isLoading: false, columns: result.columns,
        onSecondary: result.columns[0] ?? "",
      } : s))
    } catch {
      setSecondaryFiles(fs => fs.map(s => s.id === secId ? { ...s, isLoading: false } : s))
      toast.error("Impossible de recharger les colonnes")
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

  function removeRow(id: string) { setRows(r => r.filter(row => row.id !== id)) }

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
          return { ...row, sourceCol: newSrc, formula: isSimple ? (newSrc ? `=${newSrc}` : "") : row.formula }
        }
        return { ...row, [field]: value }
      })
    )
  }

  function togglePK(id: string, checked: boolean) {
    setRows(r => r.map(row => ({ ...row, isPK: row.id === id ? checked : checked ? false : row.isPK })))
  }

  // ── Preview & Download ───────────────────────────────────────────────────

  function buildConfig(format: "csv" | "excel", filename: string) {
    const ext = format === "excel" ? ".xlsx" : ".csv"
    const baseName = filename.trim() || "mapping_output"
    const finalName = baseName.endsWith(ext) ? baseName : `${baseName}${ext}`
    const validJoins = secondaryFiles.filter(s => s.file && s.alias.trim() && s.onPrimary && s.onSecondary)
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
      filters: [],
      output_filters: [],
      filter_groups: filterGroups.map(g => ({
        id: g.id, op: g.op,
        rules: g.rules.map(r => ({ col: r.col, op: r.op, val: r.val })),
      })),
      output_filter_groups: outputFilterGroups.map(g => ({
        id: g.id, op: g.op,
        rules: g.rules.map(r => ({ col: r.col, op: r.op, val: r.val })),
      })),
      dedup_by_pk: dedupByPK,
      output_format: format,
      output_filename: finalName,
      sheet_name: sourceSheetName || undefined,
      skip_rows: sourceSkipRows || 0,
      joins: validJoins.map(s => ({
        alias: s.alias.trim(),
        on_primary: s.onPrimary,
        on_secondary: s.onSecondary,
        sheet_name: s.sheetName || undefined,
        skip_rows: s.skipRows || 0,
      })),
    }
  }

  const allSourceColumns = [
    ...sourceColumns,
    ...secondaryFiles
      .filter(s => s.alias.trim() && s.columns.length > 0)
      .flatMap(s => s.columns.map(col => `${s.alias.trim()}.${col}`)),
  ]

  async function handlePreview() {
    if (!sourceFile) { toast.error("Veuillez charger un fichier source"); return }
    if (rows.length === 0) { toast.error("Aucune colonne définie"); return }
    setIsPreviewing(true)
    try {
      const config = buildConfig(outputFormat, outputFilename)
      const validSecondary = secondaryFiles.filter(s => s.file && s.alias.trim() && s.onPrimary && s.onSecondary)
      const result = await getMappingPreview(sourceFile, validSecondary, config)
      setPreviewData(result)
      setShowPreviewModal(true)
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
      const validSecondary = secondaryFiles.filter(s => s.file && s.alias.trim() && s.onPrimary && s.onSecondary)
      const { blob, filename } = await downloadMapping(sourceFile, validSecondary, config)
      const url = URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      a.download = filename
      a.click()
      URL.revokeObjectURL(url)
      toast.success("Fichier téléchargé !")
      setShowPreviewModal(false)
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
      const joinsToSave = secondaryFiles
        .filter(s => s.alias.trim() && s.onPrimary && s.onSecondary)
        .map(s => ({ alias: s.alias.trim(), on_primary: s.onPrimary, on_secondary: s.onSecondary }))

      if (mappingId) {
        const { error } = await supabase
          .from("mappings")
          .update({ rows, filters: filterGroups, output_filters: outputFilterGroups, dedup_by_pk: dedupByPK, joins: joinsToSave })
          .eq("id", mappingId)
        if (error) throw error
        toast.success(`Mapping "${name}" sauvegardé`)
        setShowSaveModal(false)
        return
      }

      const existing = savedConfigs.find(c => c.name === name)
      if (existing) {
        const { error } = await supabase
          .from("mapping_configs")
          .update({ rows, filters: filterGroups, output_filters: outputFilterGroups, dedup_by_pk: dedupByPK, joins: joinsToSave })
          .eq("id", existing.id)
        if (error) throw error
      } else {
        const { error } = await supabase
          .from("mapping_configs")
          .insert({ name, rows, filters: filterGroups, output_filters: outputFilterGroups, dedup_by_pk: dedupByPK, joins: joinsToSave })
        if (error) throw error
      }
      toast.success(`Configuration "${name}" sauvegardée`)
      setShowSaveModal(false)
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
    setFilterGroups(toFilterGroups(cfg.filters ?? []))
    setOutputFilterGroups(toFilterGroups(cfg.output_filters ?? []))
    setDedupByPK(cfg.dedup_by_pk)
    setSecondaryFiles((cfg.joins ?? []).map((j: JoinSavedConfig) => ({
      id: crypto.randomUUID(),
      file: null,
      alias: j.alias,
      columns: [],
      onPrimary: j.on_primary,
      onSecondary: j.on_secondary,
      isLoading: false,
      availableSheets: [],
      sheetName: "",
      skipRows: 0,
    })))
    setShowLoadModal(false)
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
      setShowDeleteModal(false)
      setSelectedToDelete(null)
      await loadConfigs()
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Erreur lors de la suppression")
    } finally {
      setIsDeleting(false)
    }
  }

  const step1Done = !!sourceFile && sourceColumns.length > 0
  const step2Done = rows.length > 0
  const canPreview = step1Done && step2Done
  const pkExists = rows.some(r => r.isPK)

  // ── Filter helpers ────────────────────────────────────────────────────────

  function FilterSection({
    label, num, groups, setGroups, colOptions,
  }: {
    label: string; num: string
    groups: FilterGroup[]; setGroups: React.Dispatch<React.SetStateAction<FilterGroup[]>>
    colOptions: string[]
  }) {
    const totalRules = groups.reduce((s, g) => s + g.rules.length, 0)
    return (
      <div className={s.section}>
        <div className={s.sectionHead}>
          <span className={s.sectionNum}>{num}</span>
          <span className={s.sectionTitle}>{label}</span>
          {totalRules > 0 && (
            <span className={`${s.badge} ${s.badgePrimary}`}>
              {totalRules} actif{totalRules > 1 ? "s" : ""}
            </span>
          )}
          <div className={s.sectionLine} />
          <button
            className={`${s.btn} ${s.btnSecondary} ${s.btnSm}`}
            onClick={() => setGroups(gs => [...gs, newFilterGroup(colOptions[0] ?? "")])}
            disabled={colOptions.length === 0}
          >
            <Plus size={12} /> Ajouter un filtre
          </button>
        </div>

        {groups.length === 0 ? (
          <p className={s.emptyMsg}>
            Aucun filtre — toutes les lignes seront traitées.
            {colOptions.length === 0 && " Chargez d'abord un fichier source."}
          </p>
        ) : (
          <div className={s.filterStack}>
            {groups.map((group, gIdx) => (
              <div key={group.id}>
                {gIdx > 0 && (
                  <div className={s.filterGroupAndLabel}>
                    <div className={s.sectionLine} />
                    <span className={s.filterGroupAndText}>ET</span>
                    <div className={s.sectionLine} />
                  </div>
                )}
                <div className={s.filterGroup}>
                  <div className={s.filterGroupHead}>
                    <button
                      className={`${s.opToggle} ${group.op === "OR" ? s.opToggleOr : s.opToggleAnd}`}
                      onClick={() => setGroups(gs => gs.map(g => g.id === group.id ? { ...g, op: g.op === "AND" ? "OR" : "AND" } : g))}
                    >
                      {group.op === "OR" ? "OU" : "ET"}
                    </button>
                    <span style={{ fontSize: 12, color: "var(--text-tertiary)" }}>
                      entre ces {group.rules.length} condition{group.rules.length > 1 ? "s" : ""}
                    </span>
                    <div className={s.spacer} />
                    <button
                      className={`${s.btn} ${s.btnGhost} ${s.btnXs}`}
                      onClick={() => setGroups(gs => gs.map(g => g.id === group.id ? { ...g, rules: [...g.rules, newFilterRule(colOptions[0] ?? "")] } : g))}
                    >
                      <Plus size={11} /> Condition
                    </button>
                    <button
                      className={s.btnIcon}
                      onClick={() => setGroups(gs => gs.filter(g => g.id !== group.id))}
                      style={{ color: "var(--text-tertiary)" }}
                    >
                      <X size={13} />
                    </button>
                  </div>
                  <div className={s.filterRows}>
                    {group.rules.map((f, rIdx) => {
                      const opDef = FILTER_OPS.find(o => o.value === f.op)
                      return (
                        <div key={f.id} className={s.filterRow}>
                          <select
                            className={`${s.select} ${s.selectSm}`}
                            value={f.col || ""}
                            onChange={e => setGroups(gs => gs.map(g => g.id === group.id ? { ...g, rules: g.rules.map(r => r.id === f.id ? { ...r, col: e.target.value } : r) } : g))}
                          >
                            <option value="">(choisir)</option>
                            {colOptions.map(c => <option key={c} value={c}>{c}</option>)}
                          </select>
                          <select
                            className={`${s.select} ${s.selectSm}`}
                            value={f.op}
                            onChange={e => setGroups(gs => gs.map(g => g.id === group.id ? { ...g, rules: g.rules.map(r => r.id === f.id ? { ...r, op: e.target.value as FilterOp, val: "" } : r) } : g))}
                          >
                            {FILTER_OPS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                          </select>
                          {opDef?.noVal
                            ? <span className={s.muted} style={{ fontStyle: "italic" }}>—</span>
                            : <input
                                className={`${s.input} ${s.inputSm}`}
                                value={f.val}
                                onChange={e => setGroups(gs => gs.map(g => g.id === group.id ? { ...g, rules: g.rules.map(r => r.id === f.id ? { ...r, val: e.target.value } : r) } : g))}
                                placeholder="valeur…"
                              />
                          }
                          <button
                            className={s.btnIcon}
                            onClick={() => setGroups(gs => gs.map(g => g.id === group.id ? { ...g, rules: g.rules.filter(r => r.id !== f.id) } : g).filter(g => g.rules.length > 0))}
                            style={{ color: "var(--text-tertiary)" }}
                          >
                            <X size={13} />
                          </button>
                          {rIdx > 0 && (
                            <div className={s.filterRowPrefix} style={{ position: "absolute", left: -36, color: "var(--text-tertiary)", fontSize: 10 }}>
                              {group.op}
                            </div>
                          )}
                        </div>
                      )
                    })}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    )
  }

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <AppShell>
      <div className={s.tool}>

        {/* ── Sticky inner header ──────────────────────────────────────────── */}
        <div className={s.innerHeader}>
          <div className={s.innerHeaderRow}>

            {/* Stepper */}
            <div className={s.stepper}>
              {[
                { n: 1, label: "Fichiers", done: step1Done, active: !step1Done },
                { n: 2, label: "Jointures", done: false, active: false },
                { n: 3, label: "Filtres", done: false, active: false },
                { n: 4, label: "Colonnes", done: step2Done, active: step1Done && !step2Done },
                { n: 5, label: "Export", done: false, active: canPreview },
              ].map((st, i) => (
                <div key={st.n} style={{ display: "flex", alignItems: "center", gap: 2 }}>
                  {i > 0 && <div className={`${s.stepLine} ${st.done ? s.stepLineDone : ""}`} />}
                  <div className={`${s.step} ${st.done ? s.stepDone : ""} ${st.active ? s.stepActive : ""}`}>
                    <div className={s.stepDot}>
                      {st.done ? <CheckCircle size={11} /> : st.n}
                    </div>
                    <span>{st.label}</span>
                  </div>
                </div>
              ))}
            </div>

            {/* Header actions */}
            <div className={s.headerActions}>
              <button
                className={`${s.btn} ${s.btnGhost} ${s.btnSm}`}
                onClick={() => setShowFormulaPanel(true)}
              >
                <HelpCircle size={14} />
                Formules
              </button>
              <div className={s.dropdownWrap} ref={configDropdownRef}>
                <button
                  className={`${s.btn} ${s.btnSecondary} ${s.btnSm}`}
                  onClick={() => { loadConfigs(); setShowConfigDropdown(v => !v) }}
                >
                  <FolderOpen size={14} />
                  Configurations
                  {savedConfigs.length > 0 && (
                    <span className={s.badge} style={{ marginLeft: 4, fontSize: 10, padding: "1px 6px" }}>
                      {savedConfigs.length}
                    </span>
                  )}
                </button>
                {showConfigDropdown && (
                  <div className={s.dropdown}>
                    <div className={s.dropdownHead}>
                      <span>Gestion des configurations</span>
                      <button className={s.btnIcon} onClick={() => setShowConfigDropdown(false)}>
                        <X size={13} />
                      </button>
                    </div>
                    <div className={s.dropdownFoot}>
                      <button
                        className={`${s.btn} ${s.btnSecondary} ${s.btnSm}`}
                        style={{ flex: 1 }}
                        onClick={() => { setShowConfigDropdown(false); setShowLoadModal(true) }}
                      >
                        <FolderOpen size={13} /> Charger
                      </button>
                      <button
                        className={`${s.btn} ${s.btnPrimary} ${s.btnSm}`}
                        style={{ flex: 1 }}
                        disabled={rows.length === 0}
                        onClick={() => { setShowConfigDropdown(false); setShowSaveModal(true) }}
                      >
                        <Save size={13} /> Sauvegarder
                      </button>
                    </div>
                    {savedConfigs.length > 0 && (
                      <>
                        <div className={s.dropdownLabel}>Accès rapide</div>
                        <div className={s.dropdownList}>
                          {savedConfigs.slice(0, 6).map(cfg => (
                            <button
                              key={cfg.id}
                              className={s.dropdownItem}
                              onClick={() => { handleLoadConfig(cfg); setShowConfigDropdown(false) }}
                            >
                              <CheckCircle size={13} style={{ color: "var(--text-tertiary)", flexShrink: 0 }} />
                              <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                                {cfg.name}
                              </span>
                              <span className={s.dropdownItemMeta}>{cfg.rows.length}c</span>
                            </button>
                          ))}
                        </div>
                        <div className={s.dropdownSep} />
                        <button
                          className={s.dropdownItem}
                          style={{ color: "var(--primary)", fontSize: 12 }}
                          onClick={() => { setShowConfigDropdown(false); loadConfigs(); setShowDeleteModal(true) }}
                        >
                          <Trash2 size={13} /> Supprimer une configuration
                        </button>
                      </>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* ── Main content ─────────────────────────────────────────────────── */}
        <div className={s.main}>

          {/* Page intro */}
          <div className={s.pageIntro}>
            <h1 className={s.pageTitle}>Mapping de données</h1>
            <p className={s.pageSubtitle}>
              Chargez votre fichier source, définissez le schéma cible avec des formules et exportez.
            </p>
          </div>

          {/* ── Step 1 : Files ────────────────────────────────────────────── */}
          <div className={s.section}>
            <div className={s.sectionHead}>
              <span className={`${s.sectionNum} ${step1Done ? s.sectionNumActive : ""}`}>1</span>
              <span className={s.sectionTitle}>Fichiers</span>
              <div className={s.sectionLine} />
            </div>

            <div className={s.twoCol}>
              {/* Source file */}
              <div className={s.card}>
                <div className={s.cardHeader}>
                  <div>
                    <p className={s.cardTitle}>Fichier source</p>
                    <p className={s.cardDesc}>Excel ou CSV à lire</p>
                  </div>
                  {step1Done && (
                    <span className={`${s.badge} ${s.badgeSuccess}`}>
                      <CheckCircle size={11} /> Chargé
                    </span>
                  )}
                </div>
                <div className={s.cardBody}>
                  <input
                    ref={sourceInputRef}
                    type="file"
                    accept=".xlsx,.xls,.csv"
                    style={{ display: "none" }}
                    onChange={e => { const f = e.target.files?.[0]; if (f) handleSourceFile(f); e.target.value = "" }}
                  />
                  {!sourceFile ? (
                    <div
                      className={s.dropzone}
                      onClick={() => sourceInputRef.current?.click()}
                      onDragOver={e => e.preventDefault()}
                      onDrop={e => { e.preventDefault(); const f = e.dataTransfer.files[0]; if (f) handleSourceFile(f) }}
                    >
                      <div className={s.dropzoneIcon}><Upload size={16} /></div>
                      <p className={s.dropzoneText}>Glissez votre fichier ici</p>
                      <p className={s.dropzoneHint}>ou cliquez · .xlsx .xls .csv</p>
                    </div>
                  ) : (
                    <div className={s.fileLoaded}>
                      <div className={s.fileInfo}>
                        {sourceFile.name.endsWith(".csv")
                          ? <div className={s.fileIconCsv}>CSV</div>
                          : <div className={s.fileIconXlsx}>XLSX</div>
                        }
                        <div className={s.fileInfoMeta}>
                          <p className={s.fileName}>{sourceFile.name}</p>
                          <div className={s.fileStats}>
                            {sourceRowCount !== null ? (
                              <><strong>{sourceRowCount.toLocaleString()}</strong> lignes · <strong>{sourceColumns.length}</strong> colonnes</>
                            ) : isLoadingSource ? (
                              <span>Analyse…</span>
                            ) : null}
                          </div>
                        </div>
                        <button
                          className={s.btnIcon}
                          onClick={() => { setSourceFile(null); setSourceColumns([]); setSourceRowCount(null); setSourceSheets([]); setSourceSheetName(""); setSourceSkipRows(0) }}
                        >
                          <X size={13} />
                        </button>
                      </div>

                      {sourceColumns.length > 0 && (
                        <div className={s.colBadges}>
                          {sourceColumns.slice(0, 8).map(col => (
                            <span key={col} className={`${s.badge} ${s.badgeMono}`}>{col}</span>
                          ))}
                          {sourceColumns.length > 8 && (
                            <span className={s.badge}>+{sourceColumns.length - 8}</span>
                          )}
                        </div>
                      )}

                      <div className={s.advancedOpts}>
                        {sourceSheets.length > 1 && (
                          <div className={s.advRow}>
                            <span className={s.fieldLabel}>Feuille</span>
                            <select
                              className={`${s.select} ${s.selectSm}`}
                              style={{ flex: 1 }}
                              value={sourceSheetName}
                              onChange={e => { setSourceSheetName(e.target.value); reloadSourceColumns(sourceFile, e.target.value, sourceSkipRows) }}
                            >
                              {sourceSheets.map(sh => <option key={sh} value={sh}>{sh}</option>)}
                            </select>
                          </div>
                        )}
                        <div className={s.advRow}>
                          <span className={s.fieldLabel}>Sauter</span>
                          <input
                            type="number" min={0}
                            className={`${s.input} ${s.inputSm}`}
                            style={{ width: 60 }}
                            value={sourceSkipRows}
                            onChange={e => setSourceSkipRows(Math.max(0, parseInt(e.target.value) || 0))}
                            onKeyDown={e => e.key === "Enter" && reloadSourceColumns(sourceFile, sourceSheetName, sourceSkipRows)}
                          />
                          <span className={s.muted}>lignes</span>
                          <button
                            className={`${s.btn} ${s.btnSecondary} ${s.btnXs}`}
                            onClick={() => reloadSourceColumns(sourceFile, sourceSheetName, sourceSkipRows)}
                            disabled={isLoadingSource}
                          >
                            {isLoadingSource ? "…" : "Actualiser"}
                          </button>
                        </div>
                      </div>

                      <button
                        className={`${s.btn} ${s.btnGhost} ${s.btnSm}`}
                        style={{ width: "100%", justifyContent: "center" }}
                        onClick={() => sourceInputRef.current?.click()}
                      >
                        Changer de fichier
                      </button>
                    </div>
                  )}
                </div>
              </div>

              {/* Target schema */}
              <div className={s.card}>
                <div className={s.cardHeader}>
                  <div>
                    <p className={s.cardTitle}>Schéma cible</p>
                    <p className={s.cardDesc}>Colonnes de sortie</p>
                  </div>
                  {step2Done && (
                    <span className={`${s.badge} ${s.badgeSuccess}`}>
                      <CheckCircle size={11} />
                      {rows.filter(r => r.includeInOutput).length}/{rows.length} colonnes
                    </span>
                  )}
                </div>
                <div className={s.cardBody}>
                  <div className={s.tabs}>
                    <button
                      className={`${s.tab} ${targetTab === "manual" ? s.tabActive : ""}`}
                      onClick={() => setTargetTab("manual")}
                    >Manuel</button>
                    <button
                      className={`${s.tab} ${targetTab === "file" ? s.tabActive : ""}`}
                      onClick={() => setTargetTab("file")}
                    >Depuis fichier</button>
                  </div>

                  {targetTab === "manual" ? (
                    <>
                      <div className={s.targetAdd}>
                        <input
                          className={s.input}
                          placeholder="Nom de la colonne cible…"
                          value={newColName}
                          onChange={e => setNewColName(e.target.value)}
                          onKeyDown={e => e.key === "Enter" && handleAddColumn()}
                        />
                        <button className={`${s.btn} ${s.btnPrimary}`} onClick={handleAddColumn}>
                          <Plus size={15} />
                        </button>
                      </div>
                      {rows.length === 0 && (
                        <p className={s.muted}>Tapez un nom et Entrée pour ajouter une colonne.</p>
                      )}
                    </>
                  ) : (
                    <>
                      <input
                        ref={targetInputRef}
                        type="file"
                        accept=".xlsx,.xls,.csv"
                        style={{ display: "none" }}
                        onChange={e => { const f = e.target.files?.[0]; if (f) handleTargetFile(f); e.target.value = "" }}
                      />
                      <button
                        className={`${s.btn} ${s.btnSecondary}`}
                        style={{ width: "100%", marginBottom: 8 }}
                        onClick={() => targetInputRef.current?.click()}
                        disabled={isLoadingTarget}
                      >
                        <Upload size={14} />
                        {isLoadingTarget ? "Chargement…" : "Importer les en-têtes"}
                      </button>
                      <p className={s.muted}>Les en-têtes du fichier deviendront les colonnes cibles.</p>
                    </>
                  )}

                  {rows.length > 0 && (
                    <div className={s.targetList} style={{ marginTop: 10 }}>
                      {rows.map(row => (
                        <div key={row.id} className={s.targetItem}>
                          <span className={s.targetItemName}>{row.targetName || <em style={{ color: "var(--text-disabled)" }}>sans nom</em>}</span>
                          {row.isPK && <span className={`${s.badge} ${s.badgePrimary}`} style={{ fontSize: 10, padding: "1px 6px" }}>PK</span>}
                          <button className={s.btnIcon} style={{ width: 22, height: 22 }}
                            onClick={() => removeRow(row.id)}>
                            <X size={11} />
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* ── Secondary files ────────────────────────────────────────────── */}
          <div className={s.section}>
            <div className={s.sectionHead}>
              <span className={s.sectionNum}>+</span>
              <span className={s.sectionTitle}>Fichiers secondaires (jointures)</span>
              {secondaryFiles.length > 0 && (
                <span className={s.badge}>{secondaryFiles.length}</span>
              )}
              <div className={s.sectionLine} />
              <button
                className={`${s.btn} ${s.btnGhost} ${s.btnXs}`}
                onClick={() => setSecondaryExpanded(v => !v)}
              >
                <ChevronDown size={13} style={{ transform: secondaryExpanded ? "none" : "rotate(-90deg)", transition: "transform .2s" }} />
                {secondaryExpanded ? "Réduire" : "Afficher"}
              </button>
              <button
                className={`${s.btn} ${s.btnSecondary} ${s.btnXs}`}
                disabled={!sourceFile}
                onClick={() => {
                  setSecondaryExpanded(true)
                  setSecondaryFiles(f => [...f, {
                    id: crypto.randomUUID(),
                    file: null,
                    alias: `ref${f.length + 1}`,
                    columns: [],
                    onPrimary: sourceColumns[0] ?? "",
                    onSecondary: "",
                    isLoading: false,
                    availableSheets: [],
                    sheetName: "",
                    skipRows: 0,
                  }])
                }}
              >
                <Plus size={11} /> Ajouter
              </button>
            </div>

            {secondaryExpanded && (
              secondaryFiles.length === 0 ? (
                <p className={s.emptyMsg}>
                  Aucun fichier secondaire.{!sourceFile && " Chargez d'abord le fichier principal."}
                </p>
              ) : (
                <div className={s.secondaryGrid}>
                  {secondaryFiles.map(sec => (
                    <div key={sec.id} className={s.secondaryCard}>
                      <div className={s.secondaryCardHead}>
                        <div className={s.aliasTag}>
                          <span style={{ fontSize: 11, color: "var(--info)", opacity: 0.7 }}>alias:</span>
                          <input
                            value={sec.alias}
                            onChange={e => setSecondaryFiles(fs => fs.map(s => s.id === sec.id ? { ...s, alias: e.target.value } : s))}
                            style={{
                              background: "transparent", border: "none", outline: "none",
                              fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--info)",
                              fontWeight: 600, width: 80,
                            }}
                          />
                        </div>
                        <span className={s.muted} style={{ flex: 1, margin: "0 8px", fontSize: 11 }}>
                          référencer comme <code style={{ fontFamily: "var(--font-mono)" }}>{sec.alias.trim() || "alias"}.Col</code>
                        </span>
                        <button
                          className={s.btnIcon}
                          onClick={() => setSecondaryFiles(fs => fs.filter(s => s.id !== sec.id))}
                        >
                          <X size={13} />
                        </button>
                      </div>

                      <div className={s.secondaryInner}>
                        {/* File upload */}
                        <div>
                          <input
                            ref={el => { if (el) secondaryInputRefs.current.set(sec.id, el); else secondaryInputRefs.current.delete(sec.id) }}
                            type="file" accept=".xlsx,.xls,.csv"
                            style={{ display: "none" }}
                            onChange={async e => {
                              const f = e.target.files?.[0]; e.target.value = ""
                              if (!f) return
                              setSecondaryFiles(fs => fs.map(s => s.id === sec.id ? { ...s, isLoading: true, file: f, columns: [], onSecondary: "", availableSheets: [], sheetName: "", skipRows: 0 } : s))
                              try {
                                const sheetsResult = await getMappingSheets(f)
                                const sheets = sheetsResult.sheets
                                const defaultSheet = sheets[0] ?? ""
                                const result = await getMappingColumns(f, defaultSheet, 0)
                                setSecondaryFiles(fs => fs.map(s => s.id === sec.id ? {
                                  ...s, isLoading: false, columns: result.columns,
                                  onSecondary: result.columns[0] ?? "",
                                  availableSheets: sheets, sheetName: defaultSheet, skipRows: 0,
                                } : s))
                              } catch {
                                setSecondaryFiles(fs => fs.map(s => s.id === sec.id ? { ...s, isLoading: false, file: null } : s))
                                toast.error("Impossible de lire le fichier secondaire")
                              }
                            }}
                          />
                          {!sec.file ? (
                            <div
                              className={s.dropzone}
                              style={{ padding: "16px 12px" }}
                              onClick={() => secondaryInputRefs.current.get(sec.id)?.click()}
                            >
                              <div className={s.dropzoneIcon} style={{ width: 28, height: 28, margin: "0 auto 6px" }}><Upload size={13} /></div>
                              <p className={s.dropzoneText} style={{ fontSize: 12 }}>Charger fichier</p>
                            </div>
                          ) : (
                            <div className={s.fileInfo} style={{ padding: "8px 10px" }}>
                              <FileSpreadsheet size={14} style={{ color: "var(--primary)", flexShrink: 0 }} />
                              <div className={s.fileInfoMeta}>
                                <p className={s.fileName} style={{ fontSize: 12 }}>{sec.file.name}</p>
                                <p className={s.muted}>{sec.columns.length} colonnes</p>
                              </div>
                              <button className={s.btnIcon} style={{ width: 20, height: 20 }}
                                onClick={() => setSecondaryFiles(fs => fs.map(s => s.id === sec.id ? { ...s, file: null, columns: [], onSecondary: "" } : s))}>
                                <X size={11} />
                              </button>
                            </div>
                          )}
                        </div>

                        {/* Join keys */}
                        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                          <div className={s.joinKeyBlock}>
                            <span className={s.joinKeyLabel}>Clé — fichier principal</span>
                            <select
                              className={`${s.select} ${s.selectSm}`}
                              value={sec.onPrimary}
                              onChange={e => setSecondaryFiles(fs => fs.map(s => s.id === sec.id ? { ...s, onPrimary: e.target.value } : s))}
                            >
                              <option value="">(choisir)</option>
                              {sourceColumns.map(c => <option key={c} value={c}>{c}</option>)}
                            </select>
                          </div>
                          <div className={s.joinKeyBlock}>
                            <span className={s.joinKeyLabel}>Clé — fichier secondaire</span>
                            <select
                              className={`${s.select} ${s.selectSm}`}
                              value={sec.onSecondary}
                              onChange={e => setSecondaryFiles(fs => fs.map(s => s.id === sec.id ? { ...s, onSecondary: e.target.value } : s))}
                              disabled={sec.columns.length === 0}
                            >
                              <option value="">(choisir)</option>
                              {sec.columns.map(c => <option key={c} value={c}>{c}</option>)}
                            </select>
                          </div>
                        </div>
                      </div>

                      {/* Sheet / skip rows */}
                      {sec.file && (
                        <div className={s.advancedOpts} style={{ marginTop: 10 }}>
                          {sec.availableSheets.length > 1 && (
                            <div className={s.advRow}>
                              <span className={s.fieldLabel}>Feuille</span>
                              <select
                                className={`${s.select} ${s.selectSm}`}
                                style={{ flex: 1 }}
                                value={sec.sheetName}
                                onChange={e => {
                                  setSecondaryFiles(fs => fs.map(s => s.id === sec.id ? { ...s, sheetName: e.target.value } : s))
                                  if (sec.file) reloadSecondaryColumns(sec.id, sec.file, e.target.value, sec.skipRows)
                                }}
                              >
                                {sec.availableSheets.map(sh => <option key={sh} value={sh}>{sh}</option>)}
                              </select>
                            </div>
                          )}
                          <div className={s.advRow}>
                            <span className={s.fieldLabel}>Sauter</span>
                            <input
                              type="number" min={0}
                              className={`${s.input} ${s.inputSm}`}
                              style={{ width: 56 }}
                              value={sec.skipRows}
                              onChange={e => setSecondaryFiles(fs => fs.map(s => s.id === sec.id ? { ...s, skipRows: Math.max(0, parseInt(e.target.value) || 0) } : s))}
                            />
                            <span className={s.muted}>lignes</span>
                            <button
                              className={`${s.btn} ${s.btnSecondary} ${s.btnXs}`}
                              onClick={() => { if (sec.file) reloadSecondaryColumns(sec.id, sec.file, sec.sheetName, sec.skipRows) }}
                              disabled={sec.isLoading}
                            >
                              {sec.isLoading ? "…" : "Actualiser"}
                            </button>
                          </div>
                        </div>
                      )}

                      {sec.file && sec.alias.trim() && (!sec.onPrimary || !sec.onSecondary) && (
                        <div className={s.warnChip} style={{ marginTop: 10 }}>
                          <AlertCircle size={13} />
                          Définissez les deux clés de jointure.
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )
            )}
          </div>

          {/* ── Source filters ─────────────────────────────────────────────── */}
          <FilterSection
            label="Filtres source"
            num="3"
            groups={filterGroups}
            setGroups={setFilterGroups}
            colOptions={allSourceColumns}
          />

          {/* ── Mapping table ──────────────────────────────────────────────── */}
          <div className={s.section}>
            <div className={s.sectionHead}>
              <span className={`${s.sectionNum} ${step2Done ? s.sectionNumActive : ""}`}>2</span>
              <span className={s.sectionTitle}>Mapping des colonnes</span>
              {rows.length > 0 && (
                <span className={s.badge}>
                  {rows.filter(r => r.includeInOutput).length} colonnes
                </span>
              )}
              <div className={s.sectionLine} />
              {/* Dedup toggle */}
              <label className={s.toggleWrap}>
                <button
                  type="button"
                  className={`${s.toggle} ${dedupByPK ? s.toggleOn : ""}`}
                  onClick={() => setDedupByPK(v => !v)}
                />
                Dédupliquer par PK
              </label>
              {dedupByPK && !pkExists && (
                <span className={`${s.badge} ${s.badgePrimary}`}>
                  <AlertCircle size={11} /> Aucune PK
                </span>
              )}
              {/* Formula help */}
              <button
                className={`${s.btn} ${s.btnGhost} ${s.btnXs}`}
                onClick={() => setShowFormulaPanel(true)}
              >
                <HelpCircle size={13} /> Formules
              </button>
              {/* Layout toggle */}
              <div style={{ display: "flex", border: "1px solid var(--border)", borderRadius: "var(--radius)", overflow: "hidden" }}>
                {(["table", "hybrid", "cards"] as const).map(mode => (
                  <button
                    key={mode}
                    onClick={() => setTableLayout(mode)}
                    style={{
                      height: 28, padding: "0 10px", display: "flex", alignItems: "center", gap: 5,
                      background: tableLayout === mode ? "var(--primary)" : "transparent",
                      color: tableLayout === mode ? "#fff" : "var(--text-tertiary)",
                      border: "none", borderLeft: mode !== "table" ? "1px solid var(--border)" : "none",
                      cursor: "pointer", transition: "all .15s", fontSize: 11, fontWeight: 600,
                    }}
                  >
                    {mode === "table" && <LayoutList size={12} />}
                    {mode === "hybrid" && <LayoutGrid size={12} />}
                    {mode === "cards" && <LayoutGrid size={12} />}
                    {mode}
                  </button>
                ))}
              </div>
            </div>

            <div className={s.mappingWrap}>
              {rows.length === 0 ? (
                <div className={s.emptyState}>
                  <div className={s.emptyStateIcon}><GitMerge size={56} /></div>
                  <h3>Aucune colonne définie</h3>
                  <p>Ajoutez des colonnes dans le schéma cible ci-dessus</p>
                </div>
              ) : tableLayout === "table" ? (
                <>
                  <div className={s.tableOuter}>
                    <table className={s.mappingTable}>
                      <thead>
                        <tr>
                          <th style={{ width: 150 }}>Colonne cible</th>
                          <th style={{ width: 160 }}>Source</th>
                          <th>Formule <HelpCircle size={11} style={{ cursor: "pointer", verticalAlign: "middle", marginLeft: 2, color: "var(--text-tertiary)" }} onClick={() => setShowFormulaPanel(true)} /></th>
                          <th style={{ width: 40, textAlign: "center" }}>PK</th>
                          <th style={{ width: 110 }}>Agrégation</th>
                          <th style={{ width: 120 }}>Format</th>
                          <th style={{ width: 36, textAlign: "center" }}>Incl.</th>
                          <th style={{ width: 76 }} />
                        </tr>
                      </thead>
                      <tbody>
                        {rows.map((row, idx) => (
                          <tr
                            key={row.id}
                            className={`${!row.includeInOutput ? s.rowDisabled : row.isPK ? s.rowPk : ""}`}
                          >
                            <td>
                              <input
                                className={s.cellTargetName}
                                value={row.targetName}
                                onChange={e => updateRow(row.id, "targetName", e.target.value)}
                              />
                            </td>
                            <td>
                              <select
                                className={`${s.select} ${s.selectSm}`}
                                value={row.sourceCol || ""}
                                onChange={e => updateRow(row.id, "sourceCol", e.target.value)}
                              >
                                <option value="">(aucune)</option>
                                {allSourceColumns.map(c => <option key={c} value={c}>{c}</option>)}
                              </select>
                            </td>
                            <td>
                              <EditableFormulaCell
                                value={row.formula}
                                onChange={v => updateRow(row.id, "formula", v)}
                              />
                            </td>
                            <td style={{ textAlign: "center" }}>
                              <Cb checked={row.isPK} onChange={checked => togglePK(row.id, checked)} />
                            </td>
                            <td>
                              <select
                                className={`${s.select} ${s.selectSm}`}
                                value={row.aggregation}
                                onChange={e => updateRow(row.id, "aggregation", e.target.value)}
                                disabled={!dedupByPK}
                              >
                                {AGGREGATIONS.map(a => <option key={a} value={a}>{a}</option>)}
                              </select>
                            </td>
                            <td>
                              <select
                                className={`${s.select} ${s.selectSm}`}
                                value={row.format}
                                onChange={e => updateRow(row.id, "format", e.target.value)}
                              >
                                {FORMATS.map(f => <option key={f} value={f}>{f}</option>)}
                              </select>
                            </td>
                            <td style={{ textAlign: "center" }}>
                              <button
                                className={s.btnIcon}
                                style={{ color: row.includeInOutput ? "var(--primary)" : "var(--text-disabled)" }}
                                title={row.includeInOutput ? "Inclus (cliquer pour masquer)" : "Intermédiaire (cliquer pour inclure)"}
                                onClick={() => updateRow(row.id, "includeInOutput", !row.includeInOutput)}
                              >
                                {row.includeInOutput ? <Eye size={14} /> : <EyeOff size={14} />}
                              </button>
                            </td>
                            <td>
                              <div className={s.rowActions}>
                                <button className={s.btnIcon} onClick={() => moveRow(row.id, -1)} disabled={idx === 0}><ArrowUp size={13} /></button>
                                <button className={s.btnIcon} onClick={() => moveRow(row.id, 1)} disabled={idx === rows.length - 1}><ArrowDown size={13} /></button>
                                <button className={s.btnIcon} style={{ color: "var(--text-tertiary)" }}
                                  onMouseEnter={e => (e.currentTarget.style.color = "var(--primary)")}
                                  onMouseLeave={e => (e.currentTarget.style.color = "var(--text-tertiary)")}
                                  onClick={() => removeRow(row.id)}>
                                  <X size={13} />
                                </button>
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <div className={s.mappingStatus}>
                    <span>{rows.length} ligne{rows.length > 1 ? "s" : ""} · {rows.filter(r => r.includeInOutput).length} dans l&apos;output</span>
                    <button
                      className={`${s.btn} ${s.btnGhost} ${s.btnXs}`}
                      onClick={() => setRows(r => [...r, newRow("")])}
                    >
                      <Plus size={12} /> Ajouter une ligne
                    </button>
                  </div>
                </>
              ) : tableLayout === "hybrid" ? (
                <>
                  <div className={s.mappingHybrid}>
                    <div className={s.hybridHeader}>
                      <span />
                      <span style={{ textAlign: "right" }}>#</span>
                      <span>Colonne cible</span>
                      <span>Source</span>
                      <span>Formule</span>
                      <span>Format</span>
                      <span>Agrégation</span>
                      <span style={{ textAlign: "center" }}>Incl.</span>
                      <span />
                      <span />
                      <span />
                    </div>
                    {rows.map((row, idx) => (
                      <div
                        key={row.id}
                        className={`${s.hybridRow} ${row.isPK ? s.hybridRowPk : ""} ${!row.includeInOutput ? s.hybridRowDisabled : ""}`}
                      >
                        {/* PK radio */}
                        <button
                          className={s.hybridPkBtn}
                          title={row.isPK ? "Clé primaire (cliquer pour retirer)" : "Définir comme clé primaire"}
                          onClick={() => togglePK(row.id, !row.isPK)}
                        >
                          <div className={`${s.hybridPkDot} ${row.isPK ? s.hybridPkDotActive : ""}`} />
                        </button>
                        {/* Index */}
                        <span className={s.hybridNum}>{idx + 1}</span>
                        {/* Target name */}
                        <input
                          className={s.hybridName}
                          value={row.targetName}
                          onChange={e => updateRow(row.id, "targetName", e.target.value)}
                        />
                        {/* Source */}
                        <div className={s.hybridSource}>
                          <ArrowRight size={11} style={{ flexShrink: 0, color: "var(--text-tertiary)" }} />
                          <select
                            className={`${s.select} ${s.selectSm}`}
                            style={{ flex: 1, minWidth: 0 }}
                            value={row.sourceCol || ""}
                            onChange={e => updateRow(row.id, "sourceCol", e.target.value)}
                          >
                            <option value="">(aucune)</option>
                            {allSourceColumns.map(c => <option key={c} value={c}>{c}</option>)}
                          </select>
                        </div>
                        {/* Formula */}
                        <EditableFormulaCell
                          value={row.formula}
                          onChange={v => updateRow(row.id, "formula", v)}
                        />
                        {/* Format */}
                        <select
                          className={`${s.select} ${s.selectSm}`}
                          value={row.format}
                          onChange={e => updateRow(row.id, "format", e.target.value)}
                        >
                          {FORMATS.map(f => <option key={f} value={f}>{f}</option>)}
                        </select>
                        {/* Aggregation */}
                        <select
                          className={`${s.select} ${s.selectSm}`}
                          value={row.aggregation}
                          onChange={e => updateRow(row.id, "aggregation", e.target.value)}
                          disabled={!dedupByPK}
                        >
                          {AGGREGATIONS.map(a => <option key={a} value={a}>{a}</option>)}
                        </select>
                        {/* Include */}
                        <button
                          className={s.btnIcon}
                          style={{ color: row.includeInOutput ? "var(--primary)" : "var(--text-disabled)" }}
                          title={row.includeInOutput ? "Inclus" : "Intermédiaire"}
                          onClick={() => updateRow(row.id, "includeInOutput", !row.includeInOutput)}
                        >
                          {row.includeInOutput ? <Eye size={13} /> : <EyeOff size={13} />}
                        </button>
                        {/* Move up/down */}
                        <button className={s.btnIcon} onClick={() => moveRow(row.id, -1)} disabled={idx === 0}><ArrowUp size={12} /></button>
                        <button className={s.btnIcon} onClick={() => moveRow(row.id, 1)} disabled={idx === rows.length - 1}><ArrowDown size={12} /></button>
                        {/* Delete */}
                        <button className={s.btnIcon} style={{ color: "var(--text-tertiary)" }}
                          onMouseEnter={e => (e.currentTarget.style.color = "var(--primary)")}
                          onMouseLeave={e => (e.currentTarget.style.color = "var(--text-tertiary)")}
                          onClick={() => removeRow(row.id)}
                        >
                          <X size={13} />
                        </button>
                      </div>
                    ))}
                  </div>
                  <div className={s.mappingStatus}>
                    <span>{rows.length} ligne{rows.length > 1 ? "s" : ""} · {rows.filter(r => r.includeInOutput).length} dans l&apos;output</span>
                    <button
                      className={`${s.btn} ${s.btnGhost} ${s.btnXs}`}
                      onClick={() => setRows(r => [...r, newRow("")])}
                    >
                      <Plus size={12} /> Ajouter une ligne
                    </button>
                  </div>
                </>
              ) : (
                <>
                  <div className={s.mappingCards}>
                    {rows.map(row => (
                      <div
                        key={row.id}
                        className={`${s.mappingCard} ${row.isPK ? s.mappingCardPk : ""} ${!row.includeInOutput ? s.rowDisabled : ""}`}
                      >
                        <div className={s.mcHead}>
                          {row.isPK && <span className={`${s.badge} ${s.badgePrimary}`} style={{ fontSize: 10, padding: "1px 6px" }}>PK</span>}
                          <input
                            className={s.cellTargetName}
                            style={{ flex: 1, fontSize: 13, fontWeight: 600 }}
                            value={row.targetName}
                            onChange={e => updateRow(row.id, "targetName", e.target.value)}
                          />
                          <button
                            className={s.btnIcon}
                            style={{ color: row.includeInOutput ? "var(--primary)" : "var(--text-disabled)" }}
                            onClick={() => updateRow(row.id, "includeInOutput", !row.includeInOutput)}
                          >
                            {row.includeInOutput ? <Eye size={13} /> : <EyeOff size={13} />}
                          </button>
                          <button className={s.btnIcon} style={{ color: "var(--text-tertiary)" }}
                            onClick={() => removeRow(row.id)}>
                            <X size={13} />
                          </button>
                        </div>
                        <div className={s.mcFormula}>
                          <FormulaHighlight value={row.formula} />
                        </div>
                        <div className={s.mcMeta}>
                          <div className={s.mcMetaRow}>
                            <span className={s.mcMetaLabel}>Source</span>
                            <select className={`${s.select} ${s.selectSm}`} value={row.sourceCol || ""}
                              onChange={e => updateRow(row.id, "sourceCol", e.target.value)}>
                              <option value="">(aucune)</option>
                              {allSourceColumns.map(c => <option key={c} value={c}>{c}</option>)}
                            </select>
                          </div>
                          <div className={s.mcMetaRow}>
                            <span className={s.mcMetaLabel}>Format</span>
                            <select className={`${s.select} ${s.selectSm}`} value={row.format}
                              onChange={e => updateRow(row.id, "format", e.target.value)}>
                              {FORMATS.map(f => <option key={f} value={f}>{f}</option>)}
                            </select>
                          </div>
                          <div className={s.mcMetaRow}>
                            <span className={s.mcMetaLabel}>Agrégation</span>
                            <select className={`${s.select} ${s.selectSm}`} value={row.aggregation}
                              onChange={e => updateRow(row.id, "aggregation", e.target.value)}
                              disabled={!dedupByPK}>
                              {AGGREGATIONS.map(a => <option key={a} value={a}>{a}</option>)}
                            </select>
                          </div>
                          <div className={s.mcMetaRow}>
                            <span className={s.mcMetaLabel}>Clé primaire</span>
                            <div style={{ display: "flex", alignItems: "center", gap: 8, height: 28 }}>
                              <Cb checked={row.isPK} onChange={c => togglePK(row.id, c)} />
                              <span className={s.muted}>{row.isPK ? "Oui" : "Non"}</span>
                            </div>
                          </div>
                        </div>
                        <div style={{ marginTop: 8 }}>
                          <EditableFormulaCell value={row.formula} onChange={v => updateRow(row.id, "formula", v)} />
                        </div>
                      </div>
                    ))}
                  </div>
                  <div className={s.mappingStatus}>
                    <span>{rows.length} colonne{rows.length > 1 ? "s" : ""}</span>
                    <button className={`${s.btn} ${s.btnGhost} ${s.btnXs}`}
                      onClick={() => setRows(r => [...r, newRow("")])}>
                      <Plus size={12} /> Ajouter
                    </button>
                  </div>
                </>
              )}
            </div>
          </div>

          {/* ── Output filters ─────────────────────────────────────────────── */}
          <FilterSection
            label="Filtres sur l'output"
            num="4"
            groups={outputFilterGroups}
            setGroups={setOutputFilterGroups}
            colOptions={rows.map(r => r.targetName).filter(n => n.trim())}
          />

          {/* ── Export ────────────────────────────────────────────────────── */}
          <div className={s.section}>
            <div className={s.sectionHead}>
              <span className={`${s.sectionNum} ${canPreview ? s.sectionNumActive : ""}`}>5</span>
              <span className={s.sectionTitle}>Export</span>
              <div className={s.sectionLine} />
            </div>

            <div className={s.exportBar}>
              <div className={s.exportInfo}>
                <p className={s.exportTitle}>
                  {canPreview ? (() => {
                    const included = rows.filter(r => r.includeInOutput).length
                    const hidden = rows.length - included
                    const validJoins = secondaryFiles.filter(s => s.file && s.alias.trim() && s.onPrimary && s.onSecondary)
                    const srcRules = filterGroups.reduce((s, g) => s + g.rules.length, 0)
                    const outRules = outputFilterGroups.reduce((s, g) => s + g.rules.length, 0)
                    return `Prêt · ${included} colonne${included > 1 ? "s" : ""}${hidden > 0 ? ` (+${hidden} intermédiaire${hidden > 1 ? "s" : ""})` : ""} · ${sourceRowCount?.toLocaleString() ?? "?"} lignes source${validJoins.length > 0 ? ` · ${validJoins.length} jointure${validJoins.length > 1 ? "s" : ""}` : ""}${srcRules > 0 ? ` · ${srcRules} filtre src` : ""}${outRules > 0 ? ` · ${outRules} filtre out` : ""}`
                  })() : "Complétez les étapes 1 et 2 pour continuer"}
                </p>
                <p className={s.exportSub}>Prévisualisez le résultat avant de télécharger</p>
              </div>
              <button
                className={`${s.btn} ${s.btnPrimary}`}
                onClick={handlePreview}
                disabled={isPreviewing || !canPreview}
              >
                <Eye size={15} />
                {isPreviewing ? "Analyse…" : "Prévisualiser"}
              </button>
            </div>
          </div>
        </div>

        {/* ── Formula side panel ────────────────────────────────────────────── */}
        <div
          className={`${s.panelOverlay} ${showFormulaPanel ? s.panelOverlayOpen : ""}`}
          onClick={() => { setShowFormulaPanel(false); setFormulaSearch("") }}
        />
        <div className={`${s.panel} ${showFormulaPanel ? s.panelOpen : ""}`}>
          <div className={s.panelHead}>
            <div>
              <div className={s.panelHeadTitle}><HelpCircle size={16} /> Référence des formules</div>
              <p className={s.panelHeadDesc}>
                Toute formule commence par <code style={{ background: "var(--bg-subtle)", padding: "1px 6px", borderRadius: 3, fontSize: 11, fontFamily: "var(--font-mono)" }}>=</code>.
                Noms de colonnes sensibles à la casse.
              </p>
            </div>
            <button className={s.btnIcon} onClick={() => { setShowFormulaPanel(false); setFormulaSearch("") }}>
              <X size={16} />
            </button>
          </div>
          <div className={s.panelSearch}>
            <div style={{ position: "relative" }}>
              <Search size={13} style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", color: "var(--text-tertiary)", pointerEvents: "none" }} />
              <input
                className={s.input}
                style={{ paddingLeft: 32 }}
                value={formulaSearch}
                onChange={e => setFormulaSearch(e.target.value)}
                placeholder="Rechercher une formule…"
              />
            </div>
          </div>
          <div className={s.panelBody}>
            {(() => {
              const q = formulaSearch.trim().toLowerCase()
              const filtered = FORMULA_GROUPS
                .map(g => ({ ...g, items: q ? g.items.filter(i => i.formula.toLowerCase().includes(q) || i.desc.toLowerCase().includes(q)) : g.items }))
                .filter(g => g.items.length > 0)

              if (filtered.length === 0) return (
                <div className={s.emptyState} style={{ padding: "40px 20px" }}>
                  <p>Aucune formule pour « {formulaSearch} »</p>
                </div>
              )

              return filtered.map(group => (
                <div key={group.label} className={s.formulaCat}>
                  <p className={s.formulaCatTitle}>{group.label}</p>
                  {group.items.map(({ formula, desc }) => (
                    <div key={formula} className={s.formulaItem}>
                      <span className={s.formulaSyntax}><FormulaHighlight value={formula} /></span>
                      <span className={s.formulaDesc}>{desc}</span>
                    </div>
                  ))}
                </div>
              ))
            })()}
          </div>
        </div>

        {/* ── Preview modal ─────────────────────────────────────────────────── */}
        <div
          className={`${s.modalOverlay} ${showPreviewModal ? s.modalOverlayOpen : ""}`}
          onClick={e => { if (e.target === e.currentTarget) setShowPreviewModal(false) }}
        >
          <div className={`${s.modal} ${s.modalLg}`}>
            <div className={s.modalHead}>
              <h3 className={s.modalTitle}>Résultat du mapping</h3>
              <button className={s.btnIcon} onClick={() => setShowPreviewModal(false)}><X size={16} /></button>
            </div>
            {previewData && (
              <div className={s.modalBody}>
                <div style={{ display: "flex", gap: 8, marginBottom: 14 }}>
                  <span className={`${s.badge} ${s.badgeSuccess}`}>{previewData.total_rows.toLocaleString()} lignes</span>
                  <span className={s.badge}>{previewData.columns.length} colonnes</span>
                  {previewData.total_rows > previewData.preview_rows && (
                    <span className={s.muted}>· aperçu des {previewData.preview_rows} premières lignes</span>
                  )}
                </div>
                <div style={{ border: "1px solid var(--border)", borderRadius: "var(--radius-md)", overflow: "auto", maxHeight: "38vh" }}>
                  <table className={s.previewTable}>
                    <thead>
                      <tr>
                        {previewData.columns.map(col => <th key={col}>{col}</th>)}
                      </tr>
                    </thead>
                    <tbody>
                      {previewData.rows.map((row, i) => (
                        <tr key={i}>
                          {previewData.columns.map(col => (
                            <td key={col} title={String(row[col] ?? "")}>
                              {row[col] === null || row[col] === undefined
                                ? <span style={{ color: "var(--text-disabled)", fontStyle: "italic" }}>—</span>
                                : String(row[col])}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className={s.outputOpts}>
                  <p className={s.outputOptsTitle}>Options de téléchargement</p>
                  <div className={s.outputOptsGrid}>
                    <div className={s.fieldGroup}>
                      <span className={s.fieldGroupLabel}>Nom du fichier</span>
                      <input
                        className={s.input}
                        value={outputFilename}
                        onChange={e => setOutputFilename(e.target.value)}
                        placeholder="mapping_output"
                      />
                      <span className={s.muted}>L&apos;extension sera ajoutée automatiquement</span>
                    </div>
                    <div className={s.fieldGroup}>
                      <span className={s.fieldGroupLabel}>Format</span>
                      <div className={s.formatBtns}>
                        <button
                          className={`${s.formatBtn} ${outputFormat === "csv" ? s.formatBtnActive : ""}`}
                          onClick={() => setOutputFormat("csv")}
                        >
                          CSV
                        </button>
                        <button
                          className={`${s.formatBtn} ${outputFormat === "excel" ? s.formatBtnActive : ""}`}
                          onClick={() => setOutputFormat("excel")}
                        >
                          Excel
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}
            <div className={`${s.modalFoot} ${s.modalFootBetween}`}>
              <button className={`${s.btn} ${s.btnGhost}`} onClick={() => setShowPreviewModal(false)}>Fermer</button>
              <button className={`${s.btn} ${s.btnPrimary}`} onClick={handleDownload} disabled={isDownloading}>
                <Download size={15} />
                {isDownloading ? "Téléchargement…" : `Télécharger en ${outputFormat.toUpperCase()}`}
              </button>
            </div>
          </div>
        </div>

        {/* ── Save modal ────────────────────────────────────────────────────── */}
        <div
          className={`${s.modalOverlay} ${showSaveModal ? s.modalOverlayOpen : ""}`}
          onClick={e => { if (e.target === e.currentTarget) setShowSaveModal(false) }}
          onKeyDown={e => e.key === "Escape" && setShowSaveModal(false)}
        >
          <div className={`${s.modal} ${s.modalSm}`}>
            <div className={s.modalHead}>
              <h3 className={s.modalTitle}>Sauvegarder la configuration</h3>
              <button className={s.btnIcon} onClick={() => setShowSaveModal(false)}><X size={16} /></button>
            </div>
            <div className={s.modalBody}>
              <div className={s.fieldGroup}>
                <span className={s.fieldGroupLabel}>Nom</span>
                <input
                  className={s.input}
                  value={configName}
                  onChange={e => setConfigName(e.target.value)}
                  placeholder="Ex : FPD_from_Generated"
                  onKeyDown={e => e.key === "Enter" && handleSaveConfig()}
                  autoFocus
                />
                {savedConfigs.some(c => c.name === configName.trim()) && configName.trim() && (
                  <div className={s.warnChip} style={{ marginTop: 8 }}>
                    <AlertCircle size={13} />
                    Une config portant ce nom existe déjà — elle sera mise à jour.
                  </div>
                )}
              </div>
            </div>
            <div className={s.modalFoot}>
              <button className={`${s.btn} ${s.btnGhost}`} onClick={() => setShowSaveModal(false)}>Annuler</button>
              <button
                className={`${s.btn} ${s.btnPrimary}`}
                onClick={handleSaveConfig}
                disabled={!configName.trim() || isSaving}
              >
                <Save size={14} />
                {isSaving ? "Sauvegarde…" : "Sauvegarder"}
              </button>
            </div>
          </div>
        </div>

        {/* ── Load modal ────────────────────────────────────────────────────── */}
        <div
          className={`${s.modalOverlay} ${showLoadModal ? s.modalOverlayOpen : ""}`}
          onClick={e => { if (e.target === e.currentTarget) setShowLoadModal(false) }}
        >
          <div className={`${s.modal} ${s.modalMd}`}>
            <div className={s.modalHead}>
              <h3 className={s.modalTitle}>Charger une configuration</h3>
              <button className={s.btnIcon} onClick={() => setShowLoadModal(false)}><X size={16} /></button>
            </div>
            <div className={s.modalBody} style={{ padding: "8px 0" }}>
              {isLoadingConfigs ? (
                <p style={{ textAlign: "center", padding: "24px 0", color: "var(--text-tertiary)" }}>Chargement…</p>
              ) : savedConfigs.length === 0 ? (
                <p style={{ textAlign: "center", padding: "24px 0", color: "var(--text-tertiary)" }}>Aucune configuration sauvegardée.</p>
              ) : (
                <div style={{ maxHeight: 320, overflowY: "auto" }}>
                  {savedConfigs.map(cfg => (
                    <button
                      key={cfg.id}
                      className={s.dropdownItem}
                      onClick={() => handleLoadConfig(cfg)}
                    >
                      <CheckCircle size={14} style={{ color: "var(--text-tertiary)", flexShrink: 0 }} />
                      <div style={{ flex: 1, textAlign: "left" }}>
                        <div style={{ fontWeight: 500 }}>{cfg.name}</div>
                        <div className={s.muted} style={{ fontSize: 11.5 }}>
                          {cfg.rows.length} colonne{cfg.rows.length !== 1 ? "s" : ""}
                          {cfg.dedup_by_pk ? " · Dédup PK" : ""}
                          {cfg.created_at ? ` · ${new Date(cfg.created_at).toLocaleDateString("fr-FR")}` : ""}
                        </div>
                      </div>
                      <ArrowRight size={14} style={{ color: "var(--text-tertiary)", flexShrink: 0 }} />
                    </button>
                  ))}
                </div>
              )}
            </div>
            <div className={s.modalFoot}>
              <button className={`${s.btn} ${s.btnGhost}`} onClick={() => setShowLoadModal(false)}>Fermer</button>
            </div>
          </div>
        </div>

        {/* ── Delete modal ──────────────────────────────────────────────────── */}
        <div
          className={`${s.modalOverlay} ${showDeleteModal ? s.modalOverlayOpen : ""}`}
          onClick={e => { if (e.target === e.currentTarget) { setShowDeleteModal(false); setSelectedToDelete(null) } }}
        >
          <div className={`${s.modal} ${s.modalMd}`}>
            <div className={s.modalHead}>
              <h3 className={s.modalTitle}>Supprimer une configuration</h3>
              <button className={s.btnIcon} onClick={() => { setShowDeleteModal(false); setSelectedToDelete(null) }}><X size={16} /></button>
            </div>
            <div className={s.modalBody} style={{ padding: "8px 0" }}>
              {savedConfigs.length === 0 ? (
                <p style={{ textAlign: "center", padding: "24px 0", color: "var(--text-tertiary)" }}>Aucune configuration à supprimer.</p>
              ) : (
                <div style={{ maxHeight: 280, overflowY: "auto" }}>
                  {savedConfigs.map(cfg => (
                    <button
                      key={cfg.id}
                      className={s.dropdownItem}
                      style={{
                        background: selectedToDelete?.id === cfg.id ? "var(--primary-softer)" : undefined,
                        color: selectedToDelete?.id === cfg.id ? "var(--primary)" : undefined,
                      }}
                      onClick={() => setSelectedToDelete(cfg)}
                    >
                      <div style={{ flex: 1, textAlign: "left" }}>
                        <div style={{ fontWeight: 500 }}>{cfg.name}</div>
                        <div className={s.muted} style={{ fontSize: 11.5 }}>{cfg.rows.length} colonne{cfg.rows.length !== 1 ? "s" : ""}</div>
                      </div>
                      {selectedToDelete?.id === cfg.id && <Trash2 size={14} style={{ color: "var(--primary)", flexShrink: 0 }} />}
                    </button>
                  ))}
                  {selectedToDelete && (
                    <div className={s.warnChip} style={{ margin: "8px 14px" }}>
                      <AlertCircle size={13} />
                      &ldquo;{selectedToDelete.name}&rdquo; sera supprimée définitivement.
                    </div>
                  )}
                </div>
              )}
            </div>
            <div className={s.modalFoot}>
              <button className={`${s.btn} ${s.btnGhost}`}
                onClick={() => { setShowDeleteModal(false); setSelectedToDelete(null) }}>
                Annuler
              </button>
              <button
                className={`${s.btn} ${s.btnDanger}`}
                onClick={handleDeleteConfig}
                disabled={!selectedToDelete || isDeleting}
              >
                <Trash2 size={14} />
                {isDeleting ? "Suppression…" : "Supprimer"}
              </button>
            </div>
          </div>
        </div>

      </div>
    </AppShell>
  )
}
