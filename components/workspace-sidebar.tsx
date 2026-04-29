"use client"

import { useEffect, useRef, useState } from "react"
import Link from "next/link"
import { usePathname, useRouter } from "next/navigation"
import {
  BarChart3, Building2, ChevronDown, ChevronRight,
  FileText, FolderOpen, GitMerge, Loader2,
  MoreHorizontal, Pencil, Plane, Plus, Trash2,
} from "lucide-react"

import { supabase, type Entreprise, type Mapping, type Projet, type Scenario, type Secteur } from "@/lib/supabase"
import { Button } from "@/components/ui/button"
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog"
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem,
  DropdownMenuSeparator, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"
import { toast } from "sonner"

// ─── Tree node types ───────────────────────────────────────────────────────────

interface ScenarioNode extends Scenario {
  expanded: boolean
  mappingsLoaded: boolean
  mappings: Mapping[]
  mappingsExpanded: boolean
}
interface ProjetNode extends Projet {
  expanded: boolean
  scenariosLoaded: boolean
  scenarios: ScenarioNode[]
}
interface SecteurNode extends Secteur {
  expanded: boolean
  projetsLoaded: boolean
  projets: ProjetNode[]
}
interface EntrepriseNode extends Entreprise {
  expanded: boolean
  secteursLoaded: boolean
  secteurs: SecteurNode[]
  directProjets: ProjetNode[]
  directProjetsLoaded: boolean
}

type CreateType = "entreprise" | "secteur" | "projet" | "projet-direct" | "scenario" | "mapping"
type DeleteType = "entreprise" | "secteur" | "projet" | "scenario" | "mapping"

// ─── Tree item ─────────────────────────────────────────────────────────────────

interface TreeItemProps {
  label: string
  depth: number
  icon: React.ReactNode
  href?: string
  expanded?: boolean
  hasToggle?: boolean
  isActive?: boolean
  onToggle?: () => void
  onAdd?: () => void
  addLabel?: string
  onRename?: () => void
  onDelete?: () => void
  children?: React.ReactNode
}

function TreeItem({
  label, depth, icon, href, expanded, hasToggle, isActive,
  onToggle, onAdd, addLabel, onRename, onDelete, children,
}: TreeItemProps) {
  return (
    <div>
      <div
        className={cn(
          "group relative flex items-center gap-1 py-[9px] pr-2 cursor-pointer select-none transition-colors",
          "hover:bg-gray-50",
          isActive
            ? "bg-primary/5 text-primary font-semibold border-r-2 border-primary"
            : "text-foreground",
        )}
        style={{ paddingLeft: `${8 + depth * 14}px` }}
      >
        <button
          className={cn(
            "flex h-4 w-4 shrink-0 items-center justify-center transition-colors",
            isActive ? "text-primary" : "text-muted-foreground/60",
          )}
          onClick={e => { e.stopPropagation(); onToggle?.() }}
          style={{ visibility: hasToggle ? "visible" : "hidden" }}
        >
          {expanded
            ? <ChevronDown className="h-3 w-3" />
            : <ChevronRight className="h-3 w-3" />}
        </button>

        {href ? (
          <Link href={href} prefetch className="flex flex-1 items-center gap-2 overflow-hidden min-w-0">
            <span className={cn("shrink-0", isActive ? "text-primary" : "text-muted-foreground")}>{icon}</span>
            <span className="truncate text-[12.5px] font-medium">{label}</span>
          </Link>
        ) : (
          <button className="flex flex-1 items-center gap-2 overflow-hidden text-left min-w-0" onClick={() => onToggle?.()}>
            <span className={cn("shrink-0", isActive ? "text-primary" : "text-muted-foreground")}>{icon}</span>
            <span className="truncate text-[12.5px] font-medium">{label}</span>
          </button>
        )}

        <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
          {onAdd && (
            <button
              title={addLabel}
              className="flex h-5 w-5 items-center justify-center rounded text-muted-foreground hover:text-primary hover:bg-gray-100 transition-colors"
              onClick={e => { e.stopPropagation(); onAdd() }}
            >
              <Plus className="h-3 w-3" />
            </button>
          )}
          {(onRename || onDelete) && (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button
                  className="flex h-5 w-5 items-center justify-center rounded text-muted-foreground hover:text-primary hover:bg-gray-100 transition-colors"
                  onClick={e => e.stopPropagation()}
                >
                  <MoreHorizontal className="h-3 w-3" />
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="start" className="w-40">
                {onRename && (
                  <DropdownMenuItem onClick={onRename} className="gap-2">
                    <Pencil className="h-3.5 w-3.5" /> Renommer
                  </DropdownMenuItem>
                )}
                {onRename && onDelete && <DropdownMenuSeparator />}
                {onDelete && (
                  <DropdownMenuItem onClick={onDelete} className="gap-2 text-destructive focus:text-destructive">
                    <Trash2 className="h-3.5 w-3.5" /> Supprimer
                  </DropdownMenuItem>
                )}
              </DropdownMenuContent>
            </DropdownMenu>
          )}
        </div>
      </div>
      {expanded && children}
    </div>
  )
}

