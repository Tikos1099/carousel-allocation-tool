"use client"

import { useState } from "react"
import { ArrowLeft, ArrowRight, Lock, Pencil, Sparkles, Unlock } from "lucide-react"

import { autoDetectMapping } from "@/lib/api"
import type { WizardState } from "@/app/wizard/page"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

interface StepColumnMappingProps {
  state: WizardState
  updateState: (updates: Partial<WizardState>) => void
  onNext: () => void
  onPrevious: () => void
}

export function StepColumnMapping({
  state,
  updateState,
  onNext,
  onPrevious,
}: StepColumnMappingProps) {
  const [isAutoDetecting, setIsAutoDetecting] = useState(false)

  const columns =
    state.fileColumns.length > 0
      ? state.fileColumns
      : state.filePreview.length > 0
        ? Object.keys(state.filePreview[0])
        : []

  const handleAutoDetect = async () => {
    setIsAutoDetecting(true)
    try {
      if (state.suggestedMapping) {
        updateState({ columnMapping: state.suggestedMapping })
        return
      }
      if (!state.file) return
      const mapping = await autoDetectMapping(state.file)
      updateState({ columnMapping: mapping, suggestedMapping: mapping })
    } finally {
      setIsAutoDetecting(false)
    }
  }

  const handleMappingChange = (field: keyof typeof state.columnMapping, value: string) => {
    const normalizedValue = value === "default" ? "" : value
    updateState({
      columnMapping: {
        ...state.columnMapping,
        [field]: normalizedValue,
      },
    })
  }

  const handleLockMapping = () => {
    updateState({ mappingLocked: true })
  }

  const handleUnlockMapping = () => {
    updateState({ mappingLocked: false })
  }

  const isValid =
    state.columnMapping.departureTime &&
    state.columnMapping.departureTime !== "default" &&
    state.columnMapping.flightNumber &&
    state.columnMapping.flightNumber !== "default" &&
    state.columnMapping.category &&
    state.columnMapping.category !== "default" &&
    state.columnMapping.positions &&
    state.columnMapping.positions !== "default"

  const mappingFields = [
    { key: "departureTime" as const, label: "Heure de depart (STD)", required: true },
    { key: "flightNumber" as const, label: "Numero de vol", required: true },
    { key: "category" as const, label: "Categorie", required: true },
    { key: "positions" as const, label: "Positions", required: true },
    { key: "terminal" as const, label: "Terminal", required: false },
    { key: "makeupOpening" as const, label: "Ouverture Make-Up", required: false },
    { key: "makeupClosing" as const, label: "Fermeture Make-Up", required: false },
  ]

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>Mapping des colonnes</CardTitle>
            <CardDescription>
              Associez les colonnes de votre fichier aux champs requis.
            </CardDescription>
          </div>
          {!state.mappingLocked && (
            <Button
              variant="outline"
              size="sm"
              onClick={handleAutoDetect}
              disabled={isAutoDetecting}
              className="gap-2 bg-transparent"
            >
              <Sparkles className="h-4 w-4" />
              {isAutoDetecting ? "Detection..." : "Auto-detect"}
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Preview table */}
        <div>
          <h4 className="mb-2 text-sm font-medium">Apercu des donnees (20 premieres lignes)</h4>
          <div className="max-h-[300px] overflow-auto rounded-lg border">
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
                {state.filePreview.slice(0, 20).map((row, idx) => (
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
        </div>

        {/* Mapping form */}
        <div>
          <div className="mb-4 flex items-center justify-between">
            <h4 className="text-sm font-medium">Configuration du mapping</h4>
            {state.mappingLocked ? (
              <Badge variant="secondary" className="gap-1">
                <Lock className="h-3 w-3" />
                Verrouille
              </Badge>
            ) : (
              <Badge variant="outline" className="gap-1">
                <Unlock className="h-3 w-3" />
                Modifiable
              </Badge>
            )}
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            {mappingFields.map((field) => (
              <div key={field.key} className="space-y-2">
                <Label htmlFor={field.key}>
                  {field.label}
                  {field.required && <span className="ml-1 text-destructive">*</span>}
                </Label>
                <Select
                  value={state.columnMapping[field.key] || "default"}
                  onValueChange={(value) => handleMappingChange(field.key, value)}
                  disabled={state.mappingLocked}
                >
                  <SelectTrigger id={field.key}>
                    <SelectValue placeholder="Selectionner une colonne" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="default">-- Non selectionne --</SelectItem>
                    {columns.map((col) => (
                      <SelectItem key={col} value={col}>
                        {col}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            ))}
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center justify-between">
          <Button variant="outline" onClick={onPrevious} className="gap-2 bg-transparent">
            <ArrowLeft className="h-4 w-4" />
            Retour
          </Button>

          <div className="flex gap-2">
            {state.mappingLocked ? (
              <Button variant="outline" onClick={handleUnlockMapping} className="gap-2 bg-transparent">
                <Pencil className="h-4 w-4" />
                Modifier le mapping
              </Button>
            ) : (
              <Button
                variant="secondary"
                onClick={handleLockMapping}
                disabled={!isValid}
                className="gap-2"
              >
                <Lock className="h-4 w-4" />
                Confirmer le mapping
              </Button>
            )}

            <Button onClick={onNext} disabled={!state.mappingLocked} className="gap-2">
              Continuer
              <ArrowRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
