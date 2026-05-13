"""
allocator_engine.py — Moteur d'allocation des vols sur les carrousels
======================================================================

RÔLE DANS LE SYSTÈME
--------------------
Ce fichier contient TOUTE la logique d'allocation : comment assigner chaque
vol à un ou plusieurs carrousels de bagages, en respectant les contraintes
de capacité (positions Wide/Narrow disponibles) et les règles métier.

Il est importé via la façade allocator.py, jamais directement.

CONCEPT CLÉ : CAPACITÉ D'UN CARROUSEL
--------------------------------------
Chaque carrousel a deux types de positions :
- Wide   : positions pour avions gros-porteurs (wide-body)
- Narrow : positions pour avions moyen-courriers (narrow-body)

Un vol "Wide" peut utiliser les positions Wide ET (si la règle est activée) les Narrow.
Un vol "Narrow" ne peut utiliser QUE les positions Narrow.

ALGORITHME PRINCIPAL : ROUND-ROBIN
------------------------------------
Les vols sont traités par ordre d'ouverture du makeup (MakeupOpening).
Pour chaque vol, on essaie les carrousels dans l'ordre circulaire (round-robin),
en commençant là où on s'est arrêté au dernier vol assigné.
Quand un vol se termine (MakeupClosing), ses positions sont libérées.

RÈGLES DE RÉAJUSTEMENT (optionnelles, dans l'ordre rule_order)
---------------------------------------------------------------
- "multi"        : permet de répartir un vol sur plusieurs carrousels (split)
- "narrow_wide"  : permet à un vol Narrow d'utiliser les positions Wide
- "extras"       : ajoute des carrousels EXTRA{n} si la capacité est insuffisante

FONCTIONS PUBLIQUES
-------------------
CarouselCapacity                    : dataclass(wide, narrow) — capacité d'un carrousel
allocate_round_robin(...)           : allocation simple round-robin, sans règles
allocate_round_robin_with_rules(...)  : allocation avec règles (multi, narrow→wide, extras)
allocate_with_fixed_assignments(...)  : réallocation avec vols déjà assignés (fixes)
build_timeline_from_assignments(...): construit la grille temporelle des assignations
compute_single_assignment_segments(...): calcule les segments de positions utilisées par vol
size_extra_makeups(...)             : calcule combien de makeup zones supplémentaires il faut

POUR MODIFIER
-------------
- Changer la priorité entre Wide/Narrow     : modifier _can_fit() et _consume()
- Changer l'ordre des règles de réajustement: modifier allocate_round_robin_with_rules()
- Ajouter un nouveau type de règle          : ajouter un `elif rule == "nouveau"` dans la boucle rules
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import pandas as pd


# ---------------------------------------------------------------------------
# Types de données
# ---------------------------------------------------------------------------

@dataclass
class CarouselCapacity:
    """Capacité d'un carrousel : nombre de positions Wide et Narrow disponibles.

    Exemple d'usage :
        cap = CarouselCapacity(wide=8, narrow=12)
    """
    wide: int
    narrow: int


# ---------------------------------------------------------------------------
# Utilitaires de capacité
# ---------------------------------------------------------------------------

def _normalize_category(value: object) -> str:
    """Normalise une valeur de catégorie en "wide" ou "narrow" (minuscules).

    Accepte : "Wide", "W", "wide", "WIDE", "Narrow", "N", "narrow", etc.
    """
    s = str(value or "").strip().lower()
    if s in ("wide", "w"):
        return "wide"
    if s in ("narrow", "n"):
        return "narrow"
    return s


def _max_capacity_limits(
    carousel_caps: Dict[str, CarouselCapacity],
    *,
    allow_wide_use_narrow: bool = True,
) -> Tuple[int, int]:
    """Retourne la capacité maximale atteignable par un seul vol sur n'importe quel carrousel.

    Retourne (max_wide_total, max_narrow) :
    - max_wide_total : max de positions utilisables par un vol Wide (wide + narrow si autorisé)
    - max_narrow     : max de positions utilisables par un vol Narrow (narrow seulement)

    Utilisé pour détecter les demandes impossibles AVANT de lancer l'allocation.
    """
    if not carousel_caps:
        return 0, 0

    if allow_wide_use_narrow:
        max_wide_total = max(cap.wide + cap.narrow for cap in carousel_caps.values())
    else:
        max_wide_total = max(cap.wide for cap in carousel_caps.values())

    max_narrow = max(cap.narrow for cap in carousel_caps.values())
    return max_wide_total, max_narrow


def _is_impossible_demand(category: str, positions: int, max_wide_total: int, max_narrow: int) -> bool:
    """Retourne True si la demande en positions dépasse la capacité maximale d'un carrousel.

    Un vol "impossible" ne pourra JAMAIS être assigné, peu importe le timing.
    """
    category = str(category).strip().lower()
    if category == "wide":
        return positions > max_wide_total
    if category == "narrow":
        return positions > max_narrow
    raise ValueError(f"Unknown category: {category} (expected 'Wide' or 'Narrow')")


def _can_fit(
    category: str,
    positions: int,
    free_wide: int,
    free_narrow: int,
    *,
    allow_wide_use_narrow: bool = True,
) -> bool:
    """Retourne True si un vol de la catégorie donnée peut tenir dans les positions disponibles.

    Règle :
    - Narrow : utilise uniquement les positions Narrow
    - Wide   : utilise d'abord les Wide, puis les Narrow si allow_wide_use_narrow=True
    """
    category = str(category).strip().lower()
    if category == "wide":
        if allow_wide_use_narrow:
            return (free_wide + free_narrow) >= positions
        return free_wide >= positions
    elif category == "narrow":
        return free_narrow >= positions
    else:
        raise ValueError(f"Unknown category: {category} (expected 'Wide' or 'Narrow')")


def _consume(
    category: str,
    positions: int,
    free_wide: int,
    free_narrow: int,
    *,
    allow_wide_use_narrow: bool = True,
) -> Tuple[int, int]:
    """Consomme les positions pour un vol et retourne les nouvelles capacités libres.

    Retourne (new_free_wide, new_free_narrow).

    Règle Wide (si allow_wide_use_narrow) :
        Utilise d'abord les positions Wide, puis déborde sur les Narrow si nécessaire.
    """
    category = str(category).strip().lower()
    if category == "narrow":
        return free_wide, free_narrow - positions
    if not allow_wide_use_narrow:
        return free_wide - positions, free_narrow
    # Wide peut utiliser Wide puis Narrow
    use_wide = min(free_wide, positions)
    remainder = positions - use_wide
    return free_wide - use_wide, free_narrow - remainder


def _wide_only_possible(
    free: Dict[str, Dict[str, int]],
    positions: int,
    max_carousels: int,
) -> bool:
    """Retourne True si on peut placer un vol Wide en n'utilisant QUE les positions Wide.

    Utilisé pour décider si on peut éviter de "déborder" sur les Narrow.
    """
    if max_carousels <= 0:
        return False
    wide_caps = [int(v.get("wide", 0)) for v in free.values()]
    if not wide_caps:
        return False
    wide_caps.sort(reverse=True)
    return sum(wide_caps[:min(max_carousels, len(wide_caps))]) >= positions


def _max_multi_capacity(
    carousel_caps: Dict[str, CarouselCapacity],
    category: str,
    max_carousels: int,
    *,
    allow_wide_use_narrow: bool = True,
) -> int:
    """Calcule la capacité maximale en combinant les N meilleurs carrousels.

    Utilisé pour détecter les demandes impossibles même avec la règle "multi".
    """
    if not carousel_caps or max_carousels <= 0:
        return 0

    category = _normalize_category(category)
    caps: List[int] = []
    for cap in carousel_caps.values():
        if category == "wide":
            if allow_wide_use_narrow:
                caps.append(int(cap.wide) + int(cap.narrow))
            else:
                caps.append(int(cap.wide))
        else:
            caps.append(int(cap.narrow))

    caps.sort(reverse=True)
    return sum(caps[:min(max_carousels, len(caps))])


def _is_impossible_demand_multi(
    category: str,
    positions: int,
    carousel_caps: Dict[str, CarouselCapacity],
    max_carousels: int,
    *,
    allow_wide_use_narrow: bool = True,
) -> bool:
    """Retourne True si la demande est impossible même en utilisant max_carousels carrousels."""
    return positions > _max_multi_capacity(
        carousel_caps, category, max_carousels, allow_wide_use_narrow=allow_wide_use_narrow,
    )


def _select_split_allocations(
    category: str,
    positions: int,
    free: Dict[str, Dict[str, int]],
    carousels: List[str],
    rr_idx: int,
    max_carousels: int,
    wide_only: bool = False,
    *,
    allow_wide_use_narrow: bool = True,
) -> Optional[List[Dict[str, object]]]:
    """Cherche une répartition d'un vol sur plusieurs carrousels (split).

    Sélectionne les carrousels avec le plus de capacité disponible,
    dans la limite de max_carousels. Retourne None si c'est impossible.

    Retourne une liste de dicts {carousel, wide_used, narrow_used}.
    """
    if max_carousels <= 0 or not carousels:
        return None

    category = _normalize_category(category)

    # Calcule la capacité disponible pour chaque carrousel
    candidates: List[Tuple[str, int, int]] = []
    for idx, carousel_name in enumerate(carousels):
        free_wide = free[carousel_name]["wide"]
        free_narrow = free[carousel_name]["narrow"]
        if category == "wide":
            available = free_wide if (wide_only or not allow_wide_use_narrow) else free_wide + free_narrow
        else:
            available = free_narrow

        if available > 0:
            # order = distance depuis la position round-robin actuelle
            order = (idx - rr_idx) % len(carousels)
            candidates.append((carousel_name, available, order))

    if not candidates:
        return None

    # Trie : d'abord par capacité décroissante, puis par ordre round-robin
    candidates.sort(key=lambda x: (-x[1], x[2], x[0]))

    # Vérifie que les N meilleurs peuvent couvrir toute la demande
    if sum(cap for _, cap, _ in candidates[:max_carousels]) < positions:
        return None

    # Répartit les positions sur les carrousels sélectionnés
    allocations: List[Dict[str, object]] = []
    remaining = positions
    used_count = 0

    for carousel_name, available_cap, _ in candidates:
        if used_count >= max_carousels or remaining <= 0:
            break
        take = min(remaining, available_cap)
        free_wide = free[carousel_name]["wide"]
        free_narrow = free[carousel_name]["narrow"]
        new_free_wide, new_free_narrow = _consume(
            category, take, free_wide, free_narrow, allow_wide_use_narrow=allow_wide_use_narrow
        )
        allocations.append({
            "carousel": carousel_name,
            "wide_used": free_wide - new_free_wide,
            "narrow_used": free_narrow - new_free_narrow,
        })
        remaining -= take
        used_count += 1

    if remaining > 0:
        return None  # impossible de couvrir toute la demande

    return allocations


# ---------------------------------------------------------------------------
# Construction de la grille temporelle
# ---------------------------------------------------------------------------

def _build_timeline_from_assignments(
    flights_out: pd.DataFrame,
    carousels: List[str],
    time_step_minutes: int,
    start_time: pd.Timestamp,
    end_time: pd.Timestamp,
    *,
    open_col="MakeupOpening",
    close_col="MakeupClosing",
    flight_col="FlightNumber",
) -> pd.DataFrame:
    """Construit la grille temporelle des assignations (une cellule = un créneau × un carrousel).

    Le résultat est un DataFrame avec :
    - index  : timestamps de start_time à end_time par pas de time_step_minutes
    - colonnes : une par carrousel
    - valeurs  : liste des numéros de vol présents dans ce créneau (séparés par ", ")

    Ex de cellule : "AF123, BA456"
    """
    if time_step_minutes <= 0:
        raise ValueError("time_step_minutes must be > 0")

    # Crée l'index temporel (un timestamp toutes les N minutes)
    timeline_index = pd.date_range(start=start_time, end=end_time, freq=f"{time_step_minutes}min")
    timeline_df = pd.DataFrame(index=timeline_index, columns=carousels, data="")

    if flights_out is None or len(flights_out) == 0 or not carousels:
        return timeline_df

    # cell_lists[carrousel][time_idx] = [liste de vols dans ce créneau]
    cell_lists = {c: [[] for _ in range(len(timeline_index))] for c in carousels}

    def _get_assigned_carousels(row) -> List[str]:
        """Extrait la liste des carrousels assignés depuis une ligne du DataFrame."""
        assigned_list = row.get("AssignedCarousels", None)
        if assigned_list is not None:
            if isinstance(assigned_list, (list, tuple, set)):
                return [str(x).strip() for x in assigned_list if str(x).strip()]
            s = str(assigned_list).strip()
            if s and s.lower() != "nan" and s.upper() != "UNASSIGNED":
                if "+" in s:
                    return [p.strip() for p in s.split("+") if p.strip()]
                if "," in s:
                    return [p.strip() for p in s.split(",") if p.strip()]
                return [s]
        assigned = row.get("AssignedCarousel")
        if assigned is None:
            return []
        s = str(assigned).strip()
        if not s or s.lower() == "nan" or s.upper() == "UNASSIGNED":
            return []
        return [s]

    # Pour chaque vol, remplit les créneaux couverts par son makeup window
    for _, row in flights_out.iterrows():
        assigned_carousels = _get_assigned_carousels(row)
        if not assigned_carousels:
            continue

        open_t = pd.Timestamp(row.get(open_col))
        close_t = pd.Timestamp(row.get(close_col))
        if pd.isna(open_t) or pd.isna(close_t) or close_t <= open_t:
            continue

        flight = str(row.get(flight_col) or row.get("Flight number", "")).strip()
        if not flight or flight.lower() == "nan":
            continue

        # Trouve les indices de début et fin dans le timeline
        start_idx = max(0, timeline_index.searchsorted(open_t, side="right") - 1)
        end_idx = min(len(timeline_index), timeline_index.searchsorted(close_t, side="left"))
        if start_idx >= end_idx:
            continue

        for assigned in assigned_carousels:
            if assigned not in cell_lists:
                continue
            for i in range(start_idx, end_idx):
                cell_lists[assigned][i].append(flight)

    # Convertit les listes en chaînes "vol1, vol2, ..."
    for carousel_name in carousels:
        timeline_df[carousel_name] = [
            ", ".join(items) if items else ""
            for items in cell_lists[carousel_name]
        ]

    return timeline_df


def build_timeline_from_assignments(
    flights_out: pd.DataFrame,
    carousels: List[str],
    time_step_minutes: int,
    start_time: pd.Timestamp,
    end_time: pd.Timestamp,
    *,
    open_col="MakeupOpening",
    close_col="MakeupClosing",
    flight_col="FlightNumber",
) -> pd.DataFrame:
    """Point d'entrée public pour construire la grille temporelle.

    Délègue vers _build_timeline_from_assignments (implémentation interne).
    """
    return _build_timeline_from_assignments(
        flights_out=flights_out,
        carousels=carousels,
        time_step_minutes=time_step_minutes,
        start_time=start_time,
        end_time=end_time,
        open_col=open_col,
        close_col=close_col,
        flight_col=flight_col,
    )


# ---------------------------------------------------------------------------
# Calcul des segments d'assignation (positions utilisées par vol et carrousel)
# ---------------------------------------------------------------------------

def compute_single_assignment_segments(
    flights: pd.DataFrame,
    carousel_caps: Dict[str, CarouselCapacity],
    *,
    category_col="Category",
    pos_col="Positions",
    open_col="MakeupOpening",
    close_col="MakeupClosing",
    dep_col="DepartureTime",
    assigned_col="AssignedCarousel",
    allow_wide_use_narrow: bool = True,
) -> pd.DataFrame:
    """Calcule combien de positions Wide/Narrow chaque vol utilise sur son carrousel.

    Ajoute une colonne "AssignmentSegments" : liste de dicts {carousel, wide_used, narrow_used}.
    Utilisé pour construire les heatmaps de taux d'occupation.

    Note : cette fonction simule l'occupation dans le temps pour calculer
    exactement quelles positions sont utilisées (Wide vs Narrow) selon la capacité
    disponible au moment de l'ouverture du makeup.
    """
    if flights is None or len(flights) == 0:
        out = flights.copy() if flights is not None else pd.DataFrame()
        out["AssignmentSegments"] = [[] for _ in range(len(out))]
        return out

    carousels = list(carousel_caps.keys())
    flights = flights.copy()
    flights["_rowid"] = flights.index
    flights["AssignmentSegments"] = [[] for _ in range(len(flights))]

    # État courant : vols actifs et positions libres par carrousel
    active_by_carousel = {c: [] for c in carousels}
    free = {c: {"wide": int(carousel_caps[c].wide), "narrow": int(carousel_caps[c].narrow)} for c in carousels}

    def release_finished_flights(current_time: pd.Timestamp):
        """Libère les positions des vols dont le makeup est terminé avant current_time."""
        for carousel_name in carousels:
            still_active = []
            for slot in active_by_carousel[carousel_name]:
                if slot["close"] <= current_time:
                    # Le vol est terminé → on récupère ses positions
                    free[carousel_name]["wide"] += slot["wide_used"]
                    free[carousel_name]["narrow"] += slot["narrow_used"]
                else:
                    still_active.append(slot)
            active_by_carousel[carousel_name] = still_active

    for _, row in flights.sort_values([open_col, dep_col]).reset_index(drop=True).iterrows():
        assigned = row.get(assigned_col)
        if assigned not in carousels:
            continue

        open_t = pd.Timestamp(row.get(open_col))
        close_t = pd.Timestamp(row.get(close_col))
        if pd.isna(open_t) or pd.isna(close_t):
            continue

        release_finished_flights(open_t)

        cat = _normalize_category(row.get(category_col))
        pos = int(row.get(pos_col, 0))
        free_wide = free[assigned]["wide"]
        free_narrow = free[assigned]["narrow"]

        if not _can_fit(cat, pos, free_wide, free_narrow, allow_wide_use_narrow=allow_wide_use_narrow):
            continue

        new_free_wide, new_free_narrow = _consume(cat, pos, free_wide, free_narrow, allow_wide_use_narrow=allow_wide_use_narrow)
        wide_used = free_wide - new_free_wide
        narrow_used = free_narrow - new_free_narrow

        free[assigned]["wide"] = new_free_wide
        free[assigned]["narrow"] = new_free_narrow
        active_by_carousel[assigned].append({"close": close_t, "wide_used": wide_used, "narrow_used": narrow_used})

        rowid = row.get("_rowid")
        flights.loc[flights["_rowid"] == rowid, "AssignmentSegments"] = [
            {"carousel": assigned, "wide_used": wide_used, "narrow_used": narrow_used}
        ]

    return flights.drop(columns=["_rowid"])


# ---------------------------------------------------------------------------
# Allocateur round-robin simple
# ---------------------------------------------------------------------------

def allocate_round_robin(
    flights: pd.DataFrame,
    carousel_caps: Dict[str, CarouselCapacity],
    time_step_minutes: int,
    start_time: pd.Timestamp,
    end_time: pd.Timestamp,
    *,
    category_col="Category",
    pos_col="Positions",
    open_col="MakeupOpening",
    close_col="MakeupClosing",
    dep_col="DepartureTime",
    flight_col="FlightNumber",
    allow_wide_use_narrow: bool = True,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Assigne les vols aux carrousels par rotation circulaire (round-robin).

    Algorithme :
    1. Trie les vols par ordre d'ouverture du makeup
    2. Pour chaque vol, essaie les carrousels dans l'ordre circulaire depuis
       la position courante du curseur round-robin
    3. Assigne au premier carrousel qui a assez de capacité
    4. Si aucun carrousel n'a assez de capacité → vol UNASSIGNED (NO_CAPACITY)
    5. Si le vol dépasse la capacité maximale possible → UNASSIGNED (IMPOSSIBLE_DEMAND)

    Retourne :
    - flights_out  : DataFrame avec les colonnes AssignedCarousel, UnassignedReason
    - timeline_df  : grille temporelle des assignations
    """
    if time_step_minutes <= 0:
        raise ValueError("time_step_minutes must be > 0")

    max_wide_total, max_narrow = _max_capacity_limits(carousel_caps, allow_wide_use_narrow=allow_wide_use_narrow)
    carousels = list(carousel_caps.keys())

    flights = flights.copy()
    flights["AssignedCarousel"] = None
    flights["UnassignedReason"] = ""
    flights = flights.sort_values([open_col, dep_col]).reset_index(drop=False).rename(columns={"index": "_rowid"})

    # Cas sans carrousels : tous UNASSIGNED
    if not carousels:
        flights["AssignedCarousel"] = "UNASSIGNED"
        flights["UnassignedReason"] = "NO_CAPACITY"
        flights_out = flights.sort_values("_rowid").drop(columns=["_rowid"]).reset_index(drop=True)
        return flights_out, _build_timeline_from_assignments(
            flights_out, carousels, time_step_minutes, start_time, end_time,
            open_col=open_col, close_col=close_col, flight_col=flight_col,
        )

    # Pré-marquage des vols avec une demande impossible (trop de positions pour n'importe quel carrousel)
    for idx, row in flights.iterrows():
        cat = str(row.get(category_col, "")).strip().lower()
        pos = int(row.get(pos_col, 0))
        if _is_impossible_demand(cat, pos, max_wide_total, max_narrow):
            flights.loc[idx, "AssignedCarousel"] = "UNASSIGNED"
            flights.loc[idx, "UnassignedReason"] = "IMPOSSIBLE_DEMAND"

    # État courant : vols actifs et positions libres par carrousel
    active_by_carousel = {c: [] for c in carousels}
    free = {c: {"wide": int(carousel_caps[c].wide), "narrow": int(carousel_caps[c].narrow)} for c in carousels}
    round_robin_idx = 0  # position du curseur dans la liste des carrousels

    def release_finished_flights(current_time: pd.Timestamp):
        """Libère les positions des vols dont le makeup est terminé."""
        for carousel_name in carousels:
            still_active = [item for item in active_by_carousel[carousel_name] if item["close"] > current_time]
            released = [item for item in active_by_carousel[carousel_name] if item["close"] <= current_time]
            for item in released:
                free[carousel_name]["wide"] += item["wide_used"]
                free[carousel_name]["narrow"] += item["narrow_used"]
            active_by_carousel[carousel_name] = still_active

    for idx, row in flights.iterrows():
        if flights.loc[idx, "AssignedCarousel"] == "UNASSIGNED":
            continue  # déjà marqué impossible

        open_t = pd.Timestamp(row.get(open_col))
        close_t = pd.Timestamp(row.get(close_col))
        if pd.isna(open_t) or pd.isna(close_t) or close_t <= open_t:
            flights.loc[idx, "AssignedCarousel"] = "UNASSIGNED"
            flights.loc[idx, "UnassignedReason"] = "BAD_TIME"
            continue

        release_finished_flights(open_t)

        cat = str(row.get(category_col, "")).strip().lower()
        pos = int(row.get(pos_col, 0))

        # Pour un vol Wide : si un carrousel peut le mettre en Wide pur, on préfère ça
        # (pour ne pas "bloquer" les positions Narrow pour les futurs vols Narrow)
        wide_only_available = cat == "wide" and any(free[c]["wide"] >= pos for c in carousels)

        assigned = None
        tried = 0
        while tried < len(carousels):
            c = carousels[(round_robin_idx + tried) % len(carousels)]
            free_wide = free[c]["wide"]
            free_narrow = free[c]["narrow"]

            # Vérifie si ce carrousel peut accueillir le vol
            if wide_only_available and cat == "wide":
                fits = free_wide >= pos  # Wide pur uniquement
            else:
                fits = _can_fit(cat, pos, free_wide, free_narrow, allow_wide_use_narrow=allow_wide_use_narrow)

            if fits:
                new_free_wide, new_free_narrow = _consume(cat, pos, free_wide, free_narrow, allow_wide_use_narrow=allow_wide_use_narrow)
                free[c]["wide"] = new_free_wide
                free[c]["narrow"] = new_free_narrow
                active_by_carousel[c].append({
                    "rowid": row["_rowid"],
                    "flight": str(row.get(flight_col, row.get("Flight number", ""))),
                    "close": close_t,
                    "cat": cat,
                    "pos": pos,
                    "wide_used": free_wide - new_free_wide,
                    "narrow_used": free_narrow - new_free_narrow,
                })
                assigned = c
                round_robin_idx = (round_robin_idx + tried + 1) % len(carousels)
                break

            tried += 1

        flights.loc[idx, "AssignedCarousel"] = assigned if assigned else "UNASSIGNED"
        flights.loc[idx, "UnassignedReason"] = "" if assigned else "NO_CAPACITY"

    flights_out = flights.sort_values("_rowid").drop(columns=["_rowid"]).reset_index(drop=True)
    timeline_df = _build_timeline_from_assignments(
        flights_out, carousels, time_step_minutes, start_time, end_time,
        open_col=open_col, close_col=close_col, flight_col=flight_col,
    )
    return flights_out, timeline_df


