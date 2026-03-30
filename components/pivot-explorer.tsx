"use client"

import { useRef, useState } from "react"
import PivotTableUI from "react-pivottable/PivotTableUI"
import TableRenderers from "react-pivottable/TableRenderers"
import createPlotlyRenderers from "react-pivottable/PlotlyRenderers"
import Plotly from "plotly.js-dist-min"
import createPlotlyComponent from "react-plotly.js/factory"
import "react-pivottable/pivottable.css"
import "@/app/pivot-overrides.css"
import { Download, Eye, EyeOff, Type } from "lucide-react"

const Plot = createPlotlyComponent(Plotly)
const PlotlyRenderers = createPlotlyRenderers(Plot)
const allRenderers = { ...TableRenderers, ...PlotlyRenderers }

// Plotly typed for downloadImage
const PlotlyAPI = Plotly as unknown as {
  downloadImage: (el: Element, opts: Record<string, unknown>) => void
}

interface PivotExplorerProps {
  data: Record<string, unknown>[]
  rowCount?: number
}

export function PivotExplorer({ data, rowCount }: PivotExplorerProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [state, setState] = useState<Record<string, unknown>>({})
  const [chartTitle, setChartTitle] = useState("")
  const [showLegend, setShowLegend] = useState(true)

  // Separate rendererOptions out of state so we can merge without it being overridden
  const { rendererOptions: stateRO, ...restState } = state
  const mergedRendererOptions = {
    ...((stateRO as Record<string, unknown>) ?? {}),
    plotlyOptions: {
      ...(((stateRO as Record<string, unknown>)?.plotlyOptions as Record<string, unknown>) ?? {}),
      ...(chartTitle.trim()
        ? { title: { text: chartTitle.trim(), font: { size: 15, color: "#1a1a1a" } } }
        : {}),
      showlegend: showLegend,
      legend: { orientation: "h" as const, y: -0.18, x: 0.5, xanchor: "center" as const },
      margin: { t: chartTitle.trim() ? 52 : 24, b: showLegend ? 80 : 32, l: 60, r: 20 },
    },
  }

  const handleDownload = (format: "png" | "svg" | "jpeg") => {
    if (!containerRef.current) return
    const el = containerRef.current.querySelector(".js-plotly-plot")
    if (!el) {
      alert("Aucun graphique Plotly détecté. Choisissez d'abord un type de graphique Plotly.")
      return
    }
    PlotlyAPI.downloadImage(el, {
      format,
      width: 1400,
      height: 800,
      filename: chartTitle.trim() || "graphique-explorateur",
    })
  }

  return (
    <div className="flex flex-col gap-3">
      {/* Help bar */}
      <div className="flex flex-wrap items-center gap-3 rounded-lg border bg-muted/40 px-4 py-2.5 text-xs text-muted-foreground">
        <span className="font-semibold text-foreground">Comment utiliser :</span>
        <span>
          <span className="inline-flex items-center rounded bg-background border px-1.5 py-0.5 font-mono text-[11px] mr-1">glisser</span>
          un champ vers <strong className="text-foreground">Lignes</strong> ou <strong className="text-foreground">Colonnes</strong>
        </span>
        <span className="hidden sm:inline text-border">•</span>
        <span className="hidden sm:inline">Choisir un <strong className="text-foreground">type de graphique</strong> en haut à gauche</span>
        <span className="hidden sm:inline text-border">•</span>
        <span className="hidden sm:inline">Cliquer <strong className="text-foreground">▾</strong> sur un champ pour filtrer</span>
        {rowCount !== undefined && (
          <span className="ml-auto shrink-0 font-medium text-foreground">{rowCount.toLocaleString("fr-FR")} vols</span>
        )}
      </div>

      {/* Toolbar: title + legend + download */}
      <div className="flex flex-wrap items-center gap-3 rounded-lg border bg-background px-4 py-2.5">
        {/* Title input */}
        <Type className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
        <label className="text-xs font-medium text-muted-foreground whitespace-nowrap">Titre</label>
        <input
          type="text"
          value={chartTitle}
          onChange={e => setChartTitle(e.target.value)}
          placeholder="Titre du graphique (affiché sur le graphe)..."
          className="h-8 flex-1 min-w-[200px] rounded-md border border-input bg-background px-3 text-sm outline-none focus:border-primary focus:ring-1 focus:ring-primary/20 placeholder:text-muted-foreground/50 transition-colors"
        />

        <div className="h-5 w-px bg-border" />

        {/* Legend toggle */}
        <div className="flex items-center gap-2">
          {showLegend ? <Eye className="h-3.5 w-3.5 text-muted-foreground" /> : <EyeOff className="h-3.5 w-3.5 text-muted-foreground" />}
          <span className="text-xs font-medium text-muted-foreground">Légende</span>
          <button
            onClick={() => setShowLegend(v => !v)}
            className={`relative inline-flex h-5 w-9 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 focus:outline-none ${showLegend ? "bg-primary" : "bg-input"}`}
            role="switch"
            aria-checked={showLegend}
          >
            <span className={`pointer-events-none inline-block h-4 w-4 rounded-full bg-white shadow-sm transition-transform duration-200 ${showLegend ? "translate-x-4" : "translate-x-0"}`} />
          </button>
        </div>

        <div className="h-5 w-px bg-border" />

        {/* Download buttons */}
        <div className="flex items-center gap-1.5">
          <Download className="h-3.5 w-3.5 text-muted-foreground" />
          <span className="text-xs font-medium text-muted-foreground mr-1">Enregistrer</span>
          {(["png", "jpeg", "svg"] as const).map(fmt => (
            <button
              key={fmt}
              onClick={() => handleDownload(fmt)}
              className="h-7 rounded border border-input px-2.5 text-xs font-medium transition-colors hover:bg-muted hover:border-primary/40 uppercase tracking-wide"
            >
              {fmt}
            </button>
          ))}
        </div>
      </div>

      {/* Pivot table */}
      <div ref={containerRef} className="overflow-auto rounded-xl border bg-background shadow-sm p-3">
        <PivotTableUI
          data={data}
          onChange={(s: Record<string, unknown>) => setState(s)}
          renderers={allRenderers}
          rendererOptions={mergedRendererOptions}
          unusedOrientationCutoff={Infinity}
          {...restState}
        />
      </div>
    </div>
  )
}
