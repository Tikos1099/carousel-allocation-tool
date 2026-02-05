from __future__ import annotations

from typing import Dict
import pandas as pd

from allocator_types import CarouselCapacity
from allocator_utils import _can_fit, _consume, _normalize_category


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
    free = {
        c: {"wide": int(carousel_caps[c].wide), "narrow": int(carousel_caps[c].narrow)}
        for c in carousels
    }

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

    ordered = flights.sort_values([open_col, dep_col]).reset_index(drop=True)
    for _, row in ordered.iterrows():
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
        if not _can_fit(
            cat,
            pos,
            fw,
            fn,
            allow_wide_use_narrow=allow_wide_use_narrow,
        ):
            continue
        new_fw, new_fn = _consume(
            cat,
            pos,
            fw,
            fn,
            allow_wide_use_narrow=allow_wide_use_narrow,
        )
        wide_used = fw - new_fw
        narrow_used = fn - new_fn
        free[assigned]["wide"], free[assigned]["narrow"] = new_fw, new_fn
        active[assigned].append({
            "close": close_t,
            "wide_used": wide_used,
            "narrow_used": narrow_used,
        })

        rowid = row.get("_rowid")
        flights.loc[flights["_rowid"] == rowid, "AssignmentSegments"] = [{
            "carousel": assigned,
            "wide_used": wide_used,
            "narrow_used": narrow_used,
        }]

    flights = flights.drop(columns=["_rowid"])
    return flights
