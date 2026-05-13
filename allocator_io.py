"""
allocator_io.py — Lecture des données d'entrée et écriture des fichiers de sortie
==================================================================================

RÔLE DANS LE SYSTÈME
--------------------
Ce fichier fait le lien entre l'algorithme d'allocation (allocator_engine.py)
et les fichiers Excel/CSV que l'utilisateur reçoit en sortie.

Il fait DEUX choses principales :
  1. Lire le fichier Excel de vols → renommer les colonnes vers les noms standards
  2. Écrire les résultats → timeline colorée, heatmap, résumés TXT/CSV

Il contient aussi _readjust_terminal_allocations(), qui applique les règles
de réajustement (multi, narrow→wide, extras) sur les vols non-assignés.

ORGANISATION DU FICHIER
------------------------
  1. Utilitaires I/O généraux         : _normalize_hex_color, _extract_*, etc.
  2. Lecture du fichier de vols       : read_flights_excel
  3. Maps d'informations sur les vols : _build_flight_*_map, _format_*
  4. Écriture de la timeline Excel    : write_timeline_excel
  5. Écriture de la heatmap Excel     : write_heatmap_excel
  6. Écriture des résumés TXT/CSV     : write_summary_txt, write_summary_csv
  7. Calcul de la heatmap             : _compute_occupancy_arrays, _build_heatmap_*
  8. Réajustement terminal            : _readjust_terminal_allocations + helpers

POUR MODIFIER
-------------
- Ajouter une colonne au fichier de vols            : modifier read_flights_excel (rename_map)
- Changer les couleurs par défaut de la timeline    : modifier write_timeline_excel
- Changer le format des cellules de la timeline     : modifier _format_flight_with_info
- Changer les règles de réajustement (ordre, logique) : modifier _readjust_terminal_allocations
"""

from __future__ import annotations

import ast
import re

import numpy as np
import pandas as pd

from allocator import (
    CarouselCapacity,
    allocate_with_fixed_assignments,
    build_timeline_from_assignments,
    compute_single_assignment_segments,
)


# ── 1. Utilitaires I/O généraux ───────────────────────────────────────────────

def _normalize_hex_color(value: str, fallback: str) -> str:
    """Valide et normalise une couleur hexadécimale (#RRGGBB).

    Ajoute le '#' si absent, retourne le fallback si la valeur est invalide.
    Exemples : "D32F2F" → "#D32F2F", None → fallback.
    """
    if value is None:
        return fallback
    s = str(value).strip()
    if not s:
        return fallback
    if not s.startswith("#"):
        s = "#" + s
    if not re.fullmatch(r"#[0-9A-Fa-f]{6}", s):
        return fallback
    return s.upper()


def _extract_flights(cell_value) -> list[str]:
    """Extrait la liste des numéros de vol depuis le contenu d'une cellule timeline.

    Une cellule peut contenir "AB123, CD456" → ["AB123", "CD456"].
    Retourne [] si la cellule est vide ou NaN.
    """
    if cell_value is None:
        return []
    s = str(cell_value).strip()
    if not s or s.lower() == "nan":
        return []
    return [p.strip() for p in s.split(",") if p.strip()]


def _extract_terminal_from_column(col_name) -> str | None:
    """Extrait le nom du terminal depuis un nom de colonne du type "T1-C1".

    Les colonnes timeline sont nommées "TERMINAL-CARROUSEL" (ex: "T1-C1").
    Cette fonction retourne la partie avant le "-" (ex: "T1").
    Retourne None si le format n'est pas reconnu.
    """
    if col_name is None:
        return None
    s = str(col_name).strip()
    if not s or s.lower() == "nan":
        return None
    if "-" in s:
        terminal_part = s.split("-", 1)[0].strip()
        return terminal_part or None
    return None


def _extract_carousel_from_column(col_name) -> str | None:
    """Extrait le nom du carrousel depuis un nom de colonne du type "T1-C1".

    Les colonnes timeline sont nommées "TERMINAL-CARROUSEL" (ex: "T1-C1").
    Cette fonction retourne la partie après le "-" (ex: "C1").
    Si le nom ne contient pas de "-", retourne le nom complet.
    """
    if col_name is None:
        return None
    s = str(col_name).strip()
    if not s or s.lower() == "nan":
        return None
    if "-" in s:
        carousel_part = s.split("-", 1)[1].strip()
        return carousel_part or None
    return s


# ── 2. Lecture du fichier de vols ──────────────────────────────────────────────

def read_flights_excel(file) -> pd.DataFrame:
    """Lit un fichier Excel de vols et renomme les colonnes vers les noms standards.

    Les colonnes standards attendues par l'allocateur sont :
        DepartureTime, FlightNumber, Category, Positions,
        MakeupOpening, MakeupClosing

    Si le fichier utilise des noms différents (ex: "departure time", "Heure de départ"),
    cette fonction les renomme automatiquement.

    Pour ajouter un alias : ajouter une entrée dans rename_map.
    """
    df = pd.read_excel(file)
    rename_map = {
        "heur de départ": "DepartureTime",
        "Heure de départ": "DepartureTime",
        "departure time": "DepartureTime",
        "Departure time": "DepartureTime",
        "flight number": "FlightNumber",
        "Flight number": "FlightNumber",
        "category": "Category",
        "Category": "Category",
        "position": "Positions",
        "Position": "Positions",
        "make up opening": "MakeupOpening",
        "Make up opening": "MakeupOpening",
        "make up closing": "MakeupClosing",
        "Make up closing": "MakeupClosing",
    }
    df = df.rename(columns={c: rename_map.get(c, c) for c in df.columns})
    return df


# ── 3. Maps d'informations sur les vols ───────────────────────────────────────

def _build_flight_category_map(flights_out: pd.DataFrame) -> dict[str, str]:
    """Construit un dict {numéro_vol → catégorie} depuis le DataFrame de résultats.

    Utilise "FinalCategory" si disponible (après réajustement narrow→wide),
    sinon "Category". Valeurs retournées : "wide" ou "narrow" (en minuscules).
    Les vols avec catégorie inconnue ne sont pas inclus dans le dict.
    """
    mapping: dict[str, str] = {}
    if flights_out is None:
        return mapping
    category_col = "FinalCategory" if "FinalCategory" in flights_out.columns else "Category"
    if "FlightNumber" not in flights_out.columns or category_col not in flights_out.columns:
        return mapping
    for _, row in flights_out.iterrows():
        flight = str(row.get("FlightNumber", "")).strip()
        if not flight or flight.lower() == "nan" or flight in mapping:
            continue
        cat = str(row.get(category_col, "")).strip().lower()
        if cat in ("wide", "narrow"):
            mapping[flight] = cat
    return mapping


