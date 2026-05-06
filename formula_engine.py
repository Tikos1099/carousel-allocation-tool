"""
formula_engine.py — Moteur d'évaluation des formules Excel-like pour le Mapping Tool.

Fonctions exportées :
    _split_formula_args      — découpage des arguments (guillemets + parenthèses)
    _find_comparison_in_cond — premier opérateur de comparaison à profondeur 0
    _rfind_op_at_depth0      — dernier opérateur arithmétique à profondeur 0
    _eval_condition          — évalue une condition booléenne (AND/OR/NOT/comparaisons/fonctions)
    _eval_mapping_formula    — évalue une formule et retourne une pd.Series

Toutes les fonctions évaluent leurs arguments récursivement via _eval_mapping_formula.
Combinaisons arbitrairement imbriquées supportées : IFERROR(INDEX(...,MATCH(...&...,...)),"")
etc.

Fonctions disponibles :
    Texte    : LEFT, RIGHT, MID, LEN, UPPER, LOWER, TRIM, FIND, SEARCH,
               TEXTBEFORE, TEXTAFTER, SUBSTITUTE, CONCAT, &
    Nombre   : VALUE, ROUND, INT, ABS, MOD, POWER, SQRT, MIN, MAX, SUM, AVERAGE
    Dates    : DATE, TODAY, NOW, YEAR, MONTH, DAY, HOUR, MINUTE, SECOND,
               DATEADD, DATEDIFF, TEXT, DATEVALUE, TIMEVALUE
    Temps    : TIMETOMIN, TIMETOHOUR, TIMETOSEC
    Cond.    : IF, IFS, AND, OR, NOT, IFERROR, IFNA, ISBLANK, ISNUMBER, ISTEXT
    Lookup   : VLOOKUP, MATCH, INDEX
    Divers   : LET, CHOOSE, RAND, RANDBETWEEN, COALESCE, ROW
"""

from __future__ import annotations

import re
from typing import Any, Optional

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Helpers de parsing
# ---------------------------------------------------------------------------

def _split_formula_args(s: str) -> list:
    """Split comma-separated formula arguments respecting nested parentheses and quoted strings."""
    args: list = []
    depth = 0
    in_quote = False
    quote_char = ""
    current: list = []
    for ch in s:
        if ch in ('"', "'") and not in_quote:
            in_quote, quote_char = True, ch
            current.append(ch)
        elif ch == quote_char and in_quote:
            in_quote = False
            current.append(ch)
        elif ch == "(" and not in_quote:
            depth += 1
            current.append(ch)
        elif ch == ")" and not in_quote:
            depth -= 1
            current.append(ch)
        elif ch == "," and depth == 0 and not in_quote:
            args.append("".join(current).strip())
            current = []
        else:
            current.append(ch)
    if current:
        args.append("".join(current).strip())
    return args


def _find_comparison_in_cond(s: str) -> Optional[tuple]:
    """Find the first comparison operator at paren-depth=0 outside quotes.
    Returns (op, left_str, right_str) or None. Operators checked longest-first."""
    ops = (">=", "<=", "<>", "!=", ">", "<", "=")
    in_quote = False
    quote_char = ""
    depth = 0
    i = 0
    while i < len(s):
        ch = s[i]
        if ch in ('"', "'") and not in_quote:
            in_quote, quote_char = True, ch
        elif ch == quote_char and in_quote:
            in_quote = False
        elif ch == "(" and not in_quote:
            depth += 1
        elif ch == ")" and not in_quote:
            depth -= 1
        elif depth == 0 and not in_quote:
            for op in ops:
                if s[i:i + len(op)] == op:
                    return op, s[:i].strip(), s[i + len(op):].strip()
        i += 1
    return None


def _rfind_op_at_depth0(expr: str, ops: tuple) -> Optional[tuple]:
    """Find the rightmost operator from `ops` at paren-depth=0 outside quotes, position > 0.
    Returns (op, left_str, right_str) or None."""
    in_q = False; q_ch = ""; depth = 0
    last_pos: Optional[int] = None; last_op: Optional[str] = None
    i = 0
    while i < len(expr):
        ch = expr[i]
        if ch in ('"', "'") and not in_q:
            in_q, q_ch = True, ch
        elif ch == q_ch and in_q:
            in_q = False
        elif ch == "(" and not in_q:
            depth += 1
        elif ch == ")" and not in_q:
            depth -= 1
        elif depth == 0 and not in_q and i > 0:
            for op in ops:
                if expr[i:i + len(op)] == op:
                    last_pos, last_op = i, op
                    break
        i += 1
    if last_pos is not None and last_op is not None:
        return last_op, expr[:last_pos].strip(), expr[last_pos + len(last_op):].strip()
    return None


# ---------------------------------------------------------------------------
# Évaluation des conditions
# ---------------------------------------------------------------------------