# ---------------------------------------------------------------------------
# Allocateur avec vols fixes (réassignation partielle)
# ---------------------------------------------------------------------------

def allocate_with_fixed_assignments(
    fixed_flights: pd.DataFrame,
    flex_flights: pd.DataFrame,
    carousel_caps: Dict[str, CarouselCapacity],
    *,
    category_col="Category",
    pos_col="Positions",
    open_col="MakeupOpening",
    close_col="MakeupClosing",
    dep_col="DepartureTime",
    flight_col="FlightNumber",
    max_carousels_per_flight_narrow: int = 1,
    max_carousels_per_flight_wide: int = 1,
    allow_narrow_use_wide: bool = False,
    allow_wide_use_narrow: bool = True,
) -> pd.DataFrame:
    """Réassigne les vols flexibles en tenant compte des vols déjà fixés.

    Utilisé dans le réajustement (readjustment) :
    - fixed_flights : vols dont l'assignation est figée (déjà assignés, font "obstacle")
    - flex_flights  : vols à (ré)assigner

    Les vols fixes "consomment" de la capacité sans être réassignés.
    Les vols flexibles sont ensuite assignés par round-robin dans la capacité restante.

    Retourne flex_flights avec les colonnes :
    - AssignedCarousels  : liste des carrousels (peut être plusieurs si split)
    - AssignmentSegments : détail des positions wide_used/narrow_used par carrousel
    - UnassignedReason   : "" | "NO_CAPACITY" | "IMPOSSIBLE_DEMAND"
    - AllocationCategory : catégorie réellement utilisée pour l'allocation
    """
    def _normalize_segments(value: object) -> List[Dict[str, object]]:
        """Normalise la colonne AssignmentSegments en liste de dicts."""
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
            return _normalize_segments(parsed)
        return []

    if flex_flights is None or len(flex_flights) == 0:
        out = flex_flights.copy() if flex_flights is not None else pd.DataFrame()
        out["AssignedCarousels"] = [[] for _ in range(len(out))]
        out["AssignmentSegments"] = [[] for _ in range(len(out))]
        out["UnassignedReason"] = out.get("UnassignedReason", "")
        out["AllocationCategory"] = ""
        return out

    carousels = list(carousel_caps.keys())
    max_carousels_per_flight_narrow = max(1, int(max_carousels_per_flight_narrow))
    max_carousels_per_flight_wide = max(1, int(max_carousels_per_flight_wide))

    flex = flex_flights.copy()
    flex["_rowid"] = flex.index
    flex["AssignedCarousels"] = [[] for _ in range(len(flex))]
    flex["AssignmentSegments"] = [[] for _ in range(len(flex))]
    flex["UnassignedReason"] = ""
    flex["AllocationCategory"] = ""

    if not carousels:
        flex["UnassignedReason"] = "NO_CAPACITY"
        return flex.drop(columns=["_rowid"])

    fixed = fixed_flights.copy() if fixed_flights is not None else pd.DataFrame()
    if len(fixed) > 0 and "AssignmentSegments" not in fixed.columns:
        fixed["AssignmentSegments"] = [[] for _ in range(len(fixed))]

    # Combine les vols fixes et flexibles, triés par ouverture (les fixes d'abord à heure égale)
    events = pd.concat([fixed.assign(_fixed=1), flex.assign(_fixed=0)], ignore_index=True, sort=False)
    events["_open"] = pd.to_datetime(events[open_col])
    events["_close"] = pd.to_datetime(events[close_col])
    events = events.sort_values(
        by=["_open", "_fixed", dep_col], ascending=[True, False, True], kind="mergesort"
    ).reset_index(drop=True)

    active_by_carousel = {c: [] for c in carousels}
    free = {c: {"wide": int(carousel_caps[c].wide), "narrow": int(carousel_caps[c].narrow)} for c in carousels}
    round_robin_idx = 0

    def release_finished_flights(current_time: pd.Timestamp):
        for c in carousels:
            still_active, released = [], []
            for item in active_by_carousel[c]:
                (still_active if item["close"] > current_time else released).append(item)
            for item in released:
                free[c]["wide"] += item["wide_used"]
                free[c]["narrow"] += item["narrow_used"]
            active_by_carousel[c] = still_active

    results: Dict[int, Dict[str, object]] = {}

    for _, row in events.iterrows():
        open_t, close_t = row.get("_open"), row.get("_close")
        if pd.isna(open_t) or pd.isna(close_t):
            continue
        release_finished_flights(pd.Timestamp(open_t))

        if int(row.get("_fixed", 0)) == 1:
            # Vol fixe : consomme de la capacité sans être réassigné
            for seg in _normalize_segments(row.get("AssignmentSegments")):
                c = seg.get("carousel")
                if c not in free:
                    continue
                wide_used = int(seg.get("wide_used", 0))
                narrow_used = int(seg.get("narrow_used", 0))
                free[c]["wide"] -= wide_used
                free[c]["narrow"] -= narrow_used
                active_by_carousel[c].append({
                    "close": pd.Timestamp(close_t), "wide_used": wide_used, "narrow_used": narrow_used
                })
            continue

        # Vol flexible : à assigner
        rowid = row.get("_rowid")
        cat = _normalize_category(row.get(category_col))
        pos = int(row.get(pos_col, 0))
        alloc_cat = "wide" if allow_narrow_use_wide and cat == "narrow" else cat
        max_car = max_carousels_per_flight_wide if alloc_cat == "wide" else max_carousels_per_flight_narrow
        wide_only_required = False
        if cat == "wide":
            wide_only_required = (
                any(free[c]["wide"] >= pos for c in carousels) if max_car <= 1
                else _wide_only_possible(free, pos, max_car)
            )

        assigned_list: List[str] = []
        segments: List[Dict[str, object]] = []
        reason = ""

        if _is_impossible_demand_multi(alloc_cat, pos, carousel_caps, max_car, allow_wide_use_narrow=allow_wide_use_narrow):
            reason = "IMPOSSIBLE_DEMAND"
        else:
            # Essai 1 : trouver un seul carrousel qui peut tout accueillir
            tried = 0
            while tried < len(carousels):
                c = carousels[(round_robin_idx + tried) % len(carousels)]
                free_wide = free[c]["wide"]
                free_narrow = free[c]["narrow"]
                fits = free_wide >= pos if wide_only_required else _can_fit(alloc_cat, pos, free_wide, free_narrow, allow_wide_use_narrow=allow_wide_use_narrow)
                if fits:
                    new_free_wide, new_free_narrow = _consume(alloc_cat, pos, free_wide, free_narrow, allow_wide_use_narrow=allow_wide_use_narrow)
                    wide_used = free_wide - new_free_wide
                    narrow_used = free_narrow - new_free_narrow
                    free[c]["wide"] = new_free_wide
                    free[c]["narrow"] = new_free_narrow
                    active_by_carousel[c].append({
                        "close": pd.Timestamp(close_t), "wide_used": wide_used, "narrow_used": narrow_used
                    })
                    assigned_list = [c]
                    segments = [{"carousel": c, "wide_used": wide_used, "narrow_used": narrow_used}]
                    round_robin_idx = (round_robin_idx + tried + 1) % len(carousels)
                    break
                tried += 1

            # Essai 2 : split sur plusieurs carrousels (si max_car > 1)
            if not assigned_list and max_car > 1:
                allocations = _select_split_allocations(
                    alloc_cat, pos, free, carousels, round_robin_idx, max_car,
                    wide_only=wide_only_required, allow_wide_use_narrow=allow_wide_use_narrow,
                )
                if allocations:
                    for alloc in allocations:
                        c = alloc["carousel"]
                        wide_used = int(alloc["wide_used"])
                        narrow_used = int(alloc["narrow_used"])
                        free[c]["wide"] -= wide_used
                        free[c]["narrow"] -= narrow_used
                        active_by_carousel[c].append({
                            "close": pd.Timestamp(close_t), "wide_used": wide_used, "narrow_used": narrow_used
                        })
                        assigned_list.append(c)
                        segments.append({"carousel": c, "wide_used": wide_used, "narrow_used": narrow_used})
                    round_robin_idx = (carousels.index(assigned_list[0]) + 1) % len(carousels)

            if not assigned_list and not reason:
                reason = "NO_CAPACITY"

        results[rowid] = {
            "AssignedCarousels": assigned_list,
            "AssignmentSegments": segments,
            "UnassignedReason": reason,
            "AllocationCategory": alloc_cat,
        }

    # Applique les résultats sur le DataFrame flex
    for rowid, info in results.items():
        idxs = flex.index[flex["_rowid"] == rowid]
        for idx in idxs:
            flex.at[idx, "AssignedCarousels"] = info["AssignedCarousels"]
            flex.at[idx, "AssignmentSegments"] = info["AssignmentSegments"]
            flex.at[idx, "UnassignedReason"] = info["UnassignedReason"]
            flex.at[idx, "AllocationCategory"] = info["AllocationCategory"]

    # Vols flexibles sans résultat → NO_CAPACITY par défaut
    missing = (flex["AssignedCarousels"].apply(len) == 0) & (flex["UnassignedReason"] == "")
    flex.loc[missing, "UnassignedReason"] = "NO_CAPACITY"

    return flex.drop(columns=["_rowid"])