def _format_category_short(category_value) -> str:
    """Formate une valeur de catégorie en abréviation courte.

    "Wide" → "W", "Narrow" → "N", vide → "?", autre → majuscules.
    Utilisé pour afficher la catégorie dans les cellules de la timeline.
    """
    s = str(category_value or "").strip().lower()
    if s in ("wide", "w"):
        return "W"
    if s in ("narrow", "n"):
        return "N"
    if not s or s == "nan":
        return "?"
    return s.upper()


def _format_positions_value(positions_value) -> str:
    """Formate une valeur de positions pour affichage (supprime les .0 inutiles).

    12.0 → "12", 12.5 → "12.5", None → "?", "nan" → "?".
    """
    if positions_value is None:
        return "?"
    try:
        if pd.isna(positions_value):
            return "?"
    except Exception:
        pass
    s = str(positions_value).strip()
    if not s or s.lower() == "nan":
        return "?"
    try:
        f = float(positions_value)
        return str(int(f)) if f.is_integer() else str(f)
    except Exception:
        return s


def _build_flight_info_map(flights_out: pd.DataFrame) -> dict[str, tuple[object, object]]:
    """Construit un dict {numéro_vol → (catégorie, positions)} depuis les résultats.

    Utilisé par _format_flight_with_info pour afficher dans les cellules Excel
    la catégorie (W/N) et le nombre de positions d'un vol.
    """
    mapping: dict[str, tuple[object, object]] = {}
    if flights_out is None:
        return mapping
    if "FlightNumber" not in flights_out.columns:
        return mapping
    category_col = "FinalCategory" if "FinalCategory" in flights_out.columns else "Category"
    for _, row in flights_out.iterrows():
        flight = str(row.get("FlightNumber", "")).strip()
        if not flight or flight.lower() == "nan" or flight in mapping:
            continue
        mapping[flight] = (row.get(category_col), row.get("Positions"))
    return mapping


def _format_flight_with_info(
    flight: str,
    info_map: dict[str, tuple[object, object]],
    pos_override: object | None = None,
) -> str:
    """Formate un numéro de vol avec sa catégorie et son nombre de positions.

    Exemple de sortie : "AB123 ( C= W P=8)"
    pos_override permet de remplacer le nombre de positions par une valeur calculée
    (utilisé quand un vol est splitté sur plusieurs carrousels).
    """
    flight = str(flight or "").strip()
    if not flight or not info_map:
        return flight
    info = info_map.get(flight)
    if info is None:
        return flight
    cat_value, pos_value = info
    if pos_override is not None:
        pos_value = pos_override
    return f"{flight} ( C= {_format_category_short(cat_value)} P={_format_positions_value(pos_value)})"


def _format_flight_cell(
    flights: list[str],
    info_map: dict[str, tuple[object, object]],
    pos_map: dict[tuple[str, str], int] | None = None,
    column: str | None = None,
) -> str:
    """Formate le contenu d'une cellule de la timeline pour l'affichage Excel.

    Plusieurs vols dans une même cellule sont séparés par ", ".
    Utilise pos_map pour afficher le bon nombre de positions par carrousel
    (important quand un vol est splitté : positions différentes par carrousel).
    """
    carousel_base = _extract_carousel_from_column(column) if column else None
    parts: list[str] = []
    for flight in flights:
        pos_override = pos_map.get((str(flight).strip(), carousel_base)) if pos_map and carousel_base else None
        parts.append(_format_flight_with_info(flight, info_map, pos_override))
    return ", ".join(parts)


def _normalize_segments_io(value: object) -> list[dict[str, object]]:
    """Normalise la valeur de la colonne AssignmentSegments vers une liste de dicts.

    AssignmentSegments peut être stockée comme : liste Python, dict, chaîne JSON,
    ou None. Cette fonction retourne toujours une liste de dicts (peut être vide).
    Utilisée partout où on lit les segments d'assignation depuis un DataFrame.
    """
    if value is None:
        return []
    if isinstance(value, list):
        return [seg for seg in value if isinstance(seg, dict)]
    if isinstance(value, dict):
        return [value]
    if isinstance(value, str):
        text = value.strip()
        if not text or text.lower() in ("nan", "none"):
            return []
        try:
            parsed = ast.literal_eval(text)
        except Exception:
            return []
        return _normalize_segments_io(parsed)
    return []


def _build_flight_segment_positions_map(flights_out: pd.DataFrame | None) -> dict[tuple[str, str], int]:
    """Construit un dict {(vol, carrousel) → nombre_de_positions} depuis AssignmentSegments.

    Utilisé pour afficher le bon nombre de positions par carrousel dans les cellules
    de la timeline (cas des vols splittés sur plusieurs carrousels).

    Clé : (numéro_vol, nom_carrousel), valeur : wide_used + narrow_used.
    """
    mapping: dict[tuple[str, str], int] = {}
    if flights_out is None or "FlightNumber" not in flights_out.columns:
        return mapping
    if "AssignmentSegments" not in flights_out.columns:
        return mapping
    for _, row in flights_out.iterrows():
        flight = str(row.get("FlightNumber", "")).strip()
        if not flight or flight.lower() == "nan":
            continue
        for seg in _normalize_segments_io(row.get("AssignmentSegments")):
            carousel = str(seg.get("carousel", "")).strip()
            if not carousel:
                continue
            positions = int(seg.get("wide_used", 0)) + int(seg.get("narrow_used", 0))
            key = (flight, carousel)
            if positions > mapping.get(key, 0):
                mapping[key] = positions
    return mapping


def _build_flight_status_map(flights_out: pd.DataFrame | None) -> dict[str, str]:
    """Construit un dict {vol → statut} pour décider la couleur de la cellule.

    Statuts possibles :
        "narrow_wide"  : vol Narrow réassigné sur un carrousel Wide
        "split"        : vol réparti sur plusieurs carrousels
        "wide"         : vol Wide normal
        "narrow"       : vol Narrow normal
        "other"        : catégorie inconnue

    Ce statut est utilisé pour appliquer les couleurs prioritaires (split, narrow_wide)
    avant la couleur de base (par catégorie, vol, ou terminal).
    """
    mapping: dict[str, str] = {}
    if flights_out is None or "FlightNumber" not in flights_out.columns:
        return mapping
    for _, row in flights_out.iterrows():
        flight = str(row.get("FlightNumber", "")).strip()
        if not flight or flight.lower() == "nan" or flight in mapping:
            continue
        changed = str(row.get("CategoryChanged", "")).strip().upper() == "YES"
        split_count = 0
        try:
            split_val = row.get("SplitCount", 0)
            if not pd.isna(split_val):
                split_count = int(split_val)
        except Exception:
            pass
        if split_count <= 1:
            assigned = row.get("AssignedCarousels", "") or row.get("AssignedCarousel", "")
            if isinstance(assigned, str) and "+" in assigned:
                split_count = 2
        if changed:
            mapping[flight] = "narrow_wide"
        elif split_count > 1:
            mapping[flight] = "split"
        else:
            cat = str(row.get("FinalCategory", row.get("Category", "")) or "").strip().lower()
            mapping[flight] = "wide" if cat in ("wide", "w") else "narrow" if cat in ("narrow", "n") else "other"
    return mapping


