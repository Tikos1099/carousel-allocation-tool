from __future__ import annotations
import ast
import pandas as pd
import re

def read_flights_excel(file) -> pd.DataFrame:
    df = pd.read_excel(file)
    # normalize common column names
    rename_map = {
        "heur de départ": "DepartureTime",
        "Heure de départ": "DepartureTime",
        "departure time": "DepartureTime",
        "Departure time": "DepartureTime",
        "flight number": "FlightNumber",
        "Flight number": "FlightNumber",
        "category": "Category",
        "Category": "Category",
        "position": "Positions",
        "Position": "Positions",
        "make up opening": "MakeupOpening",
        "Make up opening": "MakeupOpening",
        "make up closing": "MakeupClosing",
        "Make up closing": "MakeupClosing",
    }
    df = df.rename(columns={c: rename_map.get(c, c) for c in df.columns})
    return df

def write_summary_txt(path: str, flights_out: pd.DataFrame, extra_cols: list[str] | None = None):
    cols = ["DepartureTime", "FlightNumber", "Category", "Positions", "MakeupOpening", "MakeupClosing", "AssignedCarousel"]
    existing = [c for c in cols if c in flights_out.columns]
    extra_cols = [c for c in (extra_cols or []) if c in flights_out.columns and c not in existing]
    s = flights_out.sort_values("DepartureTime")[existing + extra_cols]
    with open(path, "w", encoding="utf-8") as f:
        for _, r in s.iterrows():
            base = (
                f"{r.get('DepartureTime')} | {r.get('FlightNumber')} | {r.get('Category')} | "
                f"pos={r.get('Positions')} | open={r.get('MakeupOpening')} | close={r.get('MakeupClosing')} | "
                f"carousel={r.get('AssignedCarousel')}"
            )
            if extra_cols:
                extras = " | ".join([f"{c}={r.get(c)}" for c in extra_cols])
                f.write(f"{base} | {extras}\n")
            else:
                f.write(f"{base}\n")

def write_summary_csv(path: str, flights_out: pd.DataFrame):
    flights_out.sort_values("DepartureTime").to_csv(path, index=False, encoding="utf-8")

def _normalize_hex_color(value: str, fallback: str) -> str:
    if value is None:
        return fallback
    s = str(value).strip()
    if not s:
        return fallback
    if not s.startswith("#"):
        s = "#" + s
    if not re.fullmatch(r"#[0-9A-Fa-f]{6}", s):
        return fallback
    return s.upper()

def _extract_flights(cell_value) -> list[str]:
    if cell_value is None:
        return []
    s = str(cell_value).strip()
    if not s or s.lower() == "nan":
        return []
    return [p.strip() for p in s.split(",") if p.strip()]

def _extract_terminal_from_column(col_name) -> str | None:
    if col_name is None:
        return None
    s = str(col_name).strip()
    if not s or s.lower() == "nan":
        return None
    if "-" in s:
        term = s.split("-", 1)[0].strip()
        return term or None
    return None

def _extract_carousel_from_column(col_name) -> str | None:
    if col_name is None:
        return None
    s = str(col_name).strip()
    if not s or s.lower() == "nan":
        return None
    if "-" in s:
        base = s.split("-", 1)[1].strip()
        return base or None
    return s

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

