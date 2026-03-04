from __future__ import annotations

import ast
import pandas as pd

from io_utils import _extract_carousel_from_column, _extract_flights, _extract_terminal_from_column


def _build_flight_category_map(flights_out: pd.DataFrame) -> dict[str, str]:
    mapping: dict[str, str] = {}
    if flights_out is None:
        return mapping
    category_col = "FinalCategory" if "FinalCategory" in flights_out.columns else "Category"
    if "FlightNumber" not in flights_out.columns or category_col not in flights_out.columns:
        return mapping
    for _, row in flights_out.iterrows():
        flight = str(row.get("FlightNumber", "")).strip()
        if not flight or flight.lower() == "nan" or flight in mapping:
            continue
        cat = str(row.get(category_col, "")).strip().lower()
        if cat in ("wide", "narrow"):
            mapping[flight] = cat
    return mapping


def _format_category_short(category_value) -> str:
    s = str(category_value or "").strip().lower()
    if s in ("wide", "w"):
        return "W"
    if s in ("narrow", "n"):
        return "N"
    if not s or s == "nan":
        return "?"
    return s.upper()


def _format_positions_value(positions_value) -> str:
    if positions_value is None:
        return "?"
    try:
        if pd.isna(positions_value):
            return "?"
    except Exception:
        pass
    s = str(positions_value).strip()
    if not s or s.lower() == "nan":
        return "?"
    try:
        f = float(positions_value)
        if f.is_integer():
            return str(int(f))
        return str(f)
    except Exception:
        return s


def _build_flight_info_map(flights_out: pd.DataFrame) -> dict[str, tuple[object, object]]:
    mapping: dict[str, tuple[object, object]] = {}
    if flights_out is None:
        return mapping
    if "FlightNumber" not in flights_out.columns:
        return mapping
    category_col = "FinalCategory" if "FinalCategory" in flights_out.columns else "Category"
    for _, row in flights_out.iterrows():
        flight = str(row.get("FlightNumber", "")).strip()
        if not flight or flight.lower() == "nan" or flight in mapping:
            continue
        mapping[flight] = (row.get(category_col), row.get("Positions"))
    return mapping


def _format_flight_with_info(
    flight: str,
    info_map: dict[str, tuple[object, object]],
    pos_override: object | None = None,
) -> str:
    flight = str(flight or "").strip()
    if not flight:
        return ""
    if not info_map:
        return flight
    info = info_map.get(flight)
    if info is None:
        return flight
    cat_value, pos_value = info
    if pos_override is not None:
        pos_value = pos_override
    cat = _format_category_short(cat_value)
    pos = _format_positions_value(pos_value)
    return f"{flight} ( C= {cat} P={pos})"


def _format_flight_cell(
    flights: list[str],
    info_map: dict[str, tuple[object, object]],
    pos_map: dict[tuple[str, str], int] | None = None,
    column: str | None = None,
) -> str:
    base = _extract_carousel_from_column(column) if column else None
    parts: list[str] = []
    for flight in flights:
        pos_override = None
        if pos_map is not None and base:
            pos_override = pos_map.get((str(flight).strip(), base))
        parts.append(_format_flight_with_info(flight, info_map, pos_override))
    return ", ".join(parts)


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


def _build_flight_segment_positions_map(
    flights_out: pd.DataFrame | None,
) -> dict[tuple[str, str], int]:
    mapping: dict[tuple[str, str], int] = {}
    if flights_out is None or "FlightNumber" not in flights_out.columns:
        return mapping
    if "AssignmentSegments" not in flights_out.columns:
        return mapping
    for _, row in flights_out.iterrows():
        flight = str(row.get("FlightNumber", "")).strip()
        if not flight or flight.lower() == "nan":
            continue
        segments = _normalize_segments(row.get("AssignmentSegments"))
        for seg in segments:
            carousel = str(seg.get("carousel", "")).strip()
            if not carousel:
                continue
            try:
                wide_used = int(seg.get("wide_used", 0))
            except Exception:
                wide_used = 0
            try:
                narrow_used = int(seg.get("narrow_used", 0))
            except Exception:
                narrow_used = 0
            positions = wide_used + narrow_used
            key = (flight, carousel)
            current = mapping.get(key, 0)
            if positions > current:
                mapping[key] = positions
    return mapping


