# Changelog

## [2026-04-29] — Modern UI Redesign & Flexible Hierarchy

### UI Redesign

**`components/app-header.tsx`**
- Replaced old header with pill-style navigation: Dashboard, Project, Usage, Help
- Removed User & Permissions link, bell icon, and user-profile avatar
- Logo: "H" icon + "HUB PERFORMANCE / AVIATION MANAGEMENT" text
- Active pill highlights based on current route (Project pill activates for `/`, `/entreprise/`, `/secteur/`, `/projet/`, `/scenario/`, `/wizard/`)

**`app/globals.css`**
- Increased border-radius from 4px to 8px (`--radius: 0.5rem`)

**`components/photo-card.tsx`** — new shared component
- `PhotoCard`: airport background image, name, creation date, 2 metrics, optional `code` badge, rename/delete dropdown (MoreHorizontal)
- `CreateCard`: dashed-border card with + icon for adding items
- Two default images: `AIRPORT_IMAGE` (planes/runway) for entreprises & projets, `SECTEUR_IMAGE` (industrial) for secteurs
- No DRAFT badge (removed)

### New Pages & Shells

**`components/app-shell.tsx`**
- Simple shell for the homepage only: header + scrollable main

**`components/app-shell-workspace.tsx`** — new
- Shell for all drill-down pages: sticky header + 260px sidebar + scrollable main
- No shadcn SidebarProvider dependency — plain div layout

**`components/workspace-sidebar.tsx`** — new
- Full collapsible hierarchy tree: Entreprise → Secteur → Projet → Scénario → Allocation / Mapping / Analyse
- Also shows **direct projets** (projets without a secteur) under each entreprise node
- Lazy-loads each level on expand
- Inline create / rename / delete via dialogs for all levels
- Auto-expands to active item based on current URL path

### Page Updates

**`app/page.tsx`** (Entreprises)
- Photo card grid with rename/delete dropdown on each card
- Create modal: Nom + Image de fond (optionnel) — no code field for entreprises

**`app/entreprise/[entrepriseId]/page.tsx`** (Secteurs + Projets directs)
- Two sections: Secteurs grid + Projets directs grid (shown only when direct projets exist)
- Two create buttons: "Projet direct" (secondary) + "Nouveau secteur" (primary)
- Projet direct modal: Nom + Code projet (optionnel) + Image de fond (optionnel)

**`app/secteur/[secteurId]/page.tsx`** (Projets)
- Projet create modal: Nom + Code projet (optionnel) + Image de fond (optionnel)
- Rename/delete modals for projets

**`app/projet/[projetId]/page.tsx`** (Scénarios)
- Breadcrumb adapts to hierarchy:
  - With secteur: `Entreprise / Secteur / Projet`
  - Without secteur: `Entreprise / Projet`
- Loads entreprise directly via `entreprise_id` when `secteur_id` is null

### Data Model Changes

**`lib/supabase.ts`** — updated types
- `Entreprise`: added `background_url: string | null`
- `Secteur`: added `background_url: string | null`
- `Projet`: added `code: string | null`, `background_url: string | null`, `entreprise_id: string | null`, made `secteur_id` nullable
- `Scenario`: added `background_url: string | null`

### Flexible Hierarchy

Projets can now exist without a secteur intermediary:
- A projet with `secteur_id = null` and `entreprise_id` set appears directly under an entreprise
- The entreprise page shows a "Projets directs" section for these
- The sidebar tree shows direct projets under the entreprise node (before secteurs)
- The projet page breadcrumb handles both cases

---

## Required SQL Migrations (run in Supabase)

```sql
-- Add background_url to all entity tables
ALTER TABLE entreprises ADD COLUMN IF NOT EXISTS background_url TEXT;
ALTER TABLE secteurs    ADD COLUMN IF NOT EXISTS background_url TEXT;
ALTER TABLE projets     ADD COLUMN IF NOT EXISTS background_url TEXT;
ALTER TABLE scenarios   ADD COLUMN IF NOT EXISTS background_url TEXT;

-- Add code to projets
ALTER TABLE projets ADD COLUMN IF NOT EXISTS code TEXT;

-- Flexible hierarchy: projets can belong directly to an entreprise (no secteur)
ALTER TABLE projets ADD COLUMN IF NOT EXISTS entreprise_id UUID REFERENCES entreprises(id);
ALTER TABLE projets ALTER COLUMN secteur_id DROP NOT NULL;
```

---

## Next Steps

- [ ] `app/scenario/[scenarioId]/page.tsx` — apply same WorkspaceShell + PhotoCard pattern for allocation runs
- [ ] `app/wizard/page.tsx` — review whether it needs to respect the new hierarchy
- [ ] Add `background_url` upload (file picker or Unsplash URL) with preview in create/edit modals
- [ ] Add `code` field (optionnel) to secteurs if needed
- [ ] RLS policies in Supabase for `entreprise_id` on projets (cascade delete / foreign key integrity)
- [ ] Consider a "move projet" action to reassign a direct projet to a secteur, or vice-versa
