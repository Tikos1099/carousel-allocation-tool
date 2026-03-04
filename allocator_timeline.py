from __future__ import annotations

from typing import List
import pandas as pd


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
                vals = [str(x).strip() for x in assigned_list if str(x).strip()]
                return vals
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
        if pd.isna(open_t) or pd.isna(close_t):
            continue
        if close_t <= open_t:
            continue

        flight = row.get(flight_col)
        if flight is None:
            flight = row.get("Flight number", "")
        flight = str(flight).strip()
        if not flight or flight.lower() == "nan":
            continue

        # Map to step intervals [t_i, t_{i+1}) so we include any overlap with [open, close).
        start_idx = timeline_index.searchsorted(open_t, side="right") - 1
        end_idx = timeline_index.searchsorted(close_t, side="left")
        if start_idx < 0:
            start_idx = 0
        if end_idx > len(timeline_index):
            end_idx = len(timeline_index)
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