# ---------------------------------------------------------------------------
# Allocateur avec règles (multi, narrow→wide, extras)
# ---------------------------------------------------------------------------

def _max_possible_capacity_with_extras(
    carousel_caps: Dict[str, CarouselCapacity],
    extra_capacity: Optional[CarouselCapacity],
    category: str,
    max_carousels: int,
    allow_extras: bool,
    *,
    allow_wide_use_narrow: bool = True,
) -> int:
    """Calcule la capacité maximale atteignable en incluant les carrousels extras éventuels.

    Utilisé pour décider si un vol est IMPOSSIBLE_DEMAND ou juste NO_CAPACITY
    (la distinction est importante pour le rapport).
    """
    if max_carousels <= 0:
        return 0

    category = _normalize_category(category)
    caps: List[int] = []

    for cap in carousel_caps.values():
        if category == "wide":
            caps.append(int(cap.wide) + int(cap.narrow) if allow_wide_use_narrow else int(cap.wide))
        else:
            caps.append(int(cap.narrow))

    if allow_extras and extra_capacity is not None:
        if category == "wide":
            extra_val = int(extra_capacity.wide) + int(extra_capacity.narrow) if allow_wide_use_narrow else int(extra_capacity.wide)
        else:
            extra_val = int(extra_capacity.narrow)
        caps.extend([extra_val] * max_carousels)

    if not caps:
        return 0

    caps.sort(reverse=True)
    return sum(caps[:min(max_carousels, len(caps))])


