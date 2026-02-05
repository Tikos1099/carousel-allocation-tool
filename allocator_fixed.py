from __future__ import annotations

import ast
from typing import Dict, List
import pandas as pd

from allocator_types import CarouselCapacity
from allocator_utils import (
    _can_fit,
    _consume,
    _is_impossible_demand_multi,
    _normalize_category,
    _select_split_allocations,
    _wide_only_possible,
)


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
    fixed["AssignmentSegments"] = fixed.get("AssignmentSegments", [[] for _ in range(len(fixed))])

    events = pd.concat(
        [
            fixed.assign(_fixed=1),
            flex.assign(_fixed=0),
        ],
        ignore_index=True,
        sort=False,
    )
    events["_open"] = pd.to_datetime(events[open_col])
    events["_close"] = pd.to_datetime(events[close_col])
    events = events.sort_values(
        by=["_open", "_fixed", dep_col],
        ascending=[True, False, True],
        kind="mergesort",
    ).reset_index(drop=True)

    active = {c: [] for c in carousels}
    free = {
        c: {"wide": int(carousel_caps[c].wide), "narrow": int(carousel_caps[c].narrow)}
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

    results: Dict[int, Dict[str, object]] = {}

    for _, row in events.iterrows():
        open_t = row.get("_open")
        close_t = row.get("_close")
        if pd.isna(open_t) or pd.isna(close_t):
            continue
        release_until(pd.Timestamp(open_t))

        if int(row.get("_fixed", 0)) == 1:
            segments = _normalize_segments(row.get("AssignmentSegments"))
            for seg in segments:
                c = seg.get("carousel")
                if c not in free:
                    continue
                wide_used = int(seg.get("wide_used", 0))
                narrow_used = int(seg.get("narrow_used", 0))
                free[c]["wide"] -= wide_used
                free[c]["narrow"] -= narrow_used
                active[c].append({
                    "close": pd.Timestamp(close_t),
                    "wide_used": wide_used,
                    "narrow_used": narrow_used,
                })
            continue

        rowid = row.get("_rowid")
        cat = _normalize_category(row.get(category_col))
        pos = int(row.get(pos_col, 0))
        alloc_cat = "wide" if allow_narrow_use_wide and cat == "narrow" else cat
        max_car = max_carousels_per_flight_wide if alloc_cat == "wide" else max_carousels_per_flight_narrow
        wide_only_required = False
        if cat == "wide":
            if max_car <= 1:
                wide_only_required = any(free[c]["wide"] >= pos for c in carousels)
            else:
                wide_only_required = _wide_only_possible(free, pos, max_car)

        assigned_list: List[str] = []
        segments: List[Dict[str, object]] = []
        reason = ""

        if _is_impossible_demand_multi(
            alloc_cat,
            pos,
            carousel_caps,
            max_car,
            allow_wide_use_narrow=allow_wide_use_narrow,
        ):
            reason = "IMPOSSIBLE_DEMAND"
        else:
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
                        "close": pd.Timestamp(close_t),
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
                    break
                tried += 1

            if not assigned_list and max_car > 1:
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
                            "close": pd.Timestamp(close_t),
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
        if len(idxs) == 0:
            continue
        for idx in idxs:
            flex.at[idx, "AssignedCarousels"] = info["AssignedCarousels"]
            flex.at[idx, "AssignmentSegments"] = info["AssignmentSegments"]
            flex.at[idx, "UnassignedReason"] = info["UnassignedReason"]
            flex.at[idx, "AllocationCategory"] = info["AllocationCategory"]

    missing_reason = (flex["AssignedCarousels"].apply(len) == 0) & (flex["UnassignedReason"] == "")
    flex.loc[missing_reason, "UnassignedReason"] = "NO_CAPACITY"

    flex = flex.drop(columns=["_rowid"])
    return flex
