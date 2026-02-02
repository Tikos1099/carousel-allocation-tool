from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
import pandas as pd

@dataclass
class CarouselCapacity:
    wide: int
    narrow: int

def _max_capacity_limits(carousel_caps: Dict[str, CarouselCapacity]) -> Tuple[int, int]:
    if not carousel_caps:
        return 0, 0
    max_wide_total = max(cap.wide + cap.narrow for cap in carousel_caps.values())
    max_narrow = max(cap.narrow for cap in carousel_caps.values())
    return max_wide_total, max_narrow

def _is_impossible_demand(category: str, positions: int, max_wide_total: int, max_narrow: int) -> bool:
    category = str(category).strip().lower()
    if category == "wide":
        return positions > max_wide_total
    if category == "narrow":
        return positions > max_narrow
    raise ValueError(f"Unknown category: {category} (expected 'Wide' or 'Narrow')")

def _can_fit(category: str, positions: int, free_wide: int, free_narrow: int) -> bool:
    """
    Wide can use wide first then narrow overflow.
    Narrow can use only narrow.
    """
    category = str(category).strip().lower()
    if category == "wide":
        return (free_wide + free_narrow) >= positions
    elif category == "narrow":
        return free_narrow >= positions
    else:
        raise ValueError(f"Unknown category: {category} (expected 'Wide' or 'Narrow')")

def _consume(category: str, positions: int, free_wide: int, free_narrow: int) -> Tuple[int, int]:
    """
    Returns updated (free_wide, free_narrow) after allocation.
    """
    category = str(category).strip().lower()
    if category == "narrow":
        # must consume narrow only
        return free_wide, free_narrow - positions

    # wide: consume wide first, overflow to narrow
    use_wide = min(free_wide, positions)
    rem = positions - use_wide
    use_narrow = rem
    return free_wide - use_wide, free_narrow - use_narrow

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
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    flights must contain: dep_col, category_col, pos_col, open_col, close_col.
    Returns:
      - flights_out: original + AssignedCarousel
      - timeline_df: index timestamps, columns carousels, values list of flights active
    """
    if time_step_minutes <= 0:
        raise ValueError("time_step_minutes must be > 0")

    max_wide_total, max_narrow = _max_capacity_limits(carousel_caps)

    # timeline
    timeline = pd.date_range(start=start_time, end=end_time, freq=f"{time_step_minutes}min")
    carousels = list(carousel_caps.keys())
    # occupancy tracking per carousel: store active flights with closing time and their consumed capacity
    active = {c: [] for c in carousels}  # list of dicts: {flight_id, close, cat, pos, wide_used, narrow_used}
    # free capacity at each carousel (mutable current state)
    free = {
        c: {"wide": carousel_caps[c].wide, "narrow": carousel_caps[c].narrow}
        for c in carousels
    }

    flights = flights.copy()
    flights["AssignedCarousel"] = None
    flights["UnassignedReason"] = ""
    # Sort flights by opening time then departure time for stable behavior
    flights = flights.sort_values([open_col, dep_col]).reset_index(drop=False).rename(columns={"index": "_rowid"})

    rr_idx = 0  # round-robin pointer

    # helper: release any active flights whose closing <= t
    def release_until(t: pd.Timestamp):
        for c in carousels:
            still = []
            for item in active[c]:
                if item["close"] <= t:
                    # release capacity
                    free[c]["wide"] += item["wide_used"]
                    free[c]["narrow"] += item["narrow_used"]
                else:
                    still.append(item)
            active[c] = still

    # timeline cells store list of flight numbers (string)
    timeline_df = pd.DataFrame(index=timeline, columns=carousels, data="")

    # We allocate flights when t reaches their opening time.
    # We'll iterate timestamps and assign flights whose opening is within (prev, t].
    prev_t = timeline[0] - pd.Timedelta(minutes=time_step_minutes)
    pending_idx = 0

    for t in timeline:
        # release capacities at time t
        release_until(t)

        # allocate flights that become active by time t (opening <= t)
        while pending_idx < len(flights) and pd.Timestamp(flights.loc[pending_idx, open_col]) <= t:
            row = flights.loc[pending_idx]
            cat = str(row[category_col]).strip().lower()
            pos = int(row[pos_col])
            close_t = pd.Timestamp(row[close_col])

            if _is_impossible_demand(cat, pos, max_wide_total, max_narrow):
                flights.loc[pending_idx, "AssignedCarousel"] = "UNASSIGNED"
                flights.loc[pending_idx, "UnassignedReason"] = "IMPOSSIBLE_DEMAND"
                pending_idx += 1
                continue

            # Try carousels starting from rr_idx (round robin)
            assigned = None
            tried = 0
            while tried < len(carousels):
                c = carousels[(rr_idx + tried) % len(carousels)]
                fw, fn = free[c]["wide"], free[c]["narrow"]
                if _can_fit(cat, pos, fw, fn):
                    # consume
                    new_fw, new_fn = _consume(cat, pos, fw, fn)
                    wide_used = fw - new_fw
                    narrow_used = fn - new_fn
                    free[c]["wide"], free[c]["narrow"] = new_fw, new_fn
                    active[c].append({
                        "rowid": row["_rowid"],
                        "flight": str(row.get("FlightNumber", row.get("Flight number", ""))),
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
                flights.loc[pending_idx, "UnassignedReason"] = "NO_CAPACITY"
                
            else:
                flights.loc[pending_idx, "UnassignedReason"] = ""

            flights.loc[pending_idx, "AssignedCarousel"] = assigned
            pending_idx += 1

        # Fill timeline grid at time t
        for c in carousels:
            # show flights that are active at t (open <= t < close)
            names = []
            for item in active[c]:
                # active list already contains open<=t by construction; check close
                if item["close"] > t:
                    names.append(item["flight"])
            timeline_df.loc[t, c] = ", ".join(names)

        prev_t = t

    # restore original row order
    flights_out = flights.sort_values("_rowid").drop(columns=["_rowid"]).reset_index(drop=True)
    return flights_out, timeline_df

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
