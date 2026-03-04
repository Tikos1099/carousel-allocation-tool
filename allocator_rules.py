from __future__ import annotations

from typing import Dict, List, Optional, Tuple
import pandas as pd

from allocator_round_robin import allocate_round_robin
from allocator_timeline import _build_timeline_from_assignments
from allocator_types import CarouselCapacity
from allocator_utils import (
    _can_fit,
    _consume,
    _is_impossible_demand,
    _is_impossible_demand_multi,
    _normalize_category,
    _select_split_allocations,
    _wide_only_possible,
)


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
            if allow_wide_use_narrow:
                caps.append(int(cap.wide) + int(cap.narrow))
            else:
                caps.append(int(cap.wide))
        else:
            caps.append(int(cap.narrow))
    if allow_extras and extra_capacity is not None:
        if category == "wide":
            if allow_wide_use_narrow:
                extra_val = int(extra_capacity.wide) + int(extra_capacity.narrow)
            else:
                extra_val = int(extra_capacity.wide)
        else:
            extra_val = int(extra_capacity.narrow)
        # Extras can be added as needed; cap by max_carousels for a single flight.
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
            empty,
            list(carousel_caps.keys()),
            time_step_minutes,
            start_time,
            end_time,
            open_col=open_col,
            close_col=close_col,
            flight_col=flight_col,
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
    free = {
        c: {"wide": int(current_caps[c].wide), "narrow": int(current_caps[c].narrow)}
        for c in carousels
    }
    rr_idx = 0

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

    def _assign_one(
        alloc_cat: str,
        pos: int,
        allow_multi: bool,
    ) -> Tuple[List[str], List[Dict[str, object]]]:
        nonlocal rr_idx
        if not carousels:
            return [], []

        max_car = _current_max(allow_multi, alloc_cat)
        wide_only_required = False
        if alloc_cat == "wide":
            if max_car <= 1:
                wide_only_required = any(free[c]["wide"] >= pos for c in carousels)
            else:
                wide_only_required = _wide_only_possible(free, pos, max_car)

        assigned_list: List[str] = []
        segments: List[Dict[str, object]] = []

        tried = 0
        while tried < len(carousels):
            c = carousels[(rr_idx + tried) % len(carousels)]
            fw, fn = free[c]["wide"], free[c]["narrow"]
            if wide_only_required:
                fits = fw >= pos
            else:
                fits = _can_fit(
                    alloc_cat,
                    pos,
                    fw,
                    fn,
                    allow_wide_use_narrow=allow_wide_use_narrow,
                )
            if fits:
                new_fw, new_fn = _consume(
                    alloc_cat,
                    pos,
                    fw,
                    fn,
                    allow_wide_use_narrow=allow_wide_use_narrow,
                )
                wide_used = fw - new_fw
                narrow_used = fn - new_fn
                free[c]["wide"], free[c]["narrow"] = new_fw, new_fn
                active[c].append({
                    "close": pd.Timestamp(current_close),
                    "wide_used": wide_used,
                    "narrow_used": narrow_used,
                })
                assigned_list = [c]
                segments = [{
                    "carousel": c,
                    "wide_used": wide_used,
                    "narrow_used": narrow_used,
                }]
                rr_idx = (rr_idx + tried + 1) % len(carousels)
                return assigned_list, segments
            tried += 1

        if allow_multi and max_car > 1:
            allocations = _select_split_allocations(
                alloc_cat,
                pos,
                free,
                carousels,
                rr_idx,
                max_car,
                wide_only=wide_only_required,
                allow_wide_use_narrow=allow_wide_use_narrow,
            )
            if allocations:
                for alloc in allocations:
                    c = alloc["carousel"]
                    free[c]["wide"] -= int(alloc["wide_used"])
                    free[c]["narrow"] -= int(alloc["narrow_used"])
                    active[c].append({
                        "close": pd.Timestamp(current_close),
                        "wide_used": int(alloc["wide_used"]),
                        "narrow_used": int(alloc["narrow_used"]),
                    })
                    assigned_list.append(c)
                    segments.append({
                        "carousel": c,
                        "wide_used": int(alloc["wide_used"]),
                        "narrow_used": int(alloc["narrow_used"]),
                    })
                first_idx = carousels.index(assigned_list[0])
                rr_idx = (first_idx + 1) % len(carousels)
                return assigned_list, segments

        return [], []

    for _, row in flights.iterrows():
        current_open = pd.Timestamp(row.get(open_col))
        current_close = pd.Timestamp(row.get(close_col))
        if pd.isna(current_open) or pd.isna(current_close):
            continue
        release_until(current_open)

        orig_cat = _normalize_category(row.get(category_col))
        pos = int(row.get(pos_col, 0))

        allow_multi = False
        allow_narrow_wide = False
        allow_extras = False

        assigned_list: List[str] = []
        segments: List[Dict[str, object]] = []
        alloc_cat = orig_cat

        def attempt():
            nonlocal alloc_cat, assigned_list, segments
            alloc_cat = "wide" if allow_narrow_wide and orig_cat == "narrow" else orig_cat
            assigned_list, segments = _assign_one(alloc_cat, pos, allow_multi)
            return len(assigned_list) > 0

        # Base attempt (no rules)
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
                        max_add = max_car if max_car > 0 else 1
                        added = 0
                        while added < max_add:
                            _ensure_extra()
                            added += 1
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
                carousel_caps,
                extra_capacity,
                final_cat,
                max_car,
                allow_extras,
                allow_wide_use_narrow=allow_wide_use_narrow,
            )
            reason = "IMPOSSIBLE_DEMAND" if pos > max_possible else "NO_CAPACITY"
            flights.at[idx, "AssignedCarousels"] = []
            flights.at[idx, "AssignmentSegments"] = []
            flights.at[idx, "SplitCount"] = 0
            flights.at[idx, "AssignedCarousel"] = "UNASSIGNED"
            flights.at[idx, "UnassignedReason"] = reason
            flights.at[idx, "FinalCategory"] = flights.at[idx, "OriginalCategory"]
            flights.at[idx, "CategoryChanged"] = "NO"

    flights["Category"] = flights["FinalCategory"]
    flights["AssignedCarousels"] = flights["AssignedCarousels"].apply(
        lambda lst: "+".join(lst) if lst else "UNASSIGNED"
    )
    flights_out = flights.sort_values("_rowid").drop(columns=["_rowid"]).reset_index(drop=True)

    carousels_list = list(carousel_caps.keys()) + extras_used
    timeline_df = _build_timeline_from_assignments(
        flights_out,
        carousels_list,
        time_step_minutes,
        start_time,
        end_time,
        open_col=open_col,
        close_col=close_col,
        flight_col=flight_col,
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
    """
    Returns:
      - k: number of extra makeups needed
      - assigned_flights: flights assigned to EXTRA* (AssignedCarousel filled)
      - timeline_df: timeline for EXTRA* carousels
      - impossible_flights: flights that cannot fit in extra_capacity
    """
    if flights is None or len(flights) == 0:
        timeline_index = pd.date_range(start=start_time, end=end_time, freq=f"{time_step_minutes}min")
        empty_timeline = pd.DataFrame(index=timeline_index)
        empty_df = flights.copy() if flights is not None else pd.DataFrame()
        return 0, empty_df, empty_timeline, empty_df.iloc[0:0]

    max_wide_total = int(extra_capacity.wide) + int(extra_capacity.narrow)
    max_narrow = int(extra_capacity.narrow)

    feasible_rows = []
    impossible_rows = []
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
        empty_timeline = pd.DataFrame(index=timeline_index)
        return 0, feasible, empty_timeline, impossible

    max_k = len(feasible)
    last_out = feasible.copy()
    last_timeline = pd.DataFrame(index=timeline_index)
    for k in range(1, max_k + 1):
        caps = {
            f"EXTRA{i}": CarouselCapacity(wide=int(extra_capacity.wide), narrow=int(extra_capacity.narrow))
            for i in range(1, k + 1)
        }
        out, timeline_df = allocate_round_robin(
            flights=feasible,
            carousel_caps=caps,
            time_step_minutes=time_step_minutes,
            start_time=start_time,
            end_time=end_time,
            category_col=category_col,
            pos_col=pos_col,
            open_col=open_col,
            close_col=close_col,
            dep_col=dep_col,
        )
        last_out = out
        last_timeline = timeline_df
        if (out["AssignedCarousel"] != "UNASSIGNED").all():
            return k, out, timeline_df, impossible

    return max_k, last_out, last_timeline, impossible
