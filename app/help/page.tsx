"use client"

import { useState } from "react"
import {
  AlertCircle, ArrowRight, BookOpen, CheckCircle, ChevronRight,
  Code, Database, Download, Eye, EyeOff, FileSpreadsheet, FileText,
  Filter, FolderOpen, GitMerge, HelpCircle, Info,
  Layers, Plane, Play, Plus, Save, Trash2, Upload,
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
                <div className="rounded-lg border overflow-hidden">
                  <FormulaRow formula="=LEFT(FlightNum, 2)" result="2 premiers caractères → « AF » depuis « AF123 »" />
                  <FormulaRow formula="=RIGHT(Route, 3)" result="3 derniers caractères → « CDG » depuis « ORLY-CDG »" />
                  <FormulaRow formula="=MID(Code, 2, 4)" result="Substring depuis position 2, longueur 4" />
                  <FormulaRow formula="=LEN(Name)" result="Nombre de caractères" />
                  <FormulaRow formula="=UPPER(Terminal)" result="Majuscules → « T2 » depuis « t2 »" />
                  <FormulaRow formula="=LOWER(Status)" result="Minuscules → « done » depuis « DONE »" />
                  <FormulaRow formula="=TRIM(Name)" result="Supprime les espaces en début et fin" />
                  <FormulaRow formula={'=TEXTBEFORE(Route, "/")'} result={'Texte avant le séparateur → « ORLY » depuis « ORLY/CDG »'} />
                  <FormulaRow formula={'=TEXTAFTER(Route, "-")'} result={'Texte après le séparateur → « CDG » depuis « ORLY-CDG »'} />
                  <FormulaRow formula={'=SUBSTITUTE(Code, "OLD", "NEW")'} result={'Remplace toutes les occurrences de « OLD » par « NEW »'} />
                  <FormulaRow formula={'=CONCAT(ColA, ColB, ColC)'} result={'Concaténation multi-colonnes (alias de &)'} />
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
                  <FormulaRow formula="=UnloadTime * 1440 + UnloadDay * 1440" result="Convertit jour + fraction en minutes totales" />
                  <FormulaRow formula="=HOUR(ArrTime) * 60 + MINUTE(ArrTime)" result="Heure → minutes depuis minuit" />
                  <FormulaRow formula="=Day * 1440 + HOUR(Time) * 60 + MINUTE(Time)" result="Jour + temps → minutes totales (ex: jour=1, 22:45 → 2805)" />
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
                      <FormulaRow formula="=HOUR(Time) * 60 + MINUTE(Time)" result="Heure « 22:45 » → 1365 minutes depuis minuit" />
                      <FormulaRow formula="=Day * 1440 + HOUR(Time) * 60 + MINUTE(Time)" result="Jour=1, 22:45 → 2805 min totales" />
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
                  Fonctions avancées
                </h3>
                <div className="rounded-lg border overflow-hidden">
                  <FormulaRow formula="=IFERROR(VALUE(Col), 0)" result="Retourne 0 si la formule échoue (erreur/vide)" />
                  <FormulaRow formula="=COALESCE(ColA, ColB, ColC)" result="Première valeur non vide parmi ColA, ColB, ColC" />
                  <FormulaRow formula="=ISBLANK(Col)" result="TRUE si la cellule est vide ou null" />
                  <FormulaRow formula="=ISNUMBER(Col)" result="TRUE si la cellule est un nombre" />
                  <FormulaRow formula="=ISTEXT(Col)" result="TRUE si la cellule est un texte non numérique" />
                  <FormulaRow formula="=IF(ISBLANK(Col), &quot;vide&quot;, Col)" result="Remplace les vides par « vide »" />
                  <FormulaRow formula="=COALESCE(PrixPromo, PrixNormal, &quot;N/A&quot;)" result="Prend PrixPromo si dispo, sinon PrixNormal, sinon N/A" />
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
                  Une configuration enregistre l&apos;intégralité du tableau de mapping (colonnes, formules, PK, agrégations, option dédup). Elle est stockée dans Supabase et accessible depuis n&apos;importe quelle session.
                </p>
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
