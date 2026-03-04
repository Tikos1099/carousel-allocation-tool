"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { BarChart3, Home, Layers, Play, Settings } from "lucide-react"

import { cn } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { SidebarTrigger } from "@/components/ui/sidebar"

const navigation = [
  { name: "Accueil", href: "/", icon: Home },
  { name: "Assistant", href: "/wizard", icon: Play },
  { name: "Resultats", href: "/results", icon: Layers },
  { name: "Analytics", href: "/analytics", icon: BarChart3 },
]

export function AppHeader() {
  const pathname = usePathname()

  return (
    <header className="sticky top-0 z-50 flex h-14 items-center border-b bg-background/95 px-4 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="flex items-center gap-2">
        <SidebarTrigger className="-ml-1" />
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <Layers className="h-4 w-4" />
          </div>
          <div className="flex items-center gap-2">
            <span className="font-semibold">MakeUp</span>
            <Badge variant="outline" className="text-xs font-normal">
              DEV
            </Badge>
          </div>
        </div>
      </div>

      <nav className="ml-8 hidden items-center gap-1 md:flex">
        {navigation.map((item) => {
          const isActive = pathname === item.href || 
            (item.href !== "/" && pathname.startsWith(item.href))
          return (
            <Button
              key={item.name}
              variant="ghost"
              size="sm"
              asChild
              className={cn(
                "gap-2",
                isActive && "bg-accent text-accent-foreground"
              )}
            >
              <Link href={item.href}>
                <item.icon className="h-4 w-4" />
                {item.name}
              </Link>
            </Button>
          )
        })}
      </nav>

      <div className="ml-auto flex items-center gap-2">
        <Button variant="ghost" size="icon">
          <Settings className="h-4 w-4" />
          <span className="sr-only">Parametres</span>
        </Button>
      </div>
    </header>
  )
}
