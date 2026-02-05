from __future__ import annotations

import pandas as pd

from allocator import (
    CarouselCapacity,
    allocate_with_fixed_assignments,
    build_timeline_from_assignments,
    compute_single_assignment_segments,
)


def _default_extra_caps_from_caps(caps: dict | None) -> tuple[int, int]:
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
    if df_ready is None or "Terminal" not in df_ready.columns:
        wide_def, nar_def = _default_extra_caps_from_caps(caps_manual)
        return ["ALL"], {"ALL": (wide_def, nar_def)}

    terminals = sorted([str(x).strip() for x in df_ready["Terminal"].dropna().unique().tolist()])
    if carousels_mode == "file" and caps_by_terminal:
        valid_terms = [t for t in terminals if t in caps_by_terminal]
        defaults = {t: _default_extra_caps_from_caps(caps_by_terminal.get(t)) for t in valid_terms}
        return valid_terms, defaults

    wide_def, nar_def = _default_extra_caps_from_caps(caps_manual)
    defaults = {t: (wide_def, nar_def) for t in terminals}
    return terminals, defaults


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
    if flights_out_term is None or len(flights_out_term) == 0:
        empty = flights_out_term.copy() if flights_out_term is not None else pd.DataFrame()
        timeline = build_timeline_from_assignments(
            empty,
            list(carousel_caps.keys()),
            time_step_minutes,
            start_time,
            end_time,
        )
        return empty, timeline, [], empty.iloc[0:0].copy()

    readjusted = flights_out_term.copy()
    readjusted["OriginalCategory"] = readjusted["Category"].astype(str).str.strip()
    readjusted["FinalCategory"] = readjusted["OriginalCategory"]
    readjusted["CategoryChanged"] = "NO"
    readjusted["AssignedCarousels"] = [[] for _ in range(len(readjusted))]
    readjusted["AssignmentSegments"] = [[] for _ in range(len(readjusted))]
    readjusted["SplitCount"] = 0

    assigned_vals = readjusted["AssignedCarousel"].fillna("").astype(str).str.strip()
    assigned_mask = (
        assigned_vals.ne("")
        & assigned_vals.str.upper().ne("UNASSIGNED")
        & assigned_vals.str.lower().ne("nan")
    )
    readjusted.loc[assigned_mask, "AssignedCarousels"] = assigned_vals[assigned_mask].apply(lambda x: [x])
    readjusted.loc[assigned_mask, "SplitCount"] = 1

    fixed = readjusted[assigned_mask].copy()
    if len(fixed) > 0:
        fixed = compute_single_assignment_segments(
            fixed,
            carousel_caps,
        )
        readjusted.loc[fixed.index, "AssignmentSegments"] = fixed["AssignmentSegments"]

    def _candidate_mask(df: pd.DataFrame) -> pd.Series:
        reasons = df["UnassignedReason"].fillna("").astype(str).str.upper()
        return (df["AssignedCarousels"].apply(len) == 0) & reasons.isin(["NO_CAPACITY", "IMPOSSIBLE_DEMAND"])

    def _apply_updates(updates: pd.DataFrame):
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
            if assigned_list and alloc_cat == "wide" and orig_cat == "narrow":
                readjusted.at[idx, "FinalCategory"] = "Wide"
                readjusted.at[idx, "CategoryChanged"] = "YES"

    extras_used: list[str] = []
    current_caps = dict(carousel_caps)
    allow_multi = False
    allow_narrow_wide = False

    def _current_max() -> tuple[int, int]:
        if allow_multi:
            return int(max_carousels_narrow), int(max_carousels_wide)
        return 1, 1

    def _allocate_step():
        flex = readjusted[_candidate_mask(readjusted)].copy()
        if len(flex) == 0:
            return
        fixed = readjusted[readjusted["AssignedCarousels"].apply(len) > 0].copy()
        max_n, max_w = _current_max()
        assigned = allocate_with_fixed_assignments(
            fixed,
            flex,
            current_caps,
            max_carousels_per_flight_narrow=max_n,
            max_carousels_per_flight_wide=max_w,
            allow_narrow_use_wide=allow_narrow_wide,
        )
        _apply_updates(assigned)

    def _allocate_with_extras():
        nonlocal current_caps, extras_used
        if extra_capacity is None:
            return
        flex = readjusted[_candidate_mask(readjusted)].copy()
        if len(flex) == 0:
            return
        fixed = readjusted[readjusted["AssignedCarousels"].apply(len) > 0].copy()
        max_n, max_w = _current_max()

        max_k = len(flex)
        best = None
        best_k = 0
        best_caps = current_caps
        for k in range(1, max_k + 1):
            caps_extra = {
                **current_caps,
                **{f"EXTRA{i}": extra_capacity for i in range(1, k + 1)},
            }
            attempt = allocate_with_fixed_assignments(
                fixed,
                flex,
                caps_extra,
                max_carousels_per_flight_narrow=max_n,
                max_carousels_per_flight_wide=max_w,
                allow_narrow_use_wide=allow_narrow_wide,
            )
            blocked = attempt[
                (attempt["AssignedCarousels"].apply(len) == 0)
                & (attempt["UnassignedReason"] != "IMPOSSIBLE_DEMAND")
            ]
            best = attempt
            best_k = k
            best_caps = caps_extra
            if len(blocked) == 0:
                break

        if best is not None:
            extras_used = [f"EXTRA{i}" for i in range(1, best_k + 1)]
            current_caps = best_caps
            _apply_updates(best)

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

    carousels_list = list(carousel_caps.keys()) + extras_used
    timeline_term = build_timeline_from_assignments(
        readjusted,
        carousels_list,
        time_step_minutes,
        start_time,
        end_time,
    )

    def _assigned_carousel_value(lst: list[str]) -> str:
        if not lst:
            return "UNASSIGNED"
        if len(lst) == 1:
            return lst[0]
        return "SPLIT"

    readjusted["SplitCount"] = readjusted["AssignedCarousels"].apply(len)
    readjusted["AssignedCarousel"] = readjusted["AssignedCarousels"].apply(_assigned_carousel_value)
    readjusted["Category"] = readjusted["FinalCategory"]
    readjusted["AssignedCarousels"] = readjusted["AssignedCarousels"].apply(
        lambda lst: "+".join(lst) if lst else "UNASSIGNED"
    )
    impossible_df = readjusted[
        (readjusted["AssignedCarousels"] == "UNASSIGNED")
        & (readjusted["UnassignedReason"] == "IMPOSSIBLE_DEMAND")
    ].copy()

    return readjusted, timeline_term, extras_used, impossible_df