def _eval_condition(cond: str, df: pd.DataFrame) -> "pd.Series":
    """Return a boolean Series for a condition string.

    Handles :
      - AND(c1, c2, ...) / OR(c1, c2, ...) / NOT(c)
      - Comparisons : Col="val", LEFT(Col,3)>"X", etc.
      - Boolean-returning formulas : ISBLANK(Col), ISNUMBER(Col), ISTEXT(Col)  [BUG 2 fix]
    """
    cond = cond.strip()
    n = len(df)

    # AND(cond1, cond2, ...)
    m = re.match(r'^AND\((.+)\)$', cond, re.IGNORECASE | re.DOTALL)
    if m:
        parts = _split_formula_args(m.group(1))
        result: "pd.Series" = pd.Series([True] * n)
        for p in parts:
            result = result & _eval_condition(p.strip(), df)
        return result.reset_index(drop=True)

    # OR(cond1, cond2, ...)
    m = re.match(r'^OR\((.+)\)$', cond, re.IGNORECASE | re.DOTALL)
    if m:
        parts = _split_formula_args(m.group(1))
        result = pd.Series([False] * n)
        for p in parts:
            result = result | _eval_condition(p.strip(), df)
        return result.reset_index(drop=True)

    # NOT(cond)
    m = re.match(r'^NOT\((.+)\)$', cond, re.IGNORECASE | re.DOTALL)
    if m:
        return (~_eval_condition(m.group(1).strip(), df)).reset_index(drop=True)

    # Comparison — depth-aware scan so operators inside parentheses are ignored
    found = _find_comparison_in_cond(cond)
    if found:
        op_str, left_s, right_s = found

        try:
            left_col = _eval_mapping_formula(left_s, df)
        except Exception:
            left_col = pd.Series([left_s] * n)

        if (right_s.startswith('"') and right_s.endswith('"')) or \
           (right_s.startswith("'") and right_s.endswith("'")):
            raw_str = right_s[1:-1]
            if pd.api.types.is_datetime64_any_dtype(left_col):
                try:
                    right_val: Any = pd.to_datetime(raw_str)
                except Exception:
                    right_val = raw_str
                    left_col = left_col.astype(str)
            else:
                right_val = raw_str
                left_col = left_col.astype(str)
        else:
            try:
                rv = float(right_s)
                right_val = int(rv) if rv == int(rv) else rv
                left_col = pd.to_numeric(left_col, errors="coerce")
            except ValueError:
                try:
                    right_val = _eval_mapping_formula(right_s, df)
                    # BUG FIX: préférer la comparaison numérique quand possible.
                    # Avant : les deux côtés étaient castés en string →
                    #   - "0.xxx" < "" (colonne absente) = toujours False
                    #   - "0.xxx" < "nan" (résultat NaN) = toujours True
                    # Ces deux cas combinés donnaient "toujours Car 2" dans LET+IF.
                    right_num = pd.to_numeric(right_val, errors="coerce")
                    left_num = pd.to_numeric(left_col, errors="coerce")
                    if right_num.notna().any():
                        right_val = right_num
                        left_col = left_num
                    else:
                        left_col = left_col.astype(str)
                        right_val = right_val.astype(str)
                except Exception:
                    right_val = right_s
                    left_col = left_col.astype(str)

        ops_map = {
            ">=": lambda a, b: a >= b,
            "<=": lambda a, b: a <= b,
            "<>": lambda a, b: a != b,
            "!=": lambda a, b: a != b,
            ">":  lambda a, b: a > b,
            "<":  lambda a, b: a < b,
            "=":  lambda a, b: a == b,
        }
        try:
            return ops_map[op_str](left_col, right_val).reset_index(drop=True)
        except Exception:
            return pd.Series([False] * n)

    # BUG 2 FIX — conditions qui sont des fonctions booléennes (ISBLANK, ISNUMBER, ISTEXT...)
    # Avant : retournait Series([True]*n) → condition toujours vraie, résultat IF incorrect.
    # Maintenant : on évalue la formule et on cast en bool.
    try:
        result = _eval_mapping_formula(cond, df)
        return result.astype(bool).reset_index(drop=True)
    except Exception:
        pass

    return pd.Series([False] * n)


# ---------------------------------------------------------------------------
# Évaluation des formules
# ---------------------------------------------------------------------------

