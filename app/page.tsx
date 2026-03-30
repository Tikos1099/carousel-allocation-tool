"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { ArrowRight, BarChart3, FileSpreadsheet, Layers, Upload, Zap, HardDrive } from "lucide-react"

import { AppShell } from "@/components/app-shell"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
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
import { supabase, type SupabaseJob } from "@/lib/supabase"

const features = [
  {
    icon: Upload,
    title: "Import Excel",
    description: "Importez vos fichiers de vols au format Excel avec detection automatique des colonnes.",
  },
  {
    icon: Zap,
    title: "Allocation Intelligente",
    description: "Algorithme d'allocation optimise pour maximiser l'utilisation des carousels.",
  },
  {
    icon: BarChart3,
    title: "Analyse Complete",
    description: "Tableaux de bord, KPIs, et visualisations pour comprendre vos allocations.",
  },
  {
    icon: FileSpreadsheet,
    title: "Export Multi-format",
    description: "Exportez vos resultats en CSV, Excel, avec heatmaps et timelines.",
  },
]

function formatStorage(bytes?: number): string {
  if (!bytes || bytes === 0) return "—"
  if (bytes < 1024) return `${bytes} o`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} Ko`
  return `${(bytes / (1024 * 1024)).toFixed(1)} Mo`
}

function formatDate(iso?: string): string {
  if (!iso) return ""
  try {
    return new Date(iso).toLocaleDateString("fr-FR", {
      day: "numeric",
      month: "long",
      year: "numeric",
    })
  } catch {
    return iso
  }
}

export default function HomePage() {
  const router = useRouter()
  const [showModal, setShowModal] = useState(false)
  const [scenarioName, setScenarioName] = useState("")
  const [jobs, setJobs] = useState<SupabaseJob[]>([])

  useEffect(() => {
    supabase
      .from("jobs")
      .select("job_id, scenario_name, status, created_at, finished_at, kpis, storage_size_bytes")
      .eq("status", "done")
      .order("created_at", { ascending: false })
      .limit(5)
      .then(({ data }) => {
        if (data) setJobs(data as SupabaseJob[])
      })
      .catch(() => {})
  }, [])

  function handleStartAllocation() {
    setScenarioName("")
    setShowModal(true)
  }

  function handleConfirm() {
    const name = scenarioName.trim()
    if (typeof window !== "undefined") {
      window.sessionStorage.setItem("carousel_scenario_name", name)
    }
    setShowModal(false)
    router.push("/wizard")
  }

  return (
    <AppShell>
      <div className="container mx-auto max-w-6xl px-4 py-8">
        {/* Hero Section */}
        <div className="mb-12 text-center">
          <div className="mb-4 inline-flex items-center gap-2 rounded-full bg-accent px-4 py-1.5 text-sm text-accent-foreground">
            <Layers className="h-4 w-4" />
            Outil d{"'"}Allocation Carousel
          </div>
          <h1 className="text-balance text-4xl font-bold tracking-tight md:text-5xl">
            Optimisez vos allocations{" "}
            <span className="text-primary">Make-Up</span>
          </h1>
          <p className="mx-auto mt-4 max-w-2xl text-pretty text-lg text-muted-foreground">
            Importez vos donnees de vols, configurez vos carousels, et obtenez une allocation
            optimisee en quelques clics.
          </p>
          <div className="mt-8 flex flex-col items-center justify-center gap-4 sm:flex-row">
            <Button size="lg" className="gap-2" onClick={handleStartAllocation}>
              Commencer l{"'"}allocation
              <ArrowRight className="h-4 w-4" />
            </Button>
            <Button size="lg" variant="outline" asChild>
              <Link href="/results">Voir les resultats</Link>
            </Button>
          </div>
        </div>

        {/* Features Grid */}
        <div className="mb-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {features.map((feature) => (
            <Card key={feature.title} className="border-border/50">
              <CardHeader className="pb-2">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-accent">
                  <feature.icon className="h-5 w-5 text-accent-foreground" />
                </div>
              </CardHeader>
              <CardContent>
                <CardTitle className="mb-1 text-base">{feature.title}</CardTitle>
                <CardDescription className="text-sm">{feature.description}</CardDescription>
              </CardContent>
            </Card>
          ))}
        </div>

        {/* Recent Jobs */}
        <Card>
          <CardHeader>
            <CardTitle>Jobs Recents</CardTitle>
            <CardDescription>
              Vos dernieres executions d{"'"}allocation
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {jobs.length === 0 && (
                <p className="py-4 text-center text-sm text-muted-foreground">
                  Aucun job disponible. Lancez votre premiere allocation !
                </p>
              )}
              {jobs.map((job) => (
                <Link
                  key={job.job_id}
                  href={`/jobs/${job.job_id}`}
                  className="flex items-center justify-between rounded-lg border border-border/50 p-4 transition-colors hover:bg-accent/50"
                >
                  <div className="flex items-center gap-4">
                    <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-muted">
                      <FileSpreadsheet className="h-5 w-5 text-muted-foreground" />
                    </div>
                    <div>
                      <p className="font-medium">
                        {job.scenario_name || job.job_id.slice(0, 8) + "…"}
                      </p>
                      <p className="text-sm text-muted-foreground">{formatDate(job.created_at ?? undefined)}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-6 text-right">
                    <div className="flex items-center gap-1 text-sm text-muted-foreground">
                      <HardDrive className="h-3.5 w-3.5" />
                      {formatStorage(job.storage_size_bytes)}
                    </div>
                    <div>
                      <p className="font-medium">{job.kpis?.total_flights ?? 0} vols</p>
                      <p className="text-sm text-muted-foreground">
                        Taux: {(job.kpis?.assigned_pct ?? 0).toFixed(1)}%
                      </p>
                    </div>
                  </div>
                </Link>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Scenario Name Modal */}
      <Dialog open={showModal} onOpenChange={setShowModal}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Nouveau scenario d{"'"}allocation</DialogTitle>
            <DialogDescription>
              Donnez un nom a ce scenario pour le retrouver facilement dans vos jobs.
            </DialogDescription>
          </DialogHeader>
          <div className="py-2">
            <Label htmlFor="scenario-name" className="mb-2 block">
              Nom du scenario
            </Label>
            <Input
              id="scenario-name"
              placeholder="Ex: Vols Mars 2024 – Terminal 2"
              value={scenarioName}
              onChange={(e) => setScenarioName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleConfirm()}
              autoFocus
            />
          </div>
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setShowModal(false)}>
              Annuler
            </Button>
            <Button onClick={handleConfirm}>
              Continuer
              <ArrowRight className="ml-2 h-4 w-4" />
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </AppShell>
  )
}
