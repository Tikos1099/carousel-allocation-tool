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

export function AppSidebar() {
  const { theme, setTheme } = useTheme()

  return (
    <Sidebar>
      <SidebarHeader className="border-b px-4 py-3">
        <div className="flex items-center gap-2">
          <Filter className="h-4 w-4 text-muted-foreground" />
          <span className="text-sm font-medium">Filtres & Options</span>
        </div>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Filtres globaux</SidebarGroupLabel>
          <SidebarGroupContent className="space-y-4 px-2">
            <div className="space-y-2">
              <Label htmlFor="terminal-filter" className="text-xs text-muted-foreground">
                Terminal
              </Label>
              <Select defaultValue="all">
                <SelectTrigger id="terminal-filter" className="h-9">
                  <SelectValue placeholder="Tous les terminaux" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Tous les terminaux</SelectItem>
                  <SelectItem value="T1">Terminal 1</SelectItem>
                  <SelectItem value="T2">Terminal 2</SelectItem>
                  <SelectItem value="T3">Terminal 3</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="date-filter" className="text-xs text-muted-foreground">
                <div className="flex items-center gap-2">
                  <Calendar className="h-3.5 w-3.5" />
                  Date
                </div>
              </Label>
              <Select defaultValue="today">
                <SelectTrigger id="date-filter" className="h-9">
                  <SelectValue placeholder="Selectionner une date" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="today">{"Aujourd'hui"}</SelectItem>
                  <SelectItem value="yesterday">Hier</SelectItem>
                  <SelectItem value="last7">7 derniers jours</SelectItem>
                  <SelectItem value="last30">30 derniers jours</SelectItem>
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
              Affichage
            </div>
          </SidebarGroupLabel>
          <SidebarGroupContent className="space-y-4 px-2">
            <div className="space-y-2">
              <Label htmlFor="color-mode" className="text-xs text-muted-foreground">
                Mode couleur
              </Label>
              <Select defaultValue="category">
                <SelectTrigger id="color-mode" className="h-9">
                  <SelectValue placeholder="Mode couleur" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="category">Par categorie</SelectItem>
                  <SelectItem value="flight">Par vol</SelectItem>
                  <SelectItem value="terminal">Par terminal</SelectItem>
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
                Theme sombre
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
          <SidebarGroupLabel>Informations</SidebarGroupLabel>
          <SidebarGroupContent className="px-2">
            <div className="rounded-lg bg-muted/50 p-3 text-xs text-muted-foreground">
              <p className="font-medium text-foreground">Version 1.0.0</p>
              <p className="mt-1">
                Outil interne de planification et allocation des carousels make-up.
              </p>
              <p className="mt-2 text-[10px]">
                Contact: support@makeup-tool.internal
              </p>
            </div>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
    </Sidebar>
  )
}