def _eval_mapping_formula(expr: str, df: pd.DataFrame) -> pd.Series:
    # Normalize semicolons used as argument separators (French/Belgian Excel)
    _norm: list = []; _in_q = False; _qc = ""
    for _ch in expr:
        if _ch in ('"', "'") and not _in_q:
            _in_q = True; _qc = _ch; _norm.append(_ch)
        elif _ch == _qc and _in_q:
            _in_q = False; _norm.append(_ch)
        elif _ch == ";" and not _in_q:
            _norm.append(",")
        else:
            _norm.append(_ch)
    expr = "".join(_norm).strip()
    n = len(df)
    empty: pd.Series = pd.Series([""] * n, dtype=object)

    if not expr:
        return empty

    # String constant
    if (expr.startswith('"') and expr.endswith('"')) or (expr.startswith("'") and expr.endswith("'")):
        return pd.Series([expr[1:-1]] * n)

    # Numeric constant
    try:
        val = float(expr)
        v: Any = int(val) if val == int(val) else val
        return pd.Series([v] * n)
    except (ValueError, TypeError):
        pass

    # Simple column reference
    if expr in df.columns:
        return df[expr].reset_index(drop=True)

    # Parenthesized expression — strip outer parens and re-evaluate
    if expr.startswith("(") and expr.endswith(")"):
        _pdepth = 0; _fully = True
        for _pi, _pc in enumerate(expr):
            if _pc == "(": _pdepth += 1
            elif _pc == ")": _pdepth -= 1
            if _pdepth == 0 and _pi < len(expr) - 1:
                _fully = False; break
        if _fully:
            return _eval_mapping_formula(expr[1:-1], df)

    # ------------------------------------------------------------------
    # Fonctions texte — BUG 1 FIX : évaluation récursive du 1er argument
    # Avant : if col in df.columns: df[col]... → échouait silencieusement
    # pour les formules imbriquées (ex. LEFT(RIGHT(Col,5),3)).
    # ------------------------------------------------------------------

    # LEFT(expr, k)
    m = re.match(r'^LEFT\((.+)\)$', expr, re.IGNORECASE)
    if m:
        args = _split_formula_args(m.group(1))
        if len(args) == 2:
            src = _eval_mapping_formula(args[0].strip(), df).astype(str)
            k_s = pd.to_numeric(_eval_mapping_formula(args[1].strip(), df), errors="coerce").fillna(0)
            return pd.Series([s[:int(k)] for s, k in zip(src, k_s)]).reset_index(drop=True)

    # RIGHT(expr, k)
    m = re.match(r'^RIGHT\((.+)\)$', expr, re.IGNORECASE)
    if m:
        args = _split_formula_args(m.group(1))
        if len(args) == 2:
            src = _eval_mapping_formula(args[0].strip(), df).astype(str)
            k_s = pd.to_numeric(_eval_mapping_formula(args[1].strip(), df), errors="coerce").fillna(0)
            return pd.Series([s[-int(k):] if int(k) > 0 else "" for s, k in zip(src, k_s)]).reset_index(drop=True)

    # MID(expr, start, length)
    m = re.match(r'^MID\((.+)\)$', expr, re.IGNORECASE)
    if m:
        args = _split_formula_args(m.group(1))
        if len(args) == 3:
            src = _eval_mapping_formula(args[0].strip(), df).astype(str)
            s_s = pd.to_numeric(_eval_mapping_formula(args[1].strip(), df), errors="coerce").fillna(1)
            l_s = pd.to_numeric(_eval_mapping_formula(args[2].strip(), df), errors="coerce").fillna(0)
            return pd.Series([x[int(s)-1:int(s)-1+int(l)] for x, s, l in zip(src, s_s, l_s)]).reset_index(drop=True)

    # LEN(expr)
    m = re.match(r'^LEN\((.+)\)$', expr, re.IGNORECASE)
    if m:
        src = _eval_mapping_formula(m.group(1).strip(), df)
        return src.astype(str).str.len().reset_index(drop=True)

    # UPPER(expr)
    m = re.match(r'^UPPER\((.+)\)$', expr, re.IGNORECASE)
    if m:
        src = _eval_mapping_formula(m.group(1).strip(), df)
        return src.astype(str).str.upper().reset_index(drop=True)

    # LOWER(expr)
    m = re.match(r'^LOWER\((.+)\)$', expr, re.IGNORECASE)
    if m:
        src = _eval_mapping_formula(m.group(1).strip(), df)
        return src.astype(str).str.lower().reset_index(drop=True)

    # TRIM(expr)
    m = re.match(r'^TRIM\((.+)\)$', expr, re.IGNORECASE)
    if m:
        src = _eval_mapping_formula(m.group(1).strip(), df)
        return src.astype(str).str.strip().reset_index(drop=True)

    # TEXTBEFORE(expr, delim)
    m = re.match(r'^TEXTBEFORE\((.+)\)$', expr, re.IGNORECASE)
    if m:
        args = _split_formula_args(m.group(1))
        if len(args) >= 2:
            src = _eval_mapping_formula(args[0].strip(), df).astype(str)
            delim_s = _eval_mapping_formula(args[1].strip(), df).astype(str)
            return pd.Series([x.split(d)[0] if d in x else x for x, d in zip(src, delim_s)]).reset_index(drop=True)

    # TEXTAFTER(expr, delim)
    m = re.match(r'^TEXTAFTER\((.+)\)$', expr, re.IGNORECASE)
    if m:
        args = _split_formula_args(m.group(1))
        if len(args) >= 2:
            src = _eval_mapping_formula(args[0].strip(), df).astype(str)
            delim_s = _eval_mapping_formula(args[1].strip(), df).astype(str)
            return pd.Series([d.join(x.split(d)[1:]) if d in x else x for x, d in zip(src, delim_s)]).reset_index(drop=True)

    # SUBSTITUTE(expr, old, new[, instance])
    m = re.match(r'^SUBSTITUTE\((.+)\)$', expr, re.IGNORECASE)
    if m:
        args = _split_formula_args(m.group(1))
        if len(args) >= 3:
            src = _eval_mapping_formula(args[0].strip(), df).astype(str)
            old_s = _eval_mapping_formula(args[1].strip(), df).astype(str)
            new_s = _eval_mapping_formula(args[2].strip(), df).astype(str)
            return pd.Series([x.replace(o, nw) for x, o, nw in zip(src, old_s, new_s)]).reset_index(drop=True)

    # FIND(find_text, within_text[, start_num]) — case-sensitive position (1-based), NaN if not found
    m = re.match(r'^FIND\((.+)\)$', expr, re.IGNORECASE)
    if m:
        args = _split_formula_args(m.group(1))
        if len(args) >= 2:
            find_s = _eval_mapping_formula(args[0].strip(), df).astype(str)
            within_s = _eval_mapping_formula(args[1].strip(), df).astype(str)
            start_s = pd.to_numeric(_eval_mapping_formula(args[2].strip(), df), errors="coerce").fillna(1) if len(args) >= 3 else pd.Series([1] * n)
            def _find_pos(f, w, s):
                try:
                    pos = w.find(f, int(s) - 1)
                    return pos + 1 if pos >= 0 else float("nan")
                except Exception:
                    return float("nan")
            return pd.Series([_find_pos(f, w, s) for f, w, s in zip(find_s, within_s, start_s)]).reset_index(drop=True)

    # SEARCH(find_text, within_text[, start_num]) — case-insensitive FIND
    m = re.match(r'^SEARCH\((.+)\)$', expr, re.IGNORECASE)
    if m:
        args = _split_formula_args(m.group(1))
        if len(args) >= 2:
            find_s = _eval_mapping_formula(args[0].strip(), df).astype(str)
            within_s = _eval_mapping_formula(args[1].strip(), df).astype(str)
            start_s = pd.to_numeric(_eval_mapping_formula(args[2].strip(), df), errors="coerce").fillna(1) if len(args) >= 3 else pd.Series([1] * n)
            def _search_pos(f, w, s):
                try:
                    pos = w.lower().find(f.lower(), int(s) - 1)
                    return pos + 1 if pos >= 0 else float("nan")
                except Exception:
                    return float("nan")
            return pd.Series([_search_pos(f, w, s) for f, w, s in zip(find_s, within_s, start_s)]).reset_index(drop=True)

    # VALUE(expr) — convert text to number
    m = re.match(r'^VALUE\((.+)\)$', expr, re.IGNORECASE)
    if m:
        src = _eval_mapping_formula(m.group(1).strip(), df)
        return pd.to_numeric(src, errors="coerce").reset_index(drop=True)

    # ROUND(expr, decimals)
    m = re.match(r'^ROUND\((.+)\)$', expr, re.IGNORECASE)
    if m:
        args = _split_formula_args(m.group(1))
        if len(args) == 2:
            src = pd.to_numeric(_eval_mapping_formula(args[0].strip(), df), errors="coerce")
            dec_s = pd.to_numeric(_eval_mapping_formula(args[1].strip(), df), errors="coerce").fillna(0)
            if dec_s.nunique() == 1:
                return src.round(int(dec_s.iloc[0])).reset_index(drop=True)
            return pd.Series([round(v, int(d)) if pd.notna(v) else v for v, d in zip(src, dec_s)]).reset_index(drop=True)

    # INT(expr) — floor to integer
    m = re.match(r'^INT\((.+)\)$', expr, re.IGNORECASE)
    if m:
        src = pd.to_numeric(_eval_mapping_formula(m.group(1).strip(), df), errors="coerce")
        return src.apply(lambda x: int(x) if pd.notna(x) else "").reset_index(drop=True)

    # ABS(expr)
    m = re.match(r'^ABS\((.+)\)$', expr, re.IGNORECASE)
    if m:
        src = pd.to_numeric(_eval_mapping_formula(m.group(1).strip(), df), errors="coerce")
        return src.abs().reset_index(drop=True)

    # IFERROR(formula, fallback)
    m = re.match(r'^IFERROR\((.+)\)$', expr, re.IGNORECASE)
    if m:
        args = _split_formula_args(m.group(1))
        if len(args) == 2:
            try:
                result = _eval_mapping_formula(args[0].strip(), df)
            except Exception:
                result = pd.Series([""] * n, dtype=object)
            fallback = _eval_mapping_formula(args[1].strip(), df)
            combined = result.where(result.notna() & (result.astype(str) != "nan"), other=fallback)
            return combined.reset_index(drop=True)

    # ISNUMBER(expr)
    m = re.match(r'^ISNUMBER\((.+)\)$', expr, re.IGNORECASE)
    if m:
        src = _eval_mapping_formula(m.group(1).strip(), df)
        return pd.to_numeric(src, errors="coerce").notna().reset_index(drop=True)

    # ISBLANK(expr)
    m = re.match(r'^ISBLANK\((.+)\)$', expr, re.IGNORECASE)
    if m:
        src = _eval_mapping_formula(m.group(1).strip(), df)
        return (src.isna() | (src.astype(str).str.strip() == "")).reset_index(drop=True)

    # ISTEXT(expr)
    m = re.match(r'^ISTEXT\((.+)\)$', expr, re.IGNORECASE)
    if m:
        src = _eval_mapping_formula(m.group(1).strip(), df)
        return (pd.to_numeric(src, errors="coerce").isna() & src.notna()).reset_index(drop=True)

    # DATE(year, month, day)
    m = re.match(r'^DATE\((.+)\)$', expr, re.IGNORECASE)
    if m:
        args = _split_formula_args(m.group(1))
        if len(args) == 3:
            y_s = pd.to_numeric(_eval_mapping_formula(args[0].strip(), df), errors="coerce")
            mo_s = pd.to_numeric(_eval_mapping_formula(args[1].strip(), df), errors="coerce")
            d_s = pd.to_numeric(_eval_mapping_formula(args[2].strip(), df), errors="coerce")
            def _mk_ts(yr, mn, dy):
                try: return pd.Timestamp(int(yr), int(mn), int(dy))
                except Exception: return pd.NaT
            return pd.Series([_mk_ts(yr, mn, dy) for yr, mn, dy in zip(y_s, mo_s, d_s)]).reset_index(drop=True)

    # TODAY()
    if re.match(r'^TODAY\(\)$', expr, re.IGNORECASE):
        return pd.Series([pd.Timestamp.today().normalize()] * n)

    # NOW()
    if re.match(r'^NOW\(\)$', expr, re.IGNORECASE):
        return pd.Series([pd.Timestamp.now()] * n)

    # YEAR/MONTH/DAY/HOUR/MINUTE/SECOND(expr)
    m = re.match(r'^(YEAR|MONTH|DAY|HOUR|MINUTE|SECOND)\((.+)\)$', expr, re.IGNORECASE)
    if m:
        fn = m.group(1).upper()
        src_eval = _eval_mapping_formula(m.group(2).strip(), df)

        if pd.api.types.is_timedelta64_dtype(src_eval) and fn in ("HOUR", "MINUTE", "SECOND"):
            ts = src_eval.dt.total_seconds()
            if fn == "HOUR":   return (ts // 3600).reset_index(drop=True)
            if fn == "MINUTE": return ((ts % 3600) // 60).reset_index(drop=True)
            if fn == "SECOND": return (ts % 60).reset_index(drop=True)

        if pd.api.types.is_numeric_dtype(src_eval) and fn in ("HOUR", "MINUTE", "SECOND"):
            ts = src_eval % 1 * 86400
            if fn == "HOUR":   return (ts // 3600).reset_index(drop=True)
            if fn == "MINUTE": return ((ts % 3600) // 60).reset_index(drop=True)
            if fn == "SECOND": return (ts % 60).reset_index(drop=True)

        if pd.api.types.is_datetime64_any_dtype(src_eval):
            src_dt = src_eval
        elif pd.api.types.is_timedelta64_dtype(src_eval):
            src_dt = pd.Timestamp("2000-01-01") + src_eval
        else:
            def _coerce_dt(x):
                try:
                    if x is None or (not hasattr(x, 'hour') and pd.isna(x)):
                        return pd.NaT
                    if hasattr(x, 'hour') and hasattr(x, 'minute'):
                        return pd.Timestamp(2000, 1, 1, x.hour, x.minute, getattr(x, 'second', 0))
                    if hasattr(x, 'total_seconds'):
                        s = float(x.total_seconds())
                        return pd.Timestamp(2000, 1, 1, int(s // 3600), int(s % 3600 // 60), int(s % 60))
                    return pd.to_datetime(x, errors='coerce')
                except Exception:
                    return pd.NaT
            src_dt = src_eval.apply(_coerce_dt)

        parts = {"YEAR": src_dt.dt.year, "MONTH": src_dt.dt.month, "DAY": src_dt.dt.day,
                 "HOUR": src_dt.dt.hour, "MINUTE": src_dt.dt.minute, "SECOND": src_dt.dt.second}
        return parts[fn].reset_index(drop=True)

    # DATEVALUE(expr)
    m = re.match(r'^DATEVALUE\((.+)\)$', expr, re.IGNORECASE)
    if m:
        src = _eval_mapping_formula(m.group(1).strip(), df)
        return pd.to_datetime(src, errors="coerce").dt.normalize().reset_index(drop=True)

    # TIMEVALUE(expr)
    m = re.match(r'^TIMEVALUE\((.+)\)$', expr, re.IGNORECASE)
    if m:
        src = _eval_mapping_formula(m.group(1).strip(), df)
        dt_t = pd.to_datetime(src, errors="coerce")
        return ((dt_t.dt.hour * 3600 + dt_t.dt.minute * 60 + dt_t.dt.second) / 86400.0).reset_index(drop=True)

    # TEXT(expr, "format")
    m = re.match(r'^TEXT\((.+)\)$', expr, re.IGNORECASE)
    if m:
        args = _split_formula_args(m.group(1))
        if len(args) == 2:
            src = _eval_mapping_formula(args[0].strip(), df)
            fmt_raw = args[1].strip().strip("\"'")
            py_chars: list = []; fi = 0
            while fi < len(fmt_raw):
                if fmt_raw[fi:fi+4] == "yyyy":          py_chars.append("%Y"); fi += 4
                elif fmt_raw[fi:fi+2] == "yy":          py_chars.append("%y"); fi += 2
                elif fmt_raw[fi:fi+2] == "MM":          py_chars.append("%m"); fi += 2
                elif fmt_raw[fi:fi+2] == "dd":          py_chars.append("%d"); fi += 2
                elif fmt_raw[fi:fi+2] in ("HH", "hh"): py_chars.append("%H"); fi += 2
                elif fmt_raw[fi:fi+2] == "mm":          py_chars.append("%M"); fi += 2
                elif fmt_raw[fi:fi+2] == "ss":          py_chars.append("%S"); fi += 2
                else: py_chars.append(fmt_raw[fi]); fi += 1
            py_fmt = "".join(py_chars)
            return pd.to_datetime(src, errors="coerce").dt.strftime(py_fmt).reset_index(drop=True)

    # DATEADD(date, n, "unit")
    m = re.match(r'^DATEADD\((.+)\)$', expr, re.IGNORECASE)
    if m:
        args = _split_formula_args(m.group(1))
        if len(args) == 3:
            dt_da = pd.to_datetime(_eval_mapping_formula(args[0].strip(), df), errors="coerce")
            n_da = pd.to_numeric(_eval_mapping_formula(args[1].strip(), df), errors="coerce").fillna(0)
            unit_da = args[2].strip().strip("\"'").lower()
            _u = {"day":"D","days":"D","d":"D","hour":"h","hours":"h","h":"h",
                  "minute":"min","minutes":"min","m":"min","min":"min","second":"s","seconds":"s","s":"s"}
            return (dt_da + pd.to_timedelta(n_da, unit=_u.get(unit_da, "D"))).reset_index(drop=True)

    # DATEDIFF(date1, date2, "unit")
    m = re.match(r'^DATEDIFF\((.+)\)$', expr, re.IGNORECASE)
    if m:
        args = _split_formula_args(m.group(1))
        if len(args) >= 2:
            dt1 = pd.to_datetime(_eval_mapping_formula(args[0].strip(), df), errors="coerce")
            dt2 = pd.to_datetime(_eval_mapping_formula(args[1].strip(), df), errors="coerce")
            unit_dd = args[2].strip().strip("\"'").lower() if len(args) >= 3 else "day"
            diff = dt2 - dt1
            if unit_dd in ("day", "days", "d"):              return diff.dt.days.reset_index(drop=True)
            if unit_dd in ("hour", "hours", "h"):            return (diff.dt.total_seconds() / 3600).reset_index(drop=True)
            if unit_dd in ("minute", "minutes", "m", "min"): return (diff.dt.total_seconds() / 60).reset_index(drop=True)
            return diff.dt.days.reset_index(drop=True)

    # TIMETOMIN(time[, day])
    m = re.match(r'^TIMETOMIN\((.+)\)$', expr, re.IGNORECASE)
    if m:
        args = _split_formula_args(m.group(1))
        t_src = _eval_mapping_formula(args[0].strip(), df)
        if pd.api.types.is_timedelta64_dtype(t_src):
            mins = t_src.dt.total_seconds() / 60
        elif pd.api.types.is_numeric_dtype(t_src):
            mins = t_src % 1 * 1440
        else:
            def _t2s(x):
                try:
                    if x is None: return float("nan")
                    if hasattr(x, 'hour'): return x.hour * 60 + x.minute + getattr(x, 'second', 0) / 60
                    if hasattr(x, 'total_seconds'): return x.total_seconds() / 60
                    ts = pd.to_datetime(x, errors='coerce')
                    return float("nan") if pd.isna(ts) else ts.hour * 60 + ts.minute + ts.second / 60
                except Exception: return float("nan")
            mins = t_src.apply(_t2s)
        if len(args) >= 2:
            day_src = pd.to_numeric(_eval_mapping_formula(args[1].strip(), df), errors="coerce").fillna(0)
            mins = mins + day_src * 1440
        return mins.reset_index(drop=True)

    # TIMETOHOUR(time[, day])
    m = re.match(r'^TIMETOHOUR\((.+)\)$', expr, re.IGNORECASE)
    if m:
        args = _split_formula_args(m.group(1))
        t_src = _eval_mapping_formula(args[0].strip(), df)
        if pd.api.types.is_timedelta64_dtype(t_src):
            hrs = t_src.dt.total_seconds() / 3600
        elif pd.api.types.is_numeric_dtype(t_src):
            hrs = t_src % 1 * 24
        else:
            def _t2h(x):
                try:
                    if x is None: return float("nan")
                    if hasattr(x, 'hour'): return x.hour + x.minute / 60 + getattr(x, 'second', 0) / 3600
                    if hasattr(x, 'total_seconds'): return x.total_seconds() / 3600
                    ts = pd.to_datetime(x, errors='coerce')
                    return float("nan") if pd.isna(ts) else ts.hour + ts.minute / 60 + ts.second / 3600
                except Exception: return float("nan")
            hrs = t_src.apply(_t2h)
        if len(args) >= 2:
            day_src = pd.to_numeric(_eval_mapping_formula(args[1].strip(), df), errors="coerce").fillna(0)
            hrs = hrs + day_src * 24
        return hrs.reset_index(drop=True)

    # TIMETOSEC(time[, day])
    m = re.match(r'^TIMETOSEC\((.+)\)$', expr, re.IGNORECASE)
    if m:
        args = _split_formula_args(m.group(1))
        t_src = _eval_mapping_formula(args[0].strip(), df)
        if pd.api.types.is_timedelta64_dtype(t_src):
            secs = t_src.dt.total_seconds()
        elif pd.api.types.is_numeric_dtype(t_src):
            secs = t_src % 1 * 86400
        else:
            def _t2sec(x):
                try:
                    if x is None: return float("nan")
                    if hasattr(x, 'hour'): return x.hour * 3600 + x.minute * 60 + getattr(x, 'second', 0)
                    if hasattr(x, 'total_seconds'): return x.total_seconds()
                    ts = pd.to_datetime(x, errors='coerce')
                    return float("nan") if pd.isna(ts) else ts.hour * 3600 + ts.minute * 60 + ts.second
                except Exception: return float("nan")
            secs = t_src.apply(_t2sec)
        if len(args) >= 2:
            day_src = pd.to_numeric(_eval_mapping_formula(args[1].strip(), df), errors="coerce").fillna(0)
            secs = secs + day_src * 86400
        return secs.reset_index(drop=True)

    # RAND() / ALEA()
    if re.match(r'^(?:RAND|ALEA)\(\)$', expr, re.IGNORECASE):
        return pd.Series(np.random.random(n))

    # RANDBETWEEN(min, max) / ALEA.ENTRE.BORNES(min, max)
    m = re.match(r'^(?:RANDBETWEEN|ALEA\.ENTRE\.BORNES)\((.+)\)$', expr, re.IGNORECASE)
    if m:
        args = _split_formula_args(m.group(1))
        if len(args) == 2:
            lo = pd.to_numeric(_eval_mapping_formula(args[0].strip(), df), errors="coerce").fillna(0)
            hi = pd.to_numeric(_eval_mapping_formula(args[1].strip(), df), errors="coerce").fillna(1)
            return pd.Series([int(np.random.randint(int(a), int(b) + 1)) for a, b in zip(lo, hi)])

    # MOD(value, divisor)
    m = re.match(r'^MOD\((.+)\)$', expr, re.IGNORECASE)
    if m:
        args = _split_formula_args(m.group(1))
        if len(args) == 2:
            a = pd.to_numeric(_eval_mapping_formula(args[0].strip(), df), errors="coerce")
            b = pd.to_numeric(_eval_mapping_formula(args[1].strip(), df), errors="coerce")
            return (a % b).reset_index(drop=True)

    # POWER(base, exp) / PUISSANCE(base, exp)
    m = re.match(r'^(?:POWER|PUISSANCE)\((.+)\)$', expr, re.IGNORECASE)
    if m:
        args = _split_formula_args(m.group(1))
        if len(args) == 2:
            base = pd.to_numeric(_eval_mapping_formula(args[0].strip(), df), errors="coerce")
            exp_ = pd.to_numeric(_eval_mapping_formula(args[1].strip(), df), errors="coerce")
            return (base ** exp_).reset_index(drop=True)

    # SQRT(value)
    m = re.match(r'^SQRT\((.+)\)$', expr, re.IGNORECASE)
    if m:
        src = pd.to_numeric(_eval_mapping_formula(m.group(1).strip(), df), errors="coerce")
        return np.sqrt(src).reset_index(drop=True)

    # MIN(a, b, ...)
    m = re.match(r'^MIN\((.+)\)$', expr, re.IGNORECASE)
    if m:
        args = _split_formula_args(m.group(1))
        cols = [pd.to_numeric(_eval_mapping_formula(a.strip(), df), errors="coerce") for a in args]
        return pd.concat(cols, axis=1).min(axis=1).reset_index(drop=True)

    # MAX(a, b, ...)
    m = re.match(r'^MAX\((.+)\)$', expr, re.IGNORECASE)
    if m:
        args = _split_formula_args(m.group(1))
        cols = [pd.to_numeric(_eval_mapping_formula(a.strip(), df), errors="coerce") for a in args]
        return pd.concat(cols, axis=1).max(axis=1).reset_index(drop=True)

    # SUM(a, b, ...) / SOMME(...)
    m = re.match(r'^(?:SUM|SOMME)\((.+)\)$', expr, re.IGNORECASE)
    if m:
        args = _split_formula_args(m.group(1))
        cols = [pd.to_numeric(_eval_mapping_formula(a.strip(), df), errors="coerce").fillna(0) for a in args]
        return pd.concat(cols, axis=1).sum(axis=1).reset_index(drop=True)

    # AVERAGE(a, b, ...) / MOYENNE(...)
    m = re.match(r'^(?:AVERAGE|MOYENNE)\((.+)\)$', expr, re.IGNORECASE)
    if m:
        args = _split_formula_args(m.group(1))
        cols = [pd.to_numeric(_eval_mapping_formula(a.strip(), df), errors="coerce") for a in args]
        return pd.concat(cols, axis=1).mean(axis=1).reset_index(drop=True)

    # IFNA(value, alt)
    m = re.match(r'^IFNA\((.+)\)$', expr, re.IGNORECASE)
    if m:
        args = _split_formula_args(m.group(1))
        if len(args) == 2:
            val_s = _eval_mapping_formula(args[0].strip(), df)
            alt_s = _eval_mapping_formula(args[1].strip(), df)
            mask = val_s.isna() | (val_s.astype(str).isin(["nan", "NaT", ""]))
            return val_s.where(~mask, other=alt_s).reset_index(drop=True)

    # IFS(cond1, val1, cond2, val2, ...) / SI.CONDITIONS(...)
    m = re.match(r'^(?:IFS|SI\.CONDITIONS)\((.+)\)$', expr, re.IGNORECASE)
    if m:
        args = _split_formula_args(m.group(1))
        result = pd.Series([""] * n, dtype=object)
        filled = pd.Series([False] * n)
        for i in range(0, len(args) - 1, 2):
            cond_s = _eval_condition(args[i].strip(), df)
            val_s = _eval_mapping_formula(args[i + 1].strip(), df)
            apply_mask = cond_s & ~filled
            result = result.where(~apply_mask, other=val_s)
            filled = filled | apply_mask
        return result.reset_index(drop=True)

    # CHOOSE(index, val1, val2, ...) / CHOISIR(...)
    m = re.match(r'^(?:CHOOSE|CHOISIR)\((.+)\)$', expr, re.IGNORECASE)
    if m:
        args = _split_formula_args(m.group(1))
        if len(args) >= 2:
            idx_s = pd.to_numeric(_eval_mapping_formula(args[0].strip(), df), errors="coerce")
            options = [_eval_mapping_formula(a.strip(), df) for a in args[1:]]
            result = pd.Series([""] * n, dtype=object)
            for row_i, idx_val in enumerate(idx_s):
                try:
                    ii = int(idx_val) - 1
                    if 0 <= ii < len(options):
                        result.iloc[row_i] = options[ii].iloc[row_i]
                except Exception:
                    pass
            return result.reset_index(drop=True)

    # MATCH(lookup, col[, 0]) / EQUIV(...)
    m = re.match(r'^(?:MATCH|EQUIV)\((.+)\)$', expr, re.IGNORECASE)
    if m:
        args = _split_formula_args(m.group(1))
        if len(args) >= 2:
            lookup_s = _eval_mapping_formula(args[0].strip(), df).astype(str)
            search_s = _eval_mapping_formula(args[1].strip(), df).astype(str)
            search_list = search_s.tolist()
            def _match_fn(val):
                try: return search_list.index(val) + 1
                except ValueError: return float("nan")
            return lookup_s.apply(_match_fn).reset_index(drop=True)

    # INDEX(col, row_num)
    m = re.match(r'^INDEX\((.+)\)$', expr, re.IGNORECASE)
    if m:
        args = _split_formula_args(m.group(1))
        if len(args) == 2:
            col_s = _eval_mapping_formula(args[0].strip(), df)
            row_s = pd.to_numeric(_eval_mapping_formula(args[1].strip(), df), errors="coerce")
            col_list = col_s.tolist()
            def _index_fn(row_num):
                try:
                    ri = int(row_num) - 1
                    return col_list[ri] if 0 <= ri < len(col_list) else float("nan")
                except Exception: return float("nan")
            return row_s.apply(_index_fn).reset_index(drop=True)

    # VLOOKUP(lookup, key_col, result_col[, exact]) / RECHERCHEV(...)
    m = re.match(r'^(?:VLOOKUP|RECHERCHEV)\((.+)\)$', expr, re.IGNORECASE)
    if m:
        args = _split_formula_args(m.group(1))
        if len(args) >= 3:
            lookup_s = _eval_mapping_formula(args[0].strip(), df).astype(str)
            key_s = _eval_mapping_formula(args[1].strip(), df).astype(str)
            result_col_s = _eval_mapping_formula(args[2].strip(), df)
            key_list = key_s.tolist()
            result_list = result_col_s.tolist()
            def _vlookup_fn(val):
                try:
                    idx = key_list.index(val)
                    return result_list[idx]
                except (ValueError, IndexError): return float("nan")
            return lookup_s.apply(_vlookup_fn).reset_index(drop=True)

    # LET(name1, val1, ..., formula)
    m = re.match(r'^LET\((.+)\)$', expr, re.IGNORECASE | re.DOTALL)
    if m:
        args = _split_formula_args(m.group(1))
        if len(args) >= 3 and len(args) % 2 == 1:
            df_let = df.copy()
            for i in range(0, len(args) - 1, 2):
                var_name = args[i].strip().strip("\"'")
                var_val = _eval_mapping_formula(args[i + 1].strip(), df_let)
                df_let[var_name] = var_val.values
            return _eval_mapping_formula(args[-1].strip(), df_let).reset_index(drop=True)

    # NOT(condition)
    m = re.match(r'^NOT\((.+)\)$', expr, re.IGNORECASE)
    if m:
        return (~_eval_condition(m.group(1).strip(), df)).reset_index(drop=True)

    # COALESCE(Col1, Col2, ...)
    m = re.match(r'^COALESCE\((.+)\)$', expr, re.IGNORECASE)
    if m:
        args = _split_formula_args(m.group(1))
        result = pd.Series([""] * n, dtype=object)
        for arg in reversed(args):
            src = _eval_mapping_formula(arg.strip(), df)
            mask = src.notna() & (src.astype(str).str.strip() != "")
            result = src.where(mask, other=result)
        return result.reset_index(drop=True)

    # CONCAT(Col1, Col2, ...)
    m = re.match(r'^CONCAT\((.+)\)$', expr, re.IGNORECASE)
    if m:
        args = _split_formula_args(m.group(1))
        result_str = pd.Series([""] * n, dtype=str)
        for arg in args:
            src = _eval_mapping_formula(arg.strip(), df)
            result_str = result_str + src.fillna("").astype(str)
        return result_str.reset_index(drop=True)

    # IF(condition, true_value, false_value) / SI(...)
    m = re.match(r'^(?:IF|SI)\((.+)\)$', expr, re.IGNORECASE)
    if m:
        args = _split_formula_args(m.group(1))
        if len(args) == 3:
            cond_str, true_str, false_str = args
            condition = _eval_condition(cond_str, df)
            true_series = _eval_mapping_formula(true_str.strip(), df)
            false_series = _eval_mapping_formula(false_str.strip(), df)
            return pd.Series(
                [t if c else f for c, t, f in zip(condition, true_series, false_series)],
                dtype=object,
            )

    # ROW([start]) — row index with optional arithmetic
    m = re.match(r'^ROW\((\d*)\)\s*(.*)$', expr, re.IGNORECASE)
    if m:
        start = int(m.group(1)) if m.group(1) else 0
        arithmetic = m.group(2).strip()
        idx = np.arange(start, start + n, dtype=float)
        if not arithmetic:
            return pd.Series(idx.astype(int))
        if re.match(r'^[\d\s\+\-\*\/\(\)\.\^%]+$', arithmetic):
            arithmetic = arithmetic.replace('^', '**')
            try:
                result_arr = eval(f"idx{arithmetic}", {"idx": idx, "__builtins__": {}})  # noqa: S307
                return pd.Series(result_arr)
            except Exception:
                pass

    # Concatenation with &
    if "&" in expr:
        amp_parts: list = []
        _depth = 0; _in_q = False; _qc = ""; _cur: list = []
        for _ch in expr:
            if _ch in ('"', "'") and not _in_q:
                _in_q, _qc = True, _ch; _cur.append(_ch)
            elif _ch == _qc and _in_q:
                _in_q = False; _cur.append(_ch)
            elif _ch == "(" and not _in_q:
                _depth += 1; _cur.append(_ch)
            elif _ch == ")" and not _in_q:
                _depth -= 1; _cur.append(_ch)
            elif _ch == "&" and _depth == 0 and not _in_q:
                amp_parts.append("".join(_cur).strip()); _cur = []
            else:
                _cur.append(_ch)
        if _cur:
            amp_parts.append("".join(_cur).strip())
        if len(amp_parts) > 1:
            result: pd.Series = pd.Series([""] * n, dtype=str)
            for p in amp_parts:
                part_val = _eval_mapping_formula(p, df)
                result = result + part_val.fillna("").astype(str)
            return result

    # Arithmetic: additive (+, -) — checked before multiplicative for correct precedence
    found_add = _rfind_op_at_depth0(expr, ("+", "-"))
    if found_add:
        op_a, l_a, r_a = found_add
        lv = _eval_mapping_formula(l_a, df)
        rv = _eval_mapping_formula(r_a, df)
        if pd.api.types.is_datetime64_any_dtype(lv):
            delta = pd.to_timedelta(pd.to_numeric(rv, errors="coerce").fillna(0), unit="D")
            return (lv + delta if op_a == "+" else lv - delta).reset_index(drop=True)
        ln = pd.to_numeric(lv, errors="coerce")
        rn = pd.to_numeric(rv, errors="coerce")
        return (ln + rn if op_a == "+" else ln - rn).reset_index(drop=True)

    # Arithmetic: multiplicative (*, /)
    found_mul = _rfind_op_at_depth0(expr, ("*", "/"))
    if found_mul:
        op_m, l_m, r_m = found_mul
        ln_m = pd.to_numeric(_eval_mapping_formula(l_m, df), errors="coerce")
        rn_m = pd.to_numeric(_eval_mapping_formula(r_m, df), errors="coerce")
        if op_m == "*":
            return (ln_m * rn_m).reset_index(drop=True)
        return (ln_m / rn_m.replace(0, float("nan"))).reset_index(drop=True)

    return empty
