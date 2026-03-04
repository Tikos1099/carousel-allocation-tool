"use client"

import { useEffect } from "react"
import { ArrowLeft, ArrowRight, Calculator, FileText, AlertTriangle } from "lucide-react"

import type { WizardState } from "@/app/wizard/page"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"

interface StepMakeupRulesProps {
  state: WizardState
  updateState: (updates: Partial<WizardState>) => void
  onNext: () => void
  onPrevious: () => void
}

export function StepMakeupRules({
  state,
  updateState,
  onNext,
  onPrevious,
}: StepMakeupRulesProps) {
  const hasMakeupColumns =
    !!state.columnMapping.makeupOpening &&
    state.columnMapping.makeupOpening !== "default" &&
    !!state.columnMapping.makeupClosing &&
    state.columnMapping.makeupClosing !== "default"

  useEffect(() => {
    if (!hasMakeupColumns && state.makeupRules.useFileColumns) {
      updateState({
        makeupRules: {
          ...state.makeupRules,
          useFileColumns: false,
        },
      })
    }
  }, [hasMakeupColumns, state.makeupRules, updateState])
  const handleModeChange = (useFileColumns: boolean) => {
    updateState({
      makeupRules: {
        ...state.makeupRules,
        useFileColumns,
      },
    })
  }

  const handleOffsetChange = (field: string, value: string) => {
    const numValue = parseInt(value, 10) || 0
    updateState({
      makeupRules: {
        ...state.makeupRules,
        [field]: numValue,
      },
    })
  }

  const isValid =
    (state.makeupRules.useFileColumns && hasMakeupColumns) ||
    (state.makeupRules.wideOffsetOpen &&
      state.makeupRules.wideOffsetClose &&
      state.makeupRules.narrowOffsetOpen &&
      state.makeupRules.narrowOffsetClose)

  // Sample flight for preview
  const sampleDeparture = "08:00"
  const computedWideOpen = state.makeupRules.wideOffsetOpen
    ? `${8 * 60 - state.makeupRules.wideOffsetOpen} min → ${Math.floor((8 * 60 - state.makeupRules.wideOffsetOpen) / 60)}:${String((8 * 60 - state.makeupRules.wideOffsetOpen) % 60).padStart(2, "0")}`
    : "--"
  const computedWideClose = state.makeupRules.wideOffsetClose
    ? `${8 * 60 - state.makeupRules.wideOffsetClose} min → ${Math.floor((8 * 60 - state.makeupRules.wideOffsetClose) / 60)}:${String((8 * 60 - state.makeupRules.wideOffsetClose) % 60).padStart(2, "0")}`
    : "--"

  return (
    <Card>
      <CardHeader>
        <CardTitle>Regles d{"'"}ouverture et fermeture Make-Up</CardTitle>
        <CardDescription>
          Definissez comment calculer les heures d{"'"}ouverture et de fermeture des make-ups.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <RadioGroup
          value={state.makeupRules.useFileColumns ? "file" : "offsets"}
          onValueChange={(v) => handleModeChange(v === "file")}
        >
          <div className="flex items-start gap-3 rounded-lg border p-4">
            <RadioGroupItem value="file" id="file" className="mt-1" />
            <div className="flex-1">
              <Label htmlFor="file" className="flex items-center gap-2 text-base font-medium">
                <FileText className="h-4 w-4" />
                Utiliser les colonnes du fichier
              </Label>
              <p className="mt-1 text-sm text-muted-foreground">
                Les colonnes MakeupOpening et MakeupClosing de votre fichier seront utilisees
                directement.
              </p>
            </div>
          </div>

          <div className="flex items-start gap-3 rounded-lg border p-4">
            <RadioGroupItem value="offsets" id="offsets" className="mt-1" />
            <div className="flex-1">
              <Label htmlFor="offsets" className="flex items-center gap-2 text-base font-medium">
                <Calculator className="h-4 w-4" />
                Calculer a partir des offsets
              </Label>
              <p className="mt-1 text-sm text-muted-foreground">
                Les heures seront calculees par rapport a l{"'"}heure de depart (STD - X minutes).
              </p>
            </div>
          </div>
        </RadioGroup>

        {!state.makeupRules.useFileColumns && (
          <div className="space-y-6 rounded-lg border bg-muted/30 p-4">
            <div className="grid gap-6 sm:grid-cols-2">
              <div className="space-y-4">
                <h4 className="font-medium">Gros porteurs (Wide)</h4>
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="space-y-2">
                    <Label htmlFor="wideOffsetOpen">Ouverture (STD - X min)</Label>
                    <Input
                      id="wideOffsetOpen"
                      type="number"
                      placeholder="ex: 180"
                      value={state.makeupRules.wideOffsetOpen || ""}
                      onChange={(e) => handleOffsetChange("wideOffsetOpen", e.target.value)}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="wideOffsetClose">Fermeture (STD - Y min)</Label>
                    <Input
                      id="wideOffsetClose"
                      type="number"
                      placeholder="ex: 30"
                      value={state.makeupRules.wideOffsetClose || ""}
                      onChange={(e) => handleOffsetChange("wideOffsetClose", e.target.value)}
                    />
                  </div>
                </div>
              </div>

              <div className="space-y-4">
                <h4 className="font-medium">Moyens porteurs (Narrow)</h4>
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="space-y-2">
                    <Label htmlFor="narrowOffsetOpen">Ouverture (STD - X min)</Label>
                    <Input
                      id="narrowOffsetOpen"
                      type="number"
                      placeholder="ex: 120"
                      value={state.makeupRules.narrowOffsetOpen || ""}
                      onChange={(e) => handleOffsetChange("narrowOffsetOpen", e.target.value)}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="narrowOffsetClose">Fermeture (STD - Y min)</Label>
                    <Input
                      id="narrowOffsetClose"
                      type="number"
                      placeholder="ex: 20"
                      value={state.makeupRules.narrowOffsetClose || ""}
                      onChange={(e) => handleOffsetChange("narrowOffsetClose", e.target.value)}
                    />
                  </div>
                </div>
              </div>
            </div>

            {/* Preview */}
            <Alert>
              <AlertDescription>
                <strong>Exemple pour un vol Wide a {sampleDeparture}:</strong>
                <br />
                Ouverture: {computedWideOpen} | Fermeture: {computedWideClose}
              </AlertDescription>
            </Alert>
          </div>
        )}

        {state.makeupRules.useFileColumns && !hasMakeupColumns && (
          <Alert variant="destructive">
            <AlertTriangle className="h-4 w-4" />
            <AlertDescription>
              Les colonnes MakeupOpening / MakeupClosing ne sont pas presentes.
              Choisissez le mode offsets.
            </AlertDescription>
          </Alert>
        )}

        {/* Actions */}
        <div className="flex items-center justify-between">
          <Button variant="outline" onClick={onPrevious} className="gap-2 bg-transparent">
            <ArrowLeft className="h-4 w-4" />
            Retour
          </Button>

          <Button onClick={onNext} disabled={!isValid} className="gap-2">
            Confirmer
            <ArrowRight className="h-4 w-4" />
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