// ─── Scenario subtree (shared between secteur-projets and direct projets) ──────

interface ScenarioSubTreeProps {
  sc: ScenarioNode
  depth: number
  pathname: string
  onToggle: () => void
  onToggleMappings: () => void
  onRename: () => void
  onDelete: () => void
  onAddMapping: () => void
  onRenameMapping: (id: string, name: string) => void
  onDeleteMapping: (id: string, name: string) => void
  openCreate: (type: CreateType, parentId?: string) => void
}

function ScenarioSubTree({
  sc, depth, pathname,
  onToggle, onToggleMappings, onRename, onDelete, onAddMapping,
  onRenameMapping, onDeleteMapping,
}: ScenarioSubTreeProps) {
  return (
    <TreeItem
      key={sc.id}
      label={sc.name}
      depth={depth}
      icon={<FolderOpen className="h-3.5 w-3.5 text-orange-400" />}
      href={`/scenario/${sc.id}`}
      hasToggle
      expanded={sc.expanded}
      isActive={pathname === `/scenario/${sc.id}`}
      onToggle={onToggle}
      onRename={onRename}
      onDelete={onDelete}
    >
      <TreeItem
        label="Make-up Allocation"
        depth={depth + 1}
        icon={<Plane className="h-3 w-3 text-primary" />}
        href={`/scenario/${sc.id}/allocation`}
        isActive={pathname === `/scenario/${sc.id}/allocation`}
      />
      <TreeItem
        label="Mapping"
        depth={depth + 1}
        icon={<GitMerge className="h-3 w-3 text-violet-500" />}
        hasToggle
        expanded={sc.mappingsExpanded}
        onToggle={onToggleMappings}
        onAdd={onAddMapping}
        addLabel="Nouveau mapping"
      >
        {sc.mappings.map(m => (
          <TreeItem
            key={m.id}
            label={m.name}
            depth={depth + 2}
            icon={<FileText className="h-3 w-3" />}
            href={`/scenario/${sc.id}/mapping/${m.id}`}
            isActive={pathname === `/scenario/${sc.id}/mapping/${m.id}`}
            onRename={() => onRenameMapping(m.id, m.name)}
            onDelete={() => onDeleteMapping(m.id, m.name)}
          />
        ))}
        {sc.mappingsLoaded && sc.mappings.length === 0 && (
          <button
            className="w-full py-1 text-center text-[11px] text-primary hover:underline"
            style={{ paddingLeft: `${8 + (depth + 2) * 14}px` }}
            onClick={onAddMapping}
          >
            + Ajouter un mapping
          </button>
        )}
      </TreeItem>
      <TreeItem
        label="Analyse"
        depth={depth + 1}
        icon={<BarChart3 className="h-3 w-3 text-emerald-500" />}
        href={`/scenario/${sc.id}/analyse`}
        isActive={pathname === `/scenario/${sc.id}/analyse`}
      />
    </TreeItem>
  )
}

// ─── Main sidebar ──────────────────────────────────────────────────────────────

