"use client"

import Link from "next/link"
import { MoreHorizontal, Pencil, Share2, Trash2 } from "lucide-react"
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem,
  DropdownMenuSeparator, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"

// Entreprise — building / city skyline
export const ENTREPRISE_IMAGE =
  "https://images.unsplash.com/photo-1486325212027-8081e485255e?w=600&q=75"

// Secteur — terminal interior / gates
export const SECTEUR_IMAGE =
  "https://images.unsplash.com/photo-1504328345606-18bbc8c9d7d1?w=600&q=75"

// Projet — runway / tarmac
export const PROJET_IMAGE =
  "https://images.unsplash.com/photo-1529074963764-98f45c47344b?w=600&q=75"

// Legacy alias — kept so existing imports don't break
export const AIRPORT_IMAGE = PROJET_IMAGE

export function formatDate(iso: string | null) {
  if (!iso) return "N/A"
  return new Date(iso).toLocaleDateString("fr-FR", { day: "2-digit", month: "short", year: "numeric" })
}

export function shortCode(name: string, code?: string | null) {
  if (code) return code
  return name.slice(0, 8).toLowerCase().replace(/\s+/g, "-")
}

interface PhotoCardProps {
  href: string
  name: string
  createdAt: string | null
  image?: string
  code?: string | null
  metric1Label: string
  metric1Value: number | string
  metric1Color?: string
  metric2Label: string
  metric2Value: number | string
  metric2Color?: string
  onRename?: (e: React.MouseEvent) => void
  onDelete?: (e: React.MouseEvent) => void
}

export function PhotoCard({
  href, name, createdAt,
  image = AIRPORT_IMAGE,
  code,
  metric1Label, metric1Value, metric1Color = "text-orange-500",
  metric2Label, metric2Value, metric2Color = "text-blue-500",
  onRename, onDelete,
}: PhotoCardProps) {
  return (
    <div className="group overflow-hidden rounded-xl border border-border bg-white shadow-sm hover:shadow-lg transition-all duration-200">
      <Link href={href} prefetch className="block">
        {/* Image */}
        <div className="relative h-44 overflow-hidden">
          <img
            src={image}
            alt=""
            className="h-full w-full object-cover brightness-90 group-hover:scale-105 transition-transform duration-500"
          />
          <div className="absolute inset-0 bg-gradient-to-t from-black/25 to-transparent" />
        </div>

        {/* Content */}
        <div className="p-4">
          <h3 className="font-bold text-[15px] text-foreground leading-tight truncate">{name}</h3>
          <p className="mt-0.5 text-[11px] text-muted-foreground">Created: {formatDate(createdAt)}</p>

          <div className="mt-3 grid grid-cols-2 gap-2 border-t border-border pt-3">
            <div>
              <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-medium">{metric1Label}</p>
              <p className={`text-xl font-bold ${metric1Color}`}>{metric1Value}</p>
            </div>
            <div>
              <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-medium">{metric2Label}</p>
              <p className={`text-xl font-bold ${metric2Color}`}>{metric2Value}</p>
            </div>
          </div>
        </div>
      </Link>

      {/* Footer */}
      <div className="flex items-center justify-between px-4 pb-4">
        <span className="rounded-md border border-border bg-gray-50 px-2 py-0.5 text-[11px] text-muted-foreground font-medium">
          {shortCode(name, code)}
        </span>
        <div className="flex items-center gap-1">
          {(onRename || onDelete) && (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button
                  onClick={e => e.preventDefault()}
                  className="rounded-md p-1.5 text-muted-foreground hover:text-primary hover:bg-gray-100 transition-colors"
                >
                  <MoreHorizontal className="h-3.5 w-3.5" />
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-40">
                {onRename && (
                  <DropdownMenuItem
                    onClick={e => { e.preventDefault(); onRename(e) }}
                    className="gap-2"
                  >
                    <Pencil className="h-3.5 w-3.5" /> Renommer
                  </DropdownMenuItem>
                )}
                {onRename && onDelete && <DropdownMenuSeparator />}
                {onDelete && (
                  <DropdownMenuItem
                    onClick={e => { e.preventDefault(); onDelete(e) }}
                    className="gap-2 text-destructive focus:text-destructive"
                  >
                    <Trash2 className="h-3.5 w-3.5" /> Supprimer
                  </DropdownMenuItem>
                )}
              </DropdownMenuContent>
            </DropdownMenu>
          )}
          <button
            onClick={e => e.preventDefault()}
            className="rounded-md p-1.5 text-muted-foreground hover:text-primary hover:bg-gray-100 transition-colors"
          >
            <Share2 className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
    </div>
  )
}

interface CreateCardProps {
  label: string
  onClick: () => void
}

export function CreateCard({ label, onClick }: CreateCardProps) {
  return (
    <button
      onClick={onClick}
      className="group flex flex-col items-center justify-center gap-3 overflow-hidden rounded-xl border-2 border-dashed border-border bg-white p-8 hover:border-primary/50 hover:bg-primary/5 transition-all duration-200 min-h-[260px]"
    >
      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-gray-100 group-hover:bg-primary/10 transition-colors">
        <span className="text-2xl font-light text-muted-foreground group-hover:text-primary transition-colors">+</span>
      </div>
      <p className="text-[13px] font-semibold text-muted-foreground group-hover:text-primary transition-colors">{label}</p>
    </button>
  )
}
