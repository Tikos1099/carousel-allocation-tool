"use client"

import React from "react"

import { ArrowLeft, ArrowRight, Clock } from "lucide-react"

import type { WizardState } from "@/app/wizard/page"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Slider } from "@/components/ui/slider"

interface StepTimelineProps {
  state: WizardState
  updateState: (updates: Partial<WizardState>) => void
  onNext: () => void
  onPrevious: () => void
}

export function StepTimeline({
  state,
  updateState,
  onNext,
  onPrevious,
}: StepTimelineProps) {
  const handleStepChange = (value: number[]) => {
    updateState({ timelineStep: value[0] })
  }

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = parseInt(e.target.value, 10)
    if (value > 0 && value <= 60) {
      updateState({ timelineStep: value })
    }
  }

  // Mock timeline range calculation
  const timelineStart = "04:00"
  const timelineEnd = "23:55"
  const totalMinutes = (23 * 60 + 55) - (4 * 60) // From 04:00 to 23:55
  const totalSlots = Math.ceil(totalMinutes / state.timelineStep)

  return (
    <Card>
      <CardHeader>
        <CardTitle>Configuration de la timeline</CardTitle>
        <CardDescription>
          Definissez le pas de temps pour la discretisation de la timeline.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="space-y-4">
          <div className="flex items-center gap-4">
            <Label htmlFor="timelineStep" className="w-48">
              Pas de temps (minutes)
            </Label>
            <div className="flex flex-1 items-center gap-4">
              <Slider
                value={[state.timelineStep]}
                onValueChange={handleStepChange}
                min={1}
                max={30}
                step={1}
                className="flex-1"
              />
              <Input
                id="timelineStep"
                type="number"
                min={1}
                max={60}
                value={state.timelineStep}
                onChange={handleInputChange}
                className="w-20"
              />
            </div>
          </div>

          <p className="text-sm text-muted-foreground">
            Un pas de temps plus petit offre une meilleure precision mais augmente le temps de
            calcul. Valeur recommandee: 5 minutes.
          </p>
        </div>

        {/* Timeline preview */}
        <div className="rounded-lg border bg-muted/30 p-4">
          <h4 className="mb-4 flex items-center gap-2 font-medium">
            <Clock className="h-4 w-4" />
            Apercu de la timeline
          </h4>

          <div className="space-y-3">
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Debut:</span>
              <span className="font-medium">{timelineStart}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Fin:</span>
              <span className="font-medium">{timelineEnd}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Pas:</span>
              <span className="font-medium">{state.timelineStep} min</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Nombre de creneaux:</span>
              <span className="font-medium">{totalSlots}</span>
            </div>
          </div>

          <div className="mt-4">
            <div className="flex items-center gap-2">
              <div className="h-2 flex-1 overflow-hidden rounded-full bg-muted">
                <div className="flex h-full">
                  {Array.from({ length: Math.min(totalSlots, 50) }).map((_, i) => (
                    <div
                      key={i}
                      className="h-full flex-1 border-r border-background/50 bg-primary/60"
                      style={{ opacity: 0.3 + (i / 50) * 0.7 }}
                    />
                  ))}
                </div>
              </div>
            </div>
            <div className="mt-1 flex justify-between text-xs text-muted-foreground">
              <span>{timelineStart}</span>
              <span>{timelineEnd}</span>
            </div>
          </div>
        </div>

        <Alert>
          <AlertDescription>
            La timeline sera calculee sur la base des donnees de votre fichier, de{" "}
            <strong>{timelineStart}</strong> a <strong>{timelineEnd}</strong> avec un pas de{" "}
            <strong>{state.timelineStep} minutes</strong>.
          </AlertDescription>
        </Alert>

        {/* Actions */}
        <div className="flex items-center justify-between">
          <Button variant="outline" onClick={onPrevious} className="gap-2 bg-transparent">
            <ArrowLeft className="h-4 w-4" />
            Retour
          </Button>

          <Button onClick={onNext} disabled={state.timelineStep <= 0} className="gap-2">
            Confirmer
            <ArrowRight className="h-4 w-4" />
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