export function WorkspaceSidebar() {
  const pathname = usePathname()
  const router = useRouter()
  const [entreprises, setEntreprises] = useState<EntrepriseNode[]>([])
  const [loading, setLoading] = useState(true)

  const [createDialog, setCreateDialog] = useState<{ type: CreateType; parentId?: string; open: boolean } | null>(null)
  const [createName, setCreateName] = useState("")
  const createInputRef = useRef<HTMLInputElement>(null)

  const [renameDialog, setRenameDialog] = useState<{ type: DeleteType; id: string; currentName: string; open: boolean } | null>(null)
  const [renameName, setRenameName] = useState("")

  const [deleteDialog, setDeleteDialog] = useState<{ type: DeleteType; id: string; name: string; open: boolean } | null>(null)

  useEffect(() => { loadEntreprises() }, [])

  useEffect(() => {
    if (loading) return
    expandSidebarForPath(pathname)
  }, [pathname, loading])

  async function expandSidebarForPath(path: string) {
    let entId: string | null = null
    const entMatch = path.match(/^\/entreprise\/([^/]+)/)
    const secMatch = path.match(/^\/secteur\/([^/]+)/)
    const projMatch = path.match(/^\/projet\/([^/]+)/)
    const scenMatch = path.match(/\/scenario\/([^/]+)/)

    if (entMatch) {
      entId = entMatch[1]
    } else if (secMatch) {
      const { data } = await supabase.from("secteurs").select("entreprise_id").eq("id", secMatch[1]).single()
      entId = data?.entreprise_id ?? null
    } else if (projMatch) {
      const { data } = await supabase.from("projets").select("secteur_id, entreprise_id").eq("id", projMatch[1]).single()
      if (data) {
        if (data.secteur_id) {
          const { data: sec } = await supabase.from("secteurs").select("entreprise_id").eq("id", data.secteur_id).single()
          entId = sec?.entreprise_id ?? null
        } else {
          entId = data.entreprise_id ?? null
        }
      }
    } else if (scenMatch) {
      const { data: scen } = await supabase.from("scenarios").select("projet_id").eq("id", scenMatch[1]).single()
      if (scen) {
        const { data: proj } = await supabase.from("projets").select("secteur_id, entreprise_id").eq("id", scen.projet_id).single()
        if (proj) {
          if (proj.secteur_id) {
            const { data: sec } = await supabase.from("secteurs").select("entreprise_id").eq("id", proj.secteur_id).single()
            entId = sec?.entreprise_id ?? null
          } else {
            entId = proj.entreprise_id ?? null
          }
        }
      }
    }
    if (!entId) return

    setEntreprises(prev => {
      const ent = prev.find(e => e.id === entId)
      if (!ent || ent.expanded) return prev
      if (!ent.secteursLoaded) {
        fetchSecteurs(entId!).then(secteurs =>
          setEntreprises(p => p.map(e => e.id === entId ? { ...e, secteurs, secteursLoaded: true, expanded: true } : e))
        )
      }
      if (!ent.directProjetsLoaded) {
        fetchDirectProjets(entId!).then(directProjets =>
          setEntreprises(p => p.map(e => e.id === entId ? { ...e, directProjets, directProjetsLoaded: true } : e))
        )
      }
      return prev.map(e => e.id === entId ? { ...e, expanded: true } : e)
    })
  }

  async function loadEntreprises() {
    setLoading(true)
    const { data } = await supabase.from("entreprises").select("*").order("created_at")
    setEntreprises((data ?? []).map(e => ({
      ...e, expanded: false, secteursLoaded: false, secteurs: [],
      directProjets: [], directProjetsLoaded: false,
    })))
    setLoading(false)
  }

  async function fetchSecteurs(entrepriseId: string): Promise<SecteurNode[]> {
    const { data } = await supabase.from("secteurs").select("*").eq("entreprise_id", entrepriseId).order("created_at")
    return (data ?? []).map(s => ({ ...s, expanded: false, projetsLoaded: false, projets: [] }))
  }

  async function fetchDirectProjets(entrepriseId: string): Promise<ProjetNode[]> {
    const { data } = await supabase.from("projets").select("*")
      .eq("entreprise_id", entrepriseId).is("secteur_id", null).order("created_at")
    return (data ?? []).map(p => ({ ...p, expanded: false, scenariosLoaded: false, scenarios: [] }))
  }

  async function fetchProjets(secteurId: string): Promise<ProjetNode[]> {
    const { data } = await supabase.from("projets").select("*").eq("secteur_id", secteurId).order("created_at")
    return (data ?? []).map(p => ({ ...p, expanded: false, scenariosLoaded: false, scenarios: [] }))
  }

  async function fetchScenarios(projetId: string): Promise<ScenarioNode[]> {
    const { data } = await supabase.from("scenarios").select("*").eq("projet_id", projetId).order("created_at")
    return (data ?? []).map(s => ({ ...s, expanded: false, mappingsLoaded: false, mappings: [], mappingsExpanded: false }))
  }

  async function fetchMappings(scenarioId: string): Promise<Mapping[]> {
    const { data } = await supabase.from("mappings").select("*").eq("scenario_id", scenarioId).order("created_at")
    return data ?? []
  }

  // ─── Toggles: secteur path ─────────────────────────────────────────────────

  async function toggleEntreprise(id: string) {
    setEntreprises(prev => prev.map(e => {
      if (e.id !== id) return e
      const willExpand = !e.expanded
      if (willExpand && !e.secteursLoaded) {
        fetchSecteurs(id).then(secteurs =>
          setEntreprises(p => p.map(x => x.id === id ? { ...x, secteurs, secteursLoaded: true } : x))
        )
      }
      if (willExpand && !e.directProjetsLoaded) {
        fetchDirectProjets(id).then(directProjets =>
          setEntreprises(p => p.map(x => x.id === id ? { ...x, directProjets, directProjetsLoaded: true } : x))
        )
      }
      return { ...e, expanded: willExpand }
    }))
  }

  async function toggleSecteur(eid: string, sid: string) {
    setEntreprises(prev => prev.map(e => e.id !== eid ? e : {
      ...e, secteurs: e.secteurs.map(s => {
        if (s.id !== sid) return s
        const willExpand = !s.expanded
        if (willExpand && !s.projetsLoaded) {
          fetchProjets(sid).then(projets =>
            setEntreprises(p => p.map(x => x.id !== eid ? x : {
              ...x, secteurs: x.secteurs.map(y => y.id === sid ? { ...y, projets, projetsLoaded: true } : y)
            }))
          )
        }
        return { ...s, expanded: willExpand }
      }),
    }))
  }

  async function toggleProjet(eid: string, sid: string, pid: string) {
    setEntreprises(prev => prev.map(e => e.id !== eid ? e : ({
      ...e, secteurs: e.secteurs.map(s => s.id !== sid ? s : ({
        ...s, projets: s.projets.map(p => {
          if (p.id !== pid) return p
          const willExpand = !p.expanded
          if (willExpand && !p.scenariosLoaded) {
            fetchScenarios(pid).then(scenarios =>
              setEntreprises(prev2 => prev2.map(e2 => e2.id !== eid ? e2 : ({
                ...e2, secteurs: e2.secteurs.map(s2 => s2.id !== sid ? s2 : ({
                  ...s2, projets: s2.projets.map(p2 => p2.id !== pid ? p2 : ({ ...p2, scenarios, scenariosLoaded: true }))
                }))
              })))
            )
          }
          return { ...p, expanded: willExpand }
        })
      }))
    })))
  }

  async function toggleScenario(eid: string, sid: string, pid: string, scid: string) {
    setEntreprises(prev => prev.map(e => e.id !== eid ? e : ({
      ...e, secteurs: e.secteurs.map(s => s.id !== sid ? s : ({
        ...s, projets: s.projets.map(p => p.id !== pid ? p : ({
          ...p, scenarios: p.scenarios.map(sc => sc.id !== scid ? sc : { ...sc, expanded: !sc.expanded })
        }))
      }))
    })))
  }

  async function toggleMappings(eid: string, sid: string, pid: string, scid: string) {
    setEntreprises(prev => prev.map(e => e.id !== eid ? e : ({
      ...e, secteurs: e.secteurs.map(s => s.id !== sid ? s : ({
        ...s, projets: s.projets.map(p => p.id !== pid ? p : ({
          ...p, scenarios: p.scenarios.map(sc => {
            if (sc.id !== scid) return sc
            const willExpand = !sc.mappingsExpanded
            if (willExpand && !sc.mappingsLoaded) {
              fetchMappings(scid).then(mappings =>
                setEntreprises(p2 => p2.map(e2 => e2.id !== eid ? e2 : ({
                  ...e2, secteurs: e2.secteurs.map(s2 => s2.id !== sid ? s2 : ({
                    ...s2, projets: s2.projets.map(p3 => p3.id !== pid ? p3 : ({
                      ...p3, scenarios: p3.scenarios.map(sc2 =>
                        sc2.id !== scid ? sc2 : { ...sc2, mappings, mappingsLoaded: true }
                      )
                    }))
                  }))
                })))
              )
            }
            return { ...sc, mappingsExpanded: willExpand }
          })
        }))
      }))
    })))
  }

  // ─── Toggles: direct projet path ──────────────────────────────────────────

  async function toggleDirectProjet(eid: string, pid: string) {
    setEntreprises(prev => prev.map(e => {
      if (e.id !== eid) return e
      return {
        ...e, directProjets: e.directProjets.map(p => {
          if (p.id !== pid) return p
          const willExpand = !p.expanded
          if (willExpand && !p.scenariosLoaded) {
            fetchScenarios(pid).then(scenarios =>
              setEntreprises(p2 => p2.map(e2 => e2.id !== eid ? e2 : {
                ...e2, directProjets: e2.directProjets.map(p3 => p3.id !== pid ? p3 : { ...p3, scenarios, scenariosLoaded: true })
              }))
            )
          }
          return { ...p, expanded: willExpand }
        })
      }
    }))
  }

  async function toggleDirectScenario(eid: string, pid: string, scid: string) {
    setEntreprises(prev => prev.map(e => e.id !== eid ? e : ({
      ...e, directProjets: e.directProjets.map(p => p.id !== pid ? p : ({
        ...p, scenarios: p.scenarios.map(sc => sc.id !== scid ? sc : { ...sc, expanded: !sc.expanded })
      }))
    })))
  }

  async function toggleDirectMappings(eid: string, pid: string, scid: string) {
    setEntreprises(prev => prev.map(e => e.id !== eid ? e : ({
      ...e, directProjets: e.directProjets.map(p => p.id !== pid ? p : ({
        ...p, scenarios: p.scenarios.map(sc => {
          if (sc.id !== scid) return sc
          const willExpand = !sc.mappingsExpanded
          if (willExpand && !sc.mappingsLoaded) {
            fetchMappings(scid).then(mappings =>
              setEntreprises(p2 => p2.map(e2 => e2.id !== eid ? e2 : ({
                ...e2, directProjets: e2.directProjets.map(p3 => p3.id !== pid ? p3 : ({
                  ...p3, scenarios: p3.scenarios.map(sc2 =>
                    sc2.id !== scid ? sc2 : { ...sc2, mappings, mappingsLoaded: true }
                  )
                }))
              })))
            )
          }
          return { ...sc, mappingsExpanded: willExpand }
        })
      }))
    })))
  }

  // ─── Create ────────────────────────────────────────────────────────────────

  function openCreate(type: CreateType, parentId?: string) {
    setCreateName("")
    setCreateDialog({ type, parentId, open: true })
    setTimeout(() => createInputRef.current?.focus(), 50)
  }

  async function handleCreate() {
    if (!createDialog || !createName.trim()) return
    const name = createName.trim()
    try {
      if (createDialog.type === "entreprise") {
        const { data, error } = await supabase.from("entreprises").insert({ name }).select().single()
        if (error) throw error
        setEntreprises(p => [...p, { ...data, expanded: false, secteursLoaded: false, secteurs: [], directProjets: [], directProjetsLoaded: false }])
      }
      if (createDialog.type === "secteur") {
        const eid = createDialog.parentId!
        const { data, error } = await supabase.from("secteurs").insert({ name, entreprise_id: eid }).select().single()
        if (error) throw error
        setEntreprises(p => p.map(e => e.id !== eid ? e : {
          ...e, expanded: true, secteursLoaded: true,
          secteurs: [...e.secteurs, { ...data, expanded: false, projetsLoaded: false, projets: [] }],
        }))
      }
      if (createDialog.type === "projet-direct") {
        const eid = createDialog.parentId!
        const { data, error } = await supabase.from("projets").insert({ name, entreprise_id: eid }).select().single()
        if (error) throw error
        setEntreprises(p => p.map(e => e.id !== eid ? e : {
          ...e, expanded: true, directProjetsLoaded: true,
          directProjets: [...e.directProjets, { ...data, expanded: false, scenariosLoaded: false, scenarios: [] }],
        }))
      }
      if (createDialog.type === "projet") {
        const sid = createDialog.parentId!
        const { data, error } = await supabase.from("projets").insert({ name, secteur_id: sid }).select().single()
        if (error) throw error
        setEntreprises(p => p.map(e => ({
          ...e, secteurs: e.secteurs.map(s => s.id !== sid ? s : {
            ...s, expanded: true, projetsLoaded: true,
            projets: [...s.projets, { ...data, expanded: false, scenariosLoaded: false, scenarios: [] }],
          })
        })))
      }
      if (createDialog.type === "scenario") {
        const pid = createDialog.parentId!
        const { data, error } = await supabase.from("scenarios").insert({ name, projet_id: pid }).select().single()
        if (error) throw error
        const newSc = { ...data, expanded: false, mappingsLoaded: false, mappings: [], mappingsExpanded: false }
        setEntreprises(p => p.map(e => ({
          ...e,
          directProjets: e.directProjets.map(p2 => p2.id !== pid ? p2 : {
            ...p2, expanded: true, scenariosLoaded: true,
            scenarios: [...p2.scenarios, newSc],
          }),
          secteurs: e.secteurs.map(s => ({
            ...s, projets: s.projets.map(p2 => p2.id !== pid ? p2 : {
              ...p2, expanded: true, scenariosLoaded: true,
              scenarios: [...p2.scenarios, newSc],
            })
          }))
        })))
        router.push(`/scenario/${data.id}`)
      }
      if (createDialog.type === "mapping") {
        const scid = createDialog.parentId!
        const { data, error } = await supabase.from("mappings").insert({
          name, scenario_id: scid, rows: [], filters: [], output_filters: [], dedup_by_pk: false,
        }).select().single()
        if (error) throw error
        setEntreprises(p => p.map(e => ({
          ...e,
          directProjets: e.directProjets.map(p2 => ({
            ...p2, scenarios: p2.scenarios.map(sc => sc.id !== scid ? sc : {
              ...sc, mappingsExpanded: true, mappingsLoaded: true,
              mappings: [...sc.mappings, data],
            })
          })),
          secteurs: e.secteurs.map(s => ({
            ...s, projets: s.projets.map(p2 => ({
              ...p2, scenarios: p2.scenarios.map(sc => sc.id !== scid ? sc : {
                ...sc, mappingsExpanded: true, mappingsLoaded: true,
                mappings: [...sc.mappings, data],
              })
            }))
          }))
        })))
        router.push(`/scenario/${scid}/mapping/${data.id}`)
      }
      toast.success(`"${name}" créé`)
      setCreateDialog(null)
    } catch {
      toast.error("Erreur lors de la création")
    }
  }

  // ─── Rename ────────────────────────────────────────────────────────────────

  function openRename(type: DeleteType, id: string, currentName: string) {
    setRenameName(currentName)
    setRenameDialog({ type, id, currentName, open: true })
  }

  async function handleRename() {
    if (!renameDialog || !renameName.trim()) return
    const { type, id } = renameDialog
    const name = renameName.trim()
    const table = type === "mapping" ? "mappings" : `${type}s`
    try {
      const { error } = await supabase.from(table as any).update({ name }).eq("id", id)
      if (error) throw error
      const upd = (node: any) => node.id === id ? { ...node, name } : node
      setEntreprises(p => p.map(e => {
        if (type === "entreprise") return upd(e)
        return {
          ...e,
          directProjets: type === "projet" ? e.directProjets.map(upd) :
            e.directProjets.map(p2 => ({
              ...p2, scenarios: p2.scenarios.map(sc => {
                if (type === "scenario") return upd(sc)
                return { ...sc, mappings: sc.mappings.map(m => type === "mapping" ? upd(m) : m) }
              })
            })),
          secteurs: e.secteurs.map(s => {
            if (type === "secteur") return upd(s)
            return {
              ...s, projets: s.projets.map(p2 => {
                if (type === "projet") return upd(p2)
                return {
                  ...p2, scenarios: p2.scenarios.map(sc => {
                    if (type === "scenario") return upd(sc)
                    return { ...sc, mappings: sc.mappings.map(m => type === "mapping" ? upd(m) : m) }
                  })
                }
              })
            }
          })
        }
      }))
      toast.success("Renommé")
      setRenameDialog(null)
    } catch {
      toast.error("Erreur lors du renommage")
    }
  }

  // ─── Delete ────────────────────────────────────────────────────────────────

  function openDelete(type: DeleteType, id: string, name: string) {
    setDeleteDialog({ type, id, name, open: true })
  }

  async function handleDelete() {
    if (!deleteDialog) return
    const { type, id } = deleteDialog
    const table = type === "mapping" ? "mappings" : `${type}s`
    try {
      const { error } = await supabase.from(table as any).delete().eq("id", id)
      if (error) throw error
      if (type === "entreprise") {
        setEntreprises(p => p.filter(e => e.id !== id))
      } else {
        setEntreprises(p => p.map(e => ({
          ...e,
          directProjets: type === "projet"
            ? e.directProjets.filter(p2 => p2.id !== id)
            : e.directProjets.map(p2 => ({
              ...p2,
              scenarios: type === "scenario"
                ? p2.scenarios.filter(sc => sc.id !== id)
                : p2.scenarios.map(sc => ({
                  ...sc,
                  mappings: type === "mapping" ? sc.mappings.filter(m => m.id !== id) : sc.mappings,
                }))
            })),
          secteurs: type === "secteur"
            ? e.secteurs.filter(s => s.id !== id)
            : e.secteurs.map(s => ({
              ...s,
              projets: type === "projet"
                ? s.projets.filter(p2 => p2.id !== id)
                : s.projets.map(p2 => ({
                  ...p2,
                  scenarios: type === "scenario"
                    ? p2.scenarios.filter(sc => sc.id !== id)
                    : p2.scenarios.map(sc => ({
                      ...sc,
                      mappings: type === "mapping" ? sc.mappings.filter(m => m.id !== id) : sc.mappings,
                    }))
                }))
            }))
        })))
      }
      toast.success("Supprimé")
      setDeleteDialog(null)
      router.push("/")
    } catch {
      toast.error("Erreur lors de la suppression")
    }
  }

  // ─── Render ────────────────────────────────────────────────────────────────

  return (
    <>
      <div className="flex w-64 shrink-0 flex-col border-r border-border bg-white">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border px-4 py-3 shrink-0">
          <p className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground/70">
            Workspace
          </p>
          <button
            title="Nouvelle entreprise"
            className="flex h-6 w-6 items-center justify-center rounded text-muted-foreground hover:text-primary hover:bg-gray-100 transition-colors"
            onClick={() => openCreate("entreprise")}
          >
            <Plus className="h-3.5 w-3.5" />
          </button>
        </div>

        {/* Tree content */}
        <div className="flex-1 overflow-y-auto py-2">
          {loading ? (
            <div className="flex items-center justify-center py-10">
              <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
            </div>
          ) : entreprises.length === 0 ? (
            <div className="px-4 py-8 text-center">
              <Building2 className="mx-auto mb-2 h-8 w-8 text-gray-200" />
              <p className="text-xs text-muted-foreground">Aucune entreprise</p>
              <button
                className="mt-3 w-full rounded-lg border border-border bg-white py-2 text-[11px] font-semibold text-muted-foreground hover:bg-gray-50 transition-colors"
                onClick={() => openCreate("entreprise")}
              >
                + Nouvelle entreprise
              </button>
            </div>
          ) : (
            <div>
              {entreprises.map(ent => (
                <TreeItem
                  key={ent.id}
                  label={ent.name}
                  depth={0}
                  icon={<Building2 className="h-4 w-4" />}
                  href={`/entreprise/${ent.id}`}
                  hasToggle
                  expanded={ent.expanded}
                  isActive={pathname.startsWith(`/entreprise/${ent.id}`)}
                  onToggle={() => toggleEntreprise(ent.id)}
                  onAdd={() => openCreate("secteur", ent.id)}
                  addLabel="Nouveau secteur"
                  onRename={() => openRename("entreprise", ent.id, ent.name)}
                  onDelete={() => openDelete("entreprise", ent.id, ent.name)}
                >
                  {/* Direct projets (no secteur) */}
                  {ent.directProjets.map(proj => (
                    <TreeItem
                      key={proj.id}
                      label={proj.name}
                      depth={1}
                      icon={<FolderOpen className="h-3.5 w-3.5 text-blue-400" />}
                      href={`/projet/${proj.id}`}
                      hasToggle
                      expanded={proj.expanded}
                      isActive={pathname.startsWith(`/projet/${proj.id}`)}
                      onToggle={() => toggleDirectProjet(ent.id, proj.id)}
                      onAdd={() => openCreate("scenario", proj.id)}
                      addLabel="Nouveau scénario"
                      onRename={() => openRename("projet", proj.id, proj.name)}
                      onDelete={() => openDelete("projet", proj.id, proj.name)}
                    >
                      {proj.scenarios.length === 0 && proj.scenariosLoaded ? (
                        <p className="py-1 text-center text-[11px] text-muted-foreground italic" style={{ paddingLeft: 50 }}>
                          Aucun scénario —{" "}
                          <button className="text-primary hover:underline" onClick={() => openCreate("scenario", proj.id)}>créer</button>
                        </p>
                      ) : proj.scenarios.map(sc => (
                        <ScenarioSubTree
                          key={sc.id}
                          sc={sc}
                          depth={2}
                          pathname={pathname}
                          openCreate={openCreate}
                          onToggle={() => toggleDirectScenario(ent.id, proj.id, sc.id)}
                          onToggleMappings={() => toggleDirectMappings(ent.id, proj.id, sc.id)}
                          onRename={() => openRename("scenario", sc.id, sc.name)}
                          onDelete={() => openDelete("scenario", sc.id, sc.name)}
                          onAddMapping={() => openCreate("mapping", sc.id)}
                          onRenameMapping={(id, name) => openRename("mapping", id, name)}
                          onDeleteMapping={(id, name) => openDelete("mapping", id, name)}
                        />
                      ))}
                    </TreeItem>
                  ))}

                  {/* Secteurs */}
                  {ent.secteurs.length === 0 && ent.secteursLoaded && ent.directProjets.length === 0 ? (
                    <p className="py-1 text-center text-[11px] text-muted-foreground italic" style={{ paddingLeft: 36 }}>
                      Vide —{" "}
                      <button className="text-primary hover:underline" onClick={() => openCreate("secteur", ent.id)}>créer un secteur</button>
                    </p>
                  ) : ent.secteurs.map(sec => (
                    <TreeItem
                      key={sec.id}
                      label={sec.name}
                      depth={1}
                      icon={<FolderOpen className="h-3.5 w-3.5" />}
                      href={`/secteur/${sec.id}`}
                      hasToggle
                      expanded={sec.expanded}
                      isActive={pathname.startsWith(`/secteur/${sec.id}`)}
                      onToggle={() => toggleSecteur(ent.id, sec.id)}
                      onAdd={() => openCreate("projet", sec.id)}
                      addLabel="Nouveau projet"
                      onRename={() => openRename("secteur", sec.id, sec.name)}
                      onDelete={() => openDelete("secteur", sec.id, sec.name)}
                    >
                      {sec.projets.length === 0 && sec.projetsLoaded ? (
                        <p className="py-1 text-center text-[11px] text-muted-foreground italic" style={{ paddingLeft: 50 }}>
                          Aucun projet —{" "}
                          <button className="text-primary hover:underline" onClick={() => openCreate("projet", sec.id)}>créer</button>
                        </p>
                      ) : sec.projets.map(proj => (
                        <TreeItem
                          key={proj.id}
                          label={proj.name}
                          depth={2}
                          icon={<FolderOpen className="h-3.5 w-3.5 text-blue-400" />}
                          href={`/projet/${proj.id}`}
                          hasToggle
                          expanded={proj.expanded}
                          isActive={pathname.startsWith(`/projet/${proj.id}`)}
                          onToggle={() => toggleProjet(ent.id, sec.id, proj.id)}
                          onAdd={() => openCreate("scenario", proj.id)}
                          addLabel="Nouveau scénario"
                          onRename={() => openRename("projet", proj.id, proj.name)}
                          onDelete={() => openDelete("projet", proj.id, proj.name)}
                        >
                          {proj.scenarios.length === 0 && proj.scenariosLoaded ? (
                            <p className="py-1 text-center text-[11px] text-muted-foreground italic" style={{ paddingLeft: 64 }}>
                              Aucun scénario —{" "}
                              <button className="text-primary hover:underline" onClick={() => openCreate("scenario", proj.id)}>créer</button>
                            </p>
                          ) : proj.scenarios.map(sc => (
                            <ScenarioSubTree
                              key={sc.id}
                              sc={sc}
                              depth={3}
                              pathname={pathname}
                              openCreate={openCreate}
                              onToggle={() => toggleScenario(ent.id, sec.id, proj.id, sc.id)}
                              onToggleMappings={() => toggleMappings(ent.id, sec.id, proj.id, sc.id)}
                              onRename={() => openRename("scenario", sc.id, sc.name)}
                              onDelete={() => openDelete("scenario", sc.id, sc.name)}
                              onAddMapping={() => openCreate("mapping", sc.id)}
                              onRenameMapping={(id, name) => openRename("mapping", id, name)}
                              onDeleteMapping={(id, name) => openDelete("mapping", id, name)}
                            />
                          ))}
                        </TreeItem>
                      ))}
                    </TreeItem>
                  ))}
                </TreeItem>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="shrink-0 border-t border-border px-4 py-3">
          <button
            className="w-full rounded-lg bg-primary/5 py-2 text-[11px] font-semibold text-primary hover:bg-primary/10 transition-colors"
            onClick={() => openCreate("entreprise")}
          >
            + Nouvelle entreprise
          </button>
        </div>
      </div>

      {/* ── Dialogs ─────────────────────────────────────────────────────────── */}
      <Dialog open={createDialog?.open ?? false} onOpenChange={open => !open && setCreateDialog(null)}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>
              {createDialog?.type === "entreprise" && "Nouvelle entreprise"}
              {createDialog?.type === "secteur" && "Nouveau secteur"}
              {createDialog?.type === "projet" && "Nouveau projet"}
              {createDialog?.type === "projet-direct" && "Nouveau projet direct"}
              {createDialog?.type === "scenario" && "Nouveau scénario"}
              {createDialog?.type === "mapping" && "Nouveau mapping"}
            </DialogTitle>
            <DialogDescription>Entrez un nom pour continuer.</DialogDescription>
          </DialogHeader>
          <Input
            ref={createInputRef}
            placeholder="Nom..."
            value={createName}
            onChange={e => setCreateName(e.target.value)}
            onKeyDown={e => e.key === "Enter" && handleCreate()}
          />
          <DialogFooter className="gap-2">
            <Button variant="outline" size="sm" onClick={() => setCreateDialog(null)}>Annuler</Button>
            <Button size="sm" onClick={handleCreate} disabled={!createName.trim()}>Créer</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={renameDialog?.open ?? false} onOpenChange={open => !open && setRenameDialog(null)}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>Renommer « {renameDialog?.currentName} »</DialogTitle>
            <DialogDescription>Entrez le nouveau nom.</DialogDescription>
          </DialogHeader>
          <Input
            value={renameName}
            onChange={e => setRenameName(e.target.value)}
            onKeyDown={e => e.key === "Enter" && handleRename()}
            autoFocus
          />
          <DialogFooter className="gap-2">
            <Button variant="outline" size="sm" onClick={() => setRenameDialog(null)}>Annuler</Button>
            <Button size="sm" onClick={handleRename} disabled={!renameName.trim()}>Renommer</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={deleteDialog?.open ?? false} onOpenChange={open => !open && setDeleteDialog(null)}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>Supprimer « {deleteDialog?.name} » ?</DialogTitle>
            <DialogDescription>Cette action est irréversible. Tout le contenu imbriqué sera supprimé.</DialogDescription>
          </DialogHeader>
          <DialogFooter className="gap-2">
            <Button variant="outline" size="sm" onClick={() => setDeleteDialog(null)}>Annuler</Button>
            <Button size="sm" variant="destructive" onClick={handleDelete}>Supprimer</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
