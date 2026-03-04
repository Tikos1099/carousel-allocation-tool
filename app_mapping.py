from __future__ import annotations

import re
import unicodedata
import pandas as pd


def _norm(s: str) -> str:
    s = str(s).strip()
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = s.lower()
    s = re.sub(r"\s+", " ", s)
    return s


def _guess_col(cols, keywords):
    norm_map = {c: _norm(c) for c in cols}
    for kw in keywords:
        for c, nc in norm_map.items():
            if kw in nc:
                return c
    return None


def suggest_cat(v: str) -> str:
    s = v.strip().lower()
    if "wide" in s or s in ["wb", "w"]:
        return "Wide"
    if "narrow" in s or s in ["nb", "n"]:
        return "Narrow"
    return "IGNORER"


def suggest_term(v: str) -> str:
    s = v.strip().upper()
    m = re.search(r"(\d+)", s)
    if s.startswith("T") and len(s) >= 2 and s[1].isdigit():
        return "T" + re.search(r"\d+", s).group(0)
    if "TERMINAL" in s and m:
        return "T" + m.group(1)
    if m and len(m.group(1)) <= 2:
        return "T" + m.group(1)
    return s if s else "INCONNU"


def _apply_cat_term_mapping(df: pd.DataFrame, cat_mapping: dict, term_mapping: dict):
    warnings = []
    df = df.copy()
    df["_CategoryStd"] = df["Category"].astype(str).str.strip().map(lambda x: cat_mapping.get(x, "IGNORER"))
    ignored_cat = df[df["_CategoryStd"] == "IGNORER"]
    if len(ignored_cat) > 0:
        warnings.append({
            "Type": "Category non mappee",
            "Message": "Lignes ignorees (Category non mappee)",
            "Count": int(len(ignored_cat)),
        })
    df = df[df["_CategoryStd"] != "IGNORER"].copy()
    df["Category"] = df["_CategoryStd"]
    df = df.drop(columns=["_CategoryStd"])

    if "Terminal" in df.columns and term_mapping:
        term_map = {}
        for key, value in (term_mapping or {}).items():
            k = str(key).strip().upper()
            if not k:
                continue
            v = str(value).strip()
            if v.lower() in ("ignore", "ignorer", "ignored", "none", "null", "nan"):
                term_map[k] = "IGNORER"
            else:
                term_map[k] = v.strip().upper()

        df["_TerminalStd"] = (
            df["Terminal"].astype(str).str.strip().str.upper().map(lambda x: term_map.get(x, "IGNORER"))
        )
        ignored_term = df[df["_TerminalStd"] == "IGNORER"]
        if len(ignored_term) > 0:
            warnings.append({
                "Type": "Terminal non mappe",
                "Message": "Lignes ignorees (Terminal non mappe)",
                "Count": int(len(ignored_term)),
            })
        df = df[df["_TerminalStd"] != "IGNORER"].copy()
        df["Terminal"] = df["_TerminalStd"].astype(str).str.strip().str.upper()
        df = df.drop(columns=["_TerminalStd"])

    return df, warnings
