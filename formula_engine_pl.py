"""
formula_engine_pl.py — Moteur de formules Excel-like sur Polars
"""
from __future__ import annotations

import datetime
import random
import re
from typing import Any, Optional

import polars as pl


# ---------------------------------------------------------------------------
# split_args
# ---------------------------------------------------------------------------

def split_args(s: str) -> list[str]:
    """Découpe les arguments en respectant parenthèses imbriquées et guillemets."""
    args: list[str] = []
    depth = 0
    in_string = False
    string_char: str = ""
    current: list[str] = []
    for char in s:
        if in_string:
            current.append(char)
            if char == string_char:
                in_string = False
        elif char in ('"', "'"):
            in_string = True
            string_char = char
            current.append(char)
        elif char == '(':
            depth += 1
            current.append(char)
        elif char == ')':
            depth -= 1
            current.append(char)
        elif char == ',' and depth == 0:
            args.append(''.join(current).strip())
            current = []
        else:
            current.append(char)
    if current:
        args.append(''.join(current).strip())
    return args


# ---------------------------------------------------------------------------
# Helpers opérateurs à profondeur 0
# ---------------------------------------------------------------------------

def _find_op_first(s: str, ops: tuple[str, ...]) -> Optional[tuple[str, str, str]]:
    """Premier opérateur de ops à profondeur 0 (hors parenthèses/guillemets)."""
    depth = 0
    in_string = False
    string_char = ""
    i = 0
    while i < len(s):
        char = s[i]
        if in_string:
            if char == string_char:
                in_string = False
        elif char in ('"', "'"):
            in_string = True
            string_char = char
        elif char == '(':
            depth += 1
        elif char == ')':
            depth -= 1
        elif depth == 0 and not in_string:
            for op in ops:
                if s[i:i + len(op)] == op:
                    left = s[:i].strip()
                    right = s[i + len(op):].strip()
                    if left:
                        return op, left, right
        i += 1
    return None


def _rfind_op_at_depth0(s: str, ops: tuple[str, ...]) -> Optional[tuple[str, str, str]]:
    """Dernier opérateur de ops à profondeur 0 (arithmétique gauche→droite)."""
    depth = 0
    in_string = False
    string_char = ""
    last_pos: Optional[int] = None
    last_op: Optional[str] = None
    i = 0
    while i < len(s):
        char = s[i]
        if in_string:
            if char == string_char:
                in_string = False
        elif char in ('"', "'"):
            in_string = True
            string_char = char
        elif char == '(':
            depth += 1
        elif char == ')':
            depth -= 1
        elif depth == 0 and not in_string and i > 0:
            for op in ops:
                if s[i:i + len(op)] == op:
                    last_pos = i
                    last_op = op
                    break
        i += 1
    if last_pos is not None and last_op is not None:
        left = s[:last_pos].strip()
        right = s[last_pos + len(last_op):].strip()
        if left:
            return last_op, left, right
    return None


def _split_on_amp(s: str) -> list[str]:
    """Découpe sur & à profondeur 0."""
    parts: list[str] = []
    depth = 0
    in_string = False
    string_char = ""
    current: list[str] = []
    for char in s:
        if in_string:
            current.append(char)
            if char == string_char:
                in_string = False
        elif char in ('"', "'"):
            in_string = True
            string_char = char
            current.append(char)
        elif char == '(':
            depth += 1
            current.append(char)
        elif char == ')':
            depth -= 1
            current.append(char)
        elif char == '&' and depth == 0:
            parts.append(''.join(current).strip())
            current = []
        else:
            current.append(char)
    if current:
        parts.append(''.join(current).strip())
    return parts


# ---------------------------------------------------------------------------
# _parse_literal
# ---------------------------------------------------------------------------

def _parse_literal(s: str) -> tuple[bool, Any]:
    """(True, valeur) si s est une constante littérale, sinon (False, None)."""
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        return True, s[1:-1]
    if s.upper() == 'TRUE':
        return True, True
    if s.upper() == 'FALSE':
        return True, False
    try:
        v = float(s)
        return True, int(v) if v == int(v) else v
    except (ValueError, TypeError):
        pass
    return False, None


