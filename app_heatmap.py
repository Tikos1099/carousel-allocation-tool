from __future__ import annotations

import ast
import numpy as np
import pandas as pd

from allocator import CarouselCapacity, compute_single_assignment_segments


def _normalize_segments(value: object) -> list[dict[str, object]]:
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


def _has_assignment_segments(flights_df: pd.DataFrame) -> bool:
    if flights_df is None or "AssignmentSegments" not in flights_df.columns:
        return False
    return flights_df["AssignmentSegments"].apply(lambda v: len(_normalize_segments(v)) > 0).any()


def _ensure_segments_for_heatmap(
    flights_df: pd.DataFrame,
    caps: dict[str, CarouselCapacity],
) -> pd.DataFrame:
    if flights_df is None:
        return pd.DataFrame()
    if flights_df.empty:
        out = flights_df.copy()
        if "AssignmentSegments" not in out.columns:
            out["AssignmentSegments"] = [[] for _ in range(len(out))]
        return out
    if not caps:
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
        start_idx = timeline_index.searchsorted(open_t, side="right") - 1
        end_idx = timeline_index.searchsorted(close_t, side="left")
        if start_idx < 0:
            start_idx = 0
        if end_idx > size:
            end_idx = size
        if start_idx >= end_idx:
            continue

        segments = _normalize_segments(row.get("AssignmentSegments"))
        if not segments:
            continue
        for seg in segments:
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
    extras: list[str] = []
    prefix = f"{term}-" if term else None
    for col in columns or []:
        name = str(col)
        if prefix:
            if not name.startswith(prefix):
                continue
            base = name[len(prefix):]
        else:
            base = name
        if base.upper().startswith("EXTRA"):
            extras.append(base)
    seen: set[str] = set()
    uniq: list[str] = []
    for extra in extras:
        if extra not in seen:
            seen.add(extra)
            uniq.append(extra)
    return uniq


def _add_extras_to_caps(
    caps: dict[str, CarouselCapacity] | None,
    extras: list[str],
    extra_cap: CarouselCapacity | None,
) -> dict[str, CarouselCapacity]:
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
    flights_seg = _ensure_segments_for_heatmap(flights_df, caps)
    carousels = list(caps.keys())
    usage_wide, usage_narrow = _compute_occupancy_arrays(flights_seg, timeline_index, carousels)

    data_occ: dict[str, object] = {}
    data_free: dict[str, object] = {}
    for carousel in carousels:
        wide_occ = usage_wide.get(carousel, np.zeros(len(timeline_index), dtype=int))
        nar_occ = usage_narrow.get(carousel, np.zeros(len(timeline_index), dtype=int))
        data_occ[f"{carousel}_Wide"] = wide_occ
        data_occ[f"{carousel}_Narrow"] = nar_occ
        cap = caps.get(carousel)
        cap_wide = int(cap.wide) if cap else 0
        cap_nar = int(cap.narrow) if cap else 0
        data_free[f"{carousel}_Wide"] = cap_wide - wide_occ
        data_free[f"{carousel}_Narrow"] = cap_nar - nar_occ

    occ_df = pd.DataFrame(data_occ, index=timeline_index)
    free_df = pd.DataFrame(data_free, index=timeline_index)
    return occ_df, free_df


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