def _build_flight_terminal_map(flights_out: pd.DataFrame) -> dict[str, str]:
    """Construit un dict {vol → terminal} depuis le DataFrame de résultats.

    Utilisé en mode de couleur "terminal" pour identifier quel terminal
    dessert chaque vol, et lui associer la bonne couleur.
    """
    mapping: dict[str, str] = {}
    if flights_out is None:
        return mapping
    if "FlightNumber" not in flights_out.columns or "Terminal" not in flights_out.columns:
        return mapping
    for _, row in flights_out.iterrows():
        flight = str(row.get("FlightNumber", "")).strip()
        if not flight or flight.lower() == "nan" or flight in mapping:
            continue
        term = str(row.get("Terminal", "")).strip()
        if term and term.lower() != "nan":
            mapping[flight] = term
    return mapping


def _build_flight_color_map(
    flights_out: pd.DataFrame | None,
    timeline_df: pd.DataFrame,
    palette: list[str],
) -> dict[str, str]:
    """Construit un dict {vol → couleur} en mode de couleur "flight".

    Chaque vol reçoit une couleur unique tirée de la palette (cyclique).
    Si flights_out n'est pas disponible, les vols sont extraits depuis la timeline.
    Les vols sont triés par ordre alphabétique pour avoir des couleurs stables.
    """
    flights: list[str] = []
    if flights_out is not None and "FlightNumber" in flights_out.columns:
        flights = [str(x).strip() for x in flights_out["FlightNumber"].dropna().tolist()]
        flights = [f for f in flights if f and f.lower() != "nan"]
    if not flights:
        for row in timeline_df.itertuples(index=False, name=None):
            for cell in row:
                flights.extend(_extract_flights(cell))
    unique_flights: list[str] = []
    seen_flights: set[str] = set()
    for f in flights:
        if f not in seen_flights:
            seen_flights.add(f)
            unique_flights.append(f)
    return {flight: palette[idx % len(palette)] for idx, flight in enumerate(sorted(unique_flights))}


def _build_terminal_color_map(
    flights_out: pd.DataFrame | None,
    timeline_df: pd.DataFrame,
    palette: list[str],
) -> dict[str, str]:
    """Construit un dict {terminal → couleur} en mode de couleur "terminal".

    Chaque terminal reçoit une couleur unique tirée de la palette (cyclique).
    Si flights_out n'est pas disponible, les terminaux sont extraits depuis
    les noms de colonnes de la timeline (format "TERMINAL-CARROUSEL").
    """
    terminals: list[str] = []
    if flights_out is not None and "Terminal" in flights_out.columns:
        terminals = [str(x).strip() for x in flights_out["Terminal"].dropna().tolist()]
        terminals = [t for t in terminals if t and t.lower() != "nan"]
    if not terminals:
        for col in timeline_df.columns:
            term = _extract_terminal_from_column(col)
            if term:
                terminals.append(term)
    unique_terminals: list[str] = []
    seen_terminals: set[str] = set()
    for t in terminals:
        if t not in seen_terminals:
            seen_terminals.add(t)
            unique_terminals.append(t)
    return {term: palette[idx % len(palette)] for idx, term in enumerate(sorted(unique_terminals))}


# ── 4. Écriture de la timeline Excel ──────────────────────────────────────────

# Palette de couleurs pastel utilisée pour les modes "flight" et "terminal".
_TIMELINE_PALETTE = [
    "#F8CBAD", "#C6E0B4", "#BDD7EE", "#FFE699", "#D9D2E9", "#B4C6E7",
    "#F4B183", "#A9D08E", "#DDEBF7", "#FFF2CC", "#E2EFDA", "#FCE4D6",
]


