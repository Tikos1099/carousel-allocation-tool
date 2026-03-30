"use client"

import { use, useEffect, useMemo, useState } from "react"
import Link from "next/link"
import { CheckCircle2, Download, List, XCircle } from "lucide-react"

import { downloadFile, getJob, type JobResult } from "@/lib/api"
import { AppShell } from "@/components/app-shell"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { InputDataTab } from "@/components/job/input-data-tab"

interface JobPageProps {
  params: Promise<{ jobId: string }>
}

function DataTable({ rows }: { rows: Record<string, unknown>[] }) {
  const columns = rows.length > 0 ? Object.keys(rows[0]) : []
  return (
    <div className="overflow-auto rounded-lg border">
      <Table>
        <TableHeader>
          <TableRow>
            {columns.map((col) => (
              <TableHead key={col} className="whitespace-nowrap">
                {col}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((row, idx) => (
            <TableRow key={idx}>
              {columns.map((col) => (
                <TableCell key={col} className="whitespace-nowrap">
                  {String(row[col] ?? "")}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

const downloadLabels: Record<string, string> = {
  summary_csv: "Resume (CSV)",
  summary_txt: "Resume (TXT)",
  timeline_xlsx: "Timeline",
  heatmap_occupied_xlsx: "Heatmap - Positions Occupees",
  heatmap_free_xlsx: "Heatmap - Positions Libres",
  timeline_readjusted_xlsx: "Timeline Reajustee",
  extra_makeups_needed_csv: "Make-ups Supplementaires",
  warnings_csv: "Warnings (CSV)",
  unassigned_reasons_csv: "Vols non assignes",
}

export default function JobPage({ params }: JobPageProps) {
  const { jobId } = use(params)
  const [job, setJob] = useState<JobResult | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    async function fetchJob() {
      setIsLoading(true)
      try {
        const result = await getJob(jobId)
        setJob(result)
      } catch {
        setJob(null)
      } finally {
        setIsLoading(false)
      }
    }
    fetchJob()
  }, [jobId])

  const downloads = useMemo(() => {
    if (!job) return []
    return Object.entries(job.downloads).map(([key, path]) => ({
      key,
      label: downloadLabels[key] || key,
      path,
    }))
  }, [job])

  const handleDownload = (path: string) => {
    if (!job) return
    const url = downloadFile(job.jobId, path)
    if (url) {
      window.open(url, "_blank")
    }
  }

  if (isLoading) {
    return (
      <AppShell>
        <div className="container mx-auto max-w-7xl px-4 py-8">
          <div className="space-y-6">
            <Skeleton className="h-10 w-64" />
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-28" />
              ))}
            </div>
            <Skeleton className="h-96" />
          </div>
        </div>
      </AppShell>
    )
  }

  if (!job) {
    return (
      <AppShell>
        <div className="container mx-auto max-w-7xl px-4 py-8">
          <Card>
            <CardContent className="flex flex-col items-center justify-center py-12">
              <XCircle className="h-12 w-12 text-muted-foreground" />
              <p className="mt-4 text-lg font-medium">Job non trouve</p>
              <p className="text-muted-foreground">Le job demande n{"'"}existe pas.</p>
              <Button asChild className="mt-4">
                <Link href="/">Retour a l{"'"}accueil</Link>
              </Button>
            </CardContent>
          </Card>
        </div>
      </AppShell>
    )
  }

  const assignedCount = Math.max(job.kpis.totalFlights - job.kpis.unassignedCount, 0)

  const kpiCards = [
    { title: "Total Vols", value: job.kpis.totalFlights, icon: List },
    { title: "Vols Assignes", value: assignedCount, icon: CheckCircle2, color: "text-green-500" },
    { title: "Non Assignes", value: job.kpis.unassignedCount, icon: XCircle, color: "text-red-500" },
    { title: "Taux d'Assignation", value: `${job.kpis.assignedPct}%`, icon: CheckCircle2 },
  ]

  return (
    <AppShell>
      <div className="container mx-auto max-w-7xl px-4 py-8">
        <div className="mb-8">
          <Button variant="ghost" size="sm" asChild className="mb-4 -ml-2">
            <Link href="/">
              Retour
            </Link>
          </Button>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <div className="flex items-center gap-3">
                <h1 className="text-2xl font-bold">Job: {job.jobId}</h1>
                <Badge variant={job.status === "done" ? "default" : "secondary"}>{job.status}</Badge>
              </div>
              {job.createdAt && (
                <p className="mt-1 text-muted-foreground">
                  Execute le {new Date(job.createdAt).toLocaleDateString("fr-FR")} a{" "}
                  {new Date(job.createdAt).toLocaleTimeString("fr-FR")}
                </p>
              )}
            </div>
          </div>
        </div>

        <div className="mb-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {kpiCards.map((kpi) => (
            <Card key={kpi.title}>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">{kpi.title}</CardTitle>
                <kpi.icon className={`h-4 w-4 ${kpi.color || "text-muted-foreground"}`} />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{kpi.value}</div>
              </CardContent>
            </Card>
          ))}
        </div>

        {job.warnings.length > 0 && (
          <Card className="mb-8">
            <CardHeader>
              <CardTitle>Warnings</CardTitle>
              <CardDescription>Alertes et points d{"'"}attention</CardDescription>
            </CardHeader>
            <CardContent>
              <DataTable rows={job.warnings} />
            </CardContent>
          </Card>
        )}

        <Tabs defaultValue="input" className="space-y-4">
          <TabsList>
            <TabsTrigger value="input">Données d{"'"}entrée</TabsTrigger>
            <TabsTrigger value="flights">Apercu vols</TabsTrigger>
            <TabsTrigger value="unassigned">Vols non assignes</TabsTrigger>
            <TabsTrigger value="extras">Extras necessaires</TabsTrigger>
            <TabsTrigger value="downloads">Telechargements</TabsTrigger>
          </TabsList>

          <TabsContent value="input">
            <InputDataTab job={job} />
          </TabsContent>

          <TabsContent value="flights">
            <Card>
              <CardHeader>
                <CardTitle>Apercu des vols</CardTitle>
                <CardDescription>Premieres lignes apres allocation</CardDescription>
              </CardHeader>
              <CardContent>
                <DataTable rows={job.tables.flightsPreview} />
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="unassigned">
            <Card>
              <CardHeader>
                <CardTitle>Vols non assignes</CardTitle>
                <CardDescription>Liste des vols en echec d{"'"}allocation</CardDescription>
              </CardHeader>
              <CardContent>
                <DataTable rows={job.tables.unassigned} />
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="extras">
            <Card>
              <CardHeader>
                <CardTitle>Extras necessaires</CardTitle>
                <CardDescription>Make-ups supplementaires par terminal</CardDescription>
              </CardHeader>
              <CardContent>
                <DataTable rows={job.tables.extrasNeeded} />
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="downloads">
            <Card>
              <CardHeader>
                <CardTitle>Telechargements</CardTitle>
                <CardDescription>Exportez les resultats</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {downloads.map((file) => (
                    <Button
                      key={file.key}
                      variant="outline"
                      className="h-auto justify-start gap-3 p-4 bg-transparent"
                      onClick={() => handleDownload(file.path)}
                    >
                      <Download className="h-5 w-5 text-muted-foreground" />
                      <div className="text-left">
                        <p className="font-medium">{file.label}</p>
                        <p className="text-xs text-muted-foreground">{file.key}</p>
                      </div>
                    </Button>
                  ))}
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </AppShell>
  )
}
