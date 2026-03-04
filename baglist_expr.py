from __future__ import annotations

import ast
import re
from typing import Iterable

import numpy as np
import pandas as pd


_QUOTED_RE = r"('(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\")"


def _split_quoted(expr: str) -> list[str]:
    return re.split(_QUOTED_RE, expr)


def _replace_bool_keywords(expr: str) -> str:
    parts = _split_quoted(expr)
    for i in range(0, len(parts), 2):
        parts[i] = re.sub(r"\bAND\b", "and", parts[i], flags=re.IGNORECASE)
        parts[i] = re.sub(r"\bOR\b", "or", parts[i], flags=re.IGNORECASE)
        parts[i] = re.sub(r"\bNOT\b", "not", parts[i], flags=re.IGNORECASE)
        parts[i] = re.sub(r"\bTRUE\b", "True", parts[i], flags=re.IGNORECASE)
        parts[i] = re.sub(r"\bFALSE\b", "False", parts[i], flags=re.IGNORECASE)
    return "".join(parts)


def _replace_if_function(expr: str) -> str:
    parts = _split_quoted(expr)
    for i in range(0, len(parts), 2):
        parts[i] = re.sub(r"\bif\s*\(", "iff(", parts[i], flags=re.IGNORECASE)
    return "".join(parts)


def _prepare_expr(expr: str) -> str:
    expr_clean = _replace_bool_keywords(expr)
    expr_clean = _replace_if_function(expr_clean)
    return expr_clean


def _to_series(value, index: pd.Index) -> pd.Series:
    if isinstance(value, pd.Series):
        return value.reindex(index)
    if isinstance(value, (np.ndarray, list, tuple, pd.Index)):
        return pd.Series(value, index=index)
    return pd.Series([value] * len(index), index=index)


def _ensure_datetime(value):
    if isinstance(value, pd.Series):
        if pd.api.types.is_datetime64_any_dtype(value):
            return value
        return pd.to_datetime(value, errors="coerce")
    return pd.to_datetime(value, errors="coerce")


def _coerce_bool(value, index: pd.Index) -> pd.Series:
    series = _to_series(value, index)
    return series.fillna(False).astype(bool)


def _coerce_numeric(value, index: pd.Index) -> pd.Series:
    series = _to_series(value, index)
    return pd.to_numeric(series, errors="coerce")


def _combine_day_time(day, time, base_date, index: pd.Index) -> pd.Series:
    day_series = _to_series(day, index)
    time_series = _to_series(time, index)

    if base_date is not None:
        base_series = _to_series(base_date, index)
        base_dt = pd.to_datetime(base_series, errors="coerce")
        day_num = pd.to_numeric(day_series, errors="coerce")
        date_part = base_dt + pd.to_timedelta(day_num, unit="D")
    else:
        date_part = pd.to_datetime(day_series, errors="coerce")

    time_delta = pd.to_timedelta(time_series, errors="coerce")
    if time_delta.isna().all():
        time_dt = pd.to_datetime(time_series, errors="coerce")
        time_delta = (
            pd.to_timedelta(time_dt.dt.hour, unit="h")
            + pd.to_timedelta(time_dt.dt.minute, unit="m")
            + pd.to_timedelta(time_dt.dt.second, unit="s")
        )

    return date_part.dt.normalize() + time_delta


def _fn_to_datetime(*args, index: pd.Index):
    if len(args) == 1:
        return _ensure_datetime(args[0])
    if len(args) == 2:
        return _combine_day_time(args[0], args[1], None, index)
    if len(args) == 3:
        return _combine_day_time(args[0], args[1], args[2], index)
    raise ValueError("to_datetime attend 1, 2 ou 3 arguments.")


def _fn_minutes(value, index: pd.Index):
    dt = _ensure_datetime(value)
    if isinstance(dt, pd.Series):
        return dt.dt.hour * 60 + dt.dt.minute + dt.dt.second / 60
    if pd.isna(dt):
        return np.nan
    return dt.hour * 60 + dt.minute + dt.second / 60


def _fn_diff_minutes(a, b, index: pd.Index):
    a_dt = _ensure_datetime(a)
    b_dt = _ensure_datetime(b)
    if isinstance(a_dt, pd.Series) or isinstance(b_dt, pd.Series):
        return (b_dt - a_dt).dt.total_seconds() / 60
    if pd.isna(a_dt) or pd.isna(b_dt):
        return np.nan
    return (b_dt - a_dt).total_seconds() / 60


def _fn_concat(*args, index: pd.Index):
    if not args:
        return pd.Series([""] * len(index), index=index)
    series_list = [_to_series(arg, index).fillna("").astype(str) for arg in args]
    result = series_list[0]
    for part in series_list[1:]:
        result = result + part
    return result


def _fn_coalesce(*args, index: pd.Index):
    if not args:
        return pd.Series([np.nan] * len(index), index=index)
    result = _to_series(args[0], index)
    for arg in args[1:]:
        result = result.combine_first(_to_series(arg, index))
    return result


def _fn_to_int(value, index: pd.Index):
    series = _coerce_numeric(value, index)
    return series


def _fn_to_str(value, index: pd.Index):
    return _to_series(value, index).astype(str)


def _fn_iff(cond, a, b, index: pd.Index):
    cond_series = _coerce_bool(cond, index)
    a_series = _to_series(a, index)
    b_series = _to_series(b, index)
    return pd.Series(np.where(cond_series, a_series, b_series), index=index)


def _build_allowed_funcs(index: pd.Index):
    return {
        "to_datetime": lambda *args: _fn_to_datetime(*args, index=index),
        "minutes": lambda *args: _fn_minutes(*args, index=index),
        "diff_minutes": lambda *args: _fn_diff_minutes(*args, index=index),
        "concat": lambda *args: _fn_concat(*args, index=index),
        "coalesce": lambda *args: _fn_coalesce(*args, index=index),
        "to_int": lambda *args: _fn_to_int(*args, index=index),
        "to_str": lambda *args: _fn_to_str(*args, index=index),
        "iff": lambda *args: _fn_iff(*args, index=index),
    }


def _eval_ast_expression(expr: str, df: pd.DataFrame) -> pd.Series:
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as exc:
        raise ValueError(f"Expression invalide: {exc.msg}") from exc

    allowed_funcs = _build_allowed_funcs(df.index)

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

    result = _eval(tree)
    return _to_series(result, df.index)


def eval_formula(expr: str, df: pd.DataFrame) -> pd.Series:
    expr_clean = _prepare_expr(expr)
    return _eval_ast_expression(expr_clean, df)


def eval_many(formulas: Iterable[tuple[str, str]], df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    out = df.copy()
    errors: list[str] = []
    for name, expr in formulas:
        if not name or not expr:
            continue
        try:
            out[name] = eval_formula(expr, out)
        except Exception as exc:
            errors.append(f"{name}: {exc}")
    return out, errors
