from __future__ import annotations

import pandas as pd

from io_flight_info import (
    _build_flight_category_map,
    _build_flight_color_map,
    _build_flight_info_map,
    _build_flight_segment_positions_map,
    _build_flight_status_map,
    _build_flight_terminal_map,
    _build_terminal_color_map,
    _format_flight_cell,
)
from io_utils import (
    _extract_flights,
    _extract_terminal_from_column,
    _normalize_hex_color,
)


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
