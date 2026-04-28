"use client"

import { useTheme } from "next-themes"
import { Calendar, Filter, Moon, Palette, Sun } from "lucide-react"

import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarSeparator,
} from "@/components/ui/sidebar"
import { Switch } from "@/components/ui/switch"
import { useI18n } from "@/lib/i18n"

export function AppSidebar() {
  const { theme, setTheme } = useTheme()
  const { t } = useI18n()

  return (
    <Sidebar>
      <SidebarHeader className="border-b px-4 py-3">
        <div className="flex items-center gap-2">
          <Filter className="h-4 w-4 text-muted-foreground" />
          <span className="text-sm font-medium">{t.sidebar.title}</span>
        </div>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>{t.sidebar.globalFilters}</SidebarGroupLabel>
          <SidebarGroupContent className="space-y-4 px-2">
            <div className="space-y-2">
              <Label htmlFor="terminal-filter" className="text-xs text-muted-foreground">
                {t.sidebar.terminal}
              </Label>
              <Select defaultValue="all">
                <SelectTrigger id="terminal-filter" className="h-9">
                  <SelectValue placeholder={t.sidebar.allTerminals} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">{t.sidebar.allTerminals}</SelectItem>
                  <SelectItem value="T1">{t.sidebar.t1}</SelectItem>
                  <SelectItem value="T2">{t.sidebar.t2}</SelectItem>
                  <SelectItem value="T3">{t.sidebar.t3}</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="date-filter" className="text-xs text-muted-foreground">
                <div className="flex items-center gap-2">
                  <Calendar className="h-3.5 w-3.5" />
                  {t.sidebar.date}
                </div>
              </Label>
              <Select defaultValue="today">
                <SelectTrigger id="date-filter" className="h-9">
                  <SelectValue placeholder={t.sidebar.today} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="today">{t.sidebar.today}</SelectItem>
                  <SelectItem value="yesterday">{t.sidebar.yesterday}</SelectItem>
                  <SelectItem value="last7">{t.sidebar.last7}</SelectItem>
                  <SelectItem value="last30">{t.sidebar.last30}</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </SidebarGroupContent>
        </SidebarGroup>

        <SidebarSeparator />

        <SidebarGroup>
          <SidebarGroupLabel>
            <div className="flex items-center gap-2">
              <Palette className="h-3.5 w-3.5" />
              {t.sidebar.display}
            </div>
          </SidebarGroupLabel>
          <SidebarGroupContent className="space-y-4 px-2">
            <div className="space-y-2">
              <Label htmlFor="color-mode" className="text-xs text-muted-foreground">
                {t.sidebar.colorMode}
              </Label>
              <Select defaultValue="category">
                <SelectTrigger id="color-mode" className="h-9">
                  <SelectValue placeholder={t.sidebar.colorMode} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="category">{t.sidebar.byCategory}</SelectItem>
                  <SelectItem value="flight">{t.sidebar.byFlight}</SelectItem>
                  <SelectItem value="terminal">{t.sidebar.byTerminal}</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="flex items-center justify-between">
              <Label htmlFor="dark-mode" className="flex items-center gap-2 text-xs text-muted-foreground">
                {theme === "dark" ? (
                  <Moon className="h-3.5 w-3.5" />
                ) : (
                  <Sun className="h-3.5 w-3.5" />
                )}
                {t.sidebar.darkTheme}
              </Label>
              <Switch
                id="dark-mode"
                checked={theme === "dark"}
                onCheckedChange={(checked) => setTheme(checked ? "dark" : "light")}
              />
            </div>
          </SidebarGroupContent>
        </SidebarGroup>

        <SidebarSeparator />

        <SidebarGroup>
          <SidebarGroupLabel>{t.sidebar.info}</SidebarGroupLabel>
          <SidebarGroupContent className="px-2">
            <div className="rounded-lg bg-muted/50 p-3 text-xs text-muted-foreground">
              <p className="font-medium text-foreground">Version 1.0.0</p>
              <p className="mt-1">{t.sidebar.description}</p>
              <p className="mt-2 text-[10px]">{t.sidebar.contact}</p>
            </div>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
    </Sidebar>
  )
}
