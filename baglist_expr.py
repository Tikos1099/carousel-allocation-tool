from __future__ import annotations

import ast
import re
from typing import Callable

import numpy as np
import pandas as pd


_QUOTED_RE = r"('(?:[^'\\\\]|\\\\.)*'|\"(?:[^\"\\\\]|\\\\.)*\")"


def _replace_outside_quotes(expr: str, fn: Callable[[str], str]) -> str:
    parts = re.split(_QUOTED_RE, expr)
    for i in range(0, len(parts), 2):
        parts[i] = fn(parts[i])
    return "".join(parts)


def _replace_bool_keywords(expr: str) -> str:
    def _swap(text: str) -> str:
        text = re.sub(r"\bAND\b", "and", text, flags=re.IGNORECASE)
        text = re.sub(r"\bOR\b", "or", text, flags=re.IGNORECASE)
        text = re.sub(r"\bNOT\b", "not", text, flags=re.IGNORECASE)
        return text

    return _replace_outside_quotes(expr, _swap)


def _replace_operators(expr: str) -> str:
    def _swap(text: str) -> str:
        text = text.replace("<>", "!=")
        text = re.sub(r"(?<![<>=!])=(?!=)", "==", text)
        return text

    return _replace_outside_quotes(expr, _swap)


def _replace_if_func(expr: str) -> str:
    def _swap(text: str) -> str:
        return re.sub(r"\bif\s*\(", "iif(", text, flags=re.IGNORECASE)

    return _replace_outside_quotes(expr, _swap)


def _normalize_expr(expr: str) -> str:
    expr = _replace_bool_keywords(expr)
    expr = _replace_operators(expr)
    expr = _replace_if_func(expr)
    return expr


def _to_series(value, index: pd.Index) -> pd.Series:
    if isinstance(value, pd.Series):
        return value.reindex(index)
    if isinstance(value, (np.ndarray, list, tuple, pd.Index)):
        return pd.Series(value, index=index)
    return pd.Series([value] * len(index), index=index)


def _coerce_bool(value, index: pd.Index) -> pd.Series:
    series = _to_series(value, index)
    return series.fillna(False).astype(bool)


def _ensure_datetime(value):
    if isinstance(value, pd.Series):
        if pd.api.types.is_datetime64_any_dtype(value):
            return value
        return pd.to_datetime(value, errors="coerce")
    return pd.to_datetime(value, errors="coerce")


def _normalize_for_concat(value, index: pd.Index) -> pd.Series:
    series = _to_series(value, index)
    return series.fillna("").astype(str)


def _coalesce_values(values: list[pd.Series]) -> pd.Series:
    if not values:
        return pd.Series([], dtype=object)
    stacked = pd.concat(values, axis=1)
    stacked = stacked.replace("", np.nan)
    return stacked.bfill(axis=1).iloc[:, 0]


def _build_datetime_from_parts(day, time=None, base_date=None, index: pd.Index | None = None):
    idx = index or (day.index if isinstance(day, pd.Series) else None)
    if idx is None:
        raise ValueError("Missing index for datetime conversion.")
    day_series = _to_series(day, idx)
    time_series = _to_series(time, idx) if time is not None else None
    base_series = _to_series(base_date, idx) if base_date is not None else None

    day_dt = pd.to_datetime(day_series, errors="coerce")
    if base_series is not None:
        base_dt = pd.to_datetime(base_series, errors="coerce")
        day_num = pd.to_numeric(day_series, errors="coerce")
        mask_use_base = day_dt.isna() & day_num.notna()
        if mask_use_base.any():
            recomposed = pd.to_datetime(
                {
                    "year": base_dt.dt.year,
                    "month": base_dt.dt.month,
                    "day": day_num,
                },
                errors="coerce",
            )
            day_dt = day_dt.where(~mask_use_base, recomposed)

    if time_series is None:
        return day_dt

    time_dt = pd.to_datetime(time_series, errors="coerce")
    time_seconds = (
        time_dt.dt.hour.fillna(0).astype(int) * 3600
        + time_dt.dt.minute.fillna(0).astype(int) * 60
        + time_dt.dt.second.fillna(0).astype(int)
    )
    combined = day_dt.dt.normalize() + pd.to_timedelta(time_seconds, unit="s")
    combined = combined.where(~day_dt.isna(), time_dt)
    return combined


