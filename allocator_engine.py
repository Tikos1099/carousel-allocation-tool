from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import pandas as pd


# ── Types ──────────────────────────────────────────────────────────────────────

@dataclass
class CarouselCapacity:
    wide: int
    narrow: int


# ── Capacity utils ─────────────────────────────────────────────────────────────

def _normalize_category(value: object) -> str:
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
    if not carousel_caps:
        return 0, 0
    if allow_wide_use_narrow:
        max_wide_total = max(cap.wide + cap.narrow for cap in carousel_caps.values())
    else:
        max_wide_total = max(cap.wide for cap in carousel_caps.values())
    max_narrow = max(cap.narrow for cap in carousel_caps.values())
    return max_wide_total, max_narrow


def _is_impossible_demand(category: str, positions: int, max_wide_total: int, max_narrow: int) -> bool:
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
    category = str(category).strip().lower()
    if category == "narrow":
        return free_wide, free_narrow - positions
    if not allow_wide_use_narrow:
        return free_wide - positions, free_narrow
    use_wide = min(free_wide, positions)
    rem = positions - use_wide
    return free_wide - use_wide, free_narrow - rem


def _wide_only_possible(
    free: Dict[str, Dict[str, int]],
    positions: int,
    max_carousels: int,
) -> bool:
    if max_carousels <= 0:
        return False
    caps = [int(v.get("wide", 0)) for v in free.values()]
    if not caps:
        return False
    caps.sort(reverse=True)
    return sum(caps[: min(max_carousels, len(caps))]) >= positions


def _max_multi_capacity(
    carousel_caps: Dict[str, CarouselCapacity],
    category: str,
    max_carousels: int,
    *,
    allow_wide_use_narrow: bool = True,
) -> int:
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
    return sum(caps[: min(max_carousels, len(caps))])


def _is_impossible_demand_multi(
    category: str,
    positions: int,
    carousel_caps: Dict[str, CarouselCapacity],
    max_carousels: int,
    *,
    allow_wide_use_narrow: bool = True,
) -> bool:
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
    if max_carousels <= 0 or not carousels:
        return None
    category = _normalize_category(category)
    candidates: List[Tuple[str, int, int]] = []
    for idx, c in enumerate(carousels):
        fw, fn = free[c]["wide"], free[c]["narrow"]
        if category == "wide":
            cap = fw if (wide_only or not allow_wide_use_narrow) else fw + fn
        else:
            cap = fn
        if cap > 0:
            order = (idx - rr_idx) % len(carousels)
            candidates.append((c, cap, order))
    if not candidates:
        return None

    candidates.sort(key=lambda x: (-x[1], x[2], x[0]))
    if sum(cap for _, cap, _ in candidates[:max_carousels]) < positions:
        return None

    allocations: List[Dict[str, object]] = []
    remaining = positions
    used = 0
    for c, cap, _ in candidates:
        if used >= max_carousels or remaining <= 0:
            break
        take = min(remaining, cap)
        fw, fn = free[c]["wide"], free[c]["narrow"]
        new_fw, new_fn = _consume(category, take, fw, fn, allow_wide_use_narrow=allow_wide_use_narrow)
        allocations.append({"carousel": c, "wide_used": fw - new_fw, "narrow_used": fn - new_fn})
        remaining -= take
        used += 1
    if remaining > 0:
        return None
    return allocations


# ── Timeline ───────────────────────────────────────────────────────────────────

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
    if time_step_minutes <= 0:
        raise ValueError("time_step_minutes must be > 0")

    timeline_index = pd.date_range(start=start_time, end=end_time, freq=f"{time_step_minutes}min")
    timeline_df = pd.DataFrame(index=timeline_index, columns=carousels, data="")

    if flights_out is None or len(flights_out) == 0 or not carousels:
        return timeline_df

    cell_lists = {c: [[] for _ in range(len(timeline_index))] for c in carousels}

    def _assigned_carousels_from_row(row) -> List[str]:
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

    for _, row in flights_out.iterrows():
        assigned_list = _assigned_carousels_from_row(row)
        if not assigned_list:
            continue
        open_t = pd.Timestamp(row.get(open_col))
        close_t = pd.Timestamp(row.get(close_col))
        if pd.isna(open_t) or pd.isna(close_t) or close_t <= open_t:
            continue
        flight = row.get(flight_col) or row.get("Flight number", "")
        flight = str(flight).strip()
        if not flight or flight.lower() == "nan":
            continue
        start_idx = max(0, timeline_index.searchsorted(open_t, side="right") - 1)
        end_idx = min(len(timeline_index), timeline_index.searchsorted(close_t, side="left"))
        if start_idx >= end_idx:
            continue
        for assigned in assigned_list:
            if assigned not in cell_lists:
                continue
            for i in range(start_idx, end_idx):
                cell_lists[assigned][i].append(flight)

    for c in carousels:
        timeline_df[c] = [", ".join(items) if items else "" for items in cell_lists[c]]

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


