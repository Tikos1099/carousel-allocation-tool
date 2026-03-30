"use client"

import { useEffect, useState, useCallback } from "react"
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
} from "recharts"
import { ChevronLeft, ChevronRight, Download } from "lucide-react"

import { previewInputData, downloadFile, type JobResult } from "@/lib/api"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

const CATEGORY_COLORS: Record<string, string> = {
  Wide: "#D32F2F",
  Narrow: "#FFCDD2",
  IGNORER: "#9E9E9E",
}
const TERMINAL_COLORS = ["#D32F2F", "#E57373", "#EF9A9A", "#FFCDD2", "#FF8A65", "#FFAB91"]
const PAGE_SIZE = 25

function StatCard({ title, value, sub }: { title: string; value: string | number; sub?: string }) {
  return (
    <Card>
      <CardHeader className="pb-1">
        <CardTitle className="text-sm font-medium text-muted-foreground">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-2xl font-bold">{value}</p>
        {sub && <p className="mt-0.5 text-xs text-muted-foreground">{sub}</p>}
      </CardContent>
    </Card>
  )
}

function formatDate(iso: string): string {
  if (!iso) return "—"
  try {
    return new Date(iso).toLocaleString("fr-FR", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    })
  } catch {
    return iso
  }
}

interface InputDataTabProps {
  job: JobResult
}

export function InputDataTab({ job }: InputDataTabProps) {
  const ia = job.inputAnalytics
  const [page, setPage] = useState(0)
  const [tableData, setTableData] = useState<{
    columns: string[]
    rows: Record<string, unknown>[]
    totalRows: number
  }>({ columns: [], rows: [], totalRows: 0 })
  const [tableLoading, setTableLoading] = useState(true)

  const fetchPage = useCallback(
    async (p: number) => {
      setTableLoading(true)
      const data = await previewInputData(job.jobId, p * PAGE_SIZE, PAGE_SIZE)
      setTableData(data)
      setTableLoading(false)
    },
    [job.jobId]
  )

  const hasInputFile = "input_data_csv" in (job.downloads || {})

  useEffect(() => {
    if (hasInputFile) fetchPage(0)
    else setTableLoading(false)
  }, [fetchPage, hasInputFile])

  const totalPages = Math.ceil(tableData.totalRows / PAGE_SIZE)

  function handlePage(p: number) {
    setPage(p)
    fetchPage(p)
  }

  if (!ia) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center justify-center py-16 text-center">
          <p className="text-muted-foreground">
            Données d{"'"}entrée non disponibles pour ce job.
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            Relancez une allocation pour activer cette visualisation.
          </p>
        </CardContent>
      </Card>
    )
  }

  const wideCount = ia.byCategory.find((c) => c.category === "Wide")?.count ?? 0
  const narrowCount = ia.byCategory.find((c) => c.category === "Narrow")?.count ?? 0

  return (
    <div className="space-y-6">
      {/* KPI cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard title="Total vols" value={ia.totalFlights} />
        <StatCard title="Vols Wide" value={wideCount} sub={`${((wideCount / ia.totalFlights) * 100).toFixed(1)}%`} />
        <StatCard title="Vols Narrow" value={narrowCount} sub={`${((narrowCount / ia.totalFlights) * 100).toFixed(1)}%`} />
        <StatCard
          title="Plage horaire"
          value={ia.dateRange.min ? formatDate(ia.dateRange.min).split(" ")[0] : "—"}
          sub={ia.dateRange.max ? `→ ${formatDate(ia.dateRange.max).split(" ")[0]}` : undefined}
        />
      </div>

      {/* Charts row */}
      <div className="grid gap-4 lg:grid-cols-3">
        {/* By hour */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-base">Distribution par heure de départ</CardTitle>
            <CardDescription>Nombre de vols par tranche horaire</CardDescription>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={ia.byHour} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                <XAxis
                  dataKey="hour"
                  tick={{ fontSize: 11 }}
                  tickFormatter={(v) => `${String(v).padStart(2, "0")}h`}
                />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip
                  formatter={(v: number) => [`${v} vols`, "Vols"]}
                  labelFormatter={(l) => `${String(l).padStart(2, "0")}h00`}
                />
                <Bar dataKey="count" fill="#D32F2F" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* By category */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Catégories</CardTitle>
            <CardDescription>Wide / Narrow</CardDescription>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie
                  data={ia.byCategory.filter((c) => c.category !== "IGNORER")}
                  dataKey="count"
                  nameKey="category"
                  cx="50%"
                  cy="50%"
                  outerRadius={80}
                  label={({ category, percent }) =>
                    `${category} ${(percent * 100).toFixed(0)}%`
                  }
                  labelLine={false}
                >
                  {ia.byCategory
                    .filter((c) => c.category !== "IGNORER")
                    .map((entry) => (
                      <Cell
                        key={entry.category}
                        fill={CATEGORY_COLORS[entry.category] || "#9E9E9E"}
                      />
                    ))}
                </Pie>
                <Tooltip formatter={(v: number) => [`${v} vols`]} />
              </PieChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>

      {/* By terminal */}
      {ia.byTerminal.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Distribution par terminal</CardTitle>
            <CardDescription>Nombre de vols par terminal</CardDescription>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={ia.byTerminal} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                <XAxis dataKey="terminal" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip formatter={(v: number) => [`${v} vols`, "Vols"]} />
                <Bar dataKey="count" radius={[3, 3, 0, 0]}>
                  {ia.byTerminal.map((_, i) => (
                    <Cell key={i} fill={TERMINAL_COLORS[i % TERMINAL_COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      )}

      {/* Raw data table */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle className="text-base">Données brutes</CardTitle>
            <CardDescription>
              {tableData.totalRows > 0
                ? `${tableData.totalRows} lignes — page ${page + 1} / ${totalPages || 1}`
                : "Chargement…"}
            </CardDescription>
          </div>
          {hasInputFile && (
            <Button
              size="sm"
              variant="outline"
              className="gap-2"
              onClick={() => {
                const url = downloadFile(job.jobId, "input_data.csv")
                if (url) window.open(url, "_blank")
              }}
            >
              <Download className="h-4 w-4" />
              CSV complet
            </Button>
          )}
        </CardHeader>
        <CardContent>
          {tableLoading ? (
            <div className="py-8 text-center text-sm text-muted-foreground">Chargement…</div>
          ) : tableData.rows.length === 0 ? (
            <div className="py-8 text-center text-sm text-muted-foreground">
              Aucune donnée disponible
            </div>
          ) : (
            <>
              <div className="overflow-auto rounded-lg border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      {tableData.columns.map((col) => (
                        <TableHead key={col} className="whitespace-nowrap text-xs">
                          {col}
                        </TableHead>
                      ))}
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {tableData.rows.map((row, idx) => (
                      <TableRow key={idx}>
                        {tableData.columns.map((col) => (
                          <TableCell key={col} className="whitespace-nowrap text-xs">
                            {String(row[col] ?? "")}
                          </TableCell>
                        ))}
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>

              {totalPages > 1 && (
                <div className="mt-3 flex items-center justify-between text-sm text-muted-foreground">
                  <span>
                    {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, tableData.totalRows)} sur{" "}
                    {tableData.totalRows}
                  </span>
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={page === 0}
                      onClick={() => handlePage(page - 1)}
                    >
                      <ChevronLeft className="h-4 w-4" />
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={page >= totalPages - 1}
                      onClick={() => handlePage(page + 1)}
                    >
                      <ChevronRight className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
