from __future__ import annotations

from typing import Dict, Tuple
import pandas as pd

from allocator_types import CarouselCapacity
from allocator_timeline import _build_timeline_from_assignments
from allocator_utils import (
    _can_fit,
    _consume,
    _is_impossible_demand,
    _max_capacity_limits,
    _wide_only_possible,
)


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
    """
    flights must contain: dep_col, category_col, pos_col, open_col, close_col.
    Returns:
      - flights_out: original + AssignedCarousel
      - timeline_df: index timestamps, columns carousels, values list of flights active
    """
    if time_step_minutes <= 0:
        raise ValueError("time_step_minutes must be > 0")

    max_wide_total, max_narrow = _max_capacity_limits(
        carousel_caps,
        allow_wide_use_narrow=allow_wide_use_narrow,
    )

    carousels = list(carousel_caps.keys())

    flights = flights.copy()
    flights["AssignedCarousel"] = None
    flights["UnassignedReason"] = ""
    # Sort flights by opening time then departure time for stable behavior
    flights = flights.sort_values([open_col, dep_col]).reset_index(drop=False).rename(columns={"index": "_rowid"})

    if not carousels:
        flights["AssignedCarousel"] = "UNASSIGNED"
        flights["UnassignedReason"] = "NO_CAPACITY"
        flights_out = flights.sort_values("_rowid").drop(columns=["_rowid"]).reset_index(drop=True)
        timeline_df = _build_timeline_from_assignments(
            flights_out,
            carousels,
            time_step_minutes,
            start_time,
            end_time,
            open_col=open_col,
            close_col=close_col,
            flight_col=flight_col,
        )
        return flights_out, timeline_df

    # Check impossible demand (flight positions > max capacity at any time)
    for idx, row in flights.iterrows():
        cat = str(row.get(category_col, "")).strip().lower()
        pos = int(row.get(pos_col, 0))
        if _is_impossible_demand(cat, pos, max_wide_total, max_narrow):
            flights.loc[idx, "AssignedCarousel"] = "UNASSIGNED"
            flights.loc[idx, "UnassignedReason"] = "IMPOSSIBLE_DEMAND"

    # Prepare for allocation
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

        # If wide, prefer to place on wide capacity if possible
        wide_only_available = False
        if cat == "wide":
            wide_only_available = any(free[c]["wide"] >= pos for c in carousels)

        # Try carousels starting from rr_idx (round robin)
        assigned = None
        tried = 0
        while tried < len(carousels):
            c = carousels[(rr_idx + tried) % len(carousels)]
            fw, fn = free[c]["wide"], free[c]["narrow"]
            if cat == "wide" and wide_only_available:
                fits = fw >= pos
            else:
                fits = _can_fit(
                    cat,
                    pos,
                    fw,
                    fn,
                    allow_wide_use_narrow=allow_wide_use_narrow,
                )
            if fits:
                # consume
                new_fw, new_fn = _consume(
                    cat,
                    pos,
                    fw,
                    fn,
                    allow_wide_use_narrow=allow_wide_use_narrow,
                )
                wide_used = fw - new_fw
                narrow_used = fn - new_fn
                free[c]["wide"], free[c]["narrow"] = new_fw, new_fn
                active[c].append({
                    "rowid": row["_rowid"],
                    "flight": str(row.get(flight_col, row.get("Flight number", ""))),
                    "close": close_t,
                    "cat": cat,
                    "pos": pos,
                    "wide_used": wide_used,
                    "narrow_used": narrow_used,
                })
                assigned = c
                rr_idx = (rr_idx + tried + 1) % len(carousels)  # next start after the chosen one
                break
            tried += 1

        if assigned is None:
            # no capacity anywhere at this time
            assigned = "UNASSIGNED"
            flights.loc[idx, "UnassignedReason"] = "NO_CAPACITY"
        else:
            flights.loc[idx, "UnassignedReason"] = ""

        flights.loc[idx, "AssignedCarousel"] = assigned

    # restore original row order
    flights_out = flights.sort_values("_rowid").drop(columns=["_rowid"]).reset_index(drop=True)
    timeline_df = _build_timeline_from_assignments(
        flights_out,
        carousels,
        time_step_minutes,
        start_time,
        end_time,
        open_col=open_col,
        close_col=close_col,
        flight_col=flight_col,
    )
    return flights_out, timeline_df
