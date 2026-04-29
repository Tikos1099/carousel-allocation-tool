"use client"

import type { ReactNode } from "react"
import { AppHeader } from "@/components/app-header"

interface AppShellProps {
  children: ReactNode
}

export function AppShell({ children }: AppShellProps) {
  return (
    <div className="min-h-screen bg-background">
      <AppHeader />
      <main className="flex-1">{children}</main>
    </div>
  )
}
