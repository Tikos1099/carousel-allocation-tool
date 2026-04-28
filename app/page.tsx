"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import {
  ArrowRight, FileSpreadsheet, GitMerge, HardDrive,
  Layers, Plane, Sparkles,
} from "lucide-react"

import { AppShell } from "@/components/app-shell"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Dialog, DialogContent, DialogDescription, DialogFooter,
  DialogHeader, DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { supabase, type SupabaseJob } from "@/lib/supabase"
import { useI18n } from "@/lib/i18n"

function formatStorage(bytes?: number): string {
  if (!bytes || bytes === 0) return "—"
  if (bytes < 1024) return `${bytes} o`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} Ko`
  return `${(bytes / (1024 * 1024)).toFixed(1)} Mo`
}

function formatDate(iso?: string, lang = "fr"): string {
  if (!iso) return ""
  try {
    return new Date(iso).toLocaleDateString(
      lang === "ar" ? "ar-SA" : lang === "en" ? "en-GB" : "fr-FR",
      { day: "numeric", month: "long", year: "numeric" }
    )
  } catch {
    return iso
  }
}

export default function HomePage() {
  const router = useRouter()
  const { t, lang } = useI18n()
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
      <div className="container mx-auto max-w-5xl px-4 py-10">

        {/* Page title */}
        <div className="mb-8 text-center">
          <div className="mb-3 inline-flex items-center gap-2 rounded-full bg-accent px-4 py-1.5 text-sm text-accent-foreground">
            <Layers className="h-4 w-4" />
            MakeUp — Outil interne
          </div>
          <h1 className="text-3xl font-bold tracking-tight">Que voulez-vous faire ?</h1>
          <p className="mt-2 text-muted-foreground">Choisissez l&apos;outil adapté à votre besoin</p>
        </div>

        {/* Tool Chooser */}
        <div className="mb-10 grid grid-cols-1 gap-5 sm:grid-cols-2">

          {/* Allocation Make-Up */}
          <button
            onClick={handleStartAllocation}
            className="group text-left"
          >
            <Card className="h-full border-2 transition-all duration-200 hover:border-primary hover:shadow-md group-focus-visible:ring-2 group-focus-visible:ring-ring">
              <CardHeader className="pb-4">
                <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-sm">
                  <Plane className="h-6 w-6" />
                </div>
                <div className="flex items-start justify-between gap-2">
                  <CardTitle className="text-xl leading-tight">
                    Allocation Make-Up
                  </CardTitle>
                  <Badge variant="secondary" className="shrink-0 text-xs">Principal</Badge>
                </div>
                <CardDescription className="text-sm leading-relaxed">
                  Optimisez l&apos;allocation des positions carousel pour vos vols. Importez vos données, configurez les règles, et générez le planning en un clic.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex items-center gap-1.5 text-sm font-medium text-primary">
                  Démarrer une allocation
                  <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
                </div>
              </CardContent>
            </Card>
          </button>

          {/* Mapping Tool */}
          <Link href="/mapping" className="group">
            <Card className="h-full border-2 transition-all duration-200 hover:border-primary hover:shadow-md group-focus-visible:ring-2 group-focus-visible:ring-ring">
              <CardHeader className="pb-4">
                <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-accent shadow-sm">
                  <GitMerge className="h-6 w-6 text-accent-foreground" />
                </div>
                <div className="flex items-start justify-between gap-2">
                  <CardTitle className="text-xl leading-tight">
                    Mapping Tool
                  </CardTitle>
                  <Badge variant="outline" className="shrink-0 text-xs">Utilitaire</Badge>
                </div>
                <CardDescription className="text-sm leading-relaxed">
                  Transformez et mappez vos données entre fichiers Excel ou CSV. Définissez des formules, dédupliquez par clé primaire, sauvegardez vos configurations.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex items-center gap-1.5 text-sm font-medium text-primary">
                  Ouvrir le Mapping Tool
                  <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
                </div>
              </CardContent>
            </Card>
          </Link>
        </div>

        {/* Recent Jobs */}
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Sparkles className="h-4 w-4 text-muted-foreground" />
                  {t.home.jobsTitle}
                </CardTitle>
                <CardDescription className="text-xs mt-0.5">{t.home.jobsSubtitle}</CardDescription>
              </div>
              <Button variant="ghost" size="sm" asChild>
                <Link href="/results" className="text-xs">{t.home.btnResults} →</Link>
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {jobs.length === 0 && (
                <p className="py-6 text-center text-sm text-muted-foreground">
                  {t.home.jobsEmpty}
                </p>
              )}
              {jobs.map((job) => (
                <Link
                  key={job.job_id}
                  href={`/jobs/${job.job_id}`}
                  className="flex items-center justify-between rounded-lg border border-border/50 p-3 transition-colors hover:bg-accent/50"
                >
                  <div className="flex items-center gap-3">
                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-muted shrink-0">
                      <FileSpreadsheet className="h-4 w-4 text-muted-foreground" />
                    </div>
                    <div>
                      <p className="text-sm font-medium">
                        {job.scenario_name || job.job_id.slice(0, 8) + "…"}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {formatDate(job.created_at ?? undefined, lang)}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-5 text-right">
                    <div className="flex items-center gap-1 text-xs text-muted-foreground">
                      <HardDrive className="h-3 w-3" />
                      {formatStorage(job.storage_size_bytes)}
                    </div>
                    <div>
                      <p className="text-sm font-medium">
                        {job.kpis?.total_flights ?? 0} {t.common.flights}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {t.common.rate}: {(job.kpis?.assigned_pct ?? 0).toFixed(1)}%
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
            <DialogTitle>{t.home.modalTitle}</DialogTitle>
            <DialogDescription>{t.home.modalDesc}</DialogDescription>
          </DialogHeader>
          <div className="py-2">
            <Label htmlFor="scenario-name" className="mb-2 block">
              {t.home.modalLabel}
            </Label>
            <Input
              id="scenario-name"
              placeholder={t.home.modalPlaceholder}
              value={scenarioName}
              onChange={(e) => setScenarioName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleConfirm()}
              autoFocus
            />
          </div>
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setShowModal(false)}>
              {t.common.cancel}
            </Button>
            <Button onClick={handleConfirm}>
              {t.common.continue}
              <ArrowRight className="ml-2 h-4 w-4" />
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </AppShell>
  )
}
