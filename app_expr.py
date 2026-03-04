from __future__ import annotations

import ast
import re
import numpy as np
import pandas as pd


def _replace_bool_keywords(expr: str) -> str:
    parts = re.split(r"('(?:[^'\\\\]|\\\\.)*'|\"(?:[^\"\\\\]|\\\\.)*\")", expr)
    for i in range(0, len(parts), 2):
        parts[i] = re.sub(r"\bAND\b", "and", parts[i], flags=re.IGNORECASE)
        parts[i] = re.sub(r"\bOR\b", "or", parts[i], flags=re.IGNORECASE)
        parts[i] = re.sub(r"\bNOT\b", "not", parts[i], flags=re.IGNORECASE)
    return "".join(parts)


def _split_if_then_else(expr: str) -> tuple[str, str, str] | None:
    expr_strip = expr.strip()
    if not re.match(r"^if\b", expr_strip, flags=re.IGNORECASE):
        return None
    remainder = re.sub(r"^if\b", "", expr_strip, flags=re.IGNORECASE).strip()
    parts = re.split(r"\bthen\b", remainder, flags=re.IGNORECASE, maxsplit=1)
    if len(parts) != 2:
        raise ValueError("Expression if/then/else invalide (then manquant).")
    cond = parts[0].strip()
    rest = parts[1].strip()
    parts2 = re.split(r"\belse\b", rest, flags=re.IGNORECASE, maxsplit=1)
    if len(parts2) != 2:
        raise ValueError("Expression if/then/else invalide (else manquant).")
    then_expr = parts2[0].strip()
    else_expr = parts2[1].strip()
    if not cond or not then_expr or not else_expr:
        raise ValueError("Expression if/then/else invalide (sections vides).")
    return cond, then_expr, else_expr


def _ensure_datetime(value):
    if isinstance(value, pd.Series):
        if pd.api.types.is_datetime64_any_dtype(value):
            return value
        return pd.to_datetime(value, errors="coerce")
    return pd.to_datetime(value, errors="coerce")


def _to_series(value, index: pd.Index) -> pd.Series:
    if isinstance(value, pd.Series):
        return value.reindex(index)
    if isinstance(value, (np.ndarray, list, tuple, pd.Index)):
        return pd.Series(value, index=index)
    return pd.Series([value] * len(index), index=index)


def _coerce_bool(value, index: pd.Index) -> pd.Series:
    series = _to_series(value, index)
    return series.fillna(False).astype(bool)


def _eval_ast_expression(expr: str, df: pd.DataFrame):
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as exc:
        raise ValueError(f"Expression invalide: {exc.msg}") from exc

    def _fn_diff_minutes(a, b):
        a_dt = _ensure_datetime(a)
        b_dt = _ensure_datetime(b)
        if isinstance(a_dt, pd.Series) or isinstance(b_dt, pd.Series):
            return (b_dt - a_dt).dt.total_seconds() / 60
        delta = b_dt - a_dt
        return delta.total_seconds() / 60 if pd.notna(delta) else np.nan

    def _fn_hour(a):
        dt = _ensure_datetime(a)
        if isinstance(dt, pd.Series):
            return dt.dt.hour
        return dt.hour if pd.notna(dt) else np.nan

    def _fn_day(a):
        dt = _ensure_datetime(a)
        if isinstance(dt, pd.Series):
            return dt.dt.date
        return dt.date() if pd.notna(dt) else np.nan

    def _fn_isnull(a):
        if isinstance(a, pd.Series):
            return a.isna()
        return pd.isna(a)

    def _fn_contains(a, b):
        series = _to_series(a, df.index).astype(str)
        return series.str.contains(str(b), na=False)

    def _fn_lower(a):
        series = _to_series(a, df.index).astype(str)
        return series.str.lower()

    allowed_funcs = {
        "diff_minutes": _fn_diff_minutes,
        "hour": _fn_hour,
        "day": _fn_day,
        "isnull": _fn_isnull,
        "contains": _fn_contains,
        "lower": _fn_lower,
    }

    bin_ops = {
        ast.Add: lambda a, b: a + b,
        ast.Sub: lambda a, b: a - b,
        ast.Mult: lambda a, b: a * b,
        ast.Div: lambda a, b: a / b,
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


def _eval_expression(expr: str, df: pd.DataFrame):
    expr_clean = _replace_bool_keywords(expr)
    parsed = _split_if_then_else(expr_clean)
    if parsed:
        cond_expr, then_expr, else_expr = parsed
        cond_val = _eval_expression(cond_expr, df)
        then_val = _eval_expression(then_expr, df)
        else_val = _eval_expression(else_expr, df)
        cond_series = _coerce_bool(cond_val, df.index)
        then_series = _to_series(then_val, df.index)
        else_series = _to_series(else_val, df.index)
        return pd.Series(np.where(cond_series, then_series, else_series), index=df.index)
    return _eval_ast_expression(expr_clean, df)


def _coerce_type(series: pd.Series, dtype: str) -> pd.Series:
    if dtype == "number":
        return pd.to_numeric(series, errors="coerce")
    if dtype == "text":
        return series.astype(str)
    if dtype == "boolean":
        return series.fillna(False).astype(bool)
    if dtype == "datetime":
        return pd.to_datetime(series, errors="coerce")
    return series


def _apply_calculated_fields(df: pd.DataFrame, variables: list[dict]) -> tuple[pd.DataFrame, list[str]]:
    out = df.copy()
    errors: list[str] = []
    for var in variables:
        name = var.get("name")
        expr = var.get("expr")
        dtype = var.get("dtype", "text")
        if not name or not expr:
            continue
        try:
            computed = _eval_expression(expr, out)
            series = _to_series(computed, out.index)
            out[name] = _coerce_type(series, dtype)
        except Exception as exc:
            errors.append(f"{name}: {exc}")
    return out, errors
