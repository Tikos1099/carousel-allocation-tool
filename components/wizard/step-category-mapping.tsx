"use client"

import { useEffect, useState } from "react"
import { AlertTriangle, ArrowLeft, ArrowRight } from "lucide-react"

import { inspectFile } from "@/lib/api"
import type { WizardState } from "@/app/wizard/page"
import { Alert, AlertDescription } from "@/components/ui/alert"
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

interface StepCategoryMappingProps {
  state: WizardState
  updateState: (updates: Partial<WizardState>) => void
  onNext: () => void
  onPrevious: () => void
}

export function StepCategoryMapping({
  state,
  updateState,
  onNext,
  onPrevious,
}: StepCategoryMappingProps) {
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Initialize mappings on mount
  useEffect(() => {
    let active = true

    async function fetchValues() {
      if ((!state.file && !state.fileMeta) || !state.mappingLocked) return
      const required = [
        state.columnMapping.departureTime,
        state.columnMapping.flightNumber,
        state.columnMapping.category,
        state.columnMapping.positions,
      ]
      if (required.some((value) => !value || value === "default")) return
      setIsLoading(true)
      setError(null)
      try {
        const result = await inspectFile(state.file, state.columnMapping)
        if (!active) return
        updateState({
          categoryValues: result.categories,
          terminalValues: result.terminals,
        })
      } catch (err) {
        if (!active) return
        const message =
          err instanceof Error
            ? err.message
            : "Impossible d'analyser le fichier. Verifiez le mapping des colonnes."
        setError(message)
      } finally {
        if (active) setIsLoading(false)
      }
    }

    fetchValues()

    return () => {
      active = false
    }
  }, [state.file, state.fileMeta, state.mappingLocked, state.columnMapping, updateState])

  useEffect(() => {
    if (state.categoryValues.length > 0 && Object.keys(state.categoryMapping).length === 0) {
      const initialCategoryMapping: Record<string, "Wide" | "Narrow" | "Ignore"> = {}
      state.categoryValues.forEach((cat) => {
        const normalized = cat.trim().toUpperCase()
        if (normalized.includes("WIDE") || normalized === "WB" || normalized === "W" || normalized === "J") {
          initialCategoryMapping[cat] = "Wide"
        } else if (normalized.includes("NARROW") || normalized === "NB" || normalized === "N" || normalized === "M") {
          initialCategoryMapping[cat] = "Narrow"
        } else {
          initialCategoryMapping[cat] = "Ignore"
        }
      })
      updateState({ categoryMapping: initialCategoryMapping })
    }
  }, [state.categoryValues, state.categoryMapping, updateState])

  useEffect(() => {
    if (state.terminalValues.length > 0 && Object.keys(state.terminalMapping).length === 0) {
      const initialTerminalMapping: Record<string, string> = {}
      state.terminalValues.forEach((term) => {
        const normalized = term.trim().toUpperCase()
        if (normalized.startsWith("T")) {
          initialTerminalMapping[term] = normalized
        } else if (normalized === "2E" || normalized === "2F") {
          initialTerminalMapping[term] = "T2"
        } else if (normalized === "CDG1") {
          initialTerminalMapping[term] = "T1"
        } else {
          initialTerminalMapping[term] = normalized || "Ignore"
        }
      })
      updateState({ terminalMapping: initialTerminalMapping })
    }
  }, [state.terminalValues, state.terminalMapping, updateState])

  const categories =
    state.categoryValues.length > 0 ? state.categoryValues : Object.keys(state.categoryMapping)
  const terminals =
    state.terminalValues.length > 0 ? state.terminalValues : Object.keys(state.terminalMapping)

  const terminalOptions = Array.from(
    new Set(
      [...terminals, ...Object.values(state.terminalMapping)]
        .map((value) => String(value || "").trim())
        .filter((value) => value && value.toLowerCase() !== "ignore")
    )
  )

  const handleCategoryChange = (value: string, mapping: "Wide" | "Narrow" | "Ignore") => {
    updateState({
      categoryMapping: {
        ...state.categoryMapping,
        [value]: mapping,
      },
    })
  }

  const handleTerminalChange = (value: string, mapping: string) => {
    updateState({
      terminalMapping: {
        ...state.terminalMapping,
        [value]: mapping,
      },
    })
  }

  const ignoredCategories = Object.entries(state.categoryMapping).filter(
    ([, v]) => v === "Ignore"
  ).length

  const ignoredTerminals = Object.entries(state.terminalMapping).filter(
    ([, v]) => v === "Ignore"
  ).length

  const totalIgnored = ignoredCategories + ignoredTerminals

  return (
    <Card>
      <CardHeader>
        <CardTitle>Mapping des categories et terminaux</CardTitle>
        <CardDescription>
          Associez les valeurs de votre fichier aux categories standard.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Category mapping */}
        <div>
          <h4 className="mb-3 text-sm font-medium">Categories trouvees dans le fichier</h4>
          <div className="mb-4 flex flex-wrap gap-2">
            {categories.map((cat) => (
              <Badge key={cat} variant="secondary">
                {cat}
              </Badge>
            ))}
          </div>

          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {categories.map((cat) => (
              <div key={cat} className="flex items-center gap-3">
                <Badge variant="outline" className="w-12 justify-center">
                  {cat}
                </Badge>
                <span className="text-muted-foreground">{"→"}</span>
                <Select
                  value={state.categoryMapping[cat] || "Ignore"}
                  onValueChange={(v) => handleCategoryChange(cat, v as "Wide" | "Narrow" | "Ignore")}
                >
                  <SelectTrigger className="flex-1">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="Wide">Wide (Gros porteur)</SelectItem>
                    <SelectItem value="Narrow">Narrow (Moyen porteur)</SelectItem>
                    <SelectItem value="Ignore">Ignorer</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            ))}
          </div>
        </div>

        {/* Terminal mapping */}
        <div>
          <h4 className="mb-3 text-sm font-medium">Terminaux trouves dans le fichier</h4>
          <div className="mb-4 flex flex-wrap gap-2">
            {terminals.map((term) => (
              <Badge key={term} variant="secondary">
                {term}
              </Badge>
            ))}
          </div>

          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {terminals.map((term) => (
              <div key={term} className="flex items-center gap-3">
                <Badge variant="outline" className="w-16 justify-center">
                  {term}
                </Badge>
                <span className="text-muted-foreground">{"→"}</span>
                  <Select
                    value={state.terminalMapping[term] || "Ignore"}
                    onValueChange={(v) => handleTerminalChange(term, v)}
                  >
                    <SelectTrigger className="flex-1">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {terminalOptions.map((option) => (
                        <SelectItem key={option} value={option}>
                          {option}
                        </SelectItem>
                      ))}
                      <SelectItem value="Ignore">Ignorer</SelectItem>
                    </SelectContent>
                  </Select>
              </div>
            ))}
          </div>
        </div>

        {/* Warning for ignored items */}
        {totalIgnored > 0 && (
          <Alert>
            <AlertTriangle className="h-4 w-4" />
            <AlertDescription>
              <strong>{totalIgnored} element(s) ignore(s):</strong> {ignoredCategories} categorie(s) et{" "}
              {ignoredTerminals} terminal(aux). Les lignes correspondantes seront exclues de
              l{"'"}allocation.
            </AlertDescription>
          </Alert>
        )}

        {isLoading && (
          <Alert>
            <AlertTriangle className="h-4 w-4" />
            <AlertDescription>Analyse du fichier en cours...</AlertDescription>
          </Alert>
        )}

        {error && (
          <Alert variant="destructive">
            <AlertTriangle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {/* Actions */}
        <div className="flex items-center justify-between">
          <Button variant="outline" onClick={onPrevious} className="gap-2 bg-transparent">
            <ArrowLeft className="h-4 w-4" />
            Retour
          </Button>

          <Button onClick={onNext} className="gap-2">
            Confirmer
            <ArrowRight className="h-4 w-4" />
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
