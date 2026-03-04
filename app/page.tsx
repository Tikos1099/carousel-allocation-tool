"use client"

import Link from "next/link"
import { ArrowRight, BarChart3, FileSpreadsheet, Layers, Upload, Zap } from "lucide-react"

import { AppShell } from "@/components/app-shell"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

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

const recentJobs = [
  { id: "job-2024-001", date: "15 Mars 2024", flights: 156, rate: "94.9%" },
  { id: "job-2024-002", date: "14 Mars 2024", flights: 142, rate: "96.5%" },
  { id: "job-2024-003", date: "13 Mars 2024", flights: 138, rate: "95.7%" },
]

export default function HomePage() {
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
            <Button size="lg" asChild className="gap-2">
              <Link href="/wizard">
                Commencer l{"'"}allocation
                <ArrowRight className="h-4 w-4" />
              </Link>
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
              {recentJobs.map((job) => (
                <Link
                  key={job.id}
                  href={`/jobs/${job.id}`}
                  className="flex items-center justify-between rounded-lg border border-border/50 p-4 transition-colors hover:bg-accent/50"
                >
                  <div className="flex items-center gap-4">
                    <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-muted">
                      <FileSpreadsheet className="h-5 w-5 text-muted-foreground" />
                    </div>
                    <div>
                      <p className="font-medium">{job.id}</p>
                      <p className="text-sm text-muted-foreground">{job.date}</p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="font-medium">{job.flights} vols</p>
                    <p className="text-sm text-muted-foreground">Taux: {job.rate}</p>
                  </div>
                </Link>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </AppShell>
  )
}
