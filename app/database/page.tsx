"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import {
  FileSpreadsheet,
  FolderOpen,
  FolderPlus,
  HardDrive,
  Inbox,
  MoreVertical,
  Trash2,
  FolderInput,
  X,
} from "lucide-react"

import { AppShell } from "@/components/app-shell"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { supabase, type Folder, type SupabaseJob } from "@/lib/supabase"
import { deleteJob } from "@/lib/api"
import { useI18n } from "@/lib/i18n"

function formatStorage(bytes?: number): string {
  if (!bytes || bytes === 0) return "—"
  if (bytes < 1024) return `${bytes} o`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} Ko`
  return `${(bytes / (1024 * 1024)).toFixed(1)} Mo`
}

function formatDate(iso?: string | null, lang = "fr"): string {
  if (!iso) return ""
  try {
    return new Date(iso).toLocaleDateString(
      lang === "ar" ? "ar-SA" : lang === "en" ? "en-GB" : "fr-FR",
      { day: "numeric", month: "long", year: "numeric" }
    )
  } catch {
    return iso
  }
}

export default function DatabasePage() {
  const { t, lang } = useI18n()
  const [jobs, setJobs] = useState<SupabaseJob[]>([])
  const [folders, setFolders] = useState<Folder[]>([])
  const [selectedFolderId, setSelectedFolderId] = useState<string | null>(null)

  // New folder dialog
  const [showNewFolder, setShowNewFolder] = useState(false)
  const [newFolderName, setNewFolderName] = useState("")
  const [savingFolder, setSavingFolder] = useState(false)

  // Delete job dialog
  const [jobToDelete, setJobToDelete] = useState<SupabaseJob | null>(null)
  const [deleting, setDeleting] = useState(false)

  // Move to folder dialog
  const [jobToMove, setJobToMove] = useState<SupabaseJob | null>(null)

  // Delete folder dialog
  const [folderToDelete, setFolderToDelete] = useState<Folder | null>(null)

  useEffect(() => {
    loadFolders()
    loadJobs()
  }, [])

  async function loadFolders() {
    const { data } = await supabase
      .from("folders")
      .select("id, name, created_at")
      .order("created_at", { ascending: true })
    if (data) setFolders(data as Folder[])
  }

  async function loadJobs() {
    const { data } = await supabase
      .from("jobs")
      .select("job_id, scenario_name, status, created_at, finished_at, kpis, storage_size_bytes, folder_id")
      .eq("status", "done")
      .order("created_at", { ascending: false })
    if (data) setJobs(data as SupabaseJob[])
  }

  async function handleCreateFolder() {
    const name = newFolderName.trim()
    if (!name) return
    setSavingFolder(true)
    const { data } = await supabase
      .from("folders")
      .insert({ name })
      .select("id, name, created_at")
      .single()
    if (data) setFolders((prev) => [...prev, data as Folder])
    setNewFolderName("")
    setShowNewFolder(false)
    setSavingFolder(false)
  }

  async function handleDeleteFolder() {
    if (!folderToDelete) return
    await supabase.from("jobs").update({ folder_id: null }).eq("folder_id", folderToDelete.id)
    await supabase.from("folders").delete().eq("id", folderToDelete.id)
    setFolders((prev) => prev.filter((f) => f.id !== folderToDelete.id))
    setJobs((prev) =>
      prev.map((j) => (j.folder_id === folderToDelete.id ? { ...j, folder_id: null } : j))
    )
    if (selectedFolderId === folderToDelete.id) setSelectedFolderId(null)
    setFolderToDelete(null)
  }

  async function handleDeleteJob() {
    if (!jobToDelete) return
    setDeleting(true)
    try {
      await deleteJob(jobToDelete.job_id)
      setJobs((prev) => prev.filter((j) => j.job_id !== jobToDelete.job_id))
    } catch {
      await supabase.from("jobs").delete().eq("job_id", jobToDelete.job_id)
      setJobs((prev) => prev.filter((j) => j.job_id !== jobToDelete.job_id))
    }
    setJobToDelete(null)
    setDeleting(false)
  }

  async function handleMoveToFolder(folderId: string | null) {
    if (!jobToMove) return
    await supabase.from("jobs").update({ folder_id: folderId }).eq("job_id", jobToMove.job_id)
    setJobs((prev) =>
      prev.map((j) => (j.job_id === jobToMove.job_id ? { ...j, folder_id: folderId } : j))
    )
    setJobToMove(null)
  }

  const unfiledCount = jobs.filter((j) => !j.folder_id).length

  const displayedJobs =
    selectedFolderId === null
      ? jobs
      : selectedFolderId === "__unfiled__"
      ? jobs.filter((j) => !j.folder_id)
      : jobs.filter((j) => j.folder_id === selectedFolderId)

  function jobDisplayName(job: SupabaseJob) {
    return job.scenario_name || job.job_id.slice(0, 8) + "…"
  }

  return (
    <AppShell>
      <div className="container mx-auto max-w-6xl px-4 py-8">
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">{t.db.title}</h1>
            <p className="text-sm text-muted-foreground">
              {jobs.length} {t.common.scenariosLabel}
            </p>
          </div>
          <Button onClick={() => setShowNewFolder(true)} className="gap-2">
            <FolderPlus className="h-4 w-4" />
            {t.db.newFolder}
          </Button>
        </div>

        <div className="flex gap-6">
          {/* Folders sidebar */}
          <div className="w-56 shrink-0 space-y-1">
            <button
              onClick={() => setSelectedFolderId(null)}
              className={`flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors ${
                selectedFolderId === null
                  ? "bg-accent text-accent-foreground font-medium"
                  : "hover:bg-accent/50 text-muted-foreground"
              }`}
            >
              <Inbox className="h-4 w-4 shrink-0" />
              <span className="flex-1 text-left">{t.db.allScenarios}</span>
              <span className="text-xs">{jobs.length}</span>
            </button>

            {folders.length > 0 && (
              <div className="pt-2">
                <p className="mb-1 px-3 text-xs font-medium text-muted-foreground uppercase tracking-wide">
                  {t.db.foldersLabel}
                </p>
                {folders.map((folder) => {
                  const count = jobs.filter((j) => j.folder_id === folder.id).length
                  return (
                    <div key={folder.id} className="group flex items-center">
                      <button
                        onClick={() => setSelectedFolderId(folder.id)}
                        className={`flex flex-1 items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors ${
                          selectedFolderId === folder.id
                            ? "bg-accent text-accent-foreground font-medium"
                            : "hover:bg-accent/50 text-muted-foreground"
                        }`}
                      >
                        <FolderOpen className="h-4 w-4 shrink-0" />
                        <span className="flex-1 text-left truncate">{folder.name}</span>
                        <span className="text-xs">{count}</span>
                      </button>
                      <button
                        onClick={() => setFolderToDelete(folder)}
                        className="mr-1 hidden rounded p-1 text-muted-foreground hover:text-destructive group-hover:flex"
                      >
                        <X className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  )
                })}
              </div>
            )}

            {unfiledCount > 0 && (
              <button
                onClick={() => setSelectedFolderId("__unfiled__")}
                className={`flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors ${
                  selectedFolderId === "__unfiled__"
                    ? "bg-accent text-accent-foreground font-medium"
                    : "hover:bg-accent/50 text-muted-foreground"
                }`}
              >
                <FileSpreadsheet className="h-4 w-4 shrink-0" />
                <span className="flex-1 text-left">{t.db.unfiled}</span>
                <span className="text-xs">{unfiledCount}</span>
              </button>
            )}
          </div>

          {/* Jobs list */}
          <Card className="flex-1">
            <CardHeader className="pb-3">
              <CardTitle className="text-base">
                {selectedFolderId === null
                  ? t.db.allScenarios
                  : selectedFolderId === "__unfiled__"
                  ? t.db.unfiled
                  : folders.find((f) => f.id === selectedFolderId)?.name ?? ""}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {displayedJobs.length === 0 && (
                  <p className="py-8 text-center text-sm text-muted-foreground">
                    {t.db.noScenarios}
                  </p>
                )}
                {displayedJobs.map((job) => (
                  <div
                    key={job.job_id}
                    className="flex items-center justify-between rounded-lg border border-border/50 p-3 hover:bg-accent/30 transition-colors"
                  >
                    <Link
                      href={`/jobs/${job.job_id}`}
                      className="flex flex-1 items-center gap-3 min-w-0"
                    >
                      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-muted">
                        <FileSpreadsheet className="h-4 w-4 text-muted-foreground" />
                      </div>
                      <div className="min-w-0">
                        <p className="font-medium truncate">{jobDisplayName(job)}</p>
                        <p className="text-xs text-muted-foreground">
                          {formatDate(job.created_at, lang)}
                        </p>
                      </div>
                    </Link>

                    <div className="flex items-center gap-4 ml-4 shrink-0">
                      <div className="hidden sm:flex items-center gap-1 text-sm text-muted-foreground">
                        <HardDrive className="h-3.5 w-3.5" />
                        {formatStorage(job.storage_size_bytes)}
                      </div>
                      <div className="text-right hidden sm:block">
                        <p className="text-sm font-medium">
                          {job.kpis?.total_flights ?? 0} {t.common.flights}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {(job.kpis?.assigned_pct ?? 0).toFixed(1)}%
                        </p>
                      </div>
                      {job.folder_id && (
                        <span className="hidden md:inline-flex items-center gap-1 rounded-full bg-accent px-2 py-0.5 text-xs text-accent-foreground">
                          <FolderOpen className="h-3 w-3" />
                          {folders.find((f) => f.id === job.folder_id)?.name}
                        </span>
                      )}

                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="icon" className="h-8 w-8">
                            <MoreVertical className="h-4 w-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem
                            onClick={() => setJobToMove(job)}
                            className="gap-2"
                          >
                            <FolderInput className="h-4 w-4" />
                            {t.db.moveToFolder}
                          </DropdownMenuItem>
                          <DropdownMenuSeparator />
                          <DropdownMenuItem
                            onClick={() => setJobToDelete(job)}
                            className="gap-2 text-destructive focus:text-destructive"
                          >
                            <Trash2 className="h-4 w-4" />
                            {t.common.delete}
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* New folder dialog */}
      <Dialog open={showNewFolder} onOpenChange={setShowNewFolder}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>{t.db.newFolderTitle}</DialogTitle>
            <DialogDescription>{t.db.newFolderDesc}</DialogDescription>
          </DialogHeader>
          <div className="py-2">
            <Label htmlFor="folder-name" className="mb-2 block">
              {t.db.folderNameLabel}
            </Label>
            <Input
              id="folder-name"
              placeholder={t.db.folderNamePlaceholder}
              value={newFolderName}
              onChange={(e) => setNewFolderName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleCreateFolder()}
              autoFocus
            />
          </div>
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setShowNewFolder(false)}>
              {t.common.cancel}
            </Button>
            <Button
              onClick={handleCreateFolder}
              disabled={savingFolder || !newFolderName.trim()}
            >
              {t.db.createBtn}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete job confirmation dialog */}
      <Dialog open={!!jobToDelete} onOpenChange={(open) => !open && setJobToDelete(null)}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>{t.db.deleteJobTitle}</DialogTitle>
            <DialogDescription>
              {t.db.deleteJobDescPre}{" "}
              <span className="font-medium text-foreground">
                {jobToDelete ? jobDisplayName(jobToDelete) : ""}
              </span>{" "}
              {t.db.deleteJobDescPost}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setJobToDelete(null)}>
              {t.common.cancel}
            </Button>
            <Button
              variant="destructive"
              onClick={handleDeleteJob}
              disabled={deleting}
              className="gap-2"
            >
              <Trash2 className="h-4 w-4" />
              {deleting ? t.common.deleting : t.common.delete}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete folder confirmation */}
      <Dialog open={!!folderToDelete} onOpenChange={(open) => !open && setFolderToDelete(null)}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>{t.db.deleteFolderTitle}</DialogTitle>
            <DialogDescription>
              {t.db.deleteFolderDescPre}{" "}
              <span className="font-medium text-foreground">{folderToDelete?.name}</span>{" "}
              {t.db.deleteFolderDescMid}{" "}
              <span className="font-medium text-foreground">{t.db.unclassified}</span>
              {t.db.deleteFolderDescPost}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setFolderToDelete(null)}>
              {t.common.cancel}
            </Button>
            <Button variant="destructive" onClick={handleDeleteFolder} className="gap-2">
              <Trash2 className="h-4 w-4" />
              {t.common.delete}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Move to folder dialog */}
      <Dialog open={!!jobToMove} onOpenChange={(open) => !open && setJobToMove(null)}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>{t.db.moveDialogTitle}</DialogTitle>
            <DialogDescription>
              {t.db.moveDialogDescPre}{" "}
              <span className="font-medium text-foreground">
                {jobToMove ? jobDisplayName(jobToMove) : ""}
              </span>
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-1 py-2">
            <button
              onClick={() => handleMoveToFolder(null)}
              className={`flex w-full items-center gap-2 rounded-lg px-3 py-2.5 text-sm transition-colors hover:bg-accent/50 ${
                !jobToMove?.folder_id ? "bg-accent text-accent-foreground font-medium" : ""
              }`}
            >
              <Inbox className="h-4 w-4" />
              {t.db.unclassifiedOption}
            </button>
            {folders.map((folder) => (
              <button
                key={folder.id}
                onClick={() => handleMoveToFolder(folder.id)}
                className={`flex w-full items-center gap-2 rounded-lg px-3 py-2.5 text-sm transition-colors hover:bg-accent/50 ${
                  jobToMove?.folder_id === folder.id
                    ? "bg-accent text-accent-foreground font-medium"
                    : ""
                }`}
              >
                <FolderOpen className="h-4 w-4" />
                {folder.name}
              </button>
            ))}
            {folders.length === 0 && (
              <p className="py-2 text-center text-xs text-muted-foreground">
                {t.db.noFolders}
              </p>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setJobToMove(null)}>
              {t.common.close}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </AppShell>
  )
}