# ---------------------------------------------------------------------------
# _parse_expr — cœur récursif
# ---------------------------------------------------------------------------

def _parse_expr(formula: str, df: pl.DataFrame) -> pl.Expr:  # noqa: C901
    s = formula.strip()

    # ── Vide ───────────────────────────────────────────────────────────────
    if not s:
        return pl.lit("")

    # ── Constante littérale ────────────────────────────────────────────────
    is_lit, lit_val = _parse_literal(s)
    if is_lit:
        return pl.lit(lit_val)

    # ── Référence de colonne ───────────────────────────────────────────────
    if s in df.columns:
        return pl.col(s)

    # ── Parenthèses englobantes ────────────────────────────────────────────
    if s.startswith('(') and s.endswith(')'):
        depth = 0
        fully_wrapped = True
        for i, c in enumerate(s):
            if c == '(':
                depth += 1
            elif c == ')':
                depth -= 1
            if depth == 0 and i < len(s) - 1:
                fully_wrapped = False
                break
        if fully_wrapped:
            return _parse_expr(s[1:-1], df)

    # ── TODAY() / NOW() ────────────────────────────────────────────────────
    if re.match(r'^TODAY\(\)$', s, re.IGNORECASE):
        return pl.lit(datetime.date.today())
    if re.match(r'^NOW\(\)$', s, re.IGNORECASE):
        return pl.lit(datetime.datetime.now())

    # ── ROW() ──────────────────────────────────────────────────────────────
    if re.match(r'^ROW\(\)$', s, re.IGNORECASE):
        return pl.int_range(pl.len(), dtype=pl.Int64)

    # ── RAND() ─────────────────────────────────────────────────────────────
    if re.match(r'^RAND\(\)$', s, re.IGNORECASE):
        return pl.lit(pl.Series("_rand", [random.random() for _ in range(len(df))]))

    # ── RANDBETWEEN(lo, hi) ────────────────────────────────────────────────
    m = re.match(r'^RANDBETWEEN\((.+)\)$', s, re.IGNORECASE)
    if m:
        args = split_args(m.group(1))
        if len(args) == 2:
            lo_s = df.select(_parse_expr(args[0], df).alias("_")).to_series()
            hi_s = df.select(_parse_expr(args[1], df).alias("_")).to_series()
            return pl.lit(pl.Series("_rb", [
                random.randint(int(lo_s[i]), int(hi_s[i])) for i in range(len(df))
            ]))

    # =========================================================================
    # FONCTIONS TEXTE
    # =========================================================================

    m = re.match(r'^UPPER\((.+)\)$', s, re.IGNORECASE)
    if m:
        return _parse_expr(m.group(1).strip(), df).cast(pl.Utf8, strict=False).str.to_uppercase()

    m = re.match(r'^LOWER\((.+)\)$', s, re.IGNORECASE)
    if m:
        return _parse_expr(m.group(1).strip(), df).cast(pl.Utf8, strict=False).str.to_lowercase()

    m = re.match(r'^TRIM\((.+)\)$', s, re.IGNORECASE)
    if m:
        return _parse_expr(m.group(1).strip(), df).cast(pl.Utf8, strict=False).str.strip_chars()

    m = re.match(r'^LEN\((.+)\)$', s, re.IGNORECASE)
    if m:
        return _parse_expr(m.group(1).strip(), df).cast(pl.Utf8, strict=False).str.len_chars()

    m = re.match(r'^LEFT\((.+)\)$', s, re.IGNORECASE)
    if m:
        args = split_args(m.group(1))
        if len(args) == 2:
            src = _parse_expr(args[0].strip(), df).cast(pl.Utf8, strict=False)
            is_lit_n, n_val = _parse_literal(args[1].strip())
            if is_lit_n and isinstance(n_val, (int, float)):
                return src.str.head(int(n_val))
            n_expr = _parse_expr(args[1].strip(), df)
            n_series = df.select(n_expr.alias("_")).to_series()
            src_series = df.select(src.alias("_")).to_series()
            return pl.lit(pl.Series("_l", [
                (src_series[i] or "")[:int(n_series[i])] for i in range(len(df))
            ]))

    m = re.match(r'^RIGHT\((.+)\)$', s, re.IGNORECASE)
    if m:
        args = split_args(m.group(1))
        if len(args) == 2:
            src = _parse_expr(args[0].strip(), df).cast(pl.Utf8, strict=False)
            is_lit_n, n_val = _parse_literal(args[1].strip())
            if is_lit_n and isinstance(n_val, (int, float)):
                return src.str.tail(int(n_val))
            n_expr = _parse_expr(args[1].strip(), df)
            n_series = df.select(n_expr.alias("_")).to_series()
            src_series = df.select(src.alias("_")).to_series()
            return pl.lit(pl.Series("_r", [
                (src_series[i] or "")[-int(n_series[i]):] if int(n_series[i]) > 0 else ""
                for i in range(len(df))
            ]))

    m = re.match(r'^MID\((.+)\)$', s, re.IGNORECASE)
    if m:
        args = split_args(m.group(1))
        if len(args) == 3:
            src = _parse_expr(args[0].strip(), df).cast(pl.Utf8, strict=False)
            start_expr = _parse_expr(args[1].strip(), df).cast(pl.Int64, strict=False)
            len_expr = _parse_expr(args[2].strip(), df).cast(pl.Int64, strict=False)
            return src.str.slice(start_expr - pl.lit(1), len_expr)

    m = re.match(r'^SUBSTITUTE\((.+)\)$', s, re.IGNORECASE)
    if m:
        args = split_args(m.group(1))
        if len(args) >= 3:
            src = _parse_expr(args[0].strip(), df).cast(pl.Utf8, strict=False)
            is_lit_o, old_v = _parse_literal(args[1].strip())
            is_lit_n, new_v = _parse_literal(args[2].strip())
            if is_lit_o and is_lit_n:
                return src.str.replace_all(str(old_v), str(new_v), literal=True)
            old_s = df.select(_parse_expr(args[1].strip(), df).cast(pl.Utf8, strict=False).alias("_")).to_series()
            new_s = df.select(_parse_expr(args[2].strip(), df).cast(pl.Utf8, strict=False).alias("_")).to_series()
            src_s = df.select(src.alias("_")).to_series()
            return pl.lit(pl.Series("_sub", [
                (src_s[i] or "").replace(old_s[i] or "", new_s[i] or "")
                for i in range(len(df))
            ]))

    m = re.match(r'^FIND\((.+)\)$', s, re.IGNORECASE)
    if m:
        args = split_args(m.group(1))
        if len(args) >= 2:
            needle_s = df.select(_parse_expr(args[0].strip(), df).cast(pl.Utf8, strict=False).alias("_")).to_series()
            hay_s = df.select(_parse_expr(args[1].strip(), df).cast(pl.Utf8, strict=False).alias("_")).to_series()
            start_s = (
                df.select(_parse_expr(args[2].strip(), df).alias("_")).to_series()
                if len(args) >= 3 else pl.Series([1] * len(df))
            )
            results: list[Optional[int]] = []
            for i in range(len(df)):
                try:
                    pos = (hay_s[i] or "").find(needle_s[i] or "", int(start_s[i]) - 1)
                    results.append(pos + 1 if pos >= 0 else None)
                except Exception:
                    results.append(None)
            return pl.lit(pl.Series("_find", results, dtype=pl.Int64))

    m = re.match(r'^TEXTBEFORE\((.+)\)$', s, re.IGNORECASE)
    if m:
        args = split_args(m.group(1))
        if len(args) >= 2:
            src = _parse_expr(args[0].strip(), df).cast(pl.Utf8, strict=False)
            is_lit_d, d_val = _parse_literal(args[1].strip())
            if is_lit_d:
                return src.str.split(str(d_val)).list.first()
            d_s = df.select(_parse_expr(args[1].strip(), df).cast(pl.Utf8, strict=False).alias("_")).to_series()
            s_s = df.select(src.alias("_")).to_series()
            return pl.lit(pl.Series("_tb", [
                (s_s[i] or "").split(d_s[i])[0] for i in range(len(df))
            ]))

    m = re.match(r'^TEXTAFTER\((.+)\)$', s, re.IGNORECASE)
    if m:
        args = split_args(m.group(1))
        if len(args) >= 2:
            src = _parse_expr(args[0].strip(), df).cast(pl.Utf8, strict=False)
            is_lit_d, d_val = _parse_literal(args[1].strip())
            if is_lit_d:
                return src.str.split(str(d_val)).list.last()
            d_s = df.select(_parse_expr(args[1].strip(), df).cast(pl.Utf8, strict=False).alias("_")).to_series()
            s_s = df.select(src.alias("_")).to_series()
            return pl.lit(pl.Series("_ta", [
                (d_s[i] or "").join((s_s[i] or "").split(d_s[i])[1:])
                for i in range(len(df))
            ]))

    m = re.match(r'^CONCAT\((.+)\)$', s, re.IGNORECASE)
    if m:
        args = split_args(m.group(1))
        exprs = [_parse_expr(a.strip(), df).cast(pl.Utf8, strict=False) for a in args]
        return pl.concat_str(exprs, ignore_nulls=True)

    m = re.match(r'^TEXT\((.+)\)$', s, re.IGNORECASE)
    if m:
        args = split_args(m.group(1))
        if len(args) == 2:
            src = _parse_expr(args[0].strip(), df)
            fmt_raw = args[1].strip().strip("\"'")
            py_chars: list[str] = []
            fi = 0
            while fi < len(fmt_raw):
                if fmt_raw[fi:fi+4] == "yyyy":          py_chars.append("%Y"); fi += 4
                elif fmt_raw[fi:fi+2] == "yy":          py_chars.append("%y"); fi += 2
                elif fmt_raw[fi:fi+2] == "MM":          py_chars.append("%m"); fi += 2
                elif fmt_raw[fi:fi+2] == "dd":          py_chars.append("%d"); fi += 2
                elif fmt_raw[fi:fi+2] in ("HH", "hh"): py_chars.append("%H"); fi += 2
                elif fmt_raw[fi:fi+2] == "mm":          py_chars.append("%M"); fi += 2
                elif fmt_raw[fi:fi+2] == "ss":          py_chars.append("%S"); fi += 2
                else:                                    py_chars.append(fmt_raw[fi]); fi += 1
            py_fmt = "".join(py_chars)
            return src.cast(pl.Datetime, strict=False).dt.strftime(py_fmt)

    # =========================================================================
    # FONCTIONS DE CONDITION
    # =========================================================================

    m = re.match(r'^ISBLANK\((.+)\)$', s, re.IGNORECASE)
    if m:
        inner = _parse_expr(m.group(1).strip(), df)
        return inner.is_null() | (inner.cast(pl.Utf8, strict=False) == pl.lit(""))

    m = re.match(r'^ISNUMBER\((.+)\)$', s, re.IGNORECASE)
    if m:
        inner = _parse_expr(m.group(1).strip(), df)
        return inner.cast(pl.Float64, strict=False).is_not_null()

    m = re.match(r'^ISTEXT\((.+)\)$', s, re.IGNORECASE)
    if m:
        inner = _parse_expr(m.group(1).strip(), df)
        series = df.select(inner.alias("_")).to_series()
        is_text = series.dtype in (pl.Utf8, pl.String)
        return pl.lit(pl.Series("_it", [is_text] * len(df)))

    m = re.match(r'^IFERROR\((.+)\)$', s, re.IGNORECASE)
    if m:
        args = split_args(m.group(1))
        if len(args) == 2:
            fallback_expr = _parse_expr(args[1].strip(), df)
            try:
                inner_expr = _parse_expr(args[0].strip(), df)
                inner_s = df.select(inner_expr.alias("_")).to_series()
                fb_s = df.select(fallback_expr.alias("_")).to_series()
                if inner_s.dtype in (pl.Float32, pl.Float64):
                    result = inner_s.fill_nan(None).fill_null(fb_s)
                else:
                    result = inner_s.fill_null(fb_s)
                return pl.lit(result)
            except Exception:
                return fallback_expr

    m = re.match(r'^IFNA\((.+)\)$', s, re.IGNORECASE)
    if m:
        args = split_args(m.group(1))
        if len(args) == 2:
            return _parse_expr(args[0].strip(), df).fill_null(_parse_expr(args[1].strip(), df))

    m = re.match(r'^IF\((.+)\)$', s, re.IGNORECASE)
    if m:
        args = split_args(m.group(1))
        if len(args) == 3:
            cond = _parse_expr(args[0].strip(), df)
            true_e = _parse_expr(args[1].strip(), df)
            false_e = _parse_expr(args[2].strip(), df)
            return pl.when(cond).then(true_e).otherwise(false_e)

    m = re.match(r'^IFS\((.+)\)$', s, re.IGNORECASE)
    if m:
        args = split_args(m.group(1))
        if len(args) >= 2:
            if len(args) % 2 == 1:
                result_e: pl.Expr = _parse_expr(args[-1].strip(), df)
                pairs = list(range(0, len(args) - 1, 2))
            else:
                result_e = pl.lit(None)
                pairs = list(range(0, len(args), 2))
            for i in reversed(pairs):
                cond = _parse_expr(args[i].strip(), df)
                val = _parse_expr(args[i + 1].strip(), df)
                result_e = pl.when(cond).then(val).otherwise(result_e)
            return result_e

    m = re.match(r'^AND\((.+)\)$', s, re.IGNORECASE)
    if m:
        args = split_args(m.group(1))
        exprs = [_parse_expr(a.strip(), df) for a in args]
        res = exprs[0]
        for e in exprs[1:]:
            res = res & e
        return res

    m = re.match(r'^OR\((.+)\)$', s, re.IGNORECASE)
    if m:
        args = split_args(m.group(1))
        exprs = [_parse_expr(a.strip(), df) for a in args]
        res = exprs[0]
        for e in exprs[1:]:
            res = res | e
        return res

    m = re.match(r'^NOT\((.+)\)$', s, re.IGNORECASE)
    if m:
        return ~_parse_expr(m.group(1).strip(), df)

    m = re.match(r'^COALESCE\((.+)\)$', s, re.IGNORECASE)
    if m:
        args = split_args(m.group(1))
        return pl.coalesce([_parse_expr(a.strip(), df) for a in args])

    # =========================================================================
    # FONCTIONS NUMÉRIQUES
    # =========================================================================

    m = re.match(r'^VALUE\((.+)\)$', s, re.IGNORECASE)
    if m:
        return _parse_expr(m.group(1).strip(), df).cast(pl.Float64, strict=False)

    m = re.match(r'^ROUND\((.+)\)$', s, re.IGNORECASE)
    if m:
        args = split_args(m.group(1))
        if len(args) == 2:
            val_expr = _parse_expr(args[0].strip(), df)
            is_lit_n, n_val = _parse_literal(args[1].strip())
            if is_lit_n:
                return val_expr.round(int(n_val))
            n_s = df.select(_parse_expr(args[1].strip(), df).alias("_")).to_series()
            return val_expr.round(int(n_s[0]))

    m = re.match(r'^INT\((.+)\)$', s, re.IGNORECASE)
    if m:
        return _parse_expr(m.group(1).strip(), df).cast(pl.Int64, strict=False)

    m = re.match(r'^ABS\((.+)\)$', s, re.IGNORECASE)
    if m:
        return _parse_expr(m.group(1).strip(), df).abs()

    m = re.match(r'^MOD\((.+)\)$', s, re.IGNORECASE)
    if m:
        args = split_args(m.group(1))
        if len(args) == 2:
            return _parse_expr(args[0].strip(), df) % _parse_expr(args[1].strip(), df)

    m = re.match(r'^POWER\((.+)\)$', s, re.IGNORECASE)
    if m:
        args = split_args(m.group(1))
        if len(args) == 2:
            return _parse_expr(args[0].strip(), df).pow(_parse_expr(args[1].strip(), df))

    m = re.match(r'^SQRT\((.+)\)$', s, re.IGNORECASE)
    if m:
        return _parse_expr(m.group(1).strip(), df).sqrt()

    m = re.match(r'^MIN\((.+)\)$', s, re.IGNORECASE)
    if m:
        args = split_args(m.group(1))
        return pl.min_horizontal([_parse_expr(a.strip(), df) for a in args])

    m = re.match(r'^MAX\((.+)\)$', s, re.IGNORECASE)
    if m:
        args = split_args(m.group(1))
        return pl.max_horizontal([_parse_expr(a.strip(), df) for a in args])

    m = re.match(r'^SUM\((.+)\)$', s, re.IGNORECASE)
    if m:
        args = split_args(m.group(1))
        exprs = [_parse_expr(a.strip(), df).cast(pl.Float64, strict=False).fill_null(0) for a in args]
        return pl.sum_horizontal(exprs)

    m = re.match(r'^AVERAGE\((.+)\)$', s, re.IGNORECASE)
    if m:
        args = split_args(m.group(1))
        exprs = [_parse_expr(a.strip(), df).cast(pl.Float64, strict=False) for a in args]
        return pl.mean_horizontal(exprs)

    # =========================================================================
    # FONCTIONS DE DATE
    # =========================================================================

    m = re.match(r'^(YEAR|MONTH|DAY)\((.+)\)$', s, re.IGNORECASE)
    if m:
        fn = m.group(1).upper()
        inner = _parse_expr(m.group(2).strip(), df).cast(pl.Date, strict=False)
        if fn == 'YEAR':
            return inner.dt.year()
        if fn == 'MONTH':
            return inner.dt.month()
        return inner.dt.day()

    m = re.match(r'^DATEVALUE\((.+)\)$', s, re.IGNORECASE)
    if m:
        inner = _parse_expr(m.group(1).strip(), df)
        return inner.cast(pl.Utf8, strict=False).str.to_date(strict=False)

    m = re.match(r'^DATEDIFF\((.+)\)$', s, re.IGNORECASE)
    if m:
        args = split_args(m.group(1))
        if len(args) >= 2:
            d1 = _parse_expr(args[0].strip(), df).cast(pl.Datetime, strict=False)
            d2 = _parse_expr(args[1].strip(), df).cast(pl.Datetime, strict=False)
            unit = args[2].strip().strip("\"'").lower() if len(args) >= 3 else "day"
            diff = d2 - d1
            if unit in ("day", "days", "d"):
                return diff.dt.total_days()
            if unit in ("hour", "hours", "h"):
                return (diff.dt.total_milliseconds() / 3_600_000).cast(pl.Float64)
            if unit in ("minute", "minutes", "m", "min"):
                return (diff.dt.total_milliseconds() / 60_000).cast(pl.Float64)
            return diff.dt.total_days()

    m = re.match(r'^DATEADD\((.+)\)$', s, re.IGNORECASE)
    if m:
        args = split_args(m.group(1))
        if len(args) == 3:
            dt_expr = _parse_expr(args[0].strip(), df).cast(pl.Datetime, strict=False)
            n_expr = _parse_expr(args[1].strip(), df).cast(pl.Int64, strict=False)
            unit = args[2].strip().strip("\"'").lower()
            unit_map = {
                "day": "days", "days": "days", "d": "days",
                "hour": "hours", "hours": "hours", "h": "hours",
                "minute": "minutes", "minutes": "minutes", "m": "minutes", "min": "minutes",
                "second": "seconds", "seconds": "seconds", "s": "seconds",
            }
            kwarg = unit_map.get(unit, "days")
            return dt_expr + pl.duration(**{kwarg: n_expr})

    # =========================================================================
    # FONCTIONS SPÉCIALES
    # =========================================================================

    m = re.match(r'^LET\((.+)\)$', s, re.IGNORECASE | re.DOTALL)
    if m:
        args = split_args(m.group(1))
        if len(args) >= 3 and len(args) % 2 == 1:
            df_let = df.clone()
            for i in range(0, len(args) - 1, 2):
                var_name = args[i].strip().strip("\"'")
                var_s = df_let.select(_parse_expr(args[i + 1].strip(), df_let).alias(var_name)).to_series()
                df_let = df_let.with_columns(var_s.alias(var_name))
            return _parse_expr(args[-1].strip(), df_let)

    m = re.match(r'^CHOOSE\((.+)\)$', s, re.IGNORECASE)
    if m:
        args = split_args(m.group(1))
        if len(args) >= 2:
            idx_expr = _parse_expr(args[0].strip(), df).cast(pl.Int64, strict=False)
            val_exprs = [_parse_expr(a.strip(), df) for a in args[1:]]
            res_e: pl.Expr = pl.lit(None)
            for i, ve in reversed(list(enumerate(val_exprs, 1))):
                res_e = pl.when(idx_expr == pl.lit(i)).then(ve).otherwise(res_e)
            return res_e

    # =========================================================================
    # OPÉRATEURS
    # =========================================================================

    # ── Concaténation & ───────────────────────────────────────────────────
    if '&' in s:
        parts = _split_on_amp(s)
        if len(parts) > 1:
            str_exprs = [_parse_expr(p, df).cast(pl.Utf8, strict=False) for p in parts]
            return pl.concat_str(str_exprs, ignore_nulls=True)

    # ── Comparaisons ──────────────────────────────────────────────────────
    cmp_ops = ('>=', '<=', '<>', '!=', '>', '<', '=')
    found_cmp = _find_op_first(s, cmp_ops)
    if found_cmp:
        op, left_s, right_s = found_cmp
        left_e = _parse_expr(left_s, df)
        right_e = _parse_expr(right_s, df)
        if op == '=':
            return left_e == right_e
        if op in ('<>', '!='):
            return left_e != right_e
        if op == '>=':
            return left_e >= right_e
        if op == '<=':
            return left_e <= right_e
        if op == '>':
            return left_e > right_e
        if op == '<':
            return left_e < right_e

    # ── Arithmétique additive (+, -) ──────────────────────────────────────
    found_add = _rfind_op_at_depth0(s, ('+', '-'))
    if found_add:
        op, left_s, right_s = found_add
        left_e = _parse_expr(left_s, df)
        right_e = _parse_expr(right_s, df)
        return left_e + right_e if op == '+' else left_e - right_e

    # ── Arithmétique multiplicative (*, /) ────────────────────────────────
    found_mul = _rfind_op_at_depth0(s, ('*', '/'))
    if found_mul:
        op, left_s, right_s = found_mul
        left_e = _parse_expr(left_s, df)
        right_e = _parse_expr(right_s, df)
        return left_e * right_e if op == '*' else left_e / right_e

    return pl.lit(None)


# ---------------------------------------------------------------------------
# eval_formula — point d'entrée public
# ---------------------------------------------------------------------------

def eval_formula(formula, df: pl.DataFrame, col_name: str = "result") -> pl.Series:
    """
    Évalue une formule sur un DataFrame Polars.

    Option A : formula est une pl.Expr (exécution directe).
    Option B : formula est une str Excel-like (parsing récursif).
    """
    if isinstance(formula, str):
        expr = _parse_expr(formula.strip(), df)
        return df.select(expr.alias(col_name)).to_series()
    elif isinstance(formula, pl.Expr):
        return df.select(formula.alias(col_name)).to_series()
    else:
        raise TypeError(f"eval_formula attend str ou pl.Expr, reçu : {type(formula)}")
