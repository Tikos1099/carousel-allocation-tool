"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { BarChart3, BookOpen, Database, GitMerge, Home, Layers, Play, Settings } from "lucide-react"

import { cn } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { SidebarTrigger } from "@/components/ui/sidebar"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { useI18n, LANGUAGES } from "@/lib/i18n"

export function AppHeader() {
  const pathname = usePathname()
  const { t, lang, setLang } = useI18n()

  const navigation = [
    { name: t.nav.home, href: "/", icon: Home },
    { name: t.nav.wizard, href: "/wizard", icon: Play },
    { name: t.nav.results, href: "/results", icon: Layers },
    { name: t.nav.database, href: "/database", icon: Database },
    { name: t.nav.analytics, href: "/analytics", icon: BarChart3 },
    { name: "Mapping", href: "/mapping", icon: GitMerge },
    { name: "Guide", href: "/help", icon: BookOpen },
  ]

  const currentLang = LANGUAGES.find((l) => l.code === lang)

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
          const isActive =
            pathname === item.href ||
            (item.href !== "/" && pathname.startsWith(item.href))
          return (
            <Button
              key={item.href}
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
        {/* Language switcher */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="sm" className="gap-2 text-sm">
              <span>{currentLang?.flag}</span>
              <span className="hidden sm:inline">{currentLang?.nativeLabel}</span>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="min-w-[140px]">
            {LANGUAGES.map((language) => (
              <DropdownMenuItem
                key={language.code}
                onClick={() => setLang(language.code)}
                className={cn(
                  "gap-2 cursor-pointer",
                  lang === language.code && "font-medium bg-accent"
                )}
              >
                <span>{language.flag}</span>
                {language.nativeLabel}
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>

        <Button variant="ghost" size="icon">
          <Settings className="h-4 w-4" />
          <span className="sr-only">{t.common.settings}</span>
        </Button>
      </div>
    </header>
  )
}
