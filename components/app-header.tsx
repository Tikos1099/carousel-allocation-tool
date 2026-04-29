"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { FolderOpen, HelpCircle, LayoutDashboard, Zap } from "lucide-react"
import { cn } from "@/lib/utils"

const NAV = [
  { label: "Dashboard", href: "/analytics",  icon: LayoutDashboard },
  { label: "Project",   href: "/",           icon: FolderOpen, matchRoot: true },
  { label: "Usage",     href: "/results",    icon: Zap },
  { label: "Help",      href: "/help",       icon: HelpCircle },
]

export function AppHeader() {
  const pathname = usePathname()

  function isActive(item: typeof NAV[0]) {
    if (item.matchRoot) {
      return pathname === "/" ||
        pathname.startsWith("/entreprise") ||
        pathname.startsWith("/secteur") ||
        pathname.startsWith("/projet") ||
        pathname.startsWith("/scenario") ||
        pathname.startsWith("/wizard")
    }
    return pathname.startsWith(item.href)
  }

  return (
    <header className="sticky top-0 z-50 flex h-16 w-full items-center gap-6 bg-white border-b border-border px-6 shadow-sm">
      {/* Logo */}
      <Link href="/" className="flex items-center gap-2.5 shrink-0">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary">
          <span className="text-white font-black text-[15px] tracking-tight">H</span>
        </div>
        <div className="leading-none">
          <p className="text-[13px] font-black tracking-tight text-foreground">HUB PERFORMANCE</p>
          <p className="text-[9px] font-semibold tracking-[0.1em] text-muted-foreground mt-0.5">
            AVIATION MANAGEMENT
          </p>
        </div>
      </Link>

      {/* Nav */}
      <nav className="hidden md:flex items-center gap-1">
        {NAV.map(item => {
          const active = isActive(item)
          const Icon = item.icon
          return (
            <Link
              key={item.label}
              href={item.href}
              className={cn(
                "flex items-center gap-1.5 rounded-full px-3.5 py-1.5 text-sm font-medium transition-colors",
                active
                  ? "bg-primary text-white"
                  : "text-muted-foreground hover:text-foreground hover:bg-gray-100"
              )}
            >
              <Icon className="h-3.5 w-3.5 shrink-0" />
              <span>{item.label}</span>
            </Link>
          )
        })}
      </nav>
    </header>
  )
}
