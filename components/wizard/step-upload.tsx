"use client"

import React from "react"

import { useCallback, useState } from "react"
import { AlertCircle, ArrowRight, CheckCircle2, FileSpreadsheet, Upload } from "lucide-react"

import { uploadFile } from "@/lib/api"
import { cn } from "@/lib/utils"
import type { WizardState } from "@/app/wizard/page"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"

interface StepUploadProps {
  state: WizardState
  updateState: (updates: Partial<WizardState>) => void
  onNext: () => void
}

export function StepUpload({ state, updateState, onNext }: StepUploadProps) {
  const [isDragging, setIsDragging] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [error, setError] = useState<string | null>(null)

  const handleFile = useCallback(
    async (file: File) => {
      // Validate file type
      const validTypes = [
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
        "text/csv",
      ]
      if (!validTypes.includes(file.type) && !file.name.endsWith(".xlsx") && !file.name.endsWith(".xls") && !file.name.endsWith(".csv")) {
        setError("Format de fichier non supporte. Utilisez Excel (.xlsx, .xls) ou CSV.")
        return
      }

      setError(null)
      setIsUploading(true)
      setUploadProgress(0)

      // Simulate upload progress
      const progressInterval = setInterval(() => {
        setUploadProgress((prev) => Math.min(prev + 15, 90))
      }, 200)

      try {
        const result = await uploadFile(file)
        clearInterval(progressInterval)
        setUploadProgress(100)

        if (result.success) {
          updateState({
            file,
            fileMeta: result.fileMeta || { name: file.name, size: file.size },
            filePreview: result.preview,
            fileColumns: result.columns,
            suggestedMapping: result.suggestedMapping,
          })
        }
      } catch (err) {
        const message =
          err instanceof Error
            ? err.message
            : "Erreur lors du chargement du fichier."
        setError(message)
        clearInterval(progressInterval)
        setUploadProgress(0)
      } finally {
        setIsUploading(false)
      }
    },
    [updateState]
  )

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      setIsDragging(false)

      const file = e.dataTransfer.files[0]
      if (file) {
        handleFile(file)
      }
    },
    [handleFile]
  )

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }

  const handleDragLeave = () => {
    setIsDragging(false)
  }

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      handleFile(file)
    }
  }

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Importer le fichier de vols</CardTitle>
        <CardDescription>
          Chargez votre fichier Excel ou CSV contenant les donnees de vols.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Drop zone */}
        <div
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          className={cn(
            "relative flex min-h-[200px] cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed transition-colors",
            isDragging
              ? "border-primary bg-primary/5"
              : state.file || state.fileMeta
                ? "border-primary/50 bg-primary/5"
                : "border-muted-foreground/25 hover:border-muted-foreground/50"
          )}
        >
          <input
            type="file"
            accept=".xlsx,.xls,.csv"
            onChange={handleFileInput}
            className="absolute inset-0 cursor-pointer opacity-0"
            disabled={isUploading}
          />

          {isUploading ? (
            <div className="flex flex-col items-center gap-4 p-8">
              <div className="flex h-16 w-16 items-center justify-center rounded-full bg-primary/10">
                <Upload className="h-8 w-8 animate-pulse text-primary" />
              </div>
              <div className="w-64">
                <Progress value={uploadProgress} className="h-2" />
                <p className="mt-2 text-center text-sm text-muted-foreground">
                  Chargement en cours... {uploadProgress}%
                </p>
              </div>
            </div>
          ) : state.file || state.fileMeta ? (
            <div className="flex flex-col items-center gap-4 p-8">
              <div className="flex h-16 w-16 items-center justify-center rounded-full bg-primary/10">
                <CheckCircle2 className="h-8 w-8 text-primary" />
              </div>
              <div className="text-center">
                <p className="font-medium">{state.file?.name || state.fileMeta?.name}</p>
                <p className="text-sm text-muted-foreground">
                  {formatFileSize(state.file?.size || state.fileMeta?.size || 0)} - {state.filePreview.length} lignes d{"'"}aperçu
                </p>
              </div>
              <Button variant="outline" size="sm">
                Changer de fichier
              </Button>
            </div>
          ) : (
            <div className="flex flex-col items-center gap-4 p-8">
              <div className="flex h-16 w-16 items-center justify-center rounded-full bg-muted">
                <FileSpreadsheet className="h-8 w-8 text-muted-foreground" />
              </div>
              <div className="text-center">
                <p className="font-medium">Glissez-deposez votre fichier ici</p>
                <p className="text-sm text-muted-foreground">
                  ou cliquez pour parcourir
                </p>
              </div>
              <p className="text-xs text-muted-foreground">
                Formats acceptes: Excel (.xlsx, .xls), CSV
              </p>
            </div>
          )}
        </div>

        {error && (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {/* Privacy notice */}
        <Alert>
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            <strong>Confidentialite des donnees:</strong> Vos fichiers sont traites localement
            et ne sont pas stockes sur nos serveurs au-dela de la session en cours.
          </AlertDescription>
        </Alert>

        {/* Actions */}
        <div className="flex justify-end">
          <Button onClick={onNext} disabled={!state.file && !state.fileMeta} className="gap-2">
            Continuer
            <ArrowRight className="h-4 w-4" />
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