def allocate_round_robin_with_rules(
    flights: pd.DataFrame,
    carousel_caps: Dict[str, CarouselCapacity],
    time_step_minutes: int,
    start_time: pd.Timestamp,
    end_time: pd.Timestamp,
    *,
    category_col="Category",
    pos_col="Positions",
    open_col="MakeupOpening",
    close_col="MakeupClosing",
    dep_col="DepartureTime",
    flight_col="FlightNumber",
    max_carousels_per_flight_narrow: int = 1,
    max_carousels_per_flight_wide: int = 1,
    rule_order: Optional[List[str]] = None,
    extra_capacity: Optional[CarouselCapacity] = None,
    allow_wide_use_narrow: bool = True,
) -> Tuple[pd.DataFrame, pd.DataFrame, List[str], pd.DataFrame]:
    """Allocation round-robin avec règles de réajustement progressives.

    Pour chaque vol non assigné, essaie les règles dans l'ordre rule_order :
    - "multi"       : autorise le split sur plusieurs carrousels
    - "narrow_wide" : autorise un vol Narrow à utiliser les positions Wide
    - "extras"      : ajoute un carrousel EXTRA{n} si nécessaire

    Les règles sont CUMULATIVES : une règle activée reste active pour tous les vols suivants.

    Retourne :
    - flights_out    : DataFrame avec colonnes AssignedCarousels, AssignedCarousel, SplitCount, etc.
    - timeline_df    : grille temporelle
    - extras_used    : liste des noms de carrousels EXTRA ajoutés (ex: ["EXTRA1", "EXTRA2"])
    - impossible_df  : subset des vols marqués IMPOSSIBLE_DEMAND
    """
    if time_step_minutes <= 0:
        raise ValueError("time_step_minutes must be > 0")

    rule_order = rule_order or []
    max_carousels_per_flight_narrow = max(1, int(max_carousels_per_flight_narrow))
    max_carousels_per_flight_wide = max(1, int(max_carousels_per_flight_wide))

    if flights is None or len(flights) == 0:
        empty = flights.copy() if flights is not None else pd.DataFrame()
        timeline = _build_timeline_from_assignments(
            empty, list(carousel_caps.keys()), time_step_minutes, start_time, end_time,
            open_col=open_col, close_col=close_col, flight_col=flight_col,
        )
        return empty, timeline, [], empty.iloc[0:0].copy()

    flights = flights.copy()
    flights["OriginalCategory"] = flights[category_col].astype(str).str.strip()
    flights["FinalCategory"] = flights["OriginalCategory"]
    flights["CategoryChanged"] = "NO"
    flights["AssignedCarousels"] = [[] for _ in range(len(flights))]
    flights["AssignmentSegments"] = [[] for _ in range(len(flights))]
    flights["SplitCount"] = 0
    flights["AssignedCarousel"] = "UNASSIGNED"
    flights["UnassignedReason"] = ""
    flights = flights.sort_values([open_col, dep_col]).reset_index(drop=False).rename(columns={"index": "_rowid"})

    # Capacités courantes (peut augmenter avec les extras)
    current_caps = dict(carousel_caps)
    carousels = list(current_caps.keys())
    extras_used: List[str] = []

    active_by_carousel = {c: [] for c in carousels}
    free = {c: {"wide": int(current_caps[c].wide), "narrow": int(current_caps[c].narrow)} for c in carousels}
    round_robin_idx = 0
    current_close: Optional[pd.Timestamp] = None

    def release_finished_flights(current_time: pd.Timestamp):
        for c in carousels:
            still_active, released = [], []
            for item in active_by_carousel[c]:
                (still_active if item["close"] > current_time else released).append(item)
            for item in released:
                free[c]["wide"] += item["wide_used"]
                free[c]["narrow"] += item["narrow_used"]
            active_by_carousel[c] = still_active

    def _add_extra_carousel():
        """Ajoute un nouveau carrousel EXTRA{n} à la liste des carrousels disponibles."""
        nonlocal carousels, active_by_carousel, free
        if extra_capacity is None:
            return None
        extra_name = f"EXTRA{len(extras_used) + 1}"
        extras_used.append(extra_name)
        current_caps[extra_name] = CarouselCapacity(int(extra_capacity.wide), int(extra_capacity.narrow))
        carousels.append(extra_name)
        active_by_carousel[extra_name] = []
        free[extra_name] = {"wide": int(extra_capacity.wide), "narrow": int(extra_capacity.narrow)}
        return extra_name

    def _get_max_carousels(allow_multi: bool, alloc_cat: str) -> int:
        if not allow_multi:
            return 1
        return max_carousels_per_flight_wide if alloc_cat == "wide" else max_carousels_per_flight_narrow

    def _try_assign(alloc_cat: str, pos: int, allow_multi: bool) -> Tuple[List[str], List[Dict[str, object]]]:
        """Essaie d'assigner un vol à un ou plusieurs carrousels disponibles.

        Retourne (assigned_list, segments) ou ([], []) si impossible.
        """
        nonlocal round_robin_idx
        if not carousels:
            return [], []

        max_car = _get_max_carousels(allow_multi, alloc_cat)
        wide_only_required = False
        if alloc_cat == "wide":
            wide_only_required = (
                any(free[c]["wide"] >= pos for c in carousels) if max_car <= 1
                else _wide_only_possible(free, pos, max_car)
            )

        # Essai 1 : un seul carrousel
        tried = 0
        while tried < len(carousels):
            c = carousels[(round_robin_idx + tried) % len(carousels)]
            free_wide = free[c]["wide"]
            free_narrow = free[c]["narrow"]
            fits = free_wide >= pos if wide_only_required else _can_fit(alloc_cat, pos, free_wide, free_narrow, allow_wide_use_narrow=allow_wide_use_narrow)
            if fits:
                new_free_wide, new_free_narrow = _consume(alloc_cat, pos, free_wide, free_narrow, allow_wide_use_narrow=allow_wide_use_narrow)
                wide_used = free_wide - new_free_wide
                narrow_used = free_narrow - new_free_narrow
                free[c]["wide"] = new_free_wide
                free[c]["narrow"] = new_free_narrow
                active_by_carousel[c].append({
                    "close": pd.Timestamp(current_close), "wide_used": wide_used, "narrow_used": narrow_used
                })
                round_robin_idx = (round_robin_idx + tried + 1) % len(carousels)
                return [c], [{"carousel": c, "wide_used": wide_used, "narrow_used": narrow_used}]
            tried += 1

        # Essai 2 : split multi-carrousels
        if allow_multi and max_car > 1:
            allocations = _select_split_allocations(
                alloc_cat, pos, free, carousels, round_robin_idx, max_car,
                wide_only=wide_only_required, allow_wide_use_narrow=allow_wide_use_narrow,
            )
            if allocations:
                assigned_list, segments = [], []
                for alloc in allocations:
                    c = alloc["carousel"]
                    wide_used = int(alloc["wide_used"])
                    narrow_used = int(alloc["narrow_used"])
                    free[c]["wide"] -= wide_used
                    free[c]["narrow"] -= narrow_used
                    active_by_carousel[c].append({
                        "close": pd.Timestamp(current_close), "wide_used": wide_used, "narrow_used": narrow_used
                    })
                    assigned_list.append(c)
                    segments.append({"carousel": c, "wide_used": wide_used, "narrow_used": narrow_used})
                round_robin_idx = (carousels.index(assigned_list[0]) + 1) % len(carousels)
                return assigned_list, segments

        return [], []

    # ── Boucle principale d'allocation ────────────────────────────────────
    for _, row in flights.iterrows():
        current_close = pd.Timestamp(row.get(close_col))
        current_open = pd.Timestamp(row.get(open_col))
        if pd.isna(current_open) or pd.isna(current_close):
            continue

        release_finished_flights(current_open)

        orig_cat = _normalize_category(row.get(category_col))
        pos = int(row.get(pos_col, 0))

        # État des règles activées pour ce vol (cumulatif : une règle activée reste active)
        allow_multi = allow_narrow_wide = allow_extras = False
        assigned_list: List[str] = []
        segments: List[Dict[str, object]] = []
        alloc_cat = orig_cat

        def attempt_assignment() -> bool:
            """Essaie d'assigner avec les règles actuellement activées."""
            nonlocal alloc_cat, assigned_list, segments
            alloc_cat = "wide" if allow_narrow_wide and orig_cat == "narrow" else orig_cat
            assigned_list, segments = _try_assign(alloc_cat, pos, allow_multi)
            return len(assigned_list) > 0

        if not attempt_assignment():
            # Essaie d'activer les règles une par une dans l'ordre configuré
            for rule in rule_order:
                if rule == "multi":
                    allow_multi = True
                elif rule == "narrow_wide":
                    allow_narrow_wide = True
                elif rule == "extras":
                    allow_extras = True
                else:
                    continue

                if rule == "extras":
                    if attempt_assignment():
                        break
                    # Ajoute des carrousels EXTRA jusqu'à ce que ça marche
                    if extra_capacity is not None:
                        max_car = _get_max_carousels(allow_multi, "wide" if (allow_narrow_wide and orig_cat == "narrow") else orig_cat)
                        for _ in range(max(max_car, 1)):
                            _add_extra_carousel()
                            if attempt_assignment():
                                break
                        if assigned_list:
                            break
                else:
                    if attempt_assignment():
                        break

        # Enregistre le résultat dans le DataFrame
        rowid = row.get("_rowid")
        idxs = flights.index[flights["_rowid"] == rowid]
        if len(idxs) == 0:
            continue
        idx = idxs[0]

        if assigned_list:
            flights.at[idx, "AssignedCarousels"] = assigned_list
            flights.at[idx, "AssignmentSegments"] = segments
            flights.at[idx, "SplitCount"] = len(assigned_list)
            flights.at[idx, "AssignedCarousel"] = assigned_list[0] if len(assigned_list) == 1 else "SPLIT"
            flights.at[idx, "UnassignedReason"] = ""
            # Mise à jour de la catégorie si le vol Narrow a été placé en Wide
            if orig_cat == "narrow" and alloc_cat == "wide":
                flights.at[idx, "FinalCategory"] = "Wide"
                flights.at[idx, "CategoryChanged"] = "YES"
            else:
                flights.at[idx, "FinalCategory"] = flights.at[idx, "OriginalCategory"]
                flights.at[idx, "CategoryChanged"] = "NO"
        else:
            # Vol non assigné : détermine si c'est IMPOSSIBLE ou juste NO_CAPACITY
            final_cat = "wide" if (allow_narrow_wide and orig_cat == "narrow") else orig_cat
            max_car = _get_max_carousels(allow_multi, final_cat)
            max_possible = _max_possible_capacity_with_extras(
                carousel_caps, extra_capacity, final_cat, max_car, allow_extras,
                allow_wide_use_narrow=allow_wide_use_narrow,
            )
            flights.at[idx, "AssignedCarousels"] = []
            flights.at[idx, "AssignmentSegments"] = []
            flights.at[idx, "SplitCount"] = 0
            flights.at[idx, "AssignedCarousel"] = "UNASSIGNED"
            flights.at[idx, "UnassignedReason"] = "IMPOSSIBLE_DEMAND" if pos > max_possible else "NO_CAPACITY"
            flights.at[idx, "FinalCategory"] = flights.at[idx, "OriginalCategory"]
            flights.at[idx, "CategoryChanged"] = "NO"

    # Post-traitement : mise en forme finale
    flights["Category"] = flights["FinalCategory"]
    flights["AssignedCarousels"] = flights["AssignedCarousels"].apply(
        lambda lst: "+".join(lst) if lst else "UNASSIGNED"
    )
    flights_out = flights.sort_values("_rowid").drop(columns=["_rowid"]).reset_index(drop=True)

    # Timeline sur tous les carrousels (y compris les extras ajoutés)
    all_carousels = list(carousel_caps.keys()) + extras_used
    timeline_df = _build_timeline_from_assignments(
        flights_out, all_carousels, time_step_minutes, start_time, end_time,
        open_col=open_col, close_col=close_col, flight_col=flight_col,
    )

    impossible_df = flights_out[
        (flights_out["AssignedCarousel"] == "UNASSIGNED")
        & (flights_out["UnassignedReason"] == "IMPOSSIBLE_DEMAND")
    ].copy()

    return flights_out, timeline_df, extras_used, impossible_df