# ── Segments ───────────────────────────────────────────────────────────────────

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
    if flights is None or len(flights) == 0:
        out = flights.copy() if flights is not None else pd.DataFrame()
        out["AssignmentSegments"] = [[] for _ in range(len(out))]
        return out

    carousels = list(carousel_caps.keys())
    flights = flights.copy()
    flights["_rowid"] = flights.index
    flights["AssignmentSegments"] = [[] for _ in range(len(flights))]

    active = {c: [] for c in carousels}
    free = {c: {"wide": int(carousel_caps[c].wide), "narrow": int(carousel_caps[c].narrow)} for c in carousels}

    def release_until(t: pd.Timestamp):
        for c in carousels:
            still = []
            for item in active[c]:
                if item["close"] <= t:
                    free[c]["wide"] += item["wide_used"]
                    free[c]["narrow"] += item["narrow_used"]
                else:
                    still.append(item)
            active[c] = still

    for _, row in flights.sort_values([open_col, dep_col]).reset_index(drop=True).iterrows():
        assigned = row.get(assigned_col)
        if assigned not in carousels:
            continue
        open_t = pd.Timestamp(row.get(open_col))
        close_t = pd.Timestamp(row.get(close_col))
        if pd.isna(open_t) or pd.isna(close_t):
            continue
        release_until(open_t)
        cat = _normalize_category(row.get(category_col))
        pos = int(row.get(pos_col, 0))
        fw, fn = free[assigned]["wide"], free[assigned]["narrow"]
        if not _can_fit(cat, pos, fw, fn, allow_wide_use_narrow=allow_wide_use_narrow):
            continue
        new_fw, new_fn = _consume(cat, pos, fw, fn, allow_wide_use_narrow=allow_wide_use_narrow)
        wide_used, narrow_used = fw - new_fw, fn - new_fn
        free[assigned]["wide"], free[assigned]["narrow"] = new_fw, new_fn
        active[assigned].append({"close": close_t, "wide_used": wide_used, "narrow_used": narrow_used})
        rowid = row.get("_rowid")
        flights.loc[flights["_rowid"] == rowid, "AssignmentSegments"] = [
            {"carousel": assigned, "wide_used": wide_used, "narrow_used": narrow_used}
        ]

    return flights.drop(columns=["_rowid"])


# ── Round-robin allocator ──────────────────────────────────────────────────────

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
    if time_step_minutes <= 0:
        raise ValueError("time_step_minutes must be > 0")

    max_wide_total, max_narrow = _max_capacity_limits(carousel_caps, allow_wide_use_narrow=allow_wide_use_narrow)
    carousels = list(carousel_caps.keys())

    flights = flights.copy()
    flights["AssignedCarousel"] = None
    flights["UnassignedReason"] = ""
    flights = flights.sort_values([open_col, dep_col]).reset_index(drop=False).rename(columns={"index": "_rowid"})

    if not carousels:
        flights["AssignedCarousel"] = "UNASSIGNED"
        flights["UnassignedReason"] = "NO_CAPACITY"
        flights_out = flights.sort_values("_rowid").drop(columns=["_rowid"]).reset_index(drop=True)
        return flights_out, _build_timeline_from_assignments(
            flights_out, carousels, time_step_minutes, start_time, end_time,
            open_col=open_col, close_col=close_col, flight_col=flight_col,
        )

    for idx, row in flights.iterrows():
        cat = str(row.get(category_col, "")).strip().lower()
        pos = int(row.get(pos_col, 0))
        if _is_impossible_demand(cat, pos, max_wide_total, max_narrow):
            flights.loc[idx, "AssignedCarousel"] = "UNASSIGNED"
            flights.loc[idx, "UnassignedReason"] = "IMPOSSIBLE_DEMAND"

    active = {c: [] for c in carousels}
    free = {c: {"wide": int(carousel_caps[c].wide), "narrow": int(carousel_caps[c].narrow)} for c in carousels}
    rr_idx = 0

    def release_until(t: pd.Timestamp):
        for c in carousels:
            still = [item for item in active[c] if item["close"] > t]
            released = [item for item in active[c] if item["close"] <= t]
            for item in released:
                free[c]["wide"] += item["wide_used"]
                free[c]["narrow"] += item["narrow_used"]
            active[c] = still

    for idx, row in flights.iterrows():
        if flights.loc[idx, "AssignedCarousel"] == "UNASSIGNED":
            continue
        open_t = pd.Timestamp(row.get(open_col))
        close_t = pd.Timestamp(row.get(close_col))
        if pd.isna(open_t) or pd.isna(close_t) or close_t <= open_t:
            flights.loc[idx, "AssignedCarousel"] = "UNASSIGNED"
            flights.loc[idx, "UnassignedReason"] = "BAD_TIME"
            continue
        release_until(open_t)

        cat = str(row.get(category_col, "")).strip().lower()
        pos = int(row.get(pos_col, 0))
        wide_only_available = cat == "wide" and any(free[c]["wide"] >= pos for c in carousels)

        assigned = None
        tried = 0
        while tried < len(carousels):
            c = carousels[(rr_idx + tried) % len(carousels)]
            fw, fn = free[c]["wide"], free[c]["narrow"]
            fits = fw >= pos if (cat == "wide" and wide_only_available) else _can_fit(
                cat, pos, fw, fn, allow_wide_use_narrow=allow_wide_use_narrow
            )
            if fits:
                new_fw, new_fn = _consume(cat, pos, fw, fn, allow_wide_use_narrow=allow_wide_use_narrow)
                free[c]["wide"], free[c]["narrow"] = new_fw, new_fn
                active[c].append({
                    "rowid": row["_rowid"],
                    "flight": str(row.get(flight_col, row.get("Flight number", ""))),
                    "close": close_t,
                    "cat": cat,
                    "pos": pos,
                    "wide_used": fw - new_fw,
                    "narrow_used": fn - new_fn,
                })
                assigned = c
                rr_idx = (rr_idx + tried + 1) % len(carousels)
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