def _build_flight_status_map(flights_out: pd.DataFrame | None) -> dict[str, str]:
    mapping: dict[str, str] = {}
    if flights_out is None or "FlightNumber" not in flights_out.columns:
        return mapping
    for _, row in flights_out.iterrows():
        flight = str(row.get("FlightNumber", "")).strip()
        if not flight or flight.lower() == "nan" or flight in mapping:
            continue
        changed = str(row.get("CategoryChanged", "")).strip().upper() == "YES"
        split_count = 0
        split_val = row.get("SplitCount", 0)
        try:
            if pd.isna(split_val):
                split_val = 0
        except Exception:
            pass
        try:
            split_count = int(split_val)
        except Exception:
            split_count = 0
        if split_count <= 1:
            assigned = row.get("AssignedCarousels", "") or row.get("AssignedCarousel", "")
            if isinstance(assigned, str) and "+" in assigned:
                split_count = 2

        if changed:
            mapping[flight] = "narrow_wide"
            continue
        if split_count > 1:
            mapping[flight] = "split"
            continue

        cat_value = row.get("FinalCategory", row.get("Category", ""))
        cat = str(cat_value or "").strip().lower()
        if cat in ("wide", "w"):
            mapping[flight] = "wide"
        elif cat in ("narrow", "n"):
            mapping[flight] = "narrow"
        else:
            mapping[flight] = "other"
    return mapping


def _build_flight_terminal_map(flights_out: pd.DataFrame) -> dict[str, str]:
    mapping: dict[str, str] = {}
    if flights_out is None:
        return mapping
    if "FlightNumber" not in flights_out.columns or "Terminal" not in flights_out.columns:
        return mapping
    for _, row in flights_out.iterrows():
        flight = str(row.get("FlightNumber", "")).strip()
        if not flight or flight.lower() == "nan" or flight in mapping:
            continue
        term = str(row.get("Terminal", "")).strip()
        if term and term.lower() != "nan":
            mapping[flight] = term
    return mapping


def _build_flight_color_map(
    flights_out: pd.DataFrame | None,
    timeline_df: pd.DataFrame,
    palette: list[str],
) -> dict[str, str]:
    flights: list[str] = []
    if flights_out is not None and "FlightNumber" in flights_out.columns:
        flights = [str(x).strip() for x in flights_out["FlightNumber"].dropna().tolist()]
        flights = [f for f in flights if f and f.lower() != "nan"]
    if not flights:
        for row in timeline_df.itertuples(index=False, name=None):
            for cell in row:
                flights.extend(_extract_flights(cell))

    uniq: list[str] = []
    seen: set[str] = set()
    for f in flights:
        if f not in seen:
            seen.add(f)
            uniq.append(f)

    mapping: dict[str, str] = {}
    for idx, flight in enumerate(sorted(uniq)):
        mapping[flight] = palette[idx % len(palette)]
    return mapping


def _build_terminal_color_map(
    flights_out: pd.DataFrame | None,
    timeline_df: pd.DataFrame,
    palette: list[str],
) -> dict[str, str]:
    terminals: list[str] = []
    if flights_out is not None and "Terminal" in flights_out.columns:
        terminals = [str(x).strip() for x in flights_out["Terminal"].dropna().tolist()]
        terminals = [t for t in terminals if t and t.lower() != "nan"]
    if not terminals:
        for col in timeline_df.columns:
            term = _extract_terminal_from_column(col)
            if term:
                terminals.append(term)

    uniq: list[str] = []
    seen: set[str] = set()
    for t in terminals:
        if t not in seen:
            seen.add(t)
            uniq.append(t)

    mapping: dict[str, str] = {}
    for idx, term in enumerate(sorted(uniq)):
        mapping[term] = palette[idx % len(palette)]
    return mapping
