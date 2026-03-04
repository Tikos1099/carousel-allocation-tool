"use client"

import React from "react"

import { useCallback, useState } from "react"
import {
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  FileSpreadsheet,
  Plus,
  Trash2,
  Upload,
} from "lucide-react"

import { validateCarouselsFile } from "@/lib/api"
import { cn } from "@/lib/utils"
import type { WizardState } from "@/app/wizard/page"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"

interface StepCarouselsProps {
  state: WizardState
  updateState: (updates: Partial<WizardState>) => void
  onNext: () => void
  onPrevious: () => void
}

export function StepCarousels({
  state,
  updateState,
  onNext,
  onPrevious,
}: StepCarouselsProps) {
  const [mode, setMode] = useState<"upload" | "manual">("upload")
  const [isUploading, setIsUploading] = useState(false)
  const [uploadedFile, setUploadedFile] = useState<File | null>(null)

  const handleFileUpload = useCallback(
    async (file: File) => {
      setIsUploading(true)
      try {
        const result = await validateCarouselsFile(file)
        if (result.valid) {
          setUploadedFile(file)
          updateState({ carousels: result.carousels })
        }
      } finally {
        setIsUploading(false)
      }
    },
    [updateState]
  )

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      handleFileUpload(file)
    }
  }

  const terminalOptions = Array.from(
    new Set(
      Object.values(state.terminalMapping)
        .map((term) => String(term || "").trim())
        .filter((term) => term && term !== "Ignore" && term !== "IGNORER")
    )
  )
  const defaultTerminal = terminalOptions[0] || "T1"

  const handleAddCarousel = () => {
    updateState({
      carousels: [
        ...state.carousels,
        {
          terminal: defaultTerminal,
          carouselName: `MU-${String(state.carousels.length + 1).padStart(3, "0")}`,
          wideCapacity: 4,
          narrowCapacity: 6,
        },
      ],
    })
  }

  const handleRemoveCarousel = (index: number) => {
    updateState({
      carousels: state.carousels.filter((_, i) => i !== index),
    })
  }

  const handleCarouselChange = (
    index: number,
    field: keyof (typeof state.carousels)[0],
    value: string | number
  ) => {
    const updated = [...state.carousels]
    updated[index] = {
      ...updated[index],
      [field]: field === "wideCapacity" || field === "narrowCapacity" ? Number(value) : value,
    }
    updateState({ carousels: updated })
  }

  // Group carousels by terminal for summary
  const carouselsByTerminal = state.carousels.reduce(
    (acc, c) => {
      acc[c.terminal] = (acc[c.terminal] || 0) + 1
      return acc
    },
    {} as Record<string, number>
  )

  return (
    <Card>
      <CardHeader>
        <CardTitle>Configuration des carousels</CardTitle>
        <CardDescription>
          Definissez les carousels disponibles par terminal avec leurs capacites.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <Tabs value={mode} onValueChange={(v) => setMode(v as "upload" | "manual")}>
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="upload">Importer un fichier</TabsTrigger>
            <TabsTrigger value="manual">Configuration manuelle</TabsTrigger>
          </TabsList>

          <TabsContent value="upload" className="space-y-4">
            <div
              className={cn(
                "relative flex min-h-[150px] cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed transition-colors",
                uploadedFile
                  ? "border-primary/50 bg-primary/5"
                  : "border-muted-foreground/25 hover:border-muted-foreground/50"
              )}
            >
              <input
                type="file"
                accept=".csv,.xlsx"
                onChange={handleFileInput}
                className="absolute inset-0 cursor-pointer opacity-0"
                disabled={isUploading}
              />

              {isUploading ? (
                <div className="flex flex-col items-center gap-2">
                  <Upload className="h-8 w-8 animate-pulse text-primary" />
                  <p className="text-sm text-muted-foreground">Validation en cours...</p>
                </div>
              ) : uploadedFile ? (
                <div className="flex flex-col items-center gap-2">
                  <CheckCircle2 className="h-8 w-8 text-primary" />
                  <p className="font-medium">{uploadedFile.name}</p>
                  <p className="text-sm text-muted-foreground">
                    {state.carousels.length} carousels importes
                  </p>
                </div>
              ) : (
                <div className="flex flex-col items-center gap-2">
                  <FileSpreadsheet className="h-8 w-8 text-muted-foreground" />
                  <p className="font-medium">Importer carousels_by_terminal.csv</p>
                  <p className="text-xs text-muted-foreground">
                    Colonnes attendues: Terminal, CarouselName, WideCapacity, NarrowCapacity
                  </p>
                </div>
              )}
            </div>
          </TabsContent>

          <TabsContent value="manual" className="space-y-4">
            <div className="flex items-center justify-between">
              <p className="text-sm text-muted-foreground">
                Ajoutez et configurez les carousels manuellement.
              </p>
              <Button variant="outline" size="sm" onClick={handleAddCarousel} className="gap-2 bg-transparent">
                <Plus className="h-4 w-4" />
                Ajouter un carousel
              </Button>
            </div>

            {state.carousels.length > 0 && (
              <div className="max-h-[300px] overflow-auto rounded-lg border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Terminal</TableHead>
                      <TableHead>Nom</TableHead>
                      <TableHead>Capacite Wide</TableHead>
                      <TableHead>Capacite Narrow</TableHead>
                      <TableHead className="w-12"></TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {state.carousels.map((carousel, index) => (
                      <TableRow key={index}>
                        <TableCell>
                          <Select
                            value={carousel.terminal}
                            onValueChange={(v) => handleCarouselChange(index, "terminal", v)}
                          >
                            <SelectTrigger className="w-24">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              {terminalOptions.length > 0 ? (
                                terminalOptions.map((term) => (
                                  <SelectItem key={term} value={term}>
                                    {term}
                                  </SelectItem>
                                ))
                              ) : (
                                <>
                                  <SelectItem value="T1">T1</SelectItem>
                                  <SelectItem value="T2">T2</SelectItem>
                                  <SelectItem value="T3">T3</SelectItem>
                                </>
                              )}
                            </SelectContent>
                          </Select>
                        </TableCell>
                        <TableCell>
                          <Input
                            value={carousel.carouselName}
                            onChange={(e) =>
                              handleCarouselChange(index, "carouselName", e.target.value)
                            }
                            className="w-32"
                          />
                        </TableCell>
                        <TableCell>
                          <Input
                            type="number"
                            min={1}
                            value={carousel.wideCapacity}
                            onChange={(e) =>
                              handleCarouselChange(index, "wideCapacity", e.target.value)
                            }
                            className="w-20"
                          />
                        </TableCell>
                        <TableCell>
                          <Input
                            type="number"
                            min={1}
                            value={carousel.narrowCapacity}
                            onChange={(e) =>
                              handleCarouselChange(index, "narrowCapacity", e.target.value)
                            }
                            className="w-20"
                          />
                        </TableCell>
                        <TableCell>
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => handleRemoveCarousel(index)}
                            className="h-8 w-8 text-destructive"
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </TabsContent>
        </Tabs>

        {/* Summary */}
        {state.carousels.length > 0 && (
          <div className="rounded-lg border bg-muted/30 p-4">
            <h4 className="mb-3 font-medium">Resume de la configuration</h4>
            <div className="flex flex-wrap gap-4">
              {Object.entries(carouselsByTerminal).map(([terminal, count]) => (
                <div key={terminal} className="flex items-center gap-2">
                  <Badge variant="outline">{terminal}</Badge>
                  <span className="text-sm text-muted-foreground">{count} carousel(s)</span>
                </div>
              ))}
            </div>
            <p className="mt-2 text-sm text-muted-foreground">
              Total: {state.carousels.length} carousel(s) configures
            </p>
          </div>
        )}

        {/* Actions */}
        <div className="flex items-center justify-between">
          <Button variant="outline" onClick={onPrevious} className="gap-2 bg-transparent">
            <ArrowLeft className="h-4 w-4" />
            Retour
          </Button>

          <Button onClick={onNext} disabled={state.carousels.length === 0} className="gap-2">
            Confirmer
            <ArrowRight className="h-4 w-4" />
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