def write_timeline_excel(
    path: str,
    timeline_df: pd.DataFrame,
    flights_out: pd.DataFrame | None = None,
    *,
    color_mode: str = "category",
    wide_color: str = "#D32F2F",
    narrow_color: str = "#FFEBEE",
    split_color: str = "#FFC107",
    narrow_wide_color: str = "#00B894",
    extra_columns: list[str] | None = None,
    extra_header_color: str = "#E6DFF7",
    extra_border_color: str = "#8064A2",
    extra_summary: pd.DataFrame | None = None,
    extra_sheet_name: str = "Summary extra makeups",
):
    """Écrit le fichier Excel de planning (timeline) avec mise en couleur.

    Paramètres principaux :
        path           : chemin du fichier Excel à créer
        timeline_df    : DataFrame dont les lignes sont des horodatages et les
                         colonnes sont des carrousels (valeurs = numéros de vols)
        flights_out    : DataFrame de résultats d'allocation (pour les couleurs)
        color_mode     : "category" (Wide/Narrow), "flight" (un vol = une couleur),
                         "terminal" (un terminal = une couleur)

    Paramètres de couleur :
        wide_color, narrow_color : couleurs des vols Wide et Narrow en mode category
        split_color              : couleur des vols splittés (prioritaire)
        narrow_wide_color        : couleur des vols Narrow→Wide (prioritaire)

    Colonnes EXTRA :
        extra_columns    : noms de colonnes qui reçoivent un formatage spécial (bordure)
        extra_header_color, extra_border_color : couleurs pour ces colonnes
        extra_summary    : DataFrame optionnel écrit dans un onglet séparé
    """
    # Normalisation et validation des paramètres de couleur
    wide_color = _normalize_hex_color(wide_color, "#D32F2F")
    narrow_color = _normalize_hex_color(narrow_color, "#FFEBEE")
    split_color = _normalize_hex_color(split_color, "#FFC107")
    narrow_wide_color = _normalize_hex_color(narrow_wide_color, "#00B894")
    color_mode = str(color_mode or "category").strip().lower()
    if color_mode not in ("category", "flight", "terminal"):
        color_mode = "category"

    extra_columns = extra_columns or []
    extra_columns_set = set(extra_columns)
    extra_header_color = _normalize_hex_color(extra_header_color, "#E6DFF7")
    extra_border_color = _normalize_hex_color(extra_border_color, "#8064A2")

    # Construction des maps d'informations vol (catégorie, positions, statut)
    flight_info = _build_flight_info_map(flights_out)
    segment_positions = _build_flight_segment_positions_map(flights_out)
    status_map = _build_flight_status_map(flights_out)

    with pd.ExcelWriter(path, engine="xlsxwriter") as writer:
        # Écriture du DataFrame timeline avec colonnes Timestamp et Legend
        timeline_with_timestamp = timeline_df.copy()
        timeline_with_timestamp.insert(0, "Timestamp", timeline_with_timestamp.index)
        timeline_with_timestamp.insert(1, "Legend / Filter", "")
        timeline_with_timestamp.to_excel(writer, index=False, sheet_name="Planning")

        if extra_summary is not None:
            extra_summary.to_excel(writer, index=False, sheet_name=extra_sheet_name)

        workbook = writer.book
        worksheet = writer.sheets["Planning"]

        # Formats Excel réutilisables
        header_format = workbook.add_format({"bold": True, "bg_color": "#D9D9D9", "border": 1, "align": "center", "valign": "vcenter"})
        header_format_extra = workbook.add_format({"bold": True, "bg_color": extra_header_color, "border": 1, "align": "center", "valign": "vcenter"})
        ts_format = workbook.add_format({"num_format": "yyyy-mm-dd hh:mm"})

        # Largeurs de colonnes : horodatage large, colonnes de données moyennes
        worksheet.set_column(0, 0, 22, ts_format)
        worksheet.set_column(1, 1, 16)
        if timeline_with_timestamp.shape[1] > 2:
            worksheet.set_column(2, timeline_with_timestamp.shape[1] - 1, 18)

        # En-têtes : les colonnes EXTRA ont un format distinct
        for col_idx, col_name in enumerate(timeline_with_timestamp.columns):
            fmt = header_format_extra if col_name in extra_columns_set else header_format
            worksheet.write(0, col_idx, col_name, fmt)

        worksheet.freeze_panes(1, 2)

        # Caches pour éviter de recréer les mêmes formats Excel à chaque cellule
        fill_cache: dict[str, object] = {}
        legend_cache: dict[str, object] = {}

        def _fill(color: str, is_extra: bool):
            """Retourne (et met en cache) un format de remplissage de cellule."""
            key = f"{color}|extra" if is_extra else color
            if key not in fill_cache:
                fmt = {"bg_color": color, "border": 1, "text_wrap": True, "valign": "top"}
                if is_extra:
                    fmt["border"] = 2
                    fmt["border_color"] = extra_border_color
                fill_cache[key] = workbook.add_format(fmt)
            return fill_cache[key]

        def _legend(color: str):
            """Retourne (et met en cache) un format pour la légende de couleur."""
            if color not in legend_cache:
                legend_cache[color] = workbook.add_format({"bg_color": color, "border": 1, "bold": True})
            return legend_cache[color]

        # Écriture de la légende dans la colonne "Legend / Filter"
        row_ptr = 1
        if color_mode == "category":
            worksheet.write(row_ptr, 1, "Wide", _legend(wide_color))
            row_ptr += 1
            worksheet.write(row_ptr, 1, "Narrow", _legend(narrow_color))
            row_ptr += 1
        worksheet.write(row_ptr, 1, "Split", _legend(split_color))
        row_ptr += 1
        worksheet.write(row_ptr, 1, "Narrow to Wide", _legend(narrow_wide_color))
        row_ptr += 1

        if color_mode == "flight":
            flight_color = _build_flight_color_map(flights_out, timeline_df, _TIMELINE_PALETTE)
            for flight in sorted(flight_color.keys()):
                worksheet.write(row_ptr, 1, flight, _legend(flight_color[flight]))
                row_ptr += 1
        elif color_mode == "terminal":
            terminal_color = _build_terminal_color_map(flights_out, timeline_df, _TIMELINE_PALETTE)
            for term in sorted(terminal_color.keys()):
                worksheet.write(row_ptr, 1, term, _legend(terminal_color[term]))
                row_ptr += 1

        if timeline_df.empty or len(timeline_df.columns) == 0:
            return

        def _rule_color(fls: list[str]) -> str | None:
            """Retourne la couleur prioritaire (split ou narrow_wide) si applicable."""
            if not status_map:
                return None
            statuses = [status_map.get(f) for f in fls]
            if "narrow_wide" in statuses:
                return narrow_wide_color
            if "split" in statuses:
                return split_color
            return None

        # Pré-calcul des maps de couleur (une seule fois, avant la boucle)
        cat_map: dict[str, str] = {}
        terminal_color: dict[str, str] = {}
        flight_terminal: dict[str, str] = {}
        flight_color: dict[str, str] = {}
        if color_mode == "category":
            cat_map = _build_flight_category_map(flights_out)
        elif color_mode == "terminal":
            terminal_color = _build_terminal_color_map(flights_out, timeline_df, _TIMELINE_PALETTE)
            flight_terminal = _build_flight_terminal_map(flights_out)
        else:
            flight_color = _build_flight_color_map(flights_out, timeline_df, _TIMELINE_PALETTE)

        # Écriture des cellules de données avec couleur selon le mode choisi
        for row_idx in range(len(timeline_df)):
            for col_idx in range(len(timeline_df.columns)):
                cell_value = timeline_df.iat[row_idx, col_idx]
                is_extra = timeline_df.columns[col_idx] in extra_columns_set
                fls = _extract_flights(cell_value)
                if not fls:
                    continue
                display_value = _format_flight_cell(fls, flight_info, segment_positions, timeline_df.columns[col_idx])
                rule_color = _rule_color(fls)

                if color_mode == "category":
                    base_color = None
                    for f in fls:
                        cat = cat_map.get(f)
                        if cat == "wide":
                            base_color = wide_color
                            break
                        if cat == "narrow":
                            base_color = narrow_color
                    color = rule_color or base_color
                elif color_mode == "terminal":
                    term = next((flight_terminal.get(f) for f in fls if flight_terminal.get(f)), None)
                    if not term:
                        term = _extract_terminal_from_column(timeline_df.columns[col_idx])
                    base_color = terminal_color.get(term) if term else None
                    color = rule_color or base_color
                else:
                    color = rule_color or (flight_color.get(fls[0]) if fls else None)

                fmt = _fill(color, is_extra) if color else None
                if fmt:
                    worksheet.write(row_idx + 1, col_idx + 2, display_value, fmt)
                else:
                    worksheet.write(row_idx + 1, col_idx + 2, display_value)


