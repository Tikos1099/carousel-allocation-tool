"use client"

import { useParams } from "next/navigation"
import { BarChart3, Construction } from "lucide-react"

import { AppShell } from "@/components/app-shell"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

export default function AnalysePage() {
  const { scenarioId } = useParams<{ scenarioId: string }>()

  return (
    <AppShell>
      <div className="container mx-auto max-w-4xl px-6 py-16">
        <div className="text-center">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-emerald-50 dark:bg-emerald-950">
            <BarChart3 className="h-8 w-8 text-emerald-500" />
          </div>
          <h1 className="mb-2 text-2xl font-bold">Onglet Analyse</h1>
          <p className="mx-auto max-w-md text-sm text-muted-foreground">
            Cette section présentera les analyses détaillées pour ce scénario.
            Elle sera disponible dans une prochaine version.
          </p>

          <div className="mt-8 inline-flex items-center gap-2 rounded-full border bg-muted/50 px-4 py-2 text-sm text-muted-foreground">
            <Construction className="h-4 w-4" />
            En cours de développement
          </div>
        </div>
      </div>
    </AppShell>
  )
}
