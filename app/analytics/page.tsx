"use client"

import { useEffect, useMemo, useState } from "react"
import {
  BarChart3,
  Calendar,
  Filter,
  Layers,
  LineChart,
  PieChart,
  Plus,
  Settings,
  TrendingUp,
} from "lucide-react"
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart as RechartsPieChart,
  XAxis,
  YAxis,
} from "recharts"

import { getJob, getSessionState, type JobResult } from "@/lib/api"
import { AppShell } from "@/components/app-shell"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"

const TERMINAL_COLORS = [
  "hsl(var(--primary))",
  "hsl(var(--chart-2))",
  "hsl(var(--chart-3))",
  "hsl(var(--chart-4))",
  "hsl(var(--chart-5))",
]

export default function AnalyticsPage() {
  const [dateRange, setDateRange] = useState("7d")
  const [terminalFilter, setTerminalFilter] = useState("all")
  const [job, setJob] = useState<JobResult | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    let active = true

    async function loadLatest() {
      setIsLoading(true)
      try {
        const session = await getSessionState()
        const lastJobId = session?.lastJobId
        if (!lastJobId) {
          if (active) {
            setJob(null)
            setIsLoading(false)
          }
          return
        }
        const result = await getJob(lastJobId)
        if (active) setJob(result)
      } catch {
        if (active) setJob(null)
      } finally {
        if (active) setIsLoading(false)
      }
    }

    loadLatest()

    return () => {
      active = false
    }
  }, [])

  const hasJob = Boolean(job)

  const trendsData = useMemo(() => {
    if (!job) return []
    const dateLabel = job.createdAt
      ? new Date(job.createdAt).toLocaleDateString("fr-FR")
      : "Scenario"
    return [
      {
        date: dateLabel,
        assignmentRate: job.kpis.assignedPct,
        totalFlights: job.kpis.totalFlights,
      },
    ]
  }, [job])

  const terminalDistribution = useMemo(() => {
    const items = job?.analytics?.terminalDistribution || []
    return items.map((item, index) => ({
      name: item.terminal,
      value: item.count,
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

  const kpiWidgets = useMemo(() => {
    if (!job) return []
    const assignedCount = Math.max(job.kpis.totalFlights - job.kpis.unassignedCount, 0)
    const extrasCount = job.tables.extrasNeeded?.length || 0
    return [
      {
        id: "rate",
        title: "Taux d'assignation",
        value: `${job.kpis.assignedPct}%`,
        trend: null,
        icon: TrendingUp,
      },
      {
        id: "flights",
        title: "Vols assignes",
        value: `${assignedCount}`,
        trend: null,
        icon: Layers,
      },
      {
        id: "unassigned",
        title: "Vols non assignes",
        value: `${job.kpis.unassignedCount}`,
        trend: null,
        icon: Calendar,
      },
      {
        id: "extras",
        title: "Extras necessaires",
        value: `${extrasCount}`,
        trend: null,
        icon: BarChart3,
      },
    ]
  }, [job])

  const terminalOptions = useMemo(() => {
    const values = terminalDistribution.map((item) => item.name)
    return values.length > 0 ? values : ["T1", "T2", "T3"]
  }, [terminalDistribution])

  useEffect(() => {
    if (terminalFilter !== "all" && !terminalOptions.includes(terminalFilter)) {
      setTerminalFilter("all")
    }
  }, [terminalFilter, terminalOptions])

  const areaChartConfig: ChartConfig = {
    assignmentRate: { label: "Taux d'assignation", color: "hsl(var(--primary))" },
  }

  const barChartConfig: ChartConfig = {
    assigned: { label: "Assignes", color: "hsl(var(--primary))" },
    unassigned: { label: "Non assignes", color: "hsl(var(--destructive))" },
  }

  const peakChartConfig: ChartConfig = {
    flights: { label: "Vols", color: "hsl(var(--primary))" },
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
          </div>
          <div className="flex flex-wrap gap-2">
            <Select value={dateRange} onValueChange={setDateRange}>
              <SelectTrigger className="w-40">
                <Calendar className="mr-2 h-4 w-4" />
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="7d">7 derniers jours</SelectItem>
                <SelectItem value="30d">30 derniers jours</SelectItem>
                <SelectItem value="90d">90 derniers jours</SelectItem>
              </SelectContent>
            </Select>
            <Select value={terminalFilter} onValueChange={setTerminalFilter}>
              <SelectTrigger className="w-40">
                <Filter className="mr-2 h-4 w-4" />
                <SelectValue />
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
            <AlertDescription>Chargement du dernier scenario...</AlertDescription>
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
                    <span className="text-2xl font-bold">{kpi.value}</span>
                    {kpi.trend && (
                      <Badge
                        variant={kpi.trend.startsWith("+") ? "default" : "secondary"}
                        className="text-xs"
                      >
                        {kpi.trend}
                      </Badge>
                    )}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}

        {/* Charts Grid */}
        <Tabs defaultValue="overview" className="space-y-4">
          <TabsList>
            <TabsTrigger value="overview">Vue d{"'"}ensemble</TabsTrigger>
            <TabsTrigger value="trends">Tendances</TabsTrigger>
            <TabsTrigger value="builder">KPI Builder</TabsTrigger>
          </TabsList>

          <TabsContent value="overview" className="space-y-4">
            <div className="grid gap-4 lg:grid-cols-2">
              {/* Assignment Rate Trend */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <LineChart className="h-5 w-5" />
                    Evolution du taux d{"'"}assignation
                  </CardTitle>
                  <CardDescription>
                    {hasJob ? "Dernier scenario" : "Aucun scenario"}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <ChartContainer config={areaChartConfig} className="h-[300px]">
                    <AreaChart data={trendsData}>
                      <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                      <XAxis dataKey="date" className="text-xs" />
                      <YAxis domain={[0, 100]} className="text-xs" />
                      <ChartTooltip content={<ChartTooltipContent />} />
                      <Area
                        type="monotone"
                        dataKey="assignmentRate"
                        stroke="var(--color-assignmentRate)"
                        fill="var(--color-assignmentRate)"
                        fillOpacity={0.2}
                        strokeWidth={2}
                      />
                    </AreaChart>
                  </ChartContainer>
                </CardContent>
              </Card>

              {/* Terminal Distribution */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <PieChart className="h-5 w-5" />
                    Repartition par terminal
                  </CardTitle>
                  <CardDescription>Distribution des vols</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="flex h-[300px] items-center justify-center">
                    <ChartContainer config={terminalChartConfig} className="h-[250px] w-[250px]">
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
                  <div className="mt-4 flex justify-center gap-6">
                    {filteredTerminalDistribution.map((item) => (
                      <div key={item.name} className="flex items-center gap-2">
                        <div
                          className="h-3 w-3 rounded-full"
                          style={{ backgroundColor: item.color }}
                        />
                        <span className="text-sm">
                          {item.name}: {item.value}%
                        </span>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>

              {/* Category Breakdown */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <BarChart3 className="h-5 w-5" />
                    Assignation par categorie
                  </CardTitle>
                  <CardDescription>Wide vs Narrow</CardDescription>
                </CardHeader>
                <CardContent>
                  <ChartContainer config={barChartConfig} className="h-[300px]">
                    <BarChart data={categoryBreakdown} layout="vertical">
                      <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                      <XAxis type="number" className="text-xs" />
                      <YAxis dataKey="category" type="category" className="text-xs" />
                      <ChartTooltip content={<ChartTooltipContent />} />
                      <Bar dataKey="assigned" stackId="a" fill="var(--color-assigned)" radius={[0, 0, 0, 0]} />
                      <Bar dataKey="unassigned" stackId="a" fill="var(--color-unassigned)" radius={[0, 4, 4, 0]} />
                    </BarChart>
                  </ChartContainer>
                </CardContent>
              </Card>

              {/* Peak Hours */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Calendar className="h-5 w-5" />
                    Distribution horaire des vols
                  </CardTitle>
                  <CardDescription>Heures de pointe</CardDescription>
                </CardHeader>
                <CardContent>
                  <ChartContainer config={peakChartConfig} className="h-[300px]">
                    <BarChart data={peakHoursData}>
                      <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                      <XAxis dataKey="hour" className="text-xs" interval={2} />
                      <YAxis className="text-xs" />
                      <ChartTooltip content={<ChartTooltipContent />} />
                      <Bar dataKey="flights" fill="var(--color-flights)" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ChartContainer>
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          <TabsContent value="trends">
            <Card>
              <CardHeader>
                <CardTitle>Analyse des tendances</CardTitle>
                <CardDescription>
                  Comparez les performances sur differentes periodes
                </CardDescription>
              </CardHeader>
              <CardContent className="flex h-[400px] items-center justify-center">
                <div className="text-center">
                  <LineChart className="mx-auto h-12 w-12 text-muted-foreground" />
                  <p className="mt-4 text-lg font-medium">Analyse detaillee</p>
                  <p className="text-muted-foreground">
                    Selectionnez une periode pour voir les tendances
                  </p>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="builder">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Settings className="h-5 w-5" />
                  KPI Builder
                </CardTitle>
                <CardDescription>
                  Creez vos propres indicateurs personnalises
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="rounded-lg border-2 border-dashed border-muted-foreground/25 p-8">
                  <div className="flex flex-col items-center justify-center text-center">
                    <div className="flex h-16 w-16 items-center justify-center rounded-full bg-muted">
                      <Plus className="h-8 w-8 text-muted-foreground" />
                    </div>
                    <h3 className="mt-4 text-lg font-medium">Creer un KPI personnalise</h3>
                    <p className="mt-2 max-w-md text-sm text-muted-foreground">
                      Definissez vos propres metriques en combinant les donnees disponibles.
                      Selectionnez les sources, les filtres et le type de visualisation.
                    </p>
                    <Button className="mt-6">
                      <Plus className="mr-2 h-4 w-4" />
                      Nouveau KPI
                    </Button>
                  </div>
                </div>

                <div className="mt-8 space-y-4">
                  <h4 className="font-medium">KPIs disponibles</h4>
                  <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                    {[
                      { name: "Taux d'assignation", type: "Pourcentage" },
                      { name: "Vols non assignes", type: "Compteur" },
                      { name: "Make-ups supplementaires", type: "Compteur" },
                      { name: "Temps de pic", type: "Heure" },
                      { name: "Terminal le plus charge", type: "Texte" },
                      { name: "Occupation moyenne", type: "Pourcentage" },
                    ].map((kpi) => (
                      <div
                        key={kpi.name}
                        className="flex items-center justify-between rounded-lg border p-4"
                      >
                        <div>
                          <p className="font-medium">{kpi.name}</p>
                          <p className="text-xs text-muted-foreground">{kpi.type}</p>
                        </div>
                        <Button variant="ghost" size="sm">
                          Ajouter
                        </Button>
                      </div>
                    ))}
                  </div>
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>

        {/* Heatmap Placeholder */}
        <Card className="mt-8">
          <CardHeader>
            <CardTitle>Heatmap des positions</CardTitle>
            <CardDescription>
              Visualisation de l{"'"}occupation des positions au fil du temps
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex h-[200px] items-center justify-center rounded-lg border-2 border-dashed border-muted-foreground/25">
              <div className="text-center">
                <BarChart3 className="mx-auto h-8 w-8 text-muted-foreground" />
                <p className="mt-2 text-sm text-muted-foreground">
                  Heatmap interactive - Disponible apres execution d{"'"}un job
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </AppShell>
  )
}
