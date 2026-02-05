from __future__ import annotations

import re
import pandas as pd


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
