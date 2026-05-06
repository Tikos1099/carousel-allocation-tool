"use client"

import { useState } from "react"
import {
  AlertCircle, ArrowRight, BookOpen, CheckCircle, ChevronRight,
  Code, Database, Download, Eye, EyeOff, FileSpreadsheet, FileText,
  Filter, FolderOpen, GitMerge, HelpCircle, Info,
  Layers, Link2, Plane, Play, Plus, Save, Trash2, Upload,
  Zap,
} from "lucide-react"
import Link from "next/link"

import { AppShell } from "@/components/app-shell"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"

// ─── Helpers ─────────────────────────────────────────────────────────────────

function SectionAnchor({ id }: { id: string }) {
  return <span id={id} className="-mt-20 pt-20 block" aria-hidden />
}

function Step({ n, title, children }: { n: number; title: string; children: React.ReactNode }) {
  return (
    <div className="flex gap-4">
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground text-sm font-bold mt-0.5">
        {n}
      </div>
      <div className="flex-1 pb-6 border-l border-dashed border-muted-foreground/20 pl-4 ml-[-20px]">
        <p className="font-semibold text-sm mb-1.5">{title}</p>
        <div className="text-sm text-muted-foreground space-y-1">{children}</div>
      </div>
    </div>
  )
}

function Callout({ icon: Icon, color, title, children }: {
  icon: React.ElementType; color: string; title: string; children: React.ReactNode
}) {
  return (
    <div className={`flex gap-3 p-3.5 rounded-lg border ${color}`}>
      <Icon className="h-4 w-4 mt-0.5 shrink-0" />
      <div className="text-sm space-y-0.5">
        <p className="font-medium">{title}</p>
        <div className="text-muted-foreground">{children}</div>
      </div>
    </div>
  )
}

function FormulaRow({ formula, result }: { formula: string; result: string }) {
  return (
    <div className="flex items-center gap-3 py-1.5 border-b last:border-0">
      <code className="text-xs bg-muted px-2 py-1 rounded font-mono w-56 shrink-0">{formula}</code>
      <ArrowRight className="h-3 w-3 text-muted-foreground shrink-0" />
      <span className="text-xs text-muted-foreground">{result}</span>
    </div>
  )
}

// ─── TOC items ────────────────────────────────────────────────────────────────

