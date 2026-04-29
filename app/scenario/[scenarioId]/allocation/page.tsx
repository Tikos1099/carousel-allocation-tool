"use client"

import { useEffect, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import {
  ArrowRight, BarChart3, CheckCircle2, Clock,
  HardDrive, Loader2, Plane, Plus, XCircle,
} from "lucide-react"
import Link from "next/link"

import { AppShell } from "@/components/app-shell"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { supabase, type AllocationRun, type Scenario } from "@/lib/supabase"

function formatDate(iso: string | null) {
  if (!iso) return "—"
  return new Date(iso).toLocaleDateString("fr-FR", {
    day: "numeric", month: "long", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  })
}

function formatStorage(bytes: number) {
  if (!bytes) return "—"
  if (bytes < 1024) return `${bytes} o`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} Ko`
  return `${(bytes / (1024 * 1024)).toFixed(1)} Mo`
}

function StatusBadge({ status }: { status: string }) {
  if (status === "done") return <Badge variant="secondary" className="gap-1 bg-green-100 text-green-700"><CheckCircle2 className="h-3 w-3" />Terminé</Badge>
  if (status === "error") return <Badge variant="destructive" className="gap-1"><XCircle className="h-3 w-3" />Erreur</Badge>
  if (status === "running") return <Badge variant="outline" className="gap-1"><Loader2 className="h-3 w-3 animate-spin" />En cours</Badge>
  return <Badge variant="outline" className="gap-1"><Clock className="h-3 w-3" />En attente</Badge>
}

export default function AllocationPage() {
  const { scenarioId } = useParams<{ scenarioId: string }>()
  const router = useRouter()

  const [scenario, setScenario] = useState<Scenario | null>(null)
  const [runs, setRuns] = useState<AllocationRun[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => { load() }, [scenarioId])

  async function load() {
    setLoading(true)
    const [{ data: sc }, { data: runList }] = await Promise.all([
      supabase.from("scenarios").select("*").eq("id", scenarioId).single(),
      supabase.from("allocation_runs").select("*").eq("scenario_id", scenarioId).order("created_at", { ascending: false }),
    ])
    if (sc) setScenario(sc)
    setRuns(runList ?? [])
    setLoading(false)
  }

  function startNewRun() {
    router.push(`/wizard?scenarioId=${scenarioId}`)
  }

  if (loading) {
    return (
      <AppShell>
        <div className="flex h-64 items-center justify-center">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      </AppShell>
    )
  }

  return (
    <AppShell>
      <div className="container mx-auto max-w-4xl px-6 py-8">
        {/* Header */}
        <div className="mb-8 flex items-start justify-between">
          <div>
            <div className="mb-1 flex items-center gap-2 text-sm text-muted-foreground">
              <Plane className="h-4 w-4 text-primary" />
              Make-up Allocation · {scenario?.name}
            </div>
            <h1 className="text-2xl font-bold">Runs d&apos;allocation</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              {runs.length} run{runs.length !== 1 ? "s" : ""} dans ce scénario
            </p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" asChild>
              <Link href={`/scenario/${scenarioId}/analyse`}>
                <BarChart3 className="mr-2 h-4 w-4" />
                Analyse
              </Link>
            </Button>
            <Button onClick={startNewRun}>
              <Plus className="mr-2 h-4 w-4" />
              Nouveau run
            </Button>
          </div>
        </div>

        {/* Runs list */}
        {runs.length === 0 ? (
          <Card className="border-dashed">
            <CardContent className="flex flex-col items-center justify-center py-16">
              <Plane className="mb-3 h-10 w-10 text-muted-foreground/40" />
              <p className="mb-1 font-medium">Aucun run pour ce scénario</p>
              <p className="mb-5 text-sm text-muted-foreground">
                Lancez l&apos;assistant pour configurer et exécuter votre première allocation.
              </p>
              <Button onClick={startNewRun}>
                <Plane className="mr-2 h-4 w-4" />
                Lancer l&apos;assistant
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-3">
            {runs.map(run => (
              <Card key={run.id} className="transition-all hover:border-primary/40 hover:shadow-sm">
                <CardContent className="flex items-center justify-between py-4">
                  <div className="flex items-center gap-4">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/5">
                      <Plane className="h-5 w-5 text-primary" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <p className="font-medium">{run.name || `Run du ${formatDate(run.created_at)}`}</p>
                        <StatusBadge status={run.status} />
                      </div>
                      <p className="text-xs text-muted-foreground">{formatDate(run.created_at)}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-6">
                    {run.kpis && (
                      <div className="hidden gap-5 text-right sm:flex">
                        <div>
                          <p className="text-sm font-medium">{run.kpis.total_flights ?? 0} vols</p>
                          <p className="text-xs text-muted-foreground">
                            {(run.kpis.assigned_pct ?? 0).toFixed(1)}% assignés
                          </p>
                        </div>
                        <div>
                          <p className="flex items-center gap-1 text-xs text-muted-foreground">
                            <HardDrive className="h-3 w-3" />
                            {formatStorage(run.storage_size_bytes)}
                          </p>
                        </div>
                      </div>
                    )}
                    {run.status === "done" && (
                      <Button size="sm" variant="outline" asChild>
                        <Link href={`/results?jobId=${run.id}`}>
                          Voir
                          <ArrowRight className="ml-1.5 h-3.5 w-3.5" />
                        </Link>
                      </Button>
                    )}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </AppShell>
  )
}