# ── Fixed-assignment allocator ─────────────────────────────────────────────────

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
    def _normalize_segments(value: object) -> List[Dict[str, object]]:
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

    events = pd.concat([fixed.assign(_fixed=1), flex.assign(_fixed=0)], ignore_index=True, sort=False)
    events["_open"] = pd.to_datetime(events[open_col])
    events["_close"] = pd.to_datetime(events[close_col])
    events = events.sort_values(
        by=["_open", "_fixed", dep_col], ascending=[True, False, True], kind="mergesort"
    ).reset_index(drop=True)

    active = {c: [] for c in carousels}
    free = {c: {"wide": int(carousel_caps[c].wide), "narrow": int(carousel_caps[c].narrow)} for c in carousels}
    rr_idx = 0

    def release_until(t: pd.Timestamp):
        for c in carousels:
            still, released = [], []
            for item in active[c]:
                (still if item["close"] > t else released).append(item)
            for item in released:
                free[c]["wide"] += item["wide_used"]
                free[c]["narrow"] += item["narrow_used"]
            active[c] = still

    results: Dict[int, Dict[str, object]] = {}

    for _, row in events.iterrows():
        open_t, close_t = row.get("_open"), row.get("_close")
        if pd.isna(open_t) or pd.isna(close_t):
            continue
        release_until(pd.Timestamp(open_t))

        if int(row.get("_fixed", 0)) == 1:
            for seg in _normalize_segments(row.get("AssignmentSegments")):
                c = seg.get("carousel")
                if c not in free:
                    continue
                wide_used, narrow_used = int(seg.get("wide_used", 0)), int(seg.get("narrow_used", 0))
                free[c]["wide"] -= wide_used
                free[c]["narrow"] -= narrow_used
                active[c].append({"close": pd.Timestamp(close_t), "wide_used": wide_used, "narrow_used": narrow_used})
            continue

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
            tried = 0
            while tried < len(carousels):
                c = carousels[(rr_idx + tried) % len(carousels)]
                fw, fn = free[c]["wide"], free[c]["narrow"]
                fits = fw >= pos if wide_only_required else _can_fit(alloc_cat, pos, fw, fn, allow_wide_use_narrow=allow_wide_use_narrow)
                if fits:
                    new_fw, new_fn = _consume(alloc_cat, pos, fw, fn, allow_wide_use_narrow=allow_wide_use_narrow)
                    wide_used, narrow_used = fw - new_fw, fn - new_fn
                    free[c]["wide"], free[c]["narrow"] = new_fw, new_fn
                    active[c].append({"close": pd.Timestamp(close_t), "wide_used": wide_used, "narrow_used": narrow_used})
                    assigned_list = [c]
                    segments = [{"carousel": c, "wide_used": wide_used, "narrow_used": narrow_used}]
                    rr_idx = (rr_idx + tried + 1) % len(carousels)
                    break
                tried += 1

            if not assigned_list and max_car > 1:
                allocations = _select_split_allocations(
                    alloc_cat, pos, free, carousels, rr_idx, max_car,
                    wide_only=wide_only_required, allow_wide_use_narrow=allow_wide_use_narrow,
                )
                if allocations:
                    for alloc in allocations:
                        c = alloc["carousel"]
                        wide_used, narrow_used = int(alloc["wide_used"]), int(alloc["narrow_used"])
                        free[c]["wide"] -= wide_used
                        free[c]["narrow"] -= narrow_used
                        active[c].append({"close": pd.Timestamp(close_t), "wide_used": wide_used, "narrow_used": narrow_used})
                        assigned_list.append(c)
                        segments.append({"carousel": c, "wide_used": wide_used, "narrow_used": narrow_used})
                    rr_idx = (carousels.index(assigned_list[0]) + 1) % len(carousels)

            if not assigned_list and not reason:
                reason = "NO_CAPACITY"

        results[rowid] = {
            "AssignedCarousels": assigned_list,
            "AssignmentSegments": segments,
            "UnassignedReason": reason,
            "AllocationCategory": alloc_cat,
        }

    for rowid, info in results.items():
        idxs = flex.index[flex["_rowid"] == rowid]
        for idx in idxs:
            flex.at[idx, "AssignedCarousels"] = info["AssignedCarousels"]
            flex.at[idx, "AssignmentSegments"] = info["AssignmentSegments"]
            flex.at[idx, "UnassignedReason"] = info["UnassignedReason"]
            flex.at[idx, "AllocationCategory"] = info["AllocationCategory"]

    missing = (flex["AssignedCarousels"].apply(len) == 0) & (flex["UnassignedReason"] == "")
    flex.loc[missing, "UnassignedReason"] = "NO_CAPACITY"
    return flex.drop(columns=["_rowid"])


