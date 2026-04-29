"use client"

import { useEffect, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import {
  ArrowRight, BarChart3, CheckCircle2,
  FileText, GitMerge, Loader2, Plane, Plus, TrendingUp,
} from "lucide-react"
import Link from "next/link"

import { AppShell } from "@/components/app-shell"
import { Button } from "@/components/ui/button"
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { supabase, type AllocationRun, type Mapping, type Scenario } from "@/lib/supabase"
import { toast } from "sonner"
import { cn } from "@/lib/utils"

type Tab = "configuration" | "resultats" | "analyse"

function formatDate(iso: string | null) {
  if (!iso) return "—"
  return new Date(iso).toLocaleDateString("fr-FR", { day: "numeric", month: "short", year: "numeric" })
}

export default function ScenarioPage() {
  const { scenarioId } = useParams<{ scenarioId: string }>()
  const router = useRouter()
  const [tab, setTab] = useState<Tab>("configuration")

  const [scenario, setScenario] = useState<Scenario | null>(null)
  const [runs, setRuns] = useState<AllocationRun[]>([])
  const [mappings, setMappings] = useState<Mapping[]>([])
  const [loading, setLoading] = useState(true)

  const [mappingDialog, setMappingDialog] = useState(false)
  const [mappingName, setMappingName] = useState("")
  const [creating, setCreating] = useState(false)

  useEffect(() => { load() }, [scenarioId])

  async function load() {
    setLoading(true)
    const [{ data: sc }, { data: runList }, { data: mapList }] = await Promise.all([
      supabase.from("scenarios").select("*").eq("id", scenarioId).single(),
      supabase.from("allocation_runs").select("*").eq("scenario_id", scenarioId).order("created_at", { ascending: false }),
      supabase.from("mappings").select("*").eq("scenario_id", scenarioId).order("created_at"),
    ])
    if (sc) setScenario(sc)
    setRuns(runList ?? [])
    setMappings(mapList ?? [])
    setLoading(false)
  }

  async function createMapping() {
    if (!mappingName.trim()) return
    setCreating(true)
    try {
      const { data, error } = await supabase
        .from("mappings")
        .insert({ name: mappingName.trim(), scenario_id: scenarioId, rows: [], filters: [], output_filters: [], dedup_by_pk: false })
        .select().single()
      if (error) throw error
      toast.success(`Mapping "${data.name}" créé`)
      setMappingDialog(false)
      setMappingName("")
      router.push(`/scenario/${scenarioId}/mapping/${data.id}`)
    } catch {
      toast.error("Erreur lors de la création")
    } finally {
      setCreating(false)
    }
  }

  const latestRun = runs.find(r => r.status === "done")

  if (loading) {
    return (
      <AppShell>
        <div className="flex h-64 items-center justify-center">
          <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
        </div>
      </AppShell>
    )
  }

  return (
    <AppShell>
      <div className="min-h-[calc(100vh-64px)]">

        {/* ── Page header ──────────────────────────────────────────────────── */}
        <div className="border-b border-border bg-white px-8 pt-6">
          {/* Breadcrumb */}
          <nav className="mb-2 flex items-center gap-1.5 text-[13px] text-muted-foreground">
            <span>Scénarios</span>
            <span>›</span>
            <span className="text-foreground">{scenario?.name}</span>
          </nav>

          {/* Title + actions */}
          <div className="flex items-end justify-between pb-4">
            <div>
              <h1 className="text-2xl font-bold tracking-tight">{scenario?.name}</h1>
              <p className="mt-0.5 text-sm text-muted-foreground">
                {runs.length} run{runs.length !== 1 ? "s" : ""} · {mappings.length} mapping{mappings.length !== 1 ? "s" : ""}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <button className="border border-border bg-white px-4 py-2 text-[11px] font-bold uppercase tracking-[0.05em] text-muted-foreground hover:bg-gray-50 transition-colors">
                Exporter
              </button>
              <button
                className="bg-primary px-4 py-2 text-[11px] font-bold uppercase tracking-[0.05em] text-white hover:bg-primary/90 transition-colors"
                onClick={() => router.push(`/wizard?scenarioId=${scenarioId}`)}
              >
                Lancer l&apos;allocation
              </button>
            </div>
          </div>

          {/* Tabs */}
          <div className="flex">
            {(["configuration", "resultats", "analyse"] as Tab[]).map(t => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={cn(
                  "px-8 py-3 text-[11px] font-bold uppercase tracking-[0.05em] border-b-2 transition-colors",
                  tab === t
                    ? "border-primary text-primary bg-red-50/30"
                    : "border-transparent text-muted-foreground hover:text-primary"
                )}
              >
                {t === "configuration" && "Configuration"}
                {t === "resultats" && "Résultats"}
                {t === "analyse" && "Analyse"}
              </button>
            ))}
          </div>
        </div>

        {/* ── Tab: Configuration ───────────────────────────────────────────── */}
        {tab === "configuration" && (
          <div className="p-8">
            {/* KPI strip */}
            {latestRun?.kpis && (
              <div className="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
                <KpiCard label="Total vols" value={String(latestRun.kpis.total_flights ?? 0)} />
                <KpiCard
                  label="Taux assignés"
                  value={`${(latestRun.kpis.assigned_pct ?? 0).toFixed(1)}%`}
                  sub="Dans la cible"
                  subColor="text-[#1976D2]"
                />
                <KpiCard
                  label="Non assignés"
                  value={String(latestRun.kpis.unassigned_count ?? 0)}
                  danger={(latestRun.kpis.unassigned_count ?? 0) > 0}
                />
                <KpiCard
                  label="Splits"
                  value={String(latestRun.kpis.split_count ?? 0)}
                />
              </div>
            )}

            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
              {/* Make-up Allocation */}
              <div className="border border-border bg-white">
                <div className="flex items-center justify-between border-b border-border px-5 py-4">
                  <div className="flex items-center gap-3">
                    <Plane className="h-4 w-4 text-primary" />
                    <span className="text-[11px] font-bold uppercase tracking-[0.05em]">Make-up Allocation</span>
                  </div>
                  <span className="rounded bg-red-50 px-2 py-0.5 text-[10px] font-bold uppercase text-primary">
                    {runs.length} run{runs.length !== 1 ? "s" : ""}
                  </span>
                </div>
                <div className="p-5">
                  {runs.length === 0 ? (
                    <p className="text-sm text-muted-foreground">Aucun run — lancez le wizard pour commencer.</p>
                  ) : (
                    <div className="space-y-2">
                      {runs.slice(0, 3).map(r => (
                        <div key={r.id} className="flex items-center justify-between border border-border px-3 py-2 text-sm">
                          <div>
                            <p className="font-medium text-[13px]">{r.name || `Run ${formatDate(r.created_at)}`}</p>
                            <p className="text-[11px] text-muted-foreground">{formatDate(r.created_at)}</p>
                          </div>
                          {r.kpis && (
                            <span className="text-[11px] font-bold text-primary">
                              {(r.kpis.assigned_pct ?? 0).toFixed(0)}%
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                  <Link
                    href={`/scenario/${scenarioId}/allocation`}
                    className="mt-4 flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-[0.05em] text-primary hover:underline"
                  >
                    Voir tous les runs <ArrowRight className="h-3 w-3" />
                  </Link>
                </div>
              </div>

              {/* Mapping */}
              <div className="border border-border bg-white">
                <div className="flex items-center justify-between border-b border-border px-5 py-4">
                  <div className="flex items-center gap-3">
                    <GitMerge className="h-4 w-4 text-[#005f7b]" />
                    <span className="text-[11px] font-bold uppercase tracking-[0.05em]">Mapping</span>
                  </div>
                  <span className="rounded bg-blue-50 px-2 py-0.5 text-[10px] font-bold uppercase text-[#005f7b]">
                    {mappings.length} fichier{mappings.length !== 1 ? "s" : ""}
                  </span>
                </div>
                <div className="p-5">
                  {mappings.length === 0 ? (
                    <p className="text-sm text-muted-foreground">Aucun mapping configuré.</p>
                  ) : (
                    <div className="space-y-1.5">
                      {mappings.map(m => (
                        <Link
                          key={m.id}
                          href={`/scenario/${scenarioId}/mapping/${m.id}`}
                          className="flex items-center justify-between border border-border px-3 py-2 hover:border-primary/40 transition-colors"
                        >
                          <span className="flex items-center gap-2 text-[13px]">
                            <FileText className="h-3.5 w-3.5 text-muted-foreground" />
                            {m.name}
                          </span>
                          <ArrowRight className="h-3.5 w-3.5 text-muted-foreground" />
                        </Link>
                      ))}
                    </div>
                  )}
                  <button
                    onClick={() => { setMappingName(""); setMappingDialog(true) }}
                    className="mt-4 flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-[0.05em] text-primary hover:underline"
                  >
                    <Plus className="h-3 w-3" />
                    Nouveau mapping
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ── Tab: Résultats ───────────────────────────────────────────────── */}
        {tab === "resultats" && (
          <div className="p-8">
            <Link href={`/scenario/${scenarioId}/allocation`}>
              <div className="inline-flex items-center gap-2 bg-primary px-4 py-2 text-[11px] font-bold uppercase tracking-[0.05em] text-white hover:bg-primary/90 transition-colors">
                <Plane className="h-4 w-4" />
                Voir les runs d&apos;allocation
                <ArrowRight className="h-3.5 w-3.5" />
              </div>
            </Link>

            {latestRun?.kpis && (
              <div className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
                <KpiCard label="Total vols" value={String(latestRun.kpis.total_flights ?? 0)} />
                <KpiCard label="Taux assignés" value={`${(latestRun.kpis.assigned_pct ?? 0).toFixed(1)}%`} sub="Dans la cible" subColor="text-[#1976D2]" />
                <KpiCard label="Non assignés" value={String(latestRun.kpis.unassigned_count ?? 0)} danger={(latestRun.kpis.unassigned_count ?? 0) > 0} />
                <KpiCard label="Splits" value={String(latestRun.kpis.split_count ?? 0)} />
              </div>
            )}

            {runs.length === 0 && (
              <div className="mt-8 flex flex-col items-center justify-center border border-dashed border-border bg-white py-16 text-center">
                <Plane className="mb-3 h-10 w-10 text-gray-300" />
                <p className="font-medium text-[13px]">Aucun run d&apos;allocation</p>
                <p className="mt-1 text-[12px] text-muted-foreground">Lancez l&apos;assistant pour générer vos premiers résultats.</p>
                <button
                  onClick={() => router.push(`/wizard?scenarioId=${scenarioId}`)}
                  className="mt-5 bg-primary px-5 py-2 text-[11px] font-bold uppercase tracking-[0.05em] text-white hover:bg-primary/90 transition-colors"
                >
                  Démarrer l&apos;assistant
                </button>
              </div>
            )}
          </div>
        )}

        {/* ── Tab: Analyse ─────────────────────────────────────────────────── */}
        {tab === "analyse" && (
          <div className="flex flex-col items-center justify-center py-24 text-center">
            <BarChart3 className="mb-3 h-10 w-10 text-gray-300" />
            <p className="font-semibold text-[13px]">Onglet Analyse</p>
            <p className="mt-1 text-[12px] text-muted-foreground">Disponible dans une prochaine version.</p>
          </div>
        )}
      </div>

      {/* Create mapping dialog */}
      <Dialog open={mappingDialog} onOpenChange={setMappingDialog}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>Nouveau mapping</DialogTitle>
            <DialogDescription>Entrez un nom pour ce mapping.</DialogDescription>
          </DialogHeader>
          <Input
            placeholder="Ex: Baglist, FPD, FPA…"
            value={mappingName}
            onChange={e => setMappingName(e.target.value)}
            onKeyDown={e => e.key === "Enter" && createMapping()}
            autoFocus
          />
          <DialogFooter className="gap-2">
            <Button variant="outline" size="sm" onClick={() => setMappingDialog(false)}>Annuler</Button>
            <Button size="sm" onClick={createMapping} disabled={creating || !mappingName.trim()}>
              {creating ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
              Créer
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </AppShell>
  )
}

function KpiCard({
  label, value, sub, subColor, danger,
}: {
  label: string
  value: string
  sub?: string
  subColor?: string
  danger?: boolean
}) {
  return (
    <div className="border border-border bg-white p-4">
      <p className="text-[11px] font-bold uppercase tracking-[0.05em] text-muted-foreground">{label}</p>
      <p className={cn("mt-1 text-2xl font-semibold", danger ? "text-[#D32F2F]" : "text-foreground")}>
        {value}
      </p>
      {sub && (
        <p className={cn("mt-0.5 flex items-center gap-1 text-[10px] font-bold", subColor ?? "text-muted-foreground")}>
          <TrendingUp className="h-3 w-3" />
          {sub}
        </p>
      )}
    </div>
  )
}