# ── 5. Écriture de la heatmap Excel ───────────────────────────────────────────

def write_heatmap_excel(
    path: str,
    sheets: dict[str, pd.DataFrame],
    *,
    mode: str = "occupied",
):
    """Écrit le fichier Excel de heatmap (positions occupées ou libres).

    La heatmap montre, pour chaque intervalle de temps et chaque carrousel,
    le nombre de positions Wide/Narrow occupées ou libres.
    La mise en couleur est une échelle 2 couleurs (rouge clair → rouge foncé).

    Paramètres :
        path   : chemin du fichier Excel à créer
        sheets : dict {nom_onglet → DataFrame} (un onglet par terminal si multi-terminal)
        mode   : "occupied" (positions utilisées) ou "free" (positions disponibles)
                 En mode "free", l'échelle de couleur est inversée.
    """
    if not sheets:
        sheets = {"Planning": pd.DataFrame()}

    mode = str(mode or "occupied").strip().lower()
    if mode not in ("occupied", "free"):
        mode = "occupied"

    # L'échelle de couleur est inversée selon le mode :
    # occupied → clair=peu occupé, foncé=très occupé
    # free     → clair=peu libre, foncé=très libre
    min_color, max_color = "#FFEBEE", "#D32F2F"
    if mode == "free":
        min_color, max_color = max_color, min_color

    def _safe_sheet_name(name: str, used: set[str]) -> str:
        """Nettoie et déduplique le nom d'un onglet Excel (max 31 caractères)."""
        base = re.sub(r"[:\\/?*\[\]]", " ", str(name or "")).strip() or "Sheet"
        base = base[:31]
        candidate = base
        idx = 1
        while candidate in used:
            suffix = f"_{idx}"
            candidate = base[:31 - len(suffix)] + suffix
            idx += 1
        used.add(candidate)
        return candidate

    with pd.ExcelWriter(path, engine="xlsxwriter") as writer:
        workbook = writer.book
        header_format = workbook.add_format({"bold": True, "bg_color": "#D9D9D9", "border": 1, "align": "center", "valign": "vcenter"})
        ts_format = workbook.add_format({"num_format": "yyyy-mm-dd hh:mm"})
        num_format = workbook.add_format({"num_format": "0", "align": "center"})

        used_names: set[str] = set()
        for sheet_name, df in sheets.items():
            sheet_with_timestamp = df.copy()
            if "Timestamp" in sheet_with_timestamp.columns:
                sheet_with_timestamp = sheet_with_timestamp.drop(columns=["Timestamp"])
            sheet_with_timestamp.insert(0, "Timestamp", sheet_with_timestamp.index)

            safe_name = _safe_sheet_name(sheet_name, used_names)
            sheet_with_timestamp.to_excel(writer, index=False, sheet_name=safe_name)
            worksheet = writer.sheets[safe_name]

            for col_idx, col_name in enumerate(sheet_with_timestamp.columns):
                worksheet.write(0, col_idx, col_name, header_format)

            worksheet.set_column(0, 0, 22, ts_format)
            for col_idx, col_name in enumerate(sheet_with_timestamp.columns[1:], start=1):
                width = max(8, min(30, len(str(col_name)) + 2))
                worksheet.set_column(col_idx, col_idx, width, num_format)

            worksheet.freeze_panes(1, 0)

            data_rows, data_cols = len(sheet_with_timestamp), sheet_with_timestamp.shape[1] - 1
            if data_rows > 0 and data_cols > 0:
                worksheet.conditional_format(1, 1, data_rows, data_cols, {
                    "type": "2_color_scale", "min_color": min_color, "max_color": max_color,
                })


# ── 6. Écriture des résumés TXT/CSV ───────────────────────────────────────────

def write_summary_txt(path: str, flights_out: pd.DataFrame, extra_cols: list[str] | None = None):
    """Écrit un résumé lisible par humain (fichier .txt) des résultats d'allocation.

    Une ligne par vol, triée par heure de départ. Colonnes toujours affichées :
        DepartureTime, FlightNumber, Category, Positions, MakeupOpening,
        MakeupClosing, AssignedCarousel
    extra_cols : colonnes supplémentaires à ajouter si présentes dans flights_out.
    """
    cols = ["DepartureTime", "FlightNumber", "Category", "Positions", "MakeupOpening", "MakeupClosing", "AssignedCarousel"]
    existing = [c for c in cols if c in flights_out.columns]
    extra_cols = [c for c in (extra_cols or []) if c in flights_out.columns and c not in existing]
    s = flights_out.sort_values("DepartureTime")[existing + extra_cols]
    with open(path, "w", encoding="utf-8") as f:
        for _, r in s.iterrows():
            base = (
                f"{r.get('DepartureTime')} | {r.get('FlightNumber')} | {r.get('Category')} | "
                f"pos={r.get('Positions')} | open={r.get('MakeupOpening')} | close={r.get('MakeupClosing')} | "
                f"carousel={r.get('AssignedCarousel')}"
            )
            if extra_cols:
                extras = " | ".join([f"{c}={r.get(c)}" for c in extra_cols])
                f.write(f"{base} | {extras}\n")
            else:
                f.write(f"{base}\n")


def write_summary_csv(path: str, flights_out: pd.DataFrame):
    """Écrit le DataFrame de résultats trié par heure de départ en fichier CSV."""
    flights_out.sort_values("DepartureTime").to_csv(path, index=False, encoding="utf-8")


# ── 7. Calcul de la heatmap ────────────────────────────────────────────────────

def _has_assignment_segments(flights_df: pd.DataFrame) -> bool:
    """Retourne True si au moins un vol a des segments d'assignation non vides.

    Utilisé pour éviter de recalculer les segments si déjà présents.
    """
    if flights_df is None or "AssignmentSegments" not in flights_df.columns:
        return False
    return flights_df["AssignmentSegments"].apply(lambda v: len(_normalize_segments_io(v)) > 0).any()


