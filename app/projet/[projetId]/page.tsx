"use client"

import { useEffect, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import { Loader2, Plus } from "lucide-react"

import { WorkspaceShell } from "@/components/app-shell-workspace"
import { PhotoCard, CreateCard } from "@/components/photo-card"
import { supabase, type Projet, type Secteur, type Entreprise } from "@/lib/supabase"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { toast } from "sonner"

interface ScenarioCard {
  id: string; name: string; created_at: string | null; runCount: number; mappingCount: number
}

export default function ProjetPage() {
  const { projetId } = useParams<{ projetId: string }>()
  const router = useRouter()
  const [projet, setProjet] = useState<Projet | null>(null)
  const [secteur, setSecteur] = useState<Secteur | null>(null)
  const [entreprise, setEntreprise] = useState<Entreprise | null>(null)
  const [scenarios, setScenarios] = useState<ScenarioCard[]>([])
  const [loading, setLoading] = useState(true)
  const [showModal, setShowModal] = useState(false)
  const [createName, setCreateName] = useState("")
  const [creating, setCreating] = useState(false)

  useEffect(() => { load() }, [projetId])

  async function load() {
    setLoading(true)
    const [{ data: proj }, { data: scens }] = await Promise.all([
      supabase.from("projets").select("*").eq("id", projetId).single(),
      supabase.from("scenarios").select("*").eq("projet_id", projetId).order("created_at"),
    ])
    if (proj) {
      setProjet(proj)
      if (proj.secteur_id) {
        const { data: sec } = await supabase.from("secteurs").select("*").eq("id", proj.secteur_id).single()
        if (sec) {
          setSecteur(sec)
          const { data: ent } = await supabase.from("entreprises").select("*").eq("id", sec.entreprise_id).single()
          if (ent) setEntreprise(ent)
        }
      } else if (proj.entreprise_id) {
        const { data: ent } = await supabase.from("entreprises").select("*").eq("id", proj.entreprise_id).single()
        if (ent) setEntreprise(ent)
      }
    }
    if (!scens) { setLoading(false); return }

    const cards = await Promise.all(
      scens.map(async sc => {
        const [{ count: rc }, { count: mc }] = await Promise.all([
          supabase.from("allocation_runs").select("*", { count: "exact", head: true }).eq("scenario_id", sc.id),
          supabase.from("mappings").select("*", { count: "exact", head: true }).eq("scenario_id", sc.id),
        ])
        return { id: sc.id, name: sc.name, created_at: sc.created_at, runCount: rc ?? 0, mappingCount: mc ?? 0 }
      })
    )
    setScenarios(cards)
    setLoading(false)
  }

  async function handleCreate() {
    const name = createName.trim()
    if (!name) return
    setCreating(true)
    try {
      const { data, error } = await supabase
        .from("scenarios")
        .insert({ name, projet_id: projetId })
        .select().single()
      if (error) throw error
      toast.success(`Scénario "${data.name}" créé`)
      setShowModal(false)
      setCreateName("")
      router.push(`/scenario/${data.id}`)
    } catch {
      toast.error("Erreur lors de la création")
    } finally {
      setCreating(false)
    }
  }

  return (
    <WorkspaceShell>
      <div className="min-h-full">
        {/* Page header */}
        <div className="border-b border-border bg-white px-8 pt-6 pb-5">
          <div className="flex items-end justify-between">
            <div>
              <p className="text-[11px] font-bold uppercase tracking-[0.08em] text-primary">
                {entreprise?.name ?? "…"}{secteur ? ` / ${secteur.name}` : ""} / Projet
              </p>
              <h1 className="mt-1 text-2xl font-black uppercase tracking-tight">{projet?.name ?? "…"}</h1>
              <p className="mt-0.5 text-sm text-muted-foreground">
                {scenarios.length} scénario{scenarios.length !== 1 ? "s" : ""}
              </p>
            </div>
            <button
              onClick={() => { setCreateName(""); setShowModal(true) }}
              className="flex items-center gap-2 rounded-lg bg-primary px-5 py-2.5 text-sm font-semibold text-white hover:bg-primary/90 transition-colors shadow-sm"
            >
              <Plus className="h-4 w-4" /> Nouveau scénario
            </button>
          </div>
        </div>

        {/* Grid */}
        <div className="p-8">
          {loading ? (
            <div className="flex h-64 items-center justify-center">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : (
            <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {scenarios.map(sc => (
                <PhotoCard
                  key={sc.id}
                  href={`/scenario/${sc.id}`}
                  name={sc.name}
                  createdAt={sc.created_at}
                  metric1Label="Runs"
                  metric1Value={sc.runCount}
                  metric1Color="text-orange-500"
                  metric2Label="Mappings"
                  metric2Value={sc.mappingCount}
                  metric2Color="text-violet-500"
                />
              ))}
              <CreateCard label="Nouveau scénario" onClick={() => { setCreateName(""); setShowModal(true) }} />
            </div>
          )}
        </div>
      </div>

      {/* Modal */}
      {showModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
          onClick={e => { if (e.target === e.currentTarget) setShowModal(false) }}
        >
          <div className="w-full max-w-md overflow-hidden rounded-2xl bg-white shadow-2xl">
            <div className="flex items-center justify-between bg-primary px-6 py-5">
              <h2 className="text-lg font-bold text-white">Nouveau scénario</h2>
              <button
                onClick={() => setShowModal(false)}
                className="flex h-7 w-7 items-center justify-center rounded-full bg-white/20 text-white hover:bg-white/30 transition-colors text-lg font-bold"
              >×</button>
            </div>
            <div className="p-6 space-y-4">
              <div className="space-y-1.5">
                <label className="text-[12px] font-semibold text-foreground">Nom du scénario</label>
                <Input
                  placeholder="Ex: Scénario A - Été 2026"
                  value={createName}
                  onChange={e => setCreateName(e.target.value)}
                  onKeyDown={e => e.key === "Enter" && handleCreate()}
                  autoFocus
                  className="rounded-lg"
                />
              </div>
              <Button
                className="w-full rounded-lg bg-primary hover:bg-primary/90 text-white font-semibold py-2.5"
                onClick={handleCreate}
                disabled={creating || !createName.trim()}
              >
                {creating && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Créer le scénario
              </Button>
            </div>
          </div>
        </div>
      )}
    </WorkspaceShell>
  )
}
