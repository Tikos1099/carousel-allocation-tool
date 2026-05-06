# Changelog

## [2026-04-30] — Extraction moteur de formules + 3 bug fixes

### `formula_engine.py` — nouveau fichier (extrait de `api_app.py`)

Toute la logique d'évaluation des formules est maintenant isolée dans `formula_engine.py` à la racine. `api_app.py` importe les 5 fonctions depuis ce fichier.

```python
from formula_engine import (
    _split_formula_args, _find_comparison_in_cond,
    _rfind_op_at_depth0, _eval_condition, _eval_mapping_formula,
)
```

**Avantages :** plus facile à lire, modifier et débugger sans toucher au reste de l'API.

### Bug fixes

**Bug 1 — Fonctions texte non récursives** (`LEFT`, `RIGHT`, `MID`, `LEN`, `UPPER`, `LOWER`, `TRIM`, `TEXTBEFORE`, `TEXTAFTER`)

Avant : `if col in df.columns: return df[col]...` → retournait vide silencieusement si le 1er argument était une formule imbriquée.

Après : `src = _eval_mapping_formula(col, df)` → `LEFT(RIGHT(Col,5),3)`, `UPPER(TRIM(Col))`, etc. fonctionnent correctement.

**Bug 2 — `IF` avec condition booléenne (`ISBLANK`, `ISNUMBER`, `ISTEXT`)**

Avant : `_eval_condition("ISBLANK(Col)")` ne trouvait pas d'opérateur de comparaison et retournait `[True, True, …]` → la branche vraie du IF était **toujours** prise.

Après : fallback → évalue la condition comme formule et caste en `bool`.

**Bug 3 — Comparaison string au lieu de numérique dans `_eval_condition`**

Avant : quand le côté droit est une colonne ou formule (ex. `p < Par1`, `p < Par2+Par3`), les deux côtés étaient castés en `str` :
- Colonne absente → `""` → `"0.xxx" < ""` toujours **False**
- Résultat NaN → `"nan"` → `"0.xxx" < "nan"` toujours **True** (`'0' < 'n'`)
- Ces deux cas combinés causaient le symptôme **"toujours Car 2"** dans `LET(p,ALEA(),IF(…))`.

Après : `pd.to_numeric` d'abord → comparaison numérique si le côté droit a des valeurs valides, string sinon.

---

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