def _ensure_segments_for_heatmap(flights_df: pd.DataFrame, caps: dict[str, CarouselCapacity]) -> pd.DataFrame:
    """S'assure que le DataFrame contient la colonne AssignmentSegments pour la heatmap.

    Si les segments sont déjà présents → retourne tel quel.
    Sinon → les calcule via compute_single_assignment_segments().
    En cas d'erreur → retourne le DataFrame avec des segments vides ([] par défaut).
    """
    if flights_df is None:
        return pd.DataFrame()
    if flights_df.empty or not caps:
        out = flights_df.copy()
        if "AssignmentSegments" not in out.columns:
            out["AssignmentSegments"] = [[] for _ in range(len(out))]
        return out
    if _has_assignment_segments(flights_df):
        return flights_df
    try:
        return compute_single_assignment_segments(flights_df, caps)
    except Exception:
        out = flights_df.copy()
        out["AssignmentSegments"] = [[] for _ in range(len(out))]
        return out


def _compute_occupancy_arrays(
    flights_df: pd.DataFrame,
    timeline_index: pd.DatetimeIndex,
    carousels: list[str],
) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    """Calcule les tableaux d'occupation (positions utilisées) pour chaque carrousel.

    Retourne deux dicts {nom_carrousel → array numpy de longueur len(timeline_index)} :
        usage_wide   : positions Wide utilisées à chaque intervalle de temps
        usage_narrow : positions Narrow utilisées à chaque intervalle de temps

    Pour chaque vol, on cherche les indices de la timeline qui tombent dans la fenêtre
    [MakeupOpening, MakeupClosing] et on incrémente les arrays correspondants.
    """
    size = len(timeline_index)
    usage_wide = {c: np.zeros(size, dtype=int) for c in carousels}
    usage_narrow = {c: np.zeros(size, dtype=int) for c in carousels}
    if flights_df is None or flights_df.empty or size == 0:
        return usage_wide, usage_narrow

    for _, row in flights_df.iterrows():
        open_t = pd.Timestamp(row.get("MakeupOpening"))
        close_t = pd.Timestamp(row.get("MakeupClosing"))
        if pd.isna(open_t) or pd.isna(close_t) or close_t <= open_t:
            continue
        start_idx = max(0, timeline_index.searchsorted(open_t, side="right") - 1)
        end_idx = min(size, timeline_index.searchsorted(close_t, side="left"))
        if start_idx >= end_idx:
            continue
        for seg in _normalize_segments_io(row.get("AssignmentSegments")):
            carousel = str(seg.get("carousel", "")).strip()
            if not carousel or carousel not in usage_wide:
                continue
            try:
                wide_used = int(seg.get("wide_used", 0))
            except Exception:
                wide_used = 0
            try:
                narrow_used = int(seg.get("narrow_used", 0))
            except Exception:
                narrow_used = 0
            if wide_used == 0 and narrow_used == 0:
                continue
            usage_wide[carousel][start_idx:end_idx] += wide_used
            usage_narrow[carousel][start_idx:end_idx] += narrow_used

    return usage_wide, usage_narrow


def _extract_extra_carousels(columns: list[str], term: str | None = None) -> list[str]:
    """Extrait les noms des carrousels EXTRA depuis les colonnes de la timeline.

    Les carrousels EXTRA ont un nom commençant par "EXTRA" (ex: "EXTRA1", "EXTRA2").
    Si term est fourni, cherche les colonnes préfixées par "TERM-" (ex: "T1-EXTRA1").
    Retourne une liste dédupliquée dans l'ordre d'apparition.
    """
    extras: list[str] = []
    prefix = f"{term}-" if term else None
    for col in columns or []:
        name = str(col)
        base = name[len(prefix):] if prefix and name.startswith(prefix) else (name if not prefix else None)
        if base and base.upper().startswith("EXTRA"):
            extras.append(base)
    seen_extras: set[str] = set()
    unique_extras: list[str] = []
    for e in extras:
        if e not in seen_extras:
            seen_extras.add(e)
            unique_extras.append(e)
    return unique_extras


def _add_extras_to_caps(
    caps: dict[str, CarouselCapacity] | None,
    extras: list[str],
    extra_cap: CarouselCapacity | None,
) -> dict[str, CarouselCapacity]:
    """Ajoute les carrousels EXTRA dans le dict de capacités si pas déjà présents.

    Utilisé pour construire le dict de capacités complet (carrousels normaux + EXTRA)
    avant de calculer la heatmap. Ne modifie pas le dict original.
    """
    out = dict(caps or {})
    if extra_cap is None:
        return out
    for extra in extras:
        if extra not in out:
            out[extra] = CarouselCapacity(int(extra_cap.wide), int(extra_cap.narrow))
    return out


