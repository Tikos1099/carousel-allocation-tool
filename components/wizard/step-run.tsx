"use client"

import { ArrowLeft, Check, FileSpreadsheet, Loader2, Play, Settings } from "lucide-react"

import type { WizardState } from "@/app/wizard/page"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"

interface StepRunProps {
  state: WizardState
  isRunning: boolean
  onRun: () => void
  onPrevious: () => void
}

export function StepRun({ state, isRunning, onRun, onPrevious }: StepRunProps) {
  const configSummary = [
    {
      label: "Fichier",
      value: state.file?.name || state.fileMeta?.name || "Non defini",
      icon: FileSpreadsheet,
    },
    {
      label: "Lignes",
      value: `${state.filePreview.length} lignes`,
      icon: FileSpreadsheet,
    },
    {
      label: "Pas de temps",
      value: `${state.timelineStep} minutes`,
      icon: Settings,
    },
    {
      label: "Carousels",
      value: `${state.carousels.length} carousel(s)`,
      icon: Settings,
    },
  ]

  const steps = [
    { id: 1, label: "Chargement des donnees", status: isRunning ? "active" : "pending" },
    { id: 2, label: "Validation des configurations", status: "pending" },
    { id: 3, label: "Construction de la timeline", status: "pending" },
    { id: 4, label: "Execution de l'algorithme", status: "pending" },
    { id: 5, label: "Generation des resultats", status: "pending" },
  ]

  return (
    <Card>
      <CardHeader>
        <CardTitle>Lancer l{"'"}allocation</CardTitle>
        <CardDescription>
          Verifiez votre configuration puis lancez l{"'"}algorithme d{"'"}allocation.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Config summary */}
        <div className="rounded-lg border bg-muted/30 p-4">
          <h4 className="mb-4 font-medium">Resume de la configuration</h4>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {configSummary.map((item) => (
              <div key={item.label} className="flex items-start gap-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-background">
                  <item.icon className="h-4 w-4 text-muted-foreground" />
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">{item.label}</p>
                  <p className="font-medium">{item.value}</p>
                </div>
              </div>
            ))}
          </div>

          <Separator className="my-4" />

          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <p className="text-xs text-muted-foreground">Mapping categories</p>
              <div className="mt-1 flex flex-wrap gap-1">
                {Object.entries(state.categoryMapping)
                  .filter(([, v]) => v !== "Ignore")
                  .map(([k, v]) => (
                    <Badge key={k} variant="secondary" className="text-xs">
                      {k} → {v}
                    </Badge>
                  ))}
              </div>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Regles Make-Up</p>
              <p className="mt-1 text-sm">
                {state.makeupRules.useFileColumns
                  ? "Colonnes du fichier"
                  : `Offsets: Wide ${state.makeupRules.wideOffsetOpen}/${state.makeupRules.wideOffsetClose}, Narrow ${state.makeupRules.narrowOffsetOpen}/${state.makeupRules.narrowOffsetClose}`}
              </p>
            </div>
          </div>
        </div>

        {/* Progress steps */}
        {isRunning && (
          <div className="rounded-lg border p-4">
            <h4 className="mb-4 font-medium">Progression</h4>
            <div className="space-y-3">
              {steps.map((step, index) => (
                <div key={step.id} className="flex items-center gap-3">
                  <div className="flex h-8 w-8 items-center justify-center rounded-full border">
                    {step.status === "active" ? (
                      <Loader2 className="h-4 w-4 animate-spin text-primary" />
                    ) : step.status === "completed" ? (
                      <Check className="h-4 w-4 text-primary" />
                    ) : (
                      <span className="text-sm text-muted-foreground">{step.id}</span>
                    )}
                  </div>
                  <span
                    className={
                      step.status === "active"
                        ? "font-medium"
                        : step.status === "completed"
                          ? "text-muted-foreground"
                          : "text-muted-foreground"
                    }
                  >
                    {step.label}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Actions */}
        <div className="flex items-center justify-between">
          <Button variant="outline" onClick={onPrevious} disabled={isRunning} className="gap-2 bg-transparent">
            <ArrowLeft className="h-4 w-4" />
            Retour
          </Button>

          <Button onClick={onRun} disabled={isRunning} size="lg" className="gap-2">
            {isRunning ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Allocation en cours...
              </>
            ) : (
              <>
                <Play className="h-4 w-4" />
                Lancer l{"'"}allocation
              </>
            )}
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
