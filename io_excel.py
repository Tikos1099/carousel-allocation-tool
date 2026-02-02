from __future__ import annotations
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

def write_summary_txt(path: str, flights_out: pd.DataFrame):
    cols = ["DepartureTime", "FlightNumber", "Category", "Positions", "MakeupOpening", "MakeupClosing", "AssignedCarousel"]
    existing = [c for c in cols if c in flights_out.columns]
    s = flights_out.sort_values("DepartureTime")[existing]
    with open(path, "w", encoding="utf-8") as f:
        for _, r in s.iterrows():
            f.write(
                f"{r.get('DepartureTime')} | {r.get('FlightNumber')} | {r.get('Category')} | "
                f"pos={r.get('Positions')} | open={r.get('MakeupOpening')} | close={r.get('MakeupClosing')} | "
                f"carousel={r.get('AssignedCarousel')}\n"
            )

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

def _build_flight_category_map(flights_out: pd.DataFrame) -> dict[str, str]:
    mapping: dict[str, str] = {}
    if flights_out is None:
        return mapping
    if "FlightNumber" not in flights_out.columns or "Category" not in flights_out.columns:
        return mapping
    for _, row in flights_out.iterrows():
        flight = str(row.get("FlightNumber", "")).strip()
        if not flight or flight.lower() == "nan" or flight in mapping:
            continue
        cat = str(row.get("Category", "")).strip().lower()
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
    for _, row in flights_out.iterrows():
        flight = str(row.get("FlightNumber", "")).strip()
        if not flight or flight.lower() == "nan" or flight in mapping:
            continue
        mapping[flight] = (row.get("Category"), row.get("Positions"))
    return mapping

def _format_flight_with_info(flight: str, info_map: dict[str, tuple[object, object]]) -> str:
    flight = str(flight or "").strip()
    if not flight:
        return ""
    if not info_map:
        return flight
    info = info_map.get(flight)
    if info is None:
        return flight
    cat_value, pos_value = info
    cat = _format_category_short(cat_value)
    pos = _format_positions_value(pos_value)
    return f"{flight} ( C= {cat} P={pos})"

def _format_flight_cell(flights: list[str], info_map: dict[str, tuple[object, object]]) -> str:
    return ", ".join(_format_flight_with_info(flight, info_map) for flight in flights)

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
    extra_columns: list[str] | None = None,
    extra_header_color: str = "#E6DFF7",
    extra_border_color: str = "#8064A2",
    extra_summary: pd.DataFrame | None = None,
    extra_sheet_name: str = "Summary extra makeups",
):
    wide_color = _normalize_hex_color(wide_color, "#D32F2F")
    narrow_color = _normalize_hex_color(narrow_color, "#FFEBEE")
    color_mode = str(color_mode or "category").strip().lower()
    if color_mode not in ("category", "flight", "terminal"):
        color_mode = "category"

    extra_columns = extra_columns or []
    extra_columns_set = set(extra_columns)
    extra_header_color = _normalize_hex_color(extra_header_color, "#E6DFF7")
    extra_border_color = _normalize_hex_color(extra_border_color, "#8064A2")
    flight_info = _build_flight_info_map(flights_out)

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

        if color_mode == "category":
            worksheet.write(1, 1, "Wide", _legend(wide_color))
            worksheet.write(2, 1, "Narrow", _legend(narrow_color))
        elif color_mode == "flight":
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
            row_ptr = 1
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
            row_ptr = 1
            for term in sorted(terminal_color.keys()):
                worksheet.write(row_ptr, 1, term, _legend(terminal_color[term]))
                row_ptr += 1

        if timeline_df.empty or len(timeline_df.columns) == 0:
            return

        if color_mode == "category":
            cat_map = _build_flight_category_map(flights_out)
            for row_idx in range(len(timeline_df)):
                for col_idx in range(len(timeline_df.columns)):
                    cell_value = timeline_df.iat[row_idx, col_idx]
                    is_extra = timeline_df.columns[col_idx] in extra_columns_set
                    flights = _extract_flights(cell_value)
                    if not flights:
                        continue
                    display_value = _format_flight_cell(flights, flight_info)
                    has_wide = False
                    has_narrow = False
                    for flight in flights:
                        cat = cat_map.get(flight)
                        if cat == "wide":
                            has_wide = True
                            break
                        if cat == "narrow":
                            has_narrow = True
                    if has_wide:
                        fmt = _fill(wide_color, is_extra)
                    elif has_narrow:
                        fmt = _fill(narrow_color, is_extra)
                    else:
                        fmt = None
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
                    display_value = _format_flight_cell(flights, flight_info)
                    term = None
                    for flight in flights:
                        term = flight_terminal.get(flight)
                        if term:
                            break
                    if not term:
                        term = _extract_terminal_from_column(timeline_df.columns[col_idx])
                    color = terminal_color.get(term) if term else None
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
                    display_value = _format_flight_cell(flights, flight_info)
                    color = flight_color.get(flights[0])
                    fmt = _fill(color, is_extra) if color else None
                    if fmt:
                        worksheet.write(row_idx + 1, col_idx + 2, display_value, fmt)
                    else:
                        worksheet.write(row_idx + 1, col_idx + 2, display_value)