def write_timeline_excel(
    path: str,
    timeline_df: pd.DataFrame,
    flights_out: pd.DataFrame | None = None,
    *,
    color_mode: str = "category",
    wide_color: str = "#D32F2F",
    narrow_color: str = "#FFEBEE",
    split_color: str = "#FFC107",
    narrow_wide_color: str = "#00B894",
    extra_columns: list[str] | None = None,
    extra_header_color: str = "#E6DFF7",
    extra_border_color: str = "#8064A2",
    extra_summary: pd.DataFrame | None = None,
    extra_sheet_name: str = "Summary extra makeups",
):
    wide_color = _normalize_hex_color(wide_color, "#D32F2F")
    narrow_color = _normalize_hex_color(narrow_color, "#FFEBEE")
    split_color = _normalize_hex_color(split_color, "#FFC107")
    narrow_wide_color = _normalize_hex_color(narrow_wide_color, "#00B894")
    color_mode = str(color_mode or "category").strip().lower()
    if color_mode not in ("category", "flight", "terminal"):
        color_mode = "category"

    extra_columns = extra_columns or []
    extra_columns_set = set(extra_columns)
    extra_header_color = _normalize_hex_color(extra_header_color, "#E6DFF7")
    extra_border_color = _normalize_hex_color(extra_border_color, "#8064A2")
    flight_info = _build_flight_info_map(flights_out)
    segment_positions = _build_flight_segment_positions_map(flights_out)
    status_map = _build_flight_status_map(flights_out)

    with pd.ExcelWriter(path, engine="xlsxwriter") as writer:
        out = timeline_df.copy()
        out.insert(0, "Timestamp", out.index)
        out.insert(1, "Legend / Filter", "")
        out.to_excel(writer, index=False, sheet_name="Planning")

        if extra_summary is not None:
            extra_summary.to_excel(writer, index=False, sheet_name=extra_sheet_name)

        workbook = writer.book
        worksheet = writer.sheets["Planning"]

        header_format = workbook.add_format({
            "bold": True,
            "bg_color": "#D9D9D9",
            "border": 1,
            "align": "center",
            "valign": "vcenter",
        })
        header_format_extra = workbook.add_format({
            "bold": True,
            "bg_color": extra_header_color,
            "border": 1,
            "align": "center",
            "valign": "vcenter",
        })
        ts_format = workbook.add_format({"num_format": "yyyy-mm-dd hh:mm"})

        worksheet.set_column(0, 0, 22, ts_format)
        worksheet.set_column(1, 1, 16)
        if out.shape[1] > 2:
            worksheet.set_column(2, out.shape[1] - 1, 18)

        for col_idx, col_name in enumerate(out.columns):
            fmt = header_format_extra if col_name in extra_columns_set else header_format
            worksheet.write(0, col_idx, col_name, fmt)

        worksheet.freeze_panes(1, 2)

        fill_cache: dict[str, object] = {}
        legend_cache: dict[str, object] = {}

        def _fill(color: str, is_extra: bool):
            key = f"{color}|extra" if is_extra else color
            if key not in fill_cache:
                fmt = {
                    "bg_color": color,
                    "border": 1,
                    "text_wrap": True,
                    "valign": "top",
                }
                if is_extra:
                    fmt["border"] = 2
                    fmt["border_color"] = extra_border_color
                fill_cache[key] = workbook.add_format(fmt)
            return fill_cache[key]

        def _legend(color: str):
            if color not in legend_cache:
                legend_cache[color] = workbook.add_format({
                    "bg_color": color,
                    "border": 1,
                    "bold": True,
                })
            return legend_cache[color]

        row_ptr = 1
        if color_mode == "category":
            worksheet.write(row_ptr, 1, "Wide", _legend(wide_color))
            row_ptr += 1
            worksheet.write(row_ptr, 1, "Narrow", _legend(narrow_color))
            row_ptr += 1
        worksheet.write(row_ptr, 1, "Split", _legend(split_color))
        row_ptr += 1
        worksheet.write(row_ptr, 1, "Narrow to Wide", _legend(narrow_wide_color))
        row_ptr += 1

        if color_mode == "flight":
            palette = [
                "#F8CBAD",
                "#C6E0B4",
                "#BDD7EE",
                "#FFE699",
                "#D9D2E9",
                "#B4C6E7",
                "#F4B183",
                "#A9D08E",
                "#DDEBF7",
                "#FFF2CC",
                "#E2EFDA",
                "#FCE4D6",
            ]
            flight_color = _build_flight_color_map(flights_out, timeline_df, palette)
            for flight in sorted(flight_color.keys()):
                worksheet.write(row_ptr, 1, flight, _legend(flight_color[flight]))
                row_ptr += 1
        else:
            palette = [
                "#F8CBAD",
                "#C6E0B4",
                "#BDD7EE",
                "#FFE699",
                "#D9D2E9",
                "#B4C6E7",
                "#F4B183",
                "#A9D08E",
                "#DDEBF7",
                "#FFF2CC",
                "#E2EFDA",
                "#FCE4D6",
            ]
            terminal_color = _build_terminal_color_map(flights_out, timeline_df, palette)
            for term in sorted(terminal_color.keys()):
                worksheet.write(row_ptr, 1, term, _legend(terminal_color[term]))
                row_ptr += 1

        if timeline_df.empty or len(timeline_df.columns) == 0:
            return

        def _rule_color(flights: list[str]) -> str | None:
            if not status_map:
                return None
            statuses = [status_map.get(f) for f in flights]
            if "narrow_wide" in statuses:
                return narrow_wide_color
            if "split" in statuses:
                return split_color
            return None

        if color_mode == "category":
            cat_map = _build_flight_category_map(flights_out)
            for row_idx in range(len(timeline_df)):
                for col_idx in range(len(timeline_df.columns)):
                    cell_value = timeline_df.iat[row_idx, col_idx]
                    is_extra = timeline_df.columns[col_idx] in extra_columns_set
                    flights = _extract_flights(cell_value)
                    if not flights:
                        continue
                    display_value = _format_flight_cell(
                        flights,
                        flight_info,
                        segment_positions,
                        timeline_df.columns[col_idx],
                    )
                    has_wide = False
                    has_narrow = False
                    for flight in flights:
                        cat = cat_map.get(flight)
                        if cat == "wide":
                            has_wide = True
                            break
                        if cat == "narrow":
                            has_narrow = True
                    base_color = None
                    if has_wide:
                        base_color = wide_color
                    elif has_narrow:
                        base_color = narrow_color

                    rule_color = _rule_color(flights)
                    color = rule_color or base_color
                    fmt = _fill(color, is_extra) if color else None
                    if fmt:
                        worksheet.write(row_idx + 1, col_idx + 2, display_value, fmt)
                    else:
                        worksheet.write(row_idx + 1, col_idx + 2, display_value)






        elif color_mode == "terminal":
            palette = [
                "#F8CBAD",
                "#C6E0B4",
                "#BDD7EE",
                "#FFE699",
                "#D9D2E9",
                "#B4C6E7",
                "#F4B183",
                "#A9D08E",
                "#DDEBF7",
                "#FFF2CC",
                "#E2EFDA",
                "#FCE4D6",
            ]
            terminal_color = _build_terminal_color_map(flights_out, timeline_df, palette)
            flight_terminal = _build_flight_terminal_map(flights_out)
            for row_idx in range(len(timeline_df)):
                for col_idx in range(len(timeline_df.columns)):
                    cell_value = timeline_df.iat[row_idx, col_idx]
                    is_extra = timeline_df.columns[col_idx] in extra_columns_set
                    flights = _extract_flights(cell_value)
                    if not flights:
                        continue
                    display_value = _format_flight_cell(
                        flights,
                        flight_info,
                        segment_positions,
                        timeline_df.columns[col_idx],
                    )
                    term = None
                    for flight in flights:
                        term = flight_terminal.get(flight)
                        if term:
                            break
                    if not term:
                        term = _extract_terminal_from_column(timeline_df.columns[col_idx])
                    base_color = terminal_color.get(term) if term else None
                    rule_color = _rule_color(flights)
                    color = rule_color or base_color
                    fmt = _fill(color, is_extra) if color else None
                    if fmt:
                        worksheet.write(row_idx + 1, col_idx + 2, display_value, fmt)
                    else:
                        worksheet.write(row_idx + 1, col_idx + 2, display_value)
        else:
            palette = [
                "#F8CBAD",
                "#C6E0B4",
                "#BDD7EE",
                "#FFE699",
                "#D9D2E9",
                "#B4C6E7",
                "#F4B183",
                "#A9D08E",
                "#DDEBF7",
                "#FFF2CC",
                "#E2EFDA",
                "#FCE4D6",
            ]
            flight_color = _build_flight_color_map(flights_out, timeline_df, palette)
            for row_idx in range(len(timeline_df)):
                for col_idx in range(len(timeline_df.columns)):
                    cell_value = timeline_df.iat[row_idx, col_idx]
                    is_extra = timeline_df.columns[col_idx] in extra_columns_set
                    flights = _extract_flights(cell_value)
                    if not flights:
                        continue
                    display_value = _format_flight_cell(
                        flights,
                        flight_info,
                        segment_positions,
                        timeline_df.columns[col_idx],
                    )
                    base_color = flight_color.get(flights[0])
                    rule_color = _rule_color(flights)
                    color = rule_color or base_color
                    fmt = _fill(color, is_extra) if color else None
                    if fmt:
                        worksheet.write(row_idx + 1, col_idx + 2, display_value, fmt)
                    else:
                        worksheet.write(row_idx + 1, col_idx + 2, display_value)