const TOC = [
  { id: "overview", label: "Vue d'ensemble" },
  { id: "allocation", label: "Outil Allocation Make-Up" },
  { id: "mapping", label: "Mapping Tool" },
  { id: "mapping-source", label: "  → Fichier source" },
  { id: "mapping-joins", label: "  → Fichiers secondaires (JOIN)" },
  { id: "mapping-filters", label: "  → Filtres ET / OU" },
  { id: "mapping-target", label: "  → Schéma cible" },
  { id: "mapping-table", label: "  → Tableau de mapping" },
  { id: "mapping-formulas", label: "  → Formules — références" },
  { id: "mapping-text", label: "  → Fonctions texte" },
  { id: "mapping-arithmetic", label: "  → Arithmétique + - * /" },
  { id: "mapping-numbers", label: "  → Fonctions numériques" },
  { id: "mapping-dates", label: "  → Dates & heures" },
  { id: "mapping-if", label: "  → IF / AND / OR / NOT" },
  { id: "mapping-row", label: "  → Séquences ROW()" },
  { id: "mapping-advanced", label: "  → Fonctions avancées" },
  { id: "mapping-excel", label: "  → LET · IFS · MATCH · VLOOKUP…" },
  { id: "mapping-nested", label: "  → Formules imbriquées" },
  { id: "mapping-crosscol", label: "  → Colonnes intermédiaires" },
  { id: "mapping-dedup", label: "  → Dédupliquer par PK" },
  { id: "mapping-configs", label: "  → Configurations" },
  { id: "mapping-export", label: "  → Export" },
]

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function HelpPage() {
  const [activeSection, setActiveSection] = useState("overview")

  return (
    <AppShell>
      <div className="mx-auto max-w-6xl px-6 py-8">

        {/* Page header */}
        <div className="mb-8">
          <div className="flex items-center gap-2 text-sm text-muted-foreground mb-2">
            <span>Accueil</span>
            <ChevronRight className="h-3.5 w-3.5" />
            <span className="text-foreground font-medium">Guide d&apos;utilisation</span>
          </div>
          <h1 className="text-3xl font-bold flex items-center gap-3">
            <BookOpen className="h-7 w-7 text-primary" />
            Guide d&apos;utilisation
          </h1>
          <p className="mt-2 text-muted-foreground">
            Tout ce que vous devez savoir pour utiliser l&apos;application MakeUp.
          </p>
        </div>

        <div className="flex gap-8">

          {/* ── Sidebar TOC ── */}
          <aside className="hidden lg:block w-52 shrink-0">
            <div className="sticky top-24 space-y-1">
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-3 px-2">
                Sur cette page
              </p>
              {TOC.map(item => (
                <a
                  key={item.id}
                  href={`#${item.id}`}
                  onClick={() => setActiveSection(item.id)}
                  className={`block text-xs px-2 py-1.5 rounded-md transition-colors hover:bg-muted
                    ${item.label.startsWith("  →") ? "pl-5 text-muted-foreground" : "font-medium"}
                    ${activeSection === item.id ? "bg-accent text-accent-foreground" : ""}`}
                >
                  {item.label.replace("  → ", "")}
                </a>
              ))}
            </div>
          </aside>

          {/* ── Main content ── */}
          <main className="flex-1 min-w-0 space-y-12">

            {/* ════ Overview ════ */}
            <section>
              <SectionAnchor id="overview" />
              <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
                <Layers className="h-5 w-5 text-primary" />
                Vue d&apos;ensemble
              </h2>
              <p className="text-sm text-muted-foreground mb-5">
                L&apos;application <strong>MakeUp</strong> est composée de deux outils indépendants accessibles depuis la page d&apos;accueil.
              </p>
              <div className="grid grid-cols-2 gap-4">
                <Card className="border-primary/20">
                  <CardHeader className="pb-2 pt-4 px-4">
                    <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary text-primary-foreground mb-2">
                      <Plane className="h-4 w-4" />
                    </div>
                    <CardTitle className="text-base">Allocation Make-Up</CardTitle>
                  </CardHeader>
                  <CardContent className="px-4 pb-4">
                    <p className="text-xs text-muted-foreground">
                      Optimise l&apos;allocation des positions carousel pour vos vols. Importez vos données, configurez les règles, et générez le planning complet.
                    </p>
                    <Badge variant="secondary" className="mt-2 text-xs">Outil principal</Badge>
                  </CardContent>
                </Card>
                <Card className="border-primary/20">
                  <CardHeader className="pb-2 pt-4 px-4">
                    <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-accent mb-2">
                      <GitMerge className="h-4 w-4 text-accent-foreground" />
                    </div>
                    <CardTitle className="text-base">Mapping Tool</CardTitle>
                  </CardHeader>
                  <CardContent className="px-4 pb-4">
                    <p className="text-xs text-muted-foreground">
                      Transforme et remapped des fichiers Excel/CSV. Permet de définir des formules de transformation colonne par colonne.
                    </p>
                    <Badge variant="outline" className="mt-2 text-xs">Utilitaire</Badge>
                  </CardContent>
                </Card>
              </div>
            </section>

            <Separator />

            {/* ════ Allocation Tool ════ */}
            <section>
              <SectionAnchor id="allocation" />
              <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
                <Plane className="h-5 w-5 text-primary" />
                Outil Allocation Make-Up
              </h2>
              <p className="text-sm text-muted-foreground mb-6">
                Cet outil suit un assistant en étapes (wizard). Cliquez sur <strong>Allocation Make-Up</strong> depuis l&apos;accueil, donnez un nom au scénario, et suivez les étapes.
              </p>

              <div className="space-y-0">
                <Step n={1} title="Upload — Chargez votre fichier de vols">
                  <p>Importez un fichier Excel (.xlsx) ou CSV contenant la liste des vols à allouer.</p>
                  <p className="mt-1">Le fichier doit contenir au minimum : un identifiant de vol, un terminal, un horaire d&apos;arrivée.</p>
                </Step>
                <Step n={2} title="Mapping des colonnes">
                  <p>Associez chaque colonne de votre fichier à un champ attendu par le moteur d&apos;allocation (ex : <em>Flight Number</em>, <em>Terminal</em>, <em>STD</em>…).</p>
                </Step>
                <Step n={3} title="Carousels — Configurez les tapis">
                  <p>Définissez la liste des tapis disponibles, leur terminal, et leur capacité en termes de vols simultanés.</p>
                </Step>
                <Step n={4} title="Règles Make-Up — Règles d'allocation">
                  <p>Configurez les règles de priorité, les fenêtres temporelles, et les contraintes de capacité par carousel.</p>
                </Step>
                <Step n={5} title="Exécution — Lancez l'allocation">
                  <p>Cliquez sur <strong>Lancer l&apos;allocation</strong>. Le moteur Python traite tous les vols et génère le planning.</p>
                  <p className="mt-1">Le traitement prend généralement quelques secondes même pour des fichiers de 90 000 lignes.</p>
                </Step>
                <Step n={6} title="Résultats — Analysez et exportez">
                  <p>Consultez le récapitulatif : taux d&apos;allocation, vols non assignés, timeline par carousel.</p>
                  <p className="mt-1">Téléchargez les résultats en Excel depuis la page Résultats.</p>
                </Step>
              </div>

              <div className="mt-2 flex gap-2">
                <Button size="sm" variant="outline" asChild>
                  <Link href="/results">
                    <Layers className="h-3.5 w-3.5 mr-1.5" />
                    Voir les résultats
                  </Link>
                </Button>
                <Button size="sm" variant="outline" asChild>
                  <Link href="/analytics">
                    <Zap className="h-3.5 w-3.5 mr-1.5" />
                    Analytics
                  </Link>
                </Button>
              </div>
            </section>

            <Separator />

            {/* ════ Mapping Tool ════ */}
            <section>
              <SectionAnchor id="mapping" />
              <h2 className="text-xl font-bold mb-2 flex items-center gap-2">
                <GitMerge className="h-5 w-5 text-primary" />
                Mapping Tool
              </h2>
              <p className="text-sm text-muted-foreground mb-6">
                Cet outil lit un fichier source, applique des transformations colonne par colonne, et génère un nouveau fichier. Il est idéal pour préparer des données avant de les utiliser dans l&apos;outil d&apos;allocation.
              </p>

              <Callout icon={Info} color="bg-blue-50 border-blue-200 dark:bg-blue-950/20 dark:border-blue-800 text-blue-800 dark:text-blue-300"
                title="Traitement côté serveur">
                Le mapping est exécuté côté Python (backend Railway). Les fichiers de 90 000 lignes sont traités en moins d&apos;une seconde avec pandas.
              </Callout>

              {/* Source */}
              <div className="mt-8">
                <SectionAnchor id="mapping-source" />
                <h3 className="font-semibold text-base mb-3 flex items-center gap-2">
                  <div className="flex h-5 w-5 items-center justify-center rounded-full bg-primary text-primary-foreground text-xs font-bold">1</div>
                  Fichier source
                </h3>
                <p className="text-sm text-muted-foreground mb-3">
                  Le fichier source est le fichier que vous voulez <strong>transformer</strong>. Il peut être au format Excel (.xlsx, .xls) ou CSV.
                </p>
                <div className="grid grid-cols-2 gap-3">
                  <div className="flex items-start gap-2 p-3 rounded-lg bg-muted/50 text-sm">
                    <Upload className="h-4 w-4 text-primary shrink-0 mt-0.5" />
                    <div>
                      <p className="font-medium text-xs">Glisser-déposer</p>
                      <p className="text-xs text-muted-foreground mt-0.5">Faites glisser votre fichier dans la zone ou cliquez pour parcourir.</p>
                    </div>
                  </div>
                  <div className="flex items-start gap-2 p-3 rounded-lg bg-muted/50 text-sm">
                    <FileSpreadsheet className="h-4 w-4 text-primary shrink-0 mt-0.5" />
                    <div>
                      <p className="font-medium text-xs">Détection automatique</p>
                      <p className="text-xs text-muted-foreground mt-0.5">Les colonnes et le nombre de lignes sont détectés et affichés immédiatement.</p>
                    </div>
                  </div>
                </div>
              </div>

              {/* Secondary files / Joins */}
              <div className="mt-8">
                <SectionAnchor id="mapping-joins" />
                <h3 className="font-semibold text-base mb-3 flex items-center gap-2">
                  <Link2 className="h-4 w-4 text-muted-foreground" />
                  Fichiers secondaires — JOIN
                </h3>
                <p className="text-sm text-muted-foreground mb-4">
                  Vous pouvez enrichir votre fichier principal avec des données venant d&apos;un ou plusieurs autres fichiers, comme un <strong>VLOOKUP</strong> ou un <strong>LEFT JOIN SQL</strong>.
                  Les colonnes du fichier secondaire deviennent accessibles dans toutes vos formules.
                </p>

                <div className="space-y-4">
                  <div className="grid grid-cols-3 gap-3">
                    <div className="p-3 rounded-lg border bg-card">
                      <p className="text-xs font-semibold mb-1">Alias</p>
                      <p className="text-xs text-muted-foreground">Nom court sans espace donné au fichier secondaire (ex : <code className="bg-muted px-1 rounded">schedule</code>, <code className="bg-muted px-1 rounded">ref1</code>). Utilisé pour préfixer ses colonnes.</p>
                    </div>
                    <div className="p-3 rounded-lg border bg-card">
                      <p className="text-xs font-semibold mb-1">Clé principale</p>
                      <p className="text-xs text-muted-foreground">La colonne du <strong>fichier principal</strong> servant de clé de jointure (ex : <code className="bg-muted px-1 rounded">DepFlightId</code>).</p>
                    </div>
                    <div className="p-3 rounded-lg border bg-card">
                      <p className="text-xs font-semibold mb-1">Clé secondaire</p>
                      <p className="text-xs text-muted-foreground">La colonne correspondante dans le <strong>fichier secondaire</strong> (ex : <code className="bg-muted px-1 rounded">FlightId</code>).</p>
                    </div>
                  </div>

                  <div>
                    <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">Accéder aux colonnes dans les formules</p>
                    <p className="text-sm text-muted-foreground mb-2">
                      Après configuration, toutes les colonnes du fichier secondaire sont disponibles sous la forme <code className="bg-muted px-1.5 py-0.5 rounded text-xs font-mono">alias.NomColonne</code> dans le dropdown Source et dans les formules.
                    </p>
                    <div className="rounded-lg border overflow-hidden">
                      <FormulaRow formula="=schedule.ArrTime" result="Copie la colonne ArrTime du fichier « schedule »" />
                      <FormulaRow formula={'=IF(schedule.ArrTime <> "", schedule.ArrTime, "N/A")'} result="ArrTime si dispo, sinon N/A" />
                      <FormulaRow formula="=ref1.Gate & &quot;-&quot; & Terminal" result="Concaténation colonne secondaire + principale" />
                      <FormulaRow formula={'=IF(ref1.Status = "OK", GateSecondary, GatePrimary)'} result="Condition croisant les deux sources" />
                    </div>
                  </div>

                  <Callout icon={Info} color="bg-blue-50 border-blue-200 dark:bg-blue-950/20 dark:border-blue-800 text-blue-800 dark:text-blue-300"
                    title="Comportement JOIN">
                    C&apos;est un <strong>LEFT JOIN</strong> : toutes les lignes du fichier principal sont conservées.
                    Si aucune ligne correspondante n&apos;est trouvée dans le secondaire, les colonnes <code className="bg-blue-100 dark:bg-blue-900 px-1 rounded text-xs">alias.Col</code> seront vides pour cette ligne.
                  </Callout>

                  <Callout icon={Save} color="bg-muted/60 border-border"
                    title="Sauvegarde des jointures">
                    La configuration de chaque jointure (alias, clés) est sauvegardée avec la configuration.
                    Les <strong>fichiers eux-mêmes ne sont pas stockés</strong> — vous devrez les re-uploader après chargement d&apos;une config.
                    Les champs alias et clés seront déjà pré-remplis.
                  </Callout>
                </div>
              </div>

              {/* Filters ET/OU */}
              <div className="mt-8">
                <SectionAnchor id="mapping-filters" />
                <h3 className="font-semibold text-base mb-3 flex items-center gap-2">
                  <Filter className="h-4 w-4 text-muted-foreground" />
                  Filtres ET / OU
                </h3>
                <p className="text-sm text-muted-foreground mb-4">
                  Il y a deux niveaux de filtres dans le mapping tool, appliqués à des moments différents du pipeline :
                </p>

                <div className="grid grid-cols-2 gap-3 mb-5">
                  <div className="p-3 rounded-lg border bg-card">
                    <div className="flex items-center gap-1.5 text-xs font-semibold mb-1">Filtres de lignes <Badge variant="secondary" className="text-[10px]">Source</Badge></div>
                    <p className="text-xs text-muted-foreground">Appliqués <strong>avant</strong> le mapping, sur les colonnes du fichier source. Permettent de n&apos;importer qu&apos;un sous-ensemble de lignes.</p>
                  </div>
                  <div className="p-3 rounded-lg border bg-card">
                    <div className="flex items-center gap-1.5 text-xs font-semibold mb-1">Filtres output <Badge variant="secondary" className="text-[10px]">Calculé</Badge></div>
                    <p className="text-xs text-muted-foreground">Appliqués <strong>après</strong> le mapping et la déduplication, sur les colonnes calculées. Permettent d&apos;exclure certaines lignes du fichier final.</p>
                  </div>
                </div>

                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-3">Logique ET / OU — groupes de conditions</p>
                <p className="text-sm text-muted-foreground mb-3">
                  Les filtres sont organisés en <strong>groupes</strong>. La logique fonctionne sur deux niveaux :
                </p>
                <div className="rounded-lg border bg-card p-4 mb-4 space-y-2 text-sm">
                  <div className="flex items-center gap-2">
                    <div className="px-2 py-0.5 rounded bg-blue-100 text-blue-700 text-[10px] font-bold uppercase tracking-widest">ET</div>
                    <span className="text-muted-foreground">Les règles <strong>à l&apos;intérieur d&apos;un groupe</strong> se combinent avec ET (toutes doivent être vraies)</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="px-2 py-0.5 rounded bg-orange-100 text-orange-700 text-[10px] font-bold uppercase tracking-widest">OU</div>
                    <span className="text-muted-foreground">En cliquant sur le badge ET, il devient OU (au moins une doit être vraie)</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="h-px flex-1 bg-border max-w-8" /><span className="text-[10px] font-bold text-muted-foreground tracking-widest">ET</span><div className="h-px flex-1 bg-border max-w-8" />
                    <span className="text-muted-foreground">Les <strong>groupes entre eux</strong> sont toujours combinés par ET</span>
                  </div>
                </div>

                <div>
                  <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">Exemple concret</p>
                  <div className="rounded-lg border bg-muted/30 p-3 text-xs font-mono mb-3">
                    <span className="text-blue-700 font-bold">Groupe 1 (ET)</span> : InputType ≠ TERM<br />
                    <span className="font-bold text-muted-foreground text-[10px]">─────── ET ───────</span><br />
                    <span className="text-orange-700 font-bold">Groupe 2 (OU)</span> : ArrTerm contient T5C<br />
                    {"                  "}OU DepTerm contient T5C<br />
                    {"                  "}OU ArrTerm contient R5D
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Résultat : seules les lignes avec <code className="bg-muted px-1 rounded">InputType ≠ TERM</code> <strong>ET</strong> dont au moins un des terminaux correspond sont conservées.
                  </p>
                </div>

                <div className="mt-4">
                  <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">Opérateurs disponibles</p>
                  <div className="grid grid-cols-2 gap-1.5 text-xs">
                    {[
                      ["= égal à", "Valeur exacte (insensible à la casse)"],
                      ["≠ différent de", "Tout sauf cette valeur"],
                      ["> / < / ≥ / ≤", "Comparaison numérique"],
                      ["contient", "La cellule contient ce texte"],
                      ["ne contient pas", "La cellule ne contient pas ce texte"],
                      ["commence par / finit par", "Préfixe ou suffixe"],
                      ["est vide / n'est pas vide", "Détection de valeurs nulles ou vides"],
                    ].map(([op, desc]) => (
                      <div key={op} className="flex gap-2 p-2 rounded border bg-card">
                        <code className="font-mono text-[10px] text-primary shrink-0 w-32">{op}</code>
                        <span className="text-muted-foreground text-[10px]">{desc}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Target schema */}
              <div className="mt-8">
                <SectionAnchor id="mapping-target" />
                <h3 className="font-semibold text-base mb-3 flex items-center gap-2">
                  <div className="flex h-5 w-5 items-center justify-center rounded-full bg-primary text-primary-foreground text-xs font-bold">2</div>
                  Schéma cible
                </h3>
                <p className="text-sm text-muted-foreground mb-3">
                  Le schéma cible définit les <strong>colonnes du fichier de sortie</strong>. Deux façons de le définir :
                </p>
                <div className="grid grid-cols-2 gap-3">
                  <div className="p-3 rounded-lg border bg-card">
                    <div className="flex items-center gap-2 mb-2">
                      <Plus className="h-4 w-4 text-muted-foreground" />
                      <p className="text-xs font-semibold">Manuel</p>
                    </div>
                    <p className="text-xs text-muted-foreground">
                      Tapez le nom d&apos;une colonne cible et appuyez sur <kbd className="bg-muted px-1 rounded text-[10px]">Entrée</kbd> ou cliquez <strong>+</strong>. Répétez pour chaque colonne.
                    </p>
                  </div>
                  <div className="p-3 rounded-lg border bg-card">
                    <div className="flex items-center gap-2 mb-2">
                      <Upload className="h-4 w-4 text-muted-foreground" />
                      <p className="text-xs font-semibold">Depuis un fichier</p>
                    </div>
                    <p className="text-xs text-muted-foreground">
                      Importez un fichier Excel/CSV dont les <strong>en-têtes</strong> (première ligne) seront utilisés comme colonnes cibles. Pratique si vous avez déjà un modèle de sortie.
                    </p>
                  </div>
                </div>
              </div>

              {/* Mapping table */}
              <div className="mt-8">
                <SectionAnchor id="mapping-table" />
                <h3 className="font-semibold text-base mb-3 flex items-center gap-2">
                  <div className="flex h-5 w-5 items-center justify-center rounded-full bg-primary text-primary-foreground text-xs font-bold">3</div>
                  Tableau de mapping
                </h3>
                <p className="text-sm text-muted-foreground mb-4">
                  Chaque ligne du tableau correspond à une colonne cible. Vous configurez pour chacune :
                </p>
                <div className="overflow-x-auto rounded-lg border">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b bg-muted/50">
                        <th className="px-4 py-2.5 text-left font-semibold w-32">Champ</th>
                        <th className="px-4 py-2.5 text-left font-semibold">Description</th>
                        <th className="px-4 py-2.5 text-left font-semibold w-40">Exemple</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y">
                      <tr>
                        <td className="px-4 py-2.5 font-medium">Colonne cible</td>
                        <td className="px-4 py-2.5 text-muted-foreground">Le nom de la colonne dans le fichier de sortie. Modifiable.</td>
                        <td className="px-4 py-2.5"><code className="bg-muted px-1 rounded">Flight_ID</code></td>
                      </tr>
                      <tr>
                        <td className="px-4 py-2.5 font-medium">Source</td>
                        <td className="px-4 py-2.5 text-muted-foreground">La colonne du fichier source à lire. Optionnel si une formule constante est utilisée.</td>
                        <td className="px-4 py-2.5"><code className="bg-muted px-1 rounded">Flight Number</code></td>
                      </tr>
                      <tr>
                        <td className="px-4 py-2.5 font-medium">Formule</td>
                        <td className="px-4 py-2.5 text-muted-foreground">Transformation à appliquer. Se remplit automatiquement quand une source est sélectionnée. Voir la section Formules.</td>
                        <td className="px-4 py-2.5"><code className="bg-muted px-1 rounded">=LEFT(FlightNum,2)</code></td>
                      </tr>
                      <tr>
                        <td className="px-4 py-2.5 font-medium align-top">PK</td>
                        <td className="px-4 py-2.5 text-muted-foreground">Clé primaire. Cochez pour marquer cette colonne comme identifiant unique. Utilisé avec la dédupication.</td>
                        <td className="px-4 py-2.5">
                          <div className="flex items-center gap-1.5">
                            <CheckCircle className="h-3.5 w-3.5 text-primary" />
                            <span>une seule PK max</span>
                          </div>
                        </td>
                      </tr>
                      <tr>
                        <td className="px-4 py-2.5 font-medium">Agrégation</td>
                        <td className="px-4 py-2.5 text-muted-foreground">Méthode de regroupement si la déduplication est activée. Inactif sinon.</td>
                        <td className="px-4 py-2.5"><code className="bg-muted px-1 rounded">First / Sum / Concat</code></td>
                      </tr>
                      <tr>
                        <td className="px-4 py-2.5 font-medium">Format</td>
                        <td className="px-4 py-2.5 text-muted-foreground">Forçage du type dans le fichier Excel de sortie (Date, Number, Text…). Auto laisse pandas décider.</td>
                        <td className="px-4 py-2.5"><code className="bg-muted px-1 rounded">Date / Number</code></td>
                      </tr>
                      <tr>
                        <td className="px-4 py-2.5 font-medium align-top">Incl. (œil)</td>
                        <td className="px-4 py-2.5 text-muted-foreground">
                          Inclure la colonne dans le fichier de sortie. Par défaut activé (œil visible).
                          Si désactivé (œil barré), la colonne est <strong>calculée et disponible</strong> pour les autres formules et les filtres output, mais <strong>absente du fichier final</strong>. Utile pour créer une colonne intermédiaire de filtrage.
                        </td>
                        <td className="px-4 py-2.5">
                          <div className="flex items-center gap-1.5">
                            <Eye className="h-3.5 w-3.5 text-primary" />
                            <span>inclus / exclu</span>
                          </div>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>

                <Callout icon={Info} color="bg-muted/60 border-border mt-4" title="Auto-complétion de la formule">
                  Quand vous sélectionnez une colonne source dans le dropdown, la formule est pré-remplie avec <code className="bg-muted px-1 rounded text-xs">=NomColonne</code>. Vous pouvez ensuite la modifier manuellement si besoin.
                </Callout>
              </div>

              {/* Formulas — references */}
              <div className="mt-8">
                <SectionAnchor id="mapping-formulas" />
                <h3 className="font-semibold text-base mb-3 flex items-center gap-2">
                  <Code className="h-4 w-4 text-muted-foreground" />
                  Formules — références &amp; constantes
                </h3>
                <p className="text-sm text-muted-foreground mb-4">
                  Toute formule commence par <code className="bg-muted px-1.5 py-0.5 rounded text-xs">=</code>. Les noms de colonnes sont <strong>sensibles à la casse</strong>.
                </p>
                <div className="rounded-lg border overflow-hidden">
                  <FormulaRow formula="=Flight Number" result="Copie la valeur de la colonne « Flight Number »" />
                  <FormulaRow formula={'="FPD"'} result="Valeur constante texte « FPD » dans toutes les lignes" />
                  <FormulaRow formula="=42" result="Valeur numérique 42 dans toutes les lignes" />
                  <FormulaRow formula={'=ColA & "-" & ColB'} result={'Concaténation → « AF-123 »'} />
                  <FormulaRow formula={'=LEFT(FlightNum,2) & "_" & Terminal'} result={'Formule + colonne → « AF_T2 »'} />
                </div>
                <Callout icon={HelpCircle} color="bg-muted/60 border-border mt-4" title="Accès rapide">
                  Cliquez sur le bouton <strong>Formules ?</strong> en haut du tableau de mapping pour ouvrir la référence complète sur le côté.
                </Callout>
              </div>

              {/* Text functions */}
              <div className="mt-8">
                <SectionAnchor id="mapping-text" />
                <h3 className="font-semibold text-base mb-3 flex items-center gap-2">
                  <Code className="h-4 w-4 text-muted-foreground" />
                  Fonctions texte
                </h3>
                <div className="space-y-4">
                  <div>
                    <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">Extraction</p>
                    <div className="rounded-lg border overflow-hidden">
                      <FormulaRow formula="=LEFT(FlightNum, 2)" result="2 premiers caractères → « AF » depuis « AF123 »" />
                      <FormulaRow formula="=LEFT(FlightNum, LEN(FlightNum)-3)" result="Tout sauf les 3 derniers caractères — argument formule" />
                      <FormulaRow formula="=RIGHT(Route, 3)" result="3 derniers caractères → « CDG » depuis « ORLY-CDG »" />
                      <FormulaRow formula="=RIGHT(Code, LEN(Code)-2)" result="Tout sauf les 2 premiers — argument formule" />
                      <FormulaRow formula="=MID(Code, 2, 4)" result="Substring depuis position 2, longueur 4" />
                      <FormulaRow formula="=MID(Code, FIND(&quot;-&quot;, Code)+1, 3)" result="3 caractères après le tiret — start = formule" />
                      <FormulaRow formula="=LEN(Name)" result="Nombre de caractères" />
                    </div>
                  </div>
                  <div>
                    <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">Recherche de position — FIND / SEARCH</p>
                    <p className="text-xs text-muted-foreground mb-2">
                      Retourne la <strong>position 1-based</strong> du texte cherché, ou vide si absent. S&apos;utilise souvent avec <code className="bg-muted px-1 rounded">ISNUMBER</code> pour tester la présence.
                    </p>
                    <div className="rounded-lg border overflow-hidden">
                      <FormulaRow formula={'=FIND("+", Col)'} result={'Position du « + » dans Col → 3 depuis « AF+123 », vide si absent'} />
                      <FormulaRow formula={'=FIND("-", Col, 3)'} result={'Cherche « - » en partant du 3ᵉ caractère'} />
                      <FormulaRow formula={'=SEARCH("t5c", Col)'} result={'Idem FIND mais insensible à la casse → trouve « T5C » ou « t5c »'} />
                      <FormulaRow formula={'=ISNUMBER(FIND("+", Col))'} result={'TRUE si « + » est présent dans Col'} />
                      <FormulaRow formula={'=IF(ISNUMBER(FIND("+", Col)), TEXTBEFORE(Col, "+"), Col)'} result={'Texte avant « + » si présent, sinon la valeur brute'} />
                    </div>
                  </div>
                  <div>
                    <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">Découpage par délimiteur</p>
                    <div className="rounded-lg border overflow-hidden">
                      <FormulaRow formula={'=TEXTBEFORE(Route, "/")'} result={'Texte avant le séparateur → « ORLY » depuis « ORLY/CDG »'} />
                      <FormulaRow formula={'=TEXTBEFORE(Route, LEFT(SepCol, 1))'} result={'Délimiteur vient d\'une colonne — argument formule'} />
                      <FormulaRow formula={'=TEXTAFTER(Route, "-")'} result={'Texte après le séparateur → « CDG » depuis « ORLY-CDG »'} />
                    </div>
                  </div>
                  <div>
                    <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">Transformation & assemblage</p>
                    <div className="rounded-lg border overflow-hidden">
                      <FormulaRow formula="=UPPER(Terminal)" result="Majuscules → « T2 » depuis « t2 »" />
                      <FormulaRow formula="=LOWER(Status)" result="Minuscules → « done » depuis « DONE »" />
                      <FormulaRow formula="=TRIM(Name)" result="Supprime les espaces en début et fin" />
                      <FormulaRow formula={'=SUBSTITUTE(Code, "OLD", "NEW")'} result={'Remplace toutes les occurrences de « OLD » par « NEW »'} />
                      <FormulaRow formula={'=SUBSTITUTE(Code, LEFT(OldCol,3), RIGHT(NewCol,3))'} result={'Old et new viennent de formules — arguments formules'} />
                      <FormulaRow formula={'=CONCAT(ColA, "-", ColB)'} result={'Concaténation multi-colonnes (alias de &)'} />
                    </div>
                  </div>
                </div>
              </div>

              {/* Arithmetic */}
              <div className="mt-8">
                <SectionAnchor id="mapping-arithmetic" />
                <h3 className="font-semibold text-base mb-3 flex items-center gap-2">
                  <Code className="h-4 w-4 text-muted-foreground" />
                  Arithmétique + − × ÷
                </h3>
                <p className="text-sm text-muted-foreground mb-3">
                  Les opérations <code className="bg-muted px-1 rounded text-xs font-mono">+  -  *  /</code> fonctionnent entre colonnes et constantes, avec la priorité habituelle (<code className="bg-muted px-1 rounded text-xs">*</code> avant <code className="bg-muted px-1 rounded text-xs">+</code>). Utilisez des parenthèses pour forcer l&apos;ordre.
                </p>
                <div className="rounded-lg border overflow-hidden mb-3">
                  <FormulaRow formula="=Weight * 2" result="Multiplie la colonne Weight par 2" />
                  <FormulaRow formula="=TIMETOMIN(UnloadTime, UnloadDay)" result="Convertit heure + décalage jour en minutes totales (22:45 + jour 1 → 2805)" />
                  <FormulaRow formula="=HOUR(ArrTime) * 60 + MINUTE(ArrTime)" result="Heure → minutes depuis minuit" />
                  <FormulaRow formula="=TIMETOMIN(Time, Day)" result="Jour + temps → minutes totales (ex: jour=1, 22:45 → 2805)" />
                  <FormulaRow formula="=(ColA + ColB) / 2" result="Moyenne de deux colonnes (parenthèses respectées)" />
                  <FormulaRow formula="=Price * Qty - Discount" result="Expression multi-opérateurs" />
                </div>
                <Callout icon={Info} color="bg-blue-50 border-blue-200 dark:bg-blue-950/20 dark:border-blue-800 text-blue-800 dark:text-blue-300"
                  title="Date + entier = décalage en jours">
                  Quand vous additionnez une date et un nombre entier, le nombre est interprété comme un <strong>nombre de jours</strong> à ajouter. Ex : <code className="bg-blue-100 dark:bg-blue-900 px-1 rounded text-xs">=DATE(2040,12,4) + InputDay</code> donne 2040-12-04 si InputDay=0, 2040-12-05 si InputDay=1, etc.
                </Callout>
              </div>

              {/* Number functions */}
              <div className="mt-8">
                <SectionAnchor id="mapping-numbers" />
                <h3 className="font-semibold text-base mb-3 flex items-center gap-2">
                  <Code className="h-4 w-4 text-muted-foreground" />
                  Fonctions numériques
                </h3>
                <div className="rounded-lg border overflow-hidden">
                  <FormulaRow formula="=VALUE(TextCol)" result="Convertit un texte en nombre → 42 depuis « 42 »" />
                  <FormulaRow formula="=ROUND(Price, 2)" result="Arrondi à 2 décimales" />
                  <FormulaRow formula="=INT(Weight)" result="Partie entière (floor) → 5 depuis 5.9" />
                  <FormulaRow formula="=ABS(Delta)" result="Valeur absolue → 3 depuis -3" />
                  <FormulaRow formula="=ISNUMBER(Col)" result="TRUE si la cellule est un nombre" />
                </div>
              </div>

              {/* Date & time */}
              <div className="mt-8">
                <SectionAnchor id="mapping-dates" />
                <h3 className="font-semibold text-base mb-3 flex items-center gap-2">
                  <Code className="h-4 w-4 text-muted-foreground" />
                  Dates &amp; heures
                </h3>
                <p className="text-sm text-muted-foreground mb-4">
                  Les colonnes de type date/heure sont converties automatiquement avec <code className="bg-muted px-1 rounded text-xs">pd.to_datetime</code>. Résultat : objet datetime Python, formaté en texte dans le CSV de sortie.
                </p>

                <div className="space-y-5">
                  <div>
                    <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">Construire une date</p>
                    <div className="rounded-lg border overflow-hidden">
                      <FormulaRow formula="=DATE(2040, 12, 4)" result="Date fixe → 2040-12-04" />
                      <FormulaRow formula="=DATE(AnneeCol, MoisCol, JourCol)" result="Date depuis 3 colonnes numériques" />
                      <FormulaRow formula="=DATE(2040, 12, 4) + InputDay" result="Date + décalage en jours (InputDay=0 → 04/12, InputDay=1 → 05/12…)" />
                      <FormulaRow formula="=TODAY()" result="Date d'aujourd'hui (sans heure)" />
                      <FormulaRow formula="=NOW()" result="Date + heure actuelles" />
                    </div>
                  </div>

                  <div>
                    <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">Extraire un composant</p>
                    <div className="rounded-lg border overflow-hidden">
                      <FormulaRow formula="=YEAR(DateCol)" result="Année → 2040" />
                      <FormulaRow formula="=MONTH(DateCol)" result="Mois → 12" />
                      <FormulaRow formula="=DAY(DateCol)" result="Jour → 4" />
                      <FormulaRow formula="=HOUR(TimeCol)" result="Heure → 22" />
                      <FormulaRow formula="=MINUTE(TimeCol)" result="Minutes → 45" />
                      <FormulaRow formula="=SECOND(TimeCol)" result="Secondes → 0" />
                    </div>
                  </div>

                  <div>
                    <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">Convertir en minutes</p>
                    <div className="rounded-lg border overflow-hidden">
                      <FormulaRow formula="=TIMETOMIN(Time)" result="Heure « 22:45 » → 1365 minutes depuis minuit" />
                      <FormulaRow formula="=TIMETOMIN(Time, Day)" result="Jour=1, 22:45 → 2805 min totales (jour × 1440 + minutes)" />
                      <FormulaRow formula="=DATEDIFF(DateDep, DateArr, &quot;minute&quot;)" result="Différence entre deux dates en minutes" />
                    </div>
                  </div>

                  <div>
                    <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">Ajouter du temps</p>
                    <div className="rounded-lg border overflow-hidden">
                      <FormulaRow formula="=DATEADD(DateCol, 7, &quot;day&quot;)" result="+7 jours" />
                      <FormulaRow formula="=DATEADD(DateCol, -2, &quot;hour&quot;)" result="-2 heures" />
                      <FormulaRow formula="=DATEADD(DateCol, 30, &quot;minute&quot;)" result="+30 minutes" />
                      <FormulaRow formula="=DATE(2040,12,4) + InputDay" result="Syntaxe courte pour ajouter des jours" />
                    </div>
                  </div>

                  <div>
                    <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">Différence entre deux dates</p>
                    <div className="rounded-lg border overflow-hidden">
                      <FormulaRow formula={'=DATEDIFF(Open, Close, "day")'} result="Nombre de jours entre Open et Close" />
                      <FormulaRow formula={'=DATEDIFF(Open, Close, "hour")'} result="Nombre d'heures" />
                      <FormulaRow formula={'=DATEDIFF(Open, Close, "minute")'} result="Nombre de minutes" />
                    </div>
                  </div>

                  <div>
                    <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">Formater en texte</p>
                    <div className="rounded-lg border overflow-hidden">
                      <FormulaRow formula={'=TEXT(DateCol, "dd/MM/yyyy")'} result={'« 04/12/2040 » — MM = mois (majuscule)'} />
                      <FormulaRow formula={'=TEXT(TimeCol, "HH:mm")'} result={'« 22:45 » — mm = minutes (minuscule)'} />
                      <FormulaRow formula={'=TEXT(DateCol, "dd/MM/yyyy HH:mm")'} result={'« 04/12/2040 22:45 »'} />
                    </div>
                    <p className="text-xs text-muted-foreground mt-2">
                      Convention : <code className="bg-muted px-1 rounded">MM</code> = mois, <code className="bg-muted px-1 rounded">mm</code> = minutes, <code className="bg-muted px-1 rounded">yyyy</code> = année 4 chiffres, <code className="bg-muted px-1 rounded">HH</code> = heure 24h.
                    </p>
                  </div>

                  <div>
                    <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">Parser une date texte</p>
                    <div className="rounded-lg border overflow-hidden">
                      <FormulaRow formula="=DATEVALUE(TextCol)" result="Convertit « 2040-12-04 » en date (heure → 00:00)" />
                      <FormulaRow formula="=TIMEVALUE(TextCol)" result="Convertit « 22:45:00 » en fraction de jour (0.947…)" />
                    </div>
                  </div>
                </div>
              </div>

              {/* IF / AND / OR / NOT */}
              <div className="mt-8">
                <SectionAnchor id="mapping-if" />
                <h3 className="font-semibold text-base mb-3 flex items-center gap-2">
                  <Code className="h-4 w-4 text-muted-foreground" />
                  Conditions — IF, AND, OR, NOT
                </h3>
                <p className="text-sm text-muted-foreground mb-2">
                  Syntaxe : <code className="bg-muted px-1.5 py-0.5 rounded font-mono text-xs">IF(condition, valeur_si_vrai, valeur_si_faux)</code>
                </p>
                <div className="space-y-4">
                  <div className="rounded-lg border overflow-hidden">
                    <FormulaRow formula={'=IF(Terminal="T1", "T1", "Autre")'} result={'« T1 » si Terminal=T1, sinon « Autre »'} />
                    <FormulaRow formula={'=IF(Weight>100, "Heavy", "Light")'} result={'Comparaison numérique'} />
                    <FormulaRow formula={'=IF(Status<>"OK", "Erreur", Status)'} result={'Si pas OK → « Erreur », sinon la valeur de Status'} />
                    <FormulaRow formula={'=IF(Col<>"", Col, "vide")'} result={'Cellule non vide → sa valeur, sinon « vide »'} />
                    <FormulaRow formula={'=IF(YEAR(DateCol)>=2040, "Futur", "Passé")'} result={'Condition sur une date extraite'} />
                  </div>

                  <div>
                    <p className="text-xs text-muted-foreground mb-2"><strong>AND</strong> — toutes les conditions vraies :</p>
                    <div className="rounded-lg border overflow-hidden">
                      <FormulaRow formula={'=IF(AND(Terminal="T1", Status="OK"), "Bon", "KO")'} result={'T1 ET Status=OK'} />
                      <FormulaRow formula={'=IF(AND(Weight>50, Weight<200), "Normal", "Hors norme")'} result={'Intervalle numérique'} />
                      <FormulaRow formula={'=IF(AND(LEFT(Code,3)="T5C", Weight>50), 1, 0)'} result={'Formule dans condition AND'} />
                    </div>
                  </div>

                  <div>
                    <p className="text-xs text-muted-foreground mb-2"><strong>OR</strong> — au moins une condition vraie :</p>
                    <div className="rounded-lg border overflow-hidden">
                      <FormulaRow formula={'=IF(OR(Status="DELAYED", Status="CANCELLED"), "Problème", "OK")'} result={'Vrai si DELAYED ou CANCELLED'} />
                      <FormulaRow formula={'=IF(OR(Terminal="T1", Terminal="T2"), "Nord", "Sud")'} result={'Regroupement de terminaux'} />
                    </div>
                  </div>

                  <div>
                    <p className="text-xs text-muted-foreground mb-2"><strong>NOT</strong> — inverse la condition :</p>
                    <div className="rounded-lg border overflow-hidden">
                      <FormulaRow formula={'=IF(NOT(Terminal="T1"), "Autre", "T1")'} result={'Inverse la condition'} />
                    </div>
                  </div>

                  <div className="mt-1">
                    <p className="text-xs font-medium text-muted-foreground mb-2">Opérateurs de comparaison :</p>
                    <div className="flex flex-wrap gap-2">
                      {[["=","égal"],["<>","différent"],[">","supérieur"],["<","inférieur"],[">=","sup. ou égal"],["<=","inf. ou égal"]].map(([op, label]) => (
                        <div key={op} className="flex items-center gap-1.5 px-2 py-1 rounded border bg-card text-xs">
                          <code className="font-mono font-bold">{op}</code>
                          <span className="text-muted-foreground">{label}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>

              {/* ROW() */}
              <div className="mt-8">
                <SectionAnchor id="mapping-row" />
                <h3 className="font-semibold text-base mb-3 flex items-center gap-2">
                  <Code className="h-4 w-4 text-muted-foreground" />
                  Séquences avec ROW()
                </h3>
                <p className="text-sm text-muted-foreground mb-4">
                  <code className="bg-muted px-1.5 py-0.5 rounded">ROW()</code> génère un <strong>index de ligne</strong> (0 pour la première, 1 pour la deuxième, etc.).
                </p>
                <div className="rounded-lg border overflow-hidden mb-4">
                  <FormulaRow formula="=ROW()" result="0, 1, 2, 3…" />
                  <FormulaRow formula="=ROW(1)" result="1, 2, 3… (démarre à 1)" />
                  <FormulaRow formula="=ROW()+1" result="1, 2, 3… (identique à ROW(1))" />
                  <FormulaRow formula="=ROW()*2+1" result="1, 3, 5, 7… (impairs)" />
                  <FormulaRow formula="=ROW()*10" result="0, 10, 20, 30…" />
                  <FormulaRow formula="=IF(ArrFlightNo<>&quot;-9&quot;, ROW()+1, &quot;&quot;)" result="Numéro de ligne seulement si condition vraie" />
                </div>
              </div>

              {/* Advanced functions */}
              <div className="mt-8">
                <SectionAnchor id="mapping-advanced" />
                <h3 className="font-semibold text-base mb-3 flex items-center gap-2">
                  <Code className="h-4 w-4 text-muted-foreground" />
                  Fonctions avancées — contrôle d&apos;erreurs &amp; valeurs nulles
                </h3>
                <div className="rounded-lg border overflow-hidden">
                  <FormulaRow formula="=IFERROR(VALUE(Col), 0)" result="Retourne 0 si la formule échoue (erreur/vide)" />
                  <FormulaRow formula="=IFNA(Col, &quot;N/A&quot;)" result="Retourne « N/A » si la valeur est nulle/NaN" />
                  <FormulaRow formula="=COALESCE(ColA, ColB, ColC)" result="Première valeur non vide parmi ColA, ColB, ColC" />
                  <FormulaRow formula="=ISBLANK(Col)" result="TRUE si la cellule est vide ou null" />
                  <FormulaRow formula="=ISNUMBER(Col)" result="TRUE si la cellule est un nombre" />
                  <FormulaRow formula="=ISTEXT(Col)" result="TRUE si la cellule est un texte non numérique" />
                  <FormulaRow formula="=IF(ISBLANK(Col), &quot;vide&quot;, Col)" result="Remplace les vides par « vide »" />
                  <FormulaRow formula="=COALESCE(PrixPromo, PrixNormal, &quot;N/A&quot;)" result="Prend PrixPromo si dispo, sinon PrixNormal, sinon N/A" />
                </div>
              </div>

              {/* New Excel-like functions */}
              <div className="mt-8">
                <SectionAnchor id="mapping-excel" />
                <h3 className="font-semibold text-base mb-3 flex items-center gap-2">
                  <Code className="h-4 w-4 text-muted-foreground" />
                  Fonctions Excel avancées — LET, IFS, CHOOSE, MATCH, INDEX, VLOOKUP…
                </h3>

                <Callout icon={Info} color="bg-blue-50 border-blue-200 dark:bg-blue-950/20 dark:border-blue-800 text-blue-800 dark:text-blue-300 mb-5"
                  title="Séparateur ; accepté (Excel français/belge)">
                  Vous pouvez utiliser <code className="bg-blue-100 dark:bg-blue-900 px-1 rounded text-xs">;</code> ou <code className="bg-blue-100 dark:bg-blue-900 px-1 rounded text-xs">,</code> comme séparateur d&apos;arguments — les deux sont acceptés. Ex : <code className="bg-blue-100 dark:bg-blue-900 px-1 rounded text-xs">=SI(p&lt;0.5; "A"; "B")</code> et <code className="bg-blue-100 dark:bg-blue-900 px-1 rounded text-xs">=IF(p&lt;0.5, "A", "B")</code> sont équivalents.
                  Les noms français <strong>SI, ALEA, EQUIV, RECHERCHEV, CHOISIR, SOMME, MOYENNE, PUISSANCE</strong> sont aussi reconnus.
                </Callout>

                <div className="space-y-5">

                  <div>
                    <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">LET — variables nommées</p>
                    <p className="text-xs text-muted-foreground mb-2">
                      Définit des variables réutilisables dans la même formule. Syntaxe : <code className="bg-muted px-1 rounded">LET(nom, valeur, ..., formule)</code>
                    </p>
                    <div className="rounded-lg border overflow-hidden">
                      <FormulaRow formula={'=LET(p, ALEA(), IF(p<0.5, "A", "B"))'} result={'Tire p une fois, l\'utilise dans le IF — garantit la même valeur'} />
                      <FormulaRow formula={'=LET(p, ALEA(), IF(p<BT2, BQ2, IF(p<BT2+BU2, BR2, BS2)))'} result={'Tirage pondéré : p comparé à des seuils cumulés'} />
                      <FormulaRow formula={'=LET(score, Weight*2+Bonus, IF(score>100, "OK", score))'} result={'Variable intermédiaire calculée depuis des colonnes'} />
                      <FormulaRow formula={'=LET(a, ColA, b, ColB, (a+b)/2)'} result={'Plusieurs variables : moyenne de deux colonnes'} />
                    </div>
                    <p className="text-xs text-muted-foreground mt-2">
                      La formule utilise la syntaxe <code className="bg-muted px-1 rounded">;</code> d&apos;Excel français : <code className="bg-muted px-1 rounded">=LET(p;ALEA();SI(p&lt;BT2;BQ2;SI(p&lt;BT2+BU2;BR2;BS2)))</code>
                    </p>
                  </div>

                  <div>
                    <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">IFS / SI.CONDITIONS — cascades de IF sans SINON</p>
                    <div className="rounded-lg border overflow-hidden">
                      <FormulaRow formula={'=IFS(Score>=90,"A", Score>=75,"B", Score>=60,"C")'} result={'Première condition vraie gagne, les suivantes ignorées'} />
                      <FormulaRow formula={'=IFS(Terminal="T1","Nord", Terminal="T2","Nord", Terminal="T5","Sud")'} result={'Regroupement multi-valeurs'} />
                    </div>
                  </div>

                  <div>
                    <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">CHOOSE / CHOISIR — sélection par indice</p>
                    <p className="text-xs text-muted-foreground mb-2">Index 1-based : CHOOSE(1, …) retourne le 1er choix.</p>
                    <div className="rounded-lg border overflow-hidden">
                      <FormulaRow formula={'=CHOOSE(Priority, "Haute", "Moyenne", "Basse")'} result={'Priority=1 → Haute, 2 → Moyenne, 3 → Basse'} />
                      <FormulaRow formula={'=CHOOSE(MONTH(DateCol), "Jan","Fév","Mar","Avr","Mai","Jun","Jul","Aoû","Sep","Oct","Nov","Déc")'} result={'Mois en abrégé français'} />
                    </div>
                  </div>

                  <div>
                    <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">MATCH / EQUIV — position d&apos;une valeur dans une colonne</p>
                    <p className="text-xs text-muted-foreground mb-2">
                      Retourne l&apos;index 1-based de la première ligne où <code className="bg-muted px-1 rounded">search_col = lookup</code>.
                    </p>
                    <div className="rounded-lg border overflow-hidden">
                      <FormulaRow formula="=MATCH(FlightId, RefCol, 0)" result="Position de FlightId dans RefCol (1-based)" />
                      <FormulaRow formula={'=MATCH("AF123", CodeCol, 0)'} result="Cherche la constante « AF123 » dans CodeCol" />
                    </div>
                  </div>

                  <div>
                    <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">INDEX — valeur à une position donnée</p>
                    <p className="text-xs text-muted-foreground mb-2">
                      Retourne la valeur de <code className="bg-muted px-1 rounded">col</code> à la ligne <code className="bg-muted px-1 rounded">row_num</code> (1-based). S&apos;utilise souvent avec MATCH.
                    </p>
                    <div className="rounded-lg border overflow-hidden">
                      <FormulaRow formula="=INDEX(NameCol, 1)" result="Valeur de NameCol à la ligne 1 (constante pour toutes les lignes)" />
                      <FormulaRow formula="=INDEX(ResultCol, MATCH(FlightId, KeyCol, 0))" result="Équivalent RECHERCHEV : cherche FlightId dans KeyCol, retourne ResultCol" />
                    </div>
                  </div>

                  <div>
                    <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">VLOOKUP / RECHERCHEV — lookup dans le même dataframe</p>
                    <p className="text-xs text-muted-foreground mb-2">
                      Cherche <code className="bg-muted px-1 rounded">lookup</code> dans <code className="bg-muted px-1 rounded">key_col</code>, retourne la valeur correspondante de <code className="bg-muted px-1 rounded">result_col</code>.
                      Pour des lookups <strong>inter-fichiers</strong>, utilisez les jointures (alias.Col).
                    </p>
                    <div className="rounded-lg border overflow-hidden">
                      <FormulaRow formula="=VLOOKUP(FlightId, RefId, GateName, 0)" result="Cherche FlightId dans RefId, retourne GateName de la même ligne" />
                      <FormulaRow formula="=RECHERCHEV(CodeVol, RefCode, Terminal, 0)" result="Alias français" />
                    </div>
                  </div>

                  <div>
                    <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">RAND / ALEA — nombre aléatoire</p>
                    <div className="rounded-lg border overflow-hidden">
                      <FormulaRow formula="=RAND()" result="Flottant aléatoire [0, 1) — différent pour chaque ligne" />
                      <FormulaRow formula="=ALEA()" result="Alias français de RAND()" />
                      <FormulaRow formula="=RANDBETWEEN(1, 100)" result="Entier aléatoire entre 1 et 100" />
                      <FormulaRow formula="=ALEA.ENTRE.BORNES(1, 6)" result="Dé à 6 faces — alias français" />
                    </div>
                  </div>

                  <div>
                    <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">Fonctions mathématiques</p>
                    <div className="rounded-lg border overflow-hidden">
                      <FormulaRow formula="=MOD(Value, 3)" result="Reste de la division de Value par 3 (0, 1 ou 2)" />
                      <FormulaRow formula="=POWER(Base, 2)" result="Carré de Base (alias : PUISSANCE)" />
                      <FormulaRow formula="=SQRT(Area)" result="Racine carrée de Area" />
                      <FormulaRow formula="=MIN(ColA, ColB, ColC)" result="Minimum par ligne entre plusieurs colonnes" />
                      <FormulaRow formula="=MAX(ColA, 0)" result="Seuil minimum à 0 (aucune valeur négative)" />
                      <FormulaRow formula="=SUM(ColA, ColB, ColC)" result="Somme de plusieurs colonnes par ligne (alias : SOMME)" />
                      <FormulaRow formula="=AVERAGE(ColA, ColB, ColC)" result="Moyenne de plusieurs colonnes par ligne (alias : MOYENNE)" />
                    </div>
                  </div>

                  <div>
                    <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">Conversion du temps</p>
                    <div className="rounded-lg border overflow-hidden">
                      <FormulaRow formula="=TIMETOMIN(Time)" result="Heure → minutes depuis minuit (22:45 → 1365)" />
                      <FormulaRow formula="=TIMETOMIN(Time, Day)" result="Avec décalage jour (jour=1, 22:45 → 2805)" />
                      <FormulaRow formula="=TIMETOHOUR(Time)" result="Heure → heures décimales (22:45 → 22.75)" />
                      <FormulaRow formula="=TIMETOHOUR(Time, Day)" result="Avec décalage jour (jour=1, 22:45 → 46.75)" />
                      <FormulaRow formula="=TIMETOSEC(Time)" result="Heure → secondes depuis minuit (22:45 → 81900)" />
                      <FormulaRow formula="=TIMETOSEC(Time, Day)" result="Avec décalage jour (jour=1, 22:45 → 168300)" />
                    </div>
                    <p className="text-xs text-muted-foreground mt-2">
                      Ces fonctions gèrent tous les formats d&apos;entrée : <code className="bg-muted px-1 rounded">timedelta</code>, fraction Excel (0–1), <code className="bg-muted px-1 rounded">datetime.time</code>, ou chaîne texte.
                    </p>
                  </div>

                </div>
              </div>

              {/* Nested formulas */}
              <div className="mt-8">
                <SectionAnchor id="mapping-nested" />
                <h3 className="font-semibold text-base mb-3 flex items-center gap-2">
                  <Code className="h-4 w-4 text-muted-foreground" />
                  Formules imbriquées — toutes les combinaisons
                </h3>
                <p className="text-sm text-muted-foreground mb-4">
                  Le moteur évalue chaque argument de façon <strong>récursive</strong> : n&apos;importe quelle fonction peut recevoir n&apos;importe quelle autre fonction comme argument, à profondeur illimitée.
                </p>

                <Callout icon={CheckCircle} color="bg-green-50 border-green-200 dark:bg-green-950/20 dark:border-green-800 text-green-800 dark:text-green-300 mb-5"
                  title="Toutes les combinaisons fonctionnent">
                  <code className="bg-green-100 dark:bg-green-900 px-1 rounded text-xs">IFERROR(INDEX(Col, MATCH(A&amp;B, KeyCol, 0)), "")</code> — lookup avec clé composée<br />
                  <code className="bg-green-100 dark:bg-green-900 px-1 rounded text-xs">IF(ISNUMBER(FIND("+", Col)), TEXTBEFORE(Col, "+"), Col)</code> — FIND dans IF<br />
                  <code className="bg-green-100 dark:bg-green-900 px-1 rounded text-xs">LEFT(Col, LEN(Col) - RIGHT(SizeCol, 2))</code> — formules dans LEFT/RIGHT
                </Callout>

                <div className="space-y-5">

                  <div>
                    <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">Lookup avec clé composée</p>
                    <div className="rounded-lg border overflow-hidden">
                      <FormulaRow formula={'=IFERROR(INDEX(KeyCol, MATCH(A & B, RefCol, 0)), "")'} result={'Cherche la concaténation A&B dans RefCol, retourne KeyCol. Vide si absent.'} />
                      <FormulaRow formula={'=IFERROR(INDEX(Col, MATCH(FlightId & Term, CompositeKey, 0)), "N/A")'} result={'Clé composite vol+terminal'} />
                    </div>
                  </div>

                  <div>
                    <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">IFERROR + IF + conditions multiples</p>
                    <div className="rounded-lg border overflow-hidden">
                      <FormulaRow
                        formula={'=IFERROR(IF(BM3>0, IF(AND(BH3>0, BE3=0), VLOOKUP(N3, RefA, 4, 0), IF(BE3=0, VLOOKUP(N3, RefB, 2, 0), BY3)), ""), 0)'}
                        result={'VLOOKUP conditionnel imbriqué dans plusieurs IF — retourne 0 sur erreur'}
                      />
                      <FormulaRow
                        formula={'=IF(BJ4=0, IFERROR(INDEX(QCol, MATCH(V4, ACol, 0)), INDEX(QCol, MATCH(U4, BCol, 0))), BZ4)'}
                        result={'INDEX/MATCH en fallback : essaie V4 sur ACol, sinon U4 sur BCol'}
                      />
                    </div>
                  </div>

                  <div>
                    <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">Conditions sur fonctions texte</p>
                    <div className="rounded-lg border overflow-hidden">
                      <FormulaRow
                        formula={'=IF(OR(LEFT(Col1,3)="T5C", LEFT(Col2,3)="T5C", LEFT(Col1,3)="R5C", LEFT(Col1,3)="R5D"), "include", "omit")'}
                        result={'OR avec plusieurs LEFT imbriqués'}
                      />
                      <FormulaRow
                        formula={'=IF(ISNUMBER(SEARCH("+", Col)), TEXTBEFORE(Col, "+"), Col)'}
                        result={'SEARCH dans ISNUMBER dans IF — retourne la partie avant + si présent'}
                      />
                      <FormulaRow
                        formula={'=IF(OR(Status="Tx", Status="CI"), IF(OR(LEFT(N,3)="T5C", LEFT(Y,3)="T5C", LEFT(N,3)="R5D"), "include", "omit"), "omit")'}
                        result={'IF imbriqué avec OR et LEFT — reproduit une formule Excel complexe'}
                      />
                    </div>
                  </div>

                  <div>
                    <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">LET avec tirage pondéré</p>
                    <div className="rounded-lg border overflow-hidden">
                      <FormulaRow
                        formula={'=LET(p, RAND(), IF(p<BT2, BQ2, IF(p<BT2+BU2, BR2, BS2)))'}
                        result={'p est tiré une seule fois et réutilisé dans les deux IF — tirage pondéré 3 catégories'}
                      />
                    </div>
                  </div>

                  <div>
                    <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">Calculs sur taille de texte</p>
                    <div className="rounded-lg border overflow-hidden">
                      <FormulaRow formula={'=LEFT(Col, LEN(Col)-3)'} result={'Tout sauf les 3 derniers caractères'} />
                      <FormulaRow formula={'=RIGHT(Col, LEN(Col)-2)'} result={'Tout sauf les 2 premiers caractères'} />
                      <FormulaRow formula={'=MID(Col, FIND("-", Col)+1, LEN(Col))'} result={'Tout ce qui suit le premier tiret'} />
                      <FormulaRow formula={'=IFERROR(TEXTBEFORE(Col, "+"), Col)'} result={'Texte avant « + » si présent, sinon valeur brute — robuste'} />
                    </div>
                  </div>

                  <div>
                    <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">ROUND / SUBSTITUTE avec formules</p>
                    <div className="rounded-lg border overflow-hidden">
                      <FormulaRow formula={'=ROUND(ColA * ColB, VALUE(DecimalsCol))'} result={'Nombre de décimales vient d\'une colonne'} />
                      <FormulaRow formula={'=SUBSTITUTE(Col, LEFT(OldCol, 3), RIGHT(NewCol, 3))'} result={'Ancien et nouveau texte calculés depuis d\'autres colonnes'} />
                    </div>
                  </div>

                </div>
              </div>

              {/* Cross-column / intermediate */}
              <div className="mt-8">
                <SectionAnchor id="mapping-crosscol" />
                <h3 className="font-semibold text-base mb-3 flex items-center gap-2">
                  <Eye className="h-4 w-4 text-muted-foreground" />
                  Colonnes intermédiaires &amp; références croisées
                </h3>
                <p className="text-sm text-muted-foreground mb-4">
                  Chaque colonne calculée est <strong>immédiatement disponible</strong> pour les colonnes suivantes dans le tableau.
                  Cela permet de découper un calcul complexe en plusieurs étapes sans dupliquer la logique.
                </p>

                <div className="space-y-4">
                  <div>
                    <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">Référencer une colonne output dans une autre</p>
                    <div className="rounded-lg border overflow-hidden">
                      <FormulaRow formula="=CreatTime" result="Réutilise la colonne output « CreatTime » calculée avant" />
                      <FormulaRow formula="=IF(LEFT(TypeCol, 3)=&quot;T5C&quot;, 1, 0)" result="Utilise une colonne calculée en amont comme source" />
                      <FormulaRow formula="=ColA + ColB_output" result="Somme d'une colonne source et d'une colonne calculée" />
                    </div>
                    <p className="text-xs text-muted-foreground mt-2">
                      La colonne référencée doit être <strong>au-dessus</strong> dans le tableau (ordre des lignes = ordre de calcul).
                      Utilisez les flèches ↑ ↓ pour réordonner.
                    </p>
                  </div>

                  <div>
                    <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">Colonne intermédiaire (œil barré)</p>
                    <div className="grid grid-cols-2 gap-3">
                      <div className="p-3 rounded-lg border bg-card">
                        <div className="flex items-center gap-2 mb-2">
                          <Eye className="h-4 w-4 text-primary" />
                          <p className="text-xs font-semibold">Inclus (défaut)</p>
                        </div>
                        <p className="text-xs text-muted-foreground">La colonne apparaît dans le fichier de sortie.</p>
                      </div>
                      <div className="p-3 rounded-lg border bg-card">
                        <div className="flex items-center gap-2 mb-2">
                          <EyeOff className="h-4 w-4 text-muted-foreground/40" />
                          <p className="text-xs font-semibold">Exclu (intermédiaire)</p>
                        </div>
                        <p className="text-xs text-muted-foreground">Calculée et disponible pour les formules et les filtres output, mais <strong>absente du fichier final</strong>.</p>
                      </div>
                    </div>
                    <Callout icon={Info} color="bg-blue-50 border-blue-200 dark:bg-blue-950/20 dark:border-blue-800 text-blue-800 dark:text-blue-300 mt-3"
                      title="Exemple typique">
                      Créez une colonne <code className="bg-blue-100 dark:bg-blue-900 px-1 rounded text-xs">=IF(Status=&quot;OK&quot;, &quot;oui&quot;, &quot;non&quot;)</code> avec l&apos;œil barré.
                      Ajoutez un filtre output <code className="bg-blue-100 dark:bg-blue-900 px-1 rounded text-xs">= oui</code> sur cette colonne.
                      Résultat : seules les lignes OK sont exportées, mais la colonne de statut n&apos;apparaît pas dans le fichier.
                    </Callout>
                  </div>
                </div>
              </div>

              {/* Dedup */}
              <div className="mt-8">
                <SectionAnchor id="mapping-dedup" />
                <h3 className="font-semibold text-base mb-3 flex items-center gap-2">
                  <Filter className="h-4 w-4 text-muted-foreground" />
                  Dédupliquer par PK
                </h3>
                <p className="text-sm text-muted-foreground mb-4">
                  Activez ce toggle pour <strong>regrouper les lignes ayant la même valeur de clé primaire</strong>.
                  Cela permet de transformer plusieurs lignes avec la même PK en une seule ligne de sortie.
                </p>
                <div className="overflow-x-auto rounded-lg border">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b bg-muted/50">
                        <th className="px-4 py-2.5 text-left font-semibold">Méthode</th>
                        <th className="px-4 py-2.5 text-left font-semibold">Comportement</th>
                        <th className="px-4 py-2.5 text-left font-semibold">Cas d&apos;usage typique</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y">
                      {[
                        ["First", "Garde la valeur de la première ligne du groupe", "Identifiant, code vol"],
                        ["Last", "Garde la valeur de la dernière ligne", "Statut, timestamp de mise à jour"],
                        ["Sum", "Somme les valeurs numériques", "Poids total, nombre de bagages"],
                        ["Count", "Compte le nombre de lignes dans le groupe", "Nombre de segments"],
                        ["Max / Min", "Valeur maximale / minimale du groupe", "Heure d'arrivée max, min"],
                        ["Average", "Moyenne des valeurs numériques", "Retard moyen"],
                        ["Concat", "Concatène toutes les valeurs séparées par « ; »", "Liste de codes, remarques"],
                      ].map(([method, desc, useCase]) => (
                        <tr key={method}>
                          <td className="px-4 py-2 font-mono font-medium">{method}</td>
                          <td className="px-4 py-2 text-muted-foreground">{desc}</td>
                          <td className="px-4 py-2 text-muted-foreground italic">{useCase}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <Callout icon={AlertCircle} color="bg-amber-50 border-amber-200 dark:bg-amber-950/20 dark:border-amber-800 text-amber-800 dark:text-amber-300 mt-4"
                  title="PK requise">
                  Pour activer la déduplication, cochez la case <strong>PK</strong> sur au moins une colonne. Une seule PK est supportée à la fois.
                </Callout>
              </div>

              {/* Configs */}
              <div className="mt-8">
                <SectionAnchor id="mapping-configs" />
                <h3 className="font-semibold text-base mb-3 flex items-center gap-2">
                  <Database className="h-4 w-4 text-muted-foreground" />
                  Configurations sauvegardées
                </h3>
                <p className="text-sm text-muted-foreground mb-4">
                  Une configuration enregistre l&apos;intégralité du mapping : colonnes, formules, PK, agrégations, option dédup, <strong>filtres groupés ET/OU</strong> (source et output), et la <strong>configuration des jointures</strong> (alias + clés). Elle est stockée dans Supabase et accessible depuis n&apos;importe quelle session.
                </p>
                <Callout icon={Info} color="bg-amber-50 border-amber-200 dark:bg-amber-950/20 dark:border-amber-800 text-amber-800 dark:text-amber-300 mb-4"
                  title="Fichiers secondaires non stockés">
                  Les fichiers secondaires (JOIN) <strong>ne sont pas sauvegardés</strong> (trop volumineux). Au chargement d&apos;une config, les alias et les clés de jointure sont restaurés, mais vous devrez <strong>re-uploader les fichiers</strong> secondaires manuellement.
                </Callout>
                <div className="grid grid-cols-3 gap-3">
                  <div className="p-3 rounded-lg border bg-card">
                    <div className="flex items-center gap-2 mb-1.5">
                      <Save className="h-3.5 w-3.5 text-muted-foreground" />
                      <p className="text-xs font-semibold">Sauvegarder</p>
                    </div>
                    <p className="text-xs text-muted-foreground">Donnez un nom à votre configuration. Si le nom existe déjà, elle est <strong>mise à jour</strong>.</p>
                  </div>
                  <div className="p-3 rounded-lg border bg-card">
                    <div className="flex items-center gap-2 mb-1.5">
                      <FolderOpen className="h-3.5 w-3.5 text-muted-foreground" />
                      <p className="text-xs font-semibold">Charger</p>
                    </div>
                    <p className="text-xs text-muted-foreground">Sélectionnez une configuration dans la liste pour <strong>restaurer</strong> tout le mapping en un clic.</p>
                  </div>
                  <div className="p-3 rounded-lg border bg-card">
                    <div className="flex items-center gap-2 mb-1.5">
                      <Trash2 className="h-3.5 w-3.5 text-muted-foreground" />
                      <p className="text-xs font-semibold">Supprimer</p>
                    </div>
                    <p className="text-xs text-muted-foreground">Sélectionnez une configuration dans la liste et confirmez la suppression.</p>
                  </div>
                </div>
                <p className="text-xs text-muted-foreground mt-3">
                  Ces actions sont accessibles via le bouton <strong>Configurations</strong> en haut à droite de la page Mapping.
                </p>
              </div>

              {/* Export */}
              <div className="mt-8">
                <SectionAnchor id="mapping-export" />
                <h3 className="font-semibold text-base mb-3 flex items-center gap-2">
                  <Download className="h-4 w-4 text-muted-foreground" />
                  Prévisualisation &amp; Export
                </h3>
                <div className="space-y-4">
                  <div className="flex items-start gap-3">
                    <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-muted text-muted-foreground text-xs font-bold mt-0.5">1</div>
                    <div>
                      <p className="text-sm font-medium">Cliquez sur &quot;Prévisualiser&quot;</p>
                      <p className="text-xs text-muted-foreground mt-0.5">Le backend applique toutes les formules sur l&apos;ensemble du fichier source et renvoie les <strong>100 premières lignes</strong> pour aperçu.</p>
                    </div>
                  </div>
                  <div className="flex items-start gap-3">
                    <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-muted text-muted-foreground text-xs font-bold mt-0.5">2</div>
                    <div>
                      <p className="text-sm font-medium">Vérifiez le résultat</p>
                      <p className="text-xs text-muted-foreground mt-0.5">La fenêtre d&apos;aperçu affiche le tableau de résultat avec le nombre total de lignes, le nombre de colonnes, et un indicateur si seules les 100 premières sont visibles.</p>
                    </div>
                  </div>
                  <div className="flex items-start gap-3">
                    <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-muted text-muted-foreground text-xs font-bold mt-0.5">3</div>
                    <div>
                      <p className="text-sm font-medium">Choisissez le format et le nom du fichier</p>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        Deux formats disponibles :
                      </p>
                      <div className="flex gap-3 mt-2">
                        <div className="flex items-center gap-1.5 px-3 py-1.5 rounded border bg-card text-xs">
                          <FileText className="h-3.5 w-3.5 text-muted-foreground" />
                          <span><strong>CSV</strong> — léger, compatible avec tout</span>
                        </div>
                        <div className="flex items-center gap-1.5 px-3 py-1.5 rounded border bg-card text-xs">
                          <FileSpreadsheet className="h-3.5 w-3.5 text-muted-foreground" />
                          <span><strong>Excel</strong> — formatage avancé, colonnes typées</span>
                        </div>
                      </div>
                    </div>
                  </div>
                  <div className="flex items-start gap-3">
                    <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground text-xs font-bold mt-0.5">
                      <Download className="h-3 w-3" />
                    </div>
                    <div>
                      <p className="text-sm font-medium">Cliquez sur &quot;Télécharger&quot;</p>
                      <p className="text-xs text-muted-foreground mt-0.5">Le fichier complet (toutes les lignes, pas seulement l&apos;aperçu) est généré et téléchargé immédiatement.</p>
                    </div>
                  </div>
                </div>
              </div>

            </section>

            {/* ════ Footer CTA ════ */}
            <Separator />
            <div className="flex items-center justify-between rounded-xl bg-muted/40 border p-5">
              <div>
                <p className="font-semibold">Prêt à commencer ?</p>
                <p className="text-sm text-muted-foreground mt-0.5">Choisissez l&apos;outil adapté à votre besoin.</p>
              </div>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" asChild>
                  <Link href="/mapping">
                    <GitMerge className="h-3.5 w-3.5 mr-1.5" />
                    Mapping Tool
                  </Link>
                </Button>
                <Button size="sm" asChild>
                  <Link href="/">
                    <Play className="h-3.5 w-3.5 mr-1.5" />
                    Démarrer une allocation
                  </Link>
                </Button>
              </div>
            </div>

          </main>
        </div>
      </div>
    </AppShell>
  )
}
