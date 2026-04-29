"use client"

import { Scale, Construction } from "lucide-react"
import { AppShell } from "@/components/app-shell"

export default function ComparePage() {
  return (
    <AppShell>
      <div className="container mx-auto max-w-4xl px-6 py-16 text-center">
        <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-amber-50 dark:bg-amber-950">
          <Scale className="h-8 w-8 text-amber-500" />
        </div>
        <h1 className="mb-2 text-2xl font-bold">Comparaison des scénarios</h1>
        <p className="mx-auto max-w-md text-sm text-muted-foreground">
          Comparez les scénarios entre eux pour identifier la meilleure option selon vos critères.
          Cette fonctionnalité sera disponible dans une prochaine version.
        </p>
        <div className="mt-8 inline-flex items-center gap-2 rounded-full border bg-muted/50 px-4 py-2 text-sm text-muted-foreground">
          <Construction className="h-4 w-4" />
          En cours de développement
        </div>
      </div>
    </AppShell>
  )
}