def write_heatmap_excel(
    path: str,
    sheets: dict[str, pd.DataFrame],
    *,
    mode: str = "occupied",
):
    if not sheets:
        sheets = {"Planning": pd.DataFrame()}

    mode = str(mode or "occupied").strip().lower()
    if mode not in ("occupied", "free"):
        mode = "occupied"

    min_color = "#FFEBEE"
    max_color = "#D32F2F"
    if mode == "free":
        min_color, max_color = max_color, min_color

    def _safe_sheet_name(name: str, used: set[str]) -> str:
        base = re.sub(r"[:\\\\/?*\\[\\]]", " ", str(name or "")).strip()
        if not base:
            base = "Sheet"
        base = base[:31]
        candidate = base
        idx = 1
        while candidate in used:
            suffix = f"_{idx}"
            cut = 31 - len(suffix)
            candidate = (base[:cut] if cut > 0 else base) + suffix
            idx += 1
        used.add(candidate)
        return candidate

    with pd.ExcelWriter(path, engine="xlsxwriter") as writer:
        workbook = writer.book
        header_format = workbook.add_format({
            "bold": True,
            "bg_color": "#D9D9D9",
            "border": 1,
            "align": "center",
            "valign": "vcenter",
        })
        ts_format = workbook.add_format({"num_format": "yyyy-mm-dd hh:mm"})
        num_format = workbook.add_format({"num_format": "0", "align": "center"})

        used_names: set[str] = set()
        for sheet_name, df in sheets.items():
            out = df.copy()
            if "Timestamp" in out.columns:
                out = out.drop(columns=["Timestamp"])
            out.insert(0, "Timestamp", out.index)

            safe_name = _safe_sheet_name(sheet_name, used_names)
            out.to_excel(writer, index=False, sheet_name=safe_name)

            worksheet = writer.sheets[safe_name]
            for col_idx, col_name in enumerate(out.columns):
                worksheet.write(0, col_idx, col_name, header_format)

            worksheet.set_column(0, 0, 22, ts_format)
            if out.shape[1] > 1:
                for col_idx, col_name in enumerate(out.columns[1:], start=1):
                    width = max(8, min(30, len(str(col_name)) + 2))
                    worksheet.set_column(col_idx, col_idx, width, num_format)

            worksheet.freeze_panes(1, 0)

            data_rows = len(out)
            data_cols = out.shape[1] - 1
            if data_rows > 0 and data_cols > 0:
                worksheet.conditional_format(
                    1,
                    1,
                    data_rows,
                    data_cols,
                    {
                        "type": "2_color_scale",
                        "min_color": min_color,
                        "max_color": max_color,
                    },
                )
