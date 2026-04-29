"use client"

import { useEffect, useState } from "react"
import { useParams } from "next/navigation"
import { Loader2, Plus } from "lucide-react"

import { WorkspaceShell } from "@/components/app-shell-workspace"
import { PhotoCard, CreateCard, PROJET_IMAGE } from "@/components/photo-card"
import { supabase, type Secteur, type Entreprise } from "@/lib/supabase"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { toast } from "sonner"

interface ProjetCard { id: string; name: string; created_at: string | null; background_url: string | null; code: string | null; scenarioCount: number }

type Modal =
  | { type: "create" }
  | { type: "rename"; id: string; name: string }
  | { type: "delete"; id: string; name: string }

export default function SecteurPage() {
  const { secteurId } = useParams<{ secteurId: string }>()
  const [secteur, setSecteur] = useState<Secteur | null>(null)
  const [entreprise, setEntreprise] = useState<Entreprise | null>(null)
  const [projets, setProjets] = useState<ProjetCard[]>([])
  const [loading, setLoading] = useState(true)
  const [modal, setModal] = useState<Modal | null>(null)
  const [inputName, setInputName] = useState("")
  const [inputCode, setInputCode] = useState("")
  const [inputUrl, setInputUrl] = useState("")
  const [saving, setSaving] = useState(false)

  useEffect(() => { load() }, [secteurId])

  async function load() {
    setLoading(true)
    const { data: sec } = await supabase.from("secteurs").select("*").eq("id", secteurId).single()
    if (sec) {
      setSecteur(sec)
      const { data: ent } = await supabase.from("entreprises").select("*").eq("id", sec.entreprise_id).single()
      if (ent) setEntreprise(ent)
    }
    const { data: projs } = await supabase.from("projets").select("*").eq("secteur_id", secteurId).order("created_at")
    if (!projs) { setLoading(false); return }

    const cards = await Promise.all(
      projs.map(async p => {
        const { count } = await supabase.from("scenarios").select("*", { count: "exact", head: true }).eq("projet_id", p.id)
        return { id: p.id, name: p.name, created_at: p.created_at, background_url: p.background_url, code: p.code, scenarioCount: count ?? 0 }
      })
    )
    setProjets(cards)
    setLoading(false)
  }

  function openCreate() { setInputName(""); setInputCode(""); setInputUrl(""); setModal({ type: "create" }) }
  function openRename(id: string, name: string) { setInputName(name); setModal({ type: "rename", id, name }) }
  function openDelete(id: string, name: string) { setModal({ type: "delete", id, name }) }
  function closeModal() { setModal(null) }

  async function handleCreate() {
    const name = inputName.trim(); if (!name) return
    setSaving(true)
    try {
      const payload: Record<string, unknown> = { name, secteur_id: secteurId }
      if (inputCode.trim()) payload.code = inputCode.trim()
      if (inputUrl.trim()) payload.background_url = inputUrl.trim()
      const { error } = await supabase.from("projets").insert(payload)
      if (error) throw error
      toast.success(`"${name}" créé`); closeModal(); load()
    } catch { toast.error("Erreur lors de la création") }
    finally { setSaving(false) }
  }

  async function handleRename() {
    if (modal?.type !== "rename") return
    const name = inputName.trim(); if (!name) return
    setSaving(true)
    try {
      await supabase.from("projets").update({ name }).eq("id", modal.id)
      toast.success("Renommé"); closeModal(); load()
    } catch { toast.error("Erreur") }
    finally { setSaving(false) }
  }

  async function handleDelete() {
    if (modal?.type !== "delete") return
    setSaving(true)
    try {
      await supabase.from("projets").delete().eq("id", modal.id)
      toast.success("Supprimé"); closeModal(); load()
    } catch { toast.error("Erreur") }
    finally { setSaving(false) }
  }

  return (
    <WorkspaceShell>
      <div className="min-h-full">
        <div className="border-b border-border bg-white px-8 pt-6 pb-5">
          <div className="flex items-end justify-between">
            <div>
              <p className="text-[11px] font-bold uppercase tracking-[0.08em] text-primary">
                {entreprise?.name ?? "…"} / Secteur
              </p>
              <h1 className="mt-1 text-2xl font-black uppercase tracking-tight">{secteur?.name ?? "…"}</h1>
              <p className="mt-0.5 text-sm text-muted-foreground">
                {projets.length} projet{projets.length !== 1 ? "s" : ""}
              </p>
            </div>
            <button onClick={openCreate}
              className="flex items-center gap-2 rounded-lg bg-primary px-5 py-2.5 text-sm font-semibold text-white hover:bg-primary/90 transition-colors shadow-sm">
              <Plus className="h-4 w-4" /> Nouveau projet
            </button>
          </div>
        </div>

        <div className="p-8">
          {loading ? (
            <div className="flex h-64 items-center justify-center">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : (
            <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {projets.map(proj => (
                <PhotoCard
                  key={proj.id}
                  href={`/projet/${proj.id}`}
                  name={proj.name}
                  createdAt={proj.created_at}
                  image={proj.background_url || PROJET_IMAGE}
                  code={proj.code}
                  metric1Label="Scénarios"
                  metric1Value={proj.scenarioCount}
                  metric2Label="Quality"
                  metric2Value="0%"
                  onRename={e => { e.preventDefault(); openRename(proj.id, proj.name) }}
                  onDelete={e => { e.preventDefault(); openDelete(proj.id, proj.name) }}
                />
              ))}
              <CreateCard label="Nouveau projet" onClick={openCreate} />
            </div>
          )}
        </div>
      </div>

      {modal?.type === "create" && (
        <ModalWrapper onClose={closeModal}>
          <ModalHeader title="Nouveau projet" onClose={closeModal} />
          <div className="p-6 space-y-4">
            <Field label="Nom du projet">
              <Input placeholder="Ex: Plan été 2026" value={inputName} onChange={e => setInputName(e.target.value)}
                onKeyDown={e => e.key === "Enter" && handleCreate()} autoFocus className="rounded-lg" />
            </Field>
            <Field label="Code projet (optionnel)">
              <Input placeholder="Ex: HP-2026" value={inputCode} onChange={e => setInputCode(e.target.value)} className="rounded-lg" />
            </Field>
            <Field label="Image de fond (optionnel)">
              <Input placeholder="https://images.unsplash.com/..." value={inputUrl} onChange={e => setInputUrl(e.target.value)} className="rounded-lg" />
            </Field>
            <Button className="w-full rounded-lg bg-primary hover:bg-primary/90 text-white font-semibold py-2.5"
              onClick={handleCreate} disabled={saving || !inputName.trim()}>
              {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />} Créer le projet
            </Button>
          </div>
        </ModalWrapper>
      )}

      {modal?.type === "rename" && (
        <ModalWrapper onClose={closeModal}>
          <ModalHeader title={`Renommer « ${modal.name} »`} onClose={closeModal} />
          <div className="p-6 space-y-4">
            <Input value={inputName} onChange={e => setInputName(e.target.value)}
              onKeyDown={e => e.key === "Enter" && handleRename()} autoFocus className="rounded-lg" />
            <Button className="w-full rounded-lg bg-primary hover:bg-primary/90 text-white font-semibold py-2.5"
              onClick={handleRename} disabled={saving || !inputName.trim()}>
              {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />} Renommer
            </Button>
          </div>
        </ModalWrapper>
      )}

      {modal?.type === "delete" && (
        <ModalWrapper onClose={closeModal}>
          <ModalHeader title={`Supprimer « ${modal.name} » ?`} onClose={closeModal} color="bg-destructive" />
          <div className="p-6 space-y-4">
            <p className="text-sm text-muted-foreground">Cette action est irréversible. Tous les scénarios liés seront supprimés.</p>
            <div className="flex gap-3">
              <Button variant="outline" className="flex-1 rounded-lg" onClick={closeModal}>Annuler</Button>
              <Button variant="destructive" className="flex-1 rounded-lg" onClick={handleDelete} disabled={saving}>
                {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />} Supprimer
              </Button>
            </div>
          </div>
        </ModalWrapper>
      )}
    </WorkspaceShell>
  )
}

function ModalWrapper({ children, onClose }: { children: React.ReactNode; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
      onClick={e => { if (e.target === e.currentTarget) onClose() }}>
      <div className="w-full max-w-md overflow-hidden rounded-2xl bg-white shadow-2xl">{children}</div>
    </div>
  )
}
function ModalHeader({ title, onClose, color = "bg-primary" }: { title: string; onClose: () => void; color?: string }) {
  return (
    <div className={`flex items-center justify-between ${color} px-6 py-5`}>
      <h2 className="text-lg font-bold text-white">{title}</h2>
      <button onClick={onClose} className="flex h-7 w-7 items-center justify-center rounded-full bg-white/20 text-white hover:bg-white/30 text-lg font-bold">×</button>
    </div>
  )
}
function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <div className="space-y-1.5"><label className="text-[12px] font-semibold text-foreground">{label}</label>{children}</div>
}