# ── Rules-based allocator ──────────────────────────────────────────────────────

def _max_possible_capacity_with_extras(
    carousel_caps: Dict[str, CarouselCapacity],
    extra_capacity: Optional[CarouselCapacity],
    category: str,
    max_carousels: int,
    allow_extras: bool,
    *,
    allow_wide_use_narrow: bool = True,
) -> int:
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
    return sum(caps[: min(max_carousels, len(caps))])


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

    current_caps = dict(carousel_caps)
    carousels = list(current_caps.keys())
    extras_used: List[str] = []

    active = {c: [] for c in carousels}
    free = {c: {"wide": int(current_caps[c].wide), "narrow": int(current_caps[c].narrow)} for c in carousels}
    rr_idx = 0
    current_close: Optional[pd.Timestamp] = None

    def release_until(t: pd.Timestamp):
        for c in carousels:
            still, released = [], []
            for item in active[c]:
                (still if item["close"] > t else released).append(item)
            for item in released:
                free[c]["wide"] += item["wide_used"]
                free[c]["narrow"] += item["narrow_used"]
            active[c] = still

    def _ensure_extra():
        nonlocal carousels, active, free
        if extra_capacity is None:
            return None
        name = f"EXTRA{len(extras_used) + 1}"
        extras_used.append(name)
        current_caps[name] = CarouselCapacity(int(extra_capacity.wide), int(extra_capacity.narrow))
        carousels.append(name)
        active[name] = []
        free[name] = {"wide": int(extra_capacity.wide), "narrow": int(extra_capacity.narrow)}
        return name

    def _current_max(allow_multi: bool, alloc_cat: str) -> int:
        if not allow_multi:
            return 1
        return max_carousels_per_flight_wide if alloc_cat == "wide" else max_carousels_per_flight_narrow

    def _assign_one(alloc_cat: str, pos: int, allow_multi: bool) -> Tuple[List[str], List[Dict[str, object]]]:
        nonlocal rr_idx
        if not carousels:
            return [], []
        max_car = _current_max(allow_multi, alloc_cat)
        wide_only_required = False
        if alloc_cat == "wide":
            wide_only_required = (
                any(free[c]["wide"] >= pos for c in carousels) if max_car <= 1
                else _wide_only_possible(free, pos, max_car)
            )
        tried = 0
        while tried < len(carousels):
            c = carousels[(rr_idx + tried) % len(carousels)]
            fw, fn = free[c]["wide"], free[c]["narrow"]
            fits = fw >= pos if wide_only_required else _can_fit(alloc_cat, pos, fw, fn, allow_wide_use_narrow=allow_wide_use_narrow)
            if fits:
                new_fw, new_fn = _consume(alloc_cat, pos, fw, fn, allow_wide_use_narrow=allow_wide_use_narrow)
                wide_used, narrow_used = fw - new_fw, fn - new_fn
                free[c]["wide"], free[c]["narrow"] = new_fw, new_fn
                active[c].append({"close": pd.Timestamp(current_close), "wide_used": wide_used, "narrow_used": narrow_used})
                rr_idx = (rr_idx + tried + 1) % len(carousels)
                return [c], [{"carousel": c, "wide_used": wide_used, "narrow_used": narrow_used}]
            tried += 1

        if allow_multi and max_car > 1:
            allocations = _select_split_allocations(
                alloc_cat, pos, free, carousels, rr_idx, max_car,
                wide_only=wide_only_required, allow_wide_use_narrow=allow_wide_use_narrow,
            )
            if allocations:
                assigned_list, segments = [], []
                for alloc in allocations:
                    c = alloc["carousel"]
                    wide_used, narrow_used = int(alloc["wide_used"]), int(alloc["narrow_used"])
                    free[c]["wide"] -= wide_used
                    free[c]["narrow"] -= narrow_used
                    active[c].append({"close": pd.Timestamp(current_close), "wide_used": wide_used, "narrow_used": narrow_used})
                    assigned_list.append(c)
                    segments.append({"carousel": c, "wide_used": wide_used, "narrow_used": narrow_used})
                rr_idx = (carousels.index(assigned_list[0]) + 1) % len(carousels)
                return assigned_list, segments
        return [], []

    for _, row in flights.iterrows():
        current_close = pd.Timestamp(row.get(close_col))
        current_open = pd.Timestamp(row.get(open_col))
        if pd.isna(current_open) or pd.isna(current_close):
            continue
        release_until(current_open)

        orig_cat = _normalize_category(row.get(category_col))
        pos = int(row.get(pos_col, 0))
        allow_multi = allow_narrow_wide = allow_extras = False
        assigned_list: List[str] = []
        segments: List[Dict[str, object]] = []
        alloc_cat = orig_cat

        def attempt():
            nonlocal alloc_cat, assigned_list, segments
            alloc_cat = "wide" if allow_narrow_wide and orig_cat == "narrow" else orig_cat
            assigned_list, segments = _assign_one(alloc_cat, pos, allow_multi)
            return len(assigned_list) > 0

        if not attempt():
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
                    if attempt():
                        break
                    if extra_capacity is not None:
                        max_car = _current_max(allow_multi, "wide" if (allow_narrow_wide and orig_cat == "narrow") else orig_cat)
                        for _ in range(max(max_car, 1)):
                            _ensure_extra()
                            if attempt():
                                break
                        if assigned_list:
                            break
                else:
                    if attempt():
                        break

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
            if orig_cat == "narrow" and alloc_cat == "wide":
                flights.at[idx, "FinalCategory"] = "Wide"
                flights.at[idx, "CategoryChanged"] = "YES"
            else:
                flights.at[idx, "FinalCategory"] = flights.at[idx, "OriginalCategory"]
                flights.at[idx, "CategoryChanged"] = "NO"
        else:
            final_cat = "wide" if (allow_narrow_wide and orig_cat == "narrow") else orig_cat
            max_car = _current_max(allow_multi, final_cat)
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

    flights["Category"] = flights["FinalCategory"]
    flights["AssignedCarousels"] = flights["AssignedCarousels"].apply(
        lambda lst: "+".join(lst) if lst else "UNASSIGNED"
    )
    flights_out = flights.sort_values("_rowid").drop(columns=["_rowid"]).reset_index(drop=True)

    carousels_list = list(carousel_caps.keys()) + extras_used
    timeline_df = _build_timeline_from_assignments(
        flights_out, carousels_list, time_step_minutes, start_time, end_time,
        open_col=open_col, close_col=close_col, flight_col=flight_col,
    )
    impossible_df = flights_out[
        (flights_out["AssignedCarousel"] == "UNASSIGNED")
        & (flights_out["UnassignedReason"] == "IMPOSSIBLE_DEMAND")
    ].copy()
    return flights_out, timeline_df, extras_used, impossible_df


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
    if flights is None or len(flights) == 0:
        timeline_index = pd.date_range(start=start_time, end=end_time, freq=f"{time_step_minutes}min")
        empty_df = flights.copy() if flights is not None else pd.DataFrame()
        return 0, empty_df, pd.DataFrame(index=timeline_index), empty_df.iloc[0:0]

    max_wide_total = int(extra_capacity.wide) + int(extra_capacity.narrow)
    max_narrow = int(extra_capacity.narrow)

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
            return k, out, timeline_df, impossible

    return max_k, last_out, last_timeline, impossible