# ---------------------------------------------------------------------------
# Calcul du nombre de makeup zones supplémentaires nécessaires
# ---------------------------------------------------------------------------

def size_extra_makeups(
    flights: pd.DataFrame,
    extra_capacity: CarouselCapacity,
    time_step_minutes: int,
    start_time: pd.Timestamp,
    end_time: pd.Timestamp,
    *,
    category_col="Category",
    pos_col="Positions",
    open_col="MakeupOpening",
    close_col="MakeupClosing",
    dep_col="DepartureTime",
) -> Tuple[int, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Calcule le nombre minimum de makeup zones supplémentaires pour assigner tous les vols.

    Essaie successivement k=1, k=2, ... carrousels EXTRA jusqu'à ce que
    tous les vols faisables soient assignés.

    Retourne :
    - k              : nombre de makeup zones EXTRA nécessaires
    - flights_out    : DataFrame d'assignation avec k zones EXTRA
    - timeline_df    : grille temporelle correspondante
    - impossible_df  : vols impossibles (trop grands pour une zone EXTRA)
    """
    if flights is None or len(flights) == 0:
        timeline_index = pd.date_range(start=start_time, end=end_time, freq=f"{time_step_minutes}min")
        empty_df = flights.copy() if flights is not None else pd.DataFrame()
        return 0, empty_df, pd.DataFrame(index=timeline_index), empty_df.iloc[0:0]

    max_wide_total = int(extra_capacity.wide) + int(extra_capacity.narrow)
    max_narrow = int(extra_capacity.narrow)

    # Sépare les vols faisables des vols impossibles
    feasible_rows, impossible_rows = [], []
    for _, row in flights.iterrows():
        cat = str(row.get(category_col, "")).strip().lower()
        pos = int(row.get(pos_col, 0))
        if _is_impossible_demand(cat, pos, max_wide_total, max_narrow):
            r = row.copy()
            r["AssignedCarousel"] = "UNASSIGNED"
            r["UnassignedReason"] = "IMPOSSIBLE_DEMAND"
            impossible_rows.append(r)
        else:
            feasible_rows.append(row)

    feasible = pd.DataFrame(feasible_rows) if feasible_rows else flights.iloc[0:0].copy()
    impossible = pd.DataFrame(impossible_rows) if impossible_rows else flights.iloc[0:0].copy()
    timeline_index = pd.date_range(start=start_time, end=end_time, freq=f"{time_step_minutes}min")

    if feasible.empty:
        return 0, feasible, pd.DataFrame(index=timeline_index), impossible

    # Essaie de plus en plus de zones EXTRA jusqu'à tout assigner
    max_k = len(feasible)
    last_out, last_timeline = feasible.copy(), pd.DataFrame(index=timeline_index)

    for k in range(1, max_k + 1):
        caps = {
            f"EXTRA{i}": CarouselCapacity(wide=int(extra_capacity.wide), narrow=int(extra_capacity.narrow))
            for i in range(1, k + 1)
        }
        out, timeline_df = allocate_round_robin(
            flights=feasible, carousel_caps=caps, time_step_minutes=time_step_minutes,
            start_time=start_time, end_time=end_time, category_col=category_col,
            pos_col=pos_col, open_col=open_col, close_col=close_col, dep_col=dep_col,
        )
        last_out, last_timeline = out, timeline_df
        if (out["AssignedCarousel"] != "UNASSIGNED").all():
            return k, out, timeline_df, impossible  # trouvé le minimum

    return max_k, last_out, last_timeline, impossible
