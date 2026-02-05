from __future__ import annotations

import re


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