def eval_expression(expr: str, df: pd.DataFrame):
    expr_clean = _normalize_expr(expr)
    try:
        tree = ast.parse(expr_clean, mode="eval")
    except SyntaxError as exc:
        raise ValueError(f"Expression invalide: {exc.msg}") from exc

    def _fn_to_datetime(day, time=None, base_date=None):
        return _build_datetime_from_parts(day, time, base_date, index=df.index)

    def _fn_minutes(value):
        dt = _ensure_datetime(value)
        if isinstance(dt, pd.Series):
            return dt.dt.hour * 60 + dt.dt.minute + dt.dt.second / 60
        return dt.hour * 60 + dt.minute + dt.second / 60 if pd.notna(dt) else np.nan

    def _fn_diff_minutes(a, b):
        a_dt = _ensure_datetime(a)
        b_dt = _ensure_datetime(b)
        if isinstance(a_dt, pd.Series) or isinstance(b_dt, pd.Series):
            return (b_dt - a_dt).dt.total_seconds() / 60
        delta = b_dt - a_dt
        return delta.total_seconds() / 60 if pd.notna(delta) else np.nan

    def _fn_concat(*args):
        if not args:
            return ""
        series_list = [_normalize_for_concat(arg, df.index) for arg in args]
        out = series_list[0]
        for series in series_list[1:]:
            out = out + series
        return out

    def _fn_coalesce(*args):
        series_list = [_to_series(arg, df.index) for arg in args]
        return _coalesce_values(series_list)

    def _fn_iif(cond, a, b):
        cond_series = _coerce_bool(cond, df.index)
        a_series = _to_series(a, df.index)
        b_series = _to_series(b, df.index)
        return pd.Series(np.where(cond_series, a_series, b_series), index=df.index)

    def _fn_to_int(value):
        series = _to_series(value, df.index)
        out = pd.to_numeric(series, errors="coerce")
        return out

    def _fn_to_str(value):
        series = _to_series(value, df.index)
        return series.fillna("").astype(str)

    allowed_funcs = {
        "to_datetime": _fn_to_datetime,
        "minutes": _fn_minutes,
        "diff_minutes": _fn_diff_minutes,
        "concat": _fn_concat,
        "coalesce": _fn_coalesce,
        "iif": _fn_iif,
        "to_int": _fn_to_int,
        "to_str": _fn_to_str,
    }

    bin_ops = {
        ast.Add: lambda a, b: a + b,
        ast.Sub: lambda a, b: a - b,
        ast.Mult: lambda a, b: a * b,
        ast.Div: lambda a, b: a / b,
        ast.Mod: lambda a, b: a % b,
    }

    cmp_ops = {
        ast.Eq: lambda a, b: a == b,
        ast.NotEq: lambda a, b: a != b,
        ast.Lt: lambda a, b: a < b,
        ast.LtE: lambda a, b: a <= b,
        ast.Gt: lambda a, b: a > b,
        ast.GtE: lambda a, b: a >= b,
    }

    def _eval(node):
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            if node.id in df.columns:
                return df[node.id]
            raise ValueError(f"Colonne inconnue: {node.id}")
        if isinstance(node, ast.BinOp):
            op_type = type(node.op)
            if op_type not in bin_ops:
                raise ValueError("Operation non supportee.")
            return bin_ops[op_type](_eval(node.left), _eval(node.right))
        if isinstance(node, ast.UnaryOp):
            if isinstance(node.op, ast.UAdd):
                return +_eval(node.operand)
            if isinstance(node.op, ast.USub):
                return -_eval(node.operand)
            if isinstance(node.op, ast.Not):
                return ~_coerce_bool(_eval(node.operand), df.index)
            raise ValueError("Operation unaire non supportee.")
        if isinstance(node, ast.BoolOp):
            values = [_coerce_bool(_eval(v), df.index) for v in node.values]
            if isinstance(node.op, ast.And):
                out = values[0]
                for v in values[1:]:
                    out = out & v
                return out
            if isinstance(node.op, ast.Or):
                out = values[0]
                for v in values[1:]:
                    out = out | v
                return out
            raise ValueError("Operation booleenne non supportee.")
        if isinstance(node, ast.Compare):
            left = _eval(node.left)
            result = None
            for op, comp in zip(node.ops, node.comparators):
                op_type = type(op)
                if op_type not in cmp_ops:
                    raise ValueError("Comparaison non supportee.")
                right = _eval(comp)
                comp_val = cmp_ops[op_type](left, right)
                result = comp_val if result is None else (result & comp_val)
                left = right
            return result
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise ValueError("Appel de fonction non supporte.")
            func_name = node.func.id
            if func_name not in allowed_funcs:
                raise ValueError(f"Fonction non autorisee: {func_name}")
            if node.keywords:
                raise ValueError("Arguments nommes non supportes.")
            args = [_eval(a) for a in node.args]
            return allowed_funcs[func_name](*args)
        raise ValueError("Expression non supportee.")

    return _eval(tree)
