"use client"

import type { ReactNode } from "react"
import { AppHeader } from "@/components/app-header"
import { WorkspaceSidebar } from "@/components/workspace-sidebar"

interface WorkspaceShellProps {
  children: ReactNode
}

export function WorkspaceShell({ children }: WorkspaceShellProps) {
  return (
    <div className="flex min-h-screen flex-col bg-background">
      <AppHeader />
      <div className="flex flex-1 overflow-hidden" style={{ height: "calc(100vh - 64px)" }}>
        <WorkspaceSidebar />
        <main className="flex-1 overflow-y-auto min-w-0">
          {children}
        </main>
      </div>
    </div>
  )
}
