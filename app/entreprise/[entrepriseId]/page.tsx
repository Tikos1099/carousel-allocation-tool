"use client"

import { useEffect, useState } from "react"
import { useParams } from "next/navigation"
import { Loader2, Plus } from "lucide-react"

import { WorkspaceShell } from "@/components/app-shell-workspace"
import { PhotoCard, CreateCard, SECTEUR_IMAGE, PROJET_IMAGE } from "@/components/photo-card"
import { supabase, type Entreprise } from "@/lib/supabase"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { toast } from "sonner"

interface SecteurCard { id: string; name: string; created_at: string | null; background_url: string | null; projetCount: number }
interface DirectProjetCard { id: string; name: string; created_at: string | null; background_url: string | null; code: string | null; scenarioCount: number }

type ModalType =
  | { type: "create-secteur" }
  | { type: "create-projet" }
  | { type: "rename-secteur"; id: string; name: string }
  | { type: "delete-secteur"; id: string; name: string }
  | { type: "rename-projet"; id: string; name: string }
  | { type: "delete-projet"; id: string; name: string }

export default function EntreprisePage() {
  const { entrepriseId } = useParams<{ entrepriseId: string }>()
  const [entreprise, setEntreprise] = useState<Entreprise | null>(null)
  const [secteurs, setSecteurs] = useState<SecteurCard[]>([])
  const [directProjets, setDirectProjets] = useState<DirectProjetCard[]>([])
  const [loading, setLoading] = useState(true)
  const [modal, setModal] = useState<ModalType | null>(null)
  const [inputName, setInputName] = useState("")
  const [inputCode, setInputCode] = useState("")
  const [inputUrl, setInputUrl] = useState("")
  const [saving, setSaving] = useState(false)

  useEffect(() => { load() }, [entrepriseId])

  async function load() {
    setLoading(true)
    const { data: ent } = await supabase.from("entreprises").select("*").eq("id", entrepriseId).single()
    if (ent) setEntreprise(ent)

    const [{ data: secs }, { data: projs }] = await Promise.all([
      supabase.from("secteurs").select("*").eq("entreprise_id", entrepriseId).order("created_at"),
      supabase.from("projets").select("*").eq("entreprise_id", entrepriseId).is("secteur_id", null).order("created_at"),
    ])

    const secteurCards = await Promise.all(
      (secs ?? []).map(async sec => {
        const { count } = await supabase.from("projets").select("*", { count: "exact", head: true }).eq("secteur_id", sec.id)
        return { id: sec.id, name: sec.name, created_at: sec.created_at, background_url: sec.background_url, projetCount: count ?? 0 }
      })
    )
    const projetCards = await Promise.all(
      (projs ?? []).map(async proj => {
        const { count } = await supabase.from("scenarios").select("*", { count: "exact", head: true }).eq("projet_id", proj.id)
        return { id: proj.id, name: proj.name, created_at: proj.created_at, background_url: proj.background_url, code: proj.code, scenarioCount: count ?? 0 }
      })
    )
    setSecteurs(secteurCards)
    setDirectProjets(projetCards)
    setLoading(false)
  }

  function open(m: ModalType, name = "", code = "", url = "") {
    setInputName(name); setInputCode(code); setInputUrl(url); setModal(m)
  }
  function closeModal() { setModal(null) }

  async function handleCreateSecteur() {
    const name = inputName.trim(); if (!name) return
    setSaving(true)
    try {
      const payload: Record<string, unknown> = { name, entreprise_id: entrepriseId }
      if (inputUrl.trim()) payload.background_url = inputUrl.trim()
      const { error } = await supabase.from("secteurs").insert(payload)
      if (error) throw error
      toast.success(`"${name}" créé`); closeModal(); load()
    } catch { toast.error("Erreur lors de la création") }
    finally { setSaving(false) }
  }

  async function handleCreateProjet() {
    const name = inputName.trim(); if (!name) return
    setSaving(true)
    try {
      const payload: Record<string, unknown> = { name, entreprise_id: entrepriseId, secteur_id: null }
      if (inputCode.trim()) payload.code = inputCode.trim()
      if (inputUrl.trim()) payload.background_url = inputUrl.trim()
      const { error } = await supabase.from("projets").insert(payload)
      if (error) throw error
      toast.success(`"${name}" créé`); closeModal(); load()
    } catch { toast.error("Erreur lors de la création") }
    finally { setSaving(false) }
  }

  async function handleRenameSecteur() {
    if (modal?.type !== "rename-secteur") return
    const name = inputName.trim(); if (!name) return
    setSaving(true)
    try {
      await supabase.from("secteurs").update({ name }).eq("id", modal.id)
      toast.success("Renommé"); closeModal(); load()
    } catch { toast.error("Erreur") }
    finally { setSaving(false) }
  }

  async function handleDeleteSecteur() {
    if (modal?.type !== "delete-secteur") return
    setSaving(true)
    try {
      await supabase.from("secteurs").delete().eq("id", modal.id)
      toast.success("Supprimé"); closeModal(); load()
    } catch { toast.error("Erreur") }
    finally { setSaving(false) }
  }

  async function handleRenameProjet() {
    if (modal?.type !== "rename-projet") return
    const name = inputName.trim(); if (!name) return
    setSaving(true)
    try {
      await supabase.from("projets").update({ name }).eq("id", modal.id)
      toast.success("Renommé"); closeModal(); load()
    } catch { toast.error("Erreur") }
    finally { setSaving(false) }
  }

  async function handleDeleteProjet() {
    if (modal?.type !== "delete-projet") return
    setSaving(true)
    try {
      await supabase.from("projets").delete().eq("id", modal.id)
      toast.success("Supprimé"); closeModal(); load()
    } catch { toast.error("Erreur") }
    finally { setSaving(false) }
  }

  const hasDirectProjets = directProjets.length > 0

  return (
    <WorkspaceShell>
      <div className="min-h-full">
        <div className="border-b border-border bg-white px-8 pt-6 pb-5">
          <div className="flex items-end justify-between">
            <div>
              <p className="text-[11px] font-bold uppercase tracking-[0.08em] text-primary">Entreprise</p>
              <h1 className="mt-1 text-2xl font-black uppercase tracking-tight">{entreprise?.name ?? "…"}</h1>
              <p className="mt-0.5 text-sm text-muted-foreground">
                {secteurs.length} secteur{secteurs.length !== 1 ? "s" : ""}
                {hasDirectProjets ? ` · ${directProjets.length} projet${directProjets.length !== 1 ? "s" : ""} direct${directProjets.length !== 1 ? "s" : ""}` : ""}
              </p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => open({ type: "create-projet" })}
                className="flex items-center gap-2 rounded-lg border border-border bg-white px-4 py-2.5 text-sm font-semibold text-foreground hover:bg-gray-50 transition-colors"
              >
                <Plus className="h-4 w-4" /> Projet direct
              </button>
              <button
                onClick={() => open({ type: "create-secteur" })}
                className="flex items-center gap-2 rounded-lg bg-primary px-5 py-2.5 text-sm font-semibold text-white hover:bg-primary/90 transition-colors shadow-sm"
              >
                <Plus className="h-4 w-4" /> Nouveau secteur
              </button>
            </div>
          </div>
        </div>

        <div className="p-8 space-y-10">
          {loading ? (
            <div className="flex h-64 items-center justify-center">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : (
            <>
              {/* Secteurs */}
              <section>
                {(secteurs.length > 0 || hasDirectProjets) && (
                  <h2 className="mb-4 text-[11px] font-bold uppercase tracking-widest text-muted-foreground">
                    Secteurs
                  </h2>
                )}
                <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                  {secteurs.map(sec => (
                    <PhotoCard
                      key={sec.id}
                      href={`/secteur/${sec.id}`}
                      name={sec.name}
                      createdAt={sec.created_at}
                      image={sec.background_url || SECTEUR_IMAGE}
                      metric1Label="Projets"
                      metric1Value={sec.projetCount}
                      metric2Label="Quality"
                      metric2Value="0%"
                      onRename={e => { e.preventDefault(); open({ type: "rename-secteur", id: sec.id, name: sec.name }, sec.name) }}
                      onDelete={e => { e.preventDefault(); open({ type: "delete-secteur", id: sec.id, name: sec.name }) }}
                    />
                  ))}
                  <CreateCard label="Nouveau secteur" onClick={() => open({ type: "create-secteur" })} />
                </div>
              </section>

              {/* Projets directs */}
              {hasDirectProjets && (
                <section>
                  <h2 className="mb-4 text-[11px] font-bold uppercase tracking-widest text-muted-foreground">
                    Projets directs
                  </h2>
                  <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                    {directProjets.map(proj => (
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
                        onRename={e => { e.preventDefault(); open({ type: "rename-projet", id: proj.id, name: proj.name }, proj.name) }}
                        onDelete={e => { e.preventDefault(); open({ type: "delete-projet", id: proj.id, name: proj.name }) }}
                      />
                    ))}
                    <CreateCard label="Projet direct" onClick={() => open({ type: "create-projet" })} />
                  </div>
                </section>
              )}
            </>
          )}
        </div>
      </div>

      {/* Modals */}
      {(modal?.type === "create-secteur") && (
        <ModalWrapper onClose={closeModal}>
          <ModalHeader title="Nouveau secteur" onClose={closeModal} />
          <div className="p-6 space-y-4">
            <Field label="Nom du secteur">
              <Input placeholder="Ex: Aéroport CDG" value={inputName} onChange={e => setInputName(e.target.value)}
                onKeyDown={e => e.key === "Enter" && handleCreateSecteur()} autoFocus className="rounded-lg" />
            </Field>
            <Field label="Image de fond (optionnel)">
              <Input placeholder="https://images.unsplash.com/..." value={inputUrl} onChange={e => setInputUrl(e.target.value)} className="rounded-lg" />
            </Field>
            <Button className="w-full rounded-lg bg-primary hover:bg-primary/90 text-white font-semibold py-2.5"
              onClick={handleCreateSecteur} disabled={saving || !inputName.trim()}>
              {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />} Créer le secteur
            </Button>
          </div>
        </ModalWrapper>
      )}

      {modal?.type === "create-projet" && (
        <ModalWrapper onClose={closeModal}>
          <ModalHeader title="Nouveau projet direct" onClose={closeModal} />
          <div className="p-6 space-y-4">
            <Field label="Nom du projet">
              <Input placeholder="Ex: Plan été 2026" value={inputName} onChange={e => setInputName(e.target.value)}
                onKeyDown={e => e.key === "Enter" && handleCreateProjet()} autoFocus className="rounded-lg" />
            </Field>
            <Field label="Code projet (optionnel)">
              <Input placeholder="Ex: HP-2026" value={inputCode} onChange={e => setInputCode(e.target.value)} className="rounded-lg" />
            </Field>
            <Field label="Image de fond (optionnel)">
              <Input placeholder="https://images.unsplash.com/..." value={inputUrl} onChange={e => setInputUrl(e.target.value)} className="rounded-lg" />
            </Field>
            <Button className="w-full rounded-lg bg-primary hover:bg-primary/90 text-white font-semibold py-2.5"
              onClick={handleCreateProjet} disabled={saving || !inputName.trim()}>
              {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />} Créer le projet
            </Button>
          </div>
        </ModalWrapper>
      )}

      {modal?.type === "rename-secteur" && (
        <ModalWrapper onClose={closeModal}>
          <ModalHeader title={`Renommer « ${modal.name} »`} onClose={closeModal} />
          <div className="p-6 space-y-4">
            <Input value={inputName} onChange={e => setInputName(e.target.value)}
              onKeyDown={e => e.key === "Enter" && handleRenameSecteur()} autoFocus className="rounded-lg" />
            <Button className="w-full rounded-lg bg-primary hover:bg-primary/90 text-white font-semibold py-2.5"
              onClick={handleRenameSecteur} disabled={saving || !inputName.trim()}>
              {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />} Renommer
            </Button>
          </div>
        </ModalWrapper>
      )}

      {modal?.type === "rename-projet" && (
        <ModalWrapper onClose={closeModal}>
          <ModalHeader title={`Renommer « ${modal.name} »`} onClose={closeModal} />
          <div className="p-6 space-y-4">
            <Input value={inputName} onChange={e => setInputName(e.target.value)}
              onKeyDown={e => e.key === "Enter" && handleRenameProjet()} autoFocus className="rounded-lg" />
            <Button className="w-full rounded-lg bg-primary hover:bg-primary/90 text-white font-semibold py-2.5"
              onClick={handleRenameProjet} disabled={saving || !inputName.trim()}>
              {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />} Renommer
            </Button>
          </div>
        </ModalWrapper>
      )}

      {(modal?.type === "delete-secteur" || modal?.type === "delete-projet") && (
        <ModalWrapper onClose={closeModal}>
          <ModalHeader title={`Supprimer « ${modal.name} » ?`} onClose={closeModal} color="bg-destructive" />
          <div className="p-6 space-y-4">
            <p className="text-sm text-muted-foreground">Cette action est irréversible.</p>
            <div className="flex gap-3">
              <Button variant="outline" className="flex-1 rounded-lg" onClick={closeModal}>Annuler</Button>
              <Button variant="destructive" className="flex-1 rounded-lg"
                onClick={modal.type === "delete-secteur" ? handleDeleteSecteur : handleDeleteProjet} disabled={saving}>
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
