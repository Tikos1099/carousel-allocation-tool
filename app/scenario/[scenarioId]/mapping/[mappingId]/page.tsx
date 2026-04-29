"use client"

import { useParams, useRouter } from "next/navigation"
import { useEffect } from "react"
import { Loader2 } from "lucide-react"

import { AppShell } from "@/components/app-shell"

// Redirect to the full mapping tool with context params
export default function MappingDetailPage() {
  const { scenarioId, mappingId } = useParams<{ scenarioId: string; mappingId: string }>()
  const router = useRouter()

  useEffect(() => {
    router.replace(`/mapping?scenarioId=${scenarioId}&mappingId=${mappingId}`)
  }, [scenarioId, mappingId])

  return (
    <AppShell>
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    </AppShell>
  )
}