def _build_heatmap_frames(
    flights_df: pd.DataFrame,
    timeline_index: pd.DatetimeIndex,
    caps: dict[str, CarouselCapacity],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Construit les DataFrames "occupé" et "libre" pour la heatmap.

    Retourne deux DataFrames indexés par timeline_index, avec une colonne
    par combinaison (carrousel, type_position) : "C1_Wide", "C1_Narrow", etc.
        occupied_df : positions utilisées à chaque instant
        free_df     : positions libres = capacité - occupé
    """
    flights_seg = _ensure_segments_for_heatmap(flights_df, caps)
    carousels = list(caps.keys())
    usage_wide, usage_narrow = _compute_occupancy_arrays(flights_seg, timeline_index, carousels)

    occupied_data: dict[str, object] = {}
    free_data: dict[str, object] = {}
    for carousel in carousels:
        wide_occ = usage_wide.get(carousel, np.zeros(len(timeline_index), dtype=int))
        nar_occ = usage_narrow.get(carousel, np.zeros(len(timeline_index), dtype=int))
        occupied_data[f"{carousel}_Wide"] = wide_occ
        occupied_data[f"{carousel}_Narrow"] = nar_occ
        cap = caps.get(carousel)
        cap_wide = int(cap.wide) if cap else 0
        cap_nar = int(cap.narrow) if cap else 0
        free_data[f"{carousel}_Wide"] = cap_wide - wide_occ
        free_data[f"{carousel}_Narrow"] = cap_nar - nar_occ

    return pd.DataFrame(occupied_data, index=timeline_index), pd.DataFrame(free_data, index=timeline_index)


def _build_heatmap_sheets(
    flights_df: pd.DataFrame,
    timeline_index: pd.DatetimeIndex,
    timeline_columns: list[str],
    *,
    carousels_mode: str | None,
    caps_manual: dict[str, CarouselCapacity] | None,
    caps_by_terminal: dict[str, dict[str, CarouselCapacity]] | None,
    extra_caps_by_terminal: dict[str, CarouselCapacity] | None,
) -> tuple[dict[str, pd.DataFrame], dict[str, pd.DataFrame]]:
    """Construit les onglets de la heatmap (un par terminal si mode multi-terminal).

    En mode "file" avec caps_by_terminal : crée un onglet par terminal, filtrant
    les vols et les carrousels correspondant au terminal.
    En mode simple (caps_manual) : crée un seul onglet "Planning".

    Retourne (occ_sheets, free_sheets) : deux dicts {nom_onglet → DataFrame}.
    """
    occ_sheets: dict[str, pd.DataFrame] = {}
    free_sheets: dict[str, pd.DataFrame] = {}

    if carousels_mode == "file" and caps_by_terminal:
        for term, caps_term in caps_by_terminal.items():
            df_term = flights_df
            if df_term is not None and "Terminal" in df_term.columns:
                df_term = df_term[df_term["Terminal"].astype(str) == str(term)]
            else:
                df_term = df_term.iloc[0:0] if df_term is not None else df_term
            extras = _extract_extra_carousels(timeline_columns, term)
            extra_cap = extra_caps_by_terminal.get(term) if extra_caps_by_terminal else None
            caps_full = _add_extras_to_caps(caps_term, extras, extra_cap)
            occ_df, free_df = _build_heatmap_frames(df_term, timeline_index, caps_full)
            occ_sheets[str(term)] = occ_df
            free_sheets[str(term)] = free_df
    else:
        extras = _extract_extra_carousels(timeline_columns)
        extra_cap = extra_caps_by_terminal.get("ALL") if extra_caps_by_terminal else None
        caps_full = _add_extras_to_caps(caps_manual, extras, extra_cap)
        occ_df, free_df = _build_heatmap_frames(flights_df, timeline_index, caps_full)
        occ_sheets["Planning"] = occ_df
        free_sheets["Planning"] = free_df

    if not occ_sheets:
        empty = pd.DataFrame(index=timeline_index)
        occ_sheets["Planning"] = empty
        free_sheets["Planning"] = empty

    return occ_sheets, free_sheets


# ── 8. Réajustement terminal ───────────────────────────────────────────────────

def _default_extra_caps_from_caps(caps: dict | None) -> tuple[int, int]:
    """Calcule la capacité par défaut d'un carrousel EXTRA depuis les capacités existantes.

    Utilise le maximum des capacités Wide et Narrow parmi tous les carrousels.
    Fallback : (8, 4) si caps est vide ou None.
    """
    if not caps:
        return 8, 4
    max_wide = max(int(c.wide) for c in caps.values())
    max_narrow = max(int(c.narrow) for c in caps.values())
    return max_wide, max_narrow


def _build_extra_terms_and_defaults(
    df_ready: pd.DataFrame,
    carousels_mode: str | None,
    caps_by_terminal: dict | None,
    caps_manual: dict | None,
) -> tuple[list[str], dict[str, tuple[int, int]]]:
    """Détermine la liste des terminaux et leur capacité EXTRA par défaut.

    Utilisé avant _readjust_terminal_allocations pour savoir :
    - Sur quels terminaux appliquer le réajustement
    - Quelle capacité donner aux carrousels EXTRA créés

    Retourne (terminaux, defaults) où defaults = {terminal → (wide, narrow)}.
    """
    if df_ready is None or "Terminal" not in df_ready.columns:
        wide_def, nar_def = _default_extra_caps_from_caps(caps_manual)
        return ["ALL"], {"ALL": (wide_def, nar_def)}

    terminals = sorted([str(x).strip() for x in df_ready["Terminal"].dropna().unique().tolist()])
    if carousels_mode == "file" and caps_by_terminal:
        valid_terms = [t for t in terminals if t in caps_by_terminal]
        defaults = {t: _default_extra_caps_from_caps(caps_by_terminal.get(t)) for t in valid_terms}
        return valid_terms, defaults

    wide_def, nar_def = _default_extra_caps_from_caps(caps_manual)
    return terminals, {t: (wide_def, nar_def) for t in terminals}


def _readjust_terminal_allocations(
    flights_out_term: pd.DataFrame,
    carousel_caps: dict[str, CarouselCapacity],
    *,
    extra_capacity: CarouselCapacity | None,
    time_step_minutes: int,
    start_time: pd.Timestamp,
    end_time: pd.Timestamp,
    max_carousels_narrow: int,
    max_carousels_wide: int,
    rule_order: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame, list[str], pd.DataFrame]:
    """Applique les règles de réajustement sur les vols non-assignés d'un terminal.

    Cette fonction est appelée après l'allocation initiale pour tenter d'assigner
    les vols qui n'ont pas pu être placés (raison : NO_CAPACITY ou IMPOSSIBLE_DEMAND).

    Règles disponibles (appliquées dans l'ordre de rule_order) :
        "multi"       : permet de splitter un vol sur plusieurs carrousels
        "narrow_wide" : permet aux vols Narrow d'utiliser des positions Wide
        "extras"      : crée des carrousels EXTRA jusqu'à tout assigner

    Paramètres :
        flights_out_term    : DataFrame des vols du terminal (déjà allocués en partie)
        carousel_caps       : capacités des carrousels du terminal
        extra_capacity      : capacité d'un carrousel EXTRA (None = pas d'extras)
        time_step_minutes   : granularité temporelle en minutes (pour la timeline)
        start_time, end_time: bornes de la timeline
        max_carousels_narrow/wide : nombre max de carrousels pour les vols Narrow/Wide
        rule_order          : ordre d'application des règles, ex: ["multi", "extras"]

    Retourne :
        (readjusted_df, timeline_df, extras_used, impossible_df)
        - readjusted_df : DataFrame mis à jour avec les nouvelles assignations
        - timeline_df   : timeline reconstruite après réajustement
        - extras_used   : liste des noms de carrousels EXTRA ajoutés (ex: ["EXTRA1"])
        - impossible_df : vols qui restent IMPOSSIBLE_DEMAND (ne peuvent pas être placés)
    """
    if flights_out_term is None or len(flights_out_term) == 0:
        empty = flights_out_term.copy() if flights_out_term is not None else pd.DataFrame()
        timeline = build_timeline_from_assignments(empty, list(carousel_caps.keys()), time_step_minutes, start_time, end_time)
        return empty, timeline, [], empty.iloc[0:0].copy()

    # Initialisation : on part du DataFrame d'entrée et on ajoute les colonnes de suivi
    readjusted = flights_out_term.copy()
    readjusted["OriginalCategory"] = readjusted["Category"].astype(str).str.strip()
    readjusted["FinalCategory"] = readjusted["OriginalCategory"]
    readjusted["CategoryChanged"] = "NO"
    readjusted["AssignedCarousels"] = [[] for _ in range(len(readjusted))]
    readjusted["AssignmentSegments"] = [[] for _ in range(len(readjusted))]
    readjusted["SplitCount"] = 0

    # Les vols déjà assignés (depuis l'allocation initiale) sont marqués comme "fixes"
    assigned_vals = readjusted["AssignedCarousel"].fillna("").astype(str).str.strip()
    assigned_mask = (
        assigned_vals.ne("") & assigned_vals.str.upper().ne("UNASSIGNED") & assigned_vals.str.lower().ne("nan")
    )
    readjusted.loc[assigned_mask, "AssignedCarousels"] = assigned_vals[assigned_mask].apply(lambda x: [x])
    readjusted.loc[assigned_mask, "SplitCount"] = 1

    # Calcul des segments de positions pour les vols déjà assignés
    fixed = readjusted[assigned_mask].copy()
    if len(fixed) > 0:
        fixed = compute_single_assignment_segments(fixed, carousel_caps)
        readjusted.loc[fixed.index, "AssignmentSegments"] = fixed["AssignmentSegments"]

    def _candidate_mask(df: pd.DataFrame) -> pd.Series:
        """Identifie les vols candidats au réajustement (non assignés, raison connue)."""
        reasons = df["UnassignedReason"].fillna("").astype(str).str.upper()
        return (df["AssignedCarousels"].apply(len) == 0) & reasons.isin(["NO_CAPACITY", "IMPOSSIBLE_DEMAND"])

    def _apply_updates(updates: pd.DataFrame):
        """Applique les résultats d'une tentative d'allocation sur readjusted."""
        if updates is None or len(updates) == 0:
            return
        for idx, row in updates.iterrows():
            assigned_list = row.get("AssignedCarousels", [])
            readjusted.at[idx, "AssignedCarousels"] = assigned_list
            readjusted.at[idx, "AssignmentSegments"] = row.get("AssignmentSegments", [])
            readjusted.at[idx, "UnassignedReason"] = row.get("UnassignedReason", "")
            readjusted.at[idx, "SplitCount"] = len(assigned_list) if assigned_list else 0
            alloc_cat = str(row.get("AllocationCategory", "")).strip().lower()
            orig_cat = str(readjusted.at[idx, "OriginalCategory"]).strip().lower()
            # Un vol Narrow placé sur Wide → marquer CategoryChanged = YES
            if assigned_list and alloc_cat == "wide" and orig_cat == "narrow":
                readjusted.at[idx, "FinalCategory"] = "Wide"
                readjusted.at[idx, "CategoryChanged"] = "YES"

    extras_used: list[str] = []
    current_caps = dict(carousel_caps)
    allow_multi = allow_narrow_wide = False

    def _current_max() -> tuple[int, int]:
        """Retourne les limites max de carrousels selon si allow_multi est actif."""
        return (int(max_carousels_narrow), int(max_carousels_wide)) if allow_multi else (1, 1)

    def _allocate_step():
        """Lance une tentative d'allocation sur les vols candidats avec les règles actives."""
        flex = readjusted[_candidate_mask(readjusted)].copy()
        if len(flex) == 0:
            return
        fixed_rows = readjusted[readjusted["AssignedCarousels"].apply(len) > 0].copy()
        max_n, max_w = _current_max()
        assigned = allocate_with_fixed_assignments(
            fixed_rows, flex, current_caps,
            max_carousels_per_flight_narrow=max_n,
            max_carousels_per_flight_wide=max_w,
            allow_narrow_use_wide=allow_narrow_wide,
        )
        _apply_updates(assigned)

    def _allocate_with_extras():
        """Ajoute des carrousels EXTRA (1, 2, 3...) jusqu'à assigner tous les vols candidats."""
        nonlocal current_caps, extras_used
        if extra_capacity is None:
            return
        flex = readjusted[_candidate_mask(readjusted)].copy()
        if len(flex) == 0:
            return
        fixed_rows = readjusted[readjusted["AssignedCarousels"].apply(len) > 0].copy()
        max_n, max_w = _current_max()
        best = None
        best_k = 0
        best_caps = current_caps
        # Essaie k = 1, 2, 3... jusqu'à ce que tous les vols soient assignés
        for k in range(1, len(flex) + 1):
            caps_extra = {**current_caps, **{f"EXTRA{i}": extra_capacity for i in range(1, k + 1)}}
            attempt = allocate_with_fixed_assignments(
                fixed_rows, flex, caps_extra,
                max_carousels_per_flight_narrow=max_n,
                max_carousels_per_flight_wide=max_w,
                allow_narrow_use_wide=allow_narrow_wide,
            )
            blocked = attempt[
                (attempt["AssignedCarousels"].apply(len) == 0)
                & (attempt["UnassignedReason"] != "IMPOSSIBLE_DEMAND")
            ]
            best, best_k, best_caps = attempt, k, caps_extra
            if len(blocked) == 0:
                break
        if best is not None:
            extras_used = [f"EXTRA{i}" for i in range(1, best_k + 1)]
            current_caps = best_caps
            _apply_updates(best)

    # Application des règles dans l'ordre fourni (chaque règle max une fois)
    seen = set()
    for rule in rule_order or []:
        if rule in seen:
            continue
        seen.add(rule)
        if rule == "multi":
            allow_multi = True
            _allocate_step()
        elif rule == "narrow_wide":
            allow_narrow_wide = True
            _allocate_step()
        elif rule == "extras":
            _allocate_with_extras()

    # Construction de la timeline finale avec les carrousels EXTRA ajoutés
    carousels_list = list(carousel_caps.keys()) + extras_used
    timeline_term = build_timeline_from_assignments(readjusted, carousels_list, time_step_minutes, start_time, end_time)

    # Normalisation des colonnes de résultat : listes → chaînes, catégorie finale
    readjusted["SplitCount"] = readjusted["AssignedCarousels"].apply(len)
    readjusted["AssignedCarousel"] = readjusted["AssignedCarousels"].apply(
        lambda lst: "UNASSIGNED" if not lst else (lst[0] if len(lst) == 1 else "SPLIT")
    )
    readjusted["Category"] = readjusted["FinalCategory"]
    readjusted["AssignedCarousels"] = readjusted["AssignedCarousels"].apply(
        lambda lst: "+".join(lst) if lst else "UNASSIGNED"
    )
    impossible_df = readjusted[
        (readjusted["AssignedCarousels"] == "UNASSIGNED")
        & (readjusted["UnassignedReason"] == "IMPOSSIBLE_DEMAND")
    ].copy()
    return readjusted, timeline_term, extras_used, impossible_df
