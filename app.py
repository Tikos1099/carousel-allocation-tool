from __future__ import annotations
import streamlit as st
import pandas as pd
import re
import unicodedata
import ast
import json
import uuid
from datetime import date, datetime
from pathlib import Path
import numpy as np
import altair as alt

from allocator import (
    CarouselCapacity,
    allocate_round_robin,
    allocate_round_robin_with_rules,
    allocate_with_fixed_assignments,
    build_timeline_from_assignments,
    compute_single_assignment_segments,
)
from io_excel import write_summary_txt, write_summary_csv, write_timeline_excel, write_heatmap_excel

BRAND_RED = "#D32F2F"
BRAND_RED_DARK = "#B71C1C"
BRAND_BG = "#FFFFFF"
BRAND_SIDEBAR = "#F7F7F7"
BRAND_BORDER = "#E5E5E5"

st.set_page_config(page_title="Carousel Allocation Tool", layout="wide")
st.markdown(
    f"""
    <style>
        :root {{
            --brand-red: {BRAND_RED};
            --brand-red-dark: {BRAND_RED_DARK};
            --brand-bg: {BRAND_BG};
            --brand-sidebar: {BRAND_SIDEBAR};
            --brand-border: {BRAND_BORDER};
            --primary-color: var(--brand-red);
            --secondary-background-color: var(--brand-sidebar);
            --background-color: var(--brand-bg);
            --text-color: #111111;
        }}
        html, body, [data-testid="stAppViewContainer"] {{
            background: var(--brand-bg);
            color: #111111;
        }}
        [data-testid="stHeader"] {{
            background: #ffffff;
            border-bottom: 1px solid var(--brand-border);
        }}
        [data-testid="stToolbar"] {{
            background: #ffffff;
        }}
        [data-testid="stDecoration"] {{
            background: #ffffff;
        }}
        [data-testid="stSidebar"] > div:first-child {{
            background: var(--brand-sidebar);
        }}
        h1, h2, h3, h4, label, p, span {{
            color: #111111;
        }}
        input, textarea, [data-baseweb="select"] > div {{
            background: #ffffff !important;
            color: #111111 !important;
            border: 1px solid var(--brand-border) !important;
        }}
        input:focus, textarea:focus, [data-baseweb="select"] > div:focus-within {{
            border-color: var(--brand-red) !important;
            box-shadow: 0 0 0 2px rgba(211, 47, 47, 0.2);
        }}
        input[type="radio"], input[type="checkbox"], input[type="range"] {{
            accent-color: var(--brand-red);
        }}
        :focus-visible {{
            outline-color: var(--brand-red) !important;
        }}
        [data-testid="stFileUploader"] section {{
            background: #ffffff !important;
            border: 1px dashed var(--brand-border) !important;
            color: #111111 !important;
        }}
        [data-testid="stFileUploader"] button {{
            background: #ffffff !important;
            color: #111111 !important;
            border: 1px solid var(--brand-border) !important;
        }}
        div.stButton > button, div.stDownloadButton > button {{
            background: var(--brand-red);
            color: #ffffff;
            border: 0;
        }}
        div.stButton > button * , div.stDownloadButton > button * {{
            color: #ffffff !important;
        }}
        div.stButton > button:hover, div.stDownloadButton > button:hover {{
            background: var(--brand-red-dark);
            color: #ffffff;
        }}
        [data-testid="stMetric"] {{
            background: #ffffff;
            border: 1px solid var(--brand-border);
            padding: 0.5rem;
            border-radius: 0.5rem;
        }}
        .stAlert {{
            background: #ffffff;
            color: #111111;
            border: 1px solid var(--brand-border);
            border-left: 4px solid var(--brand-red);
        }}
    </style>
    """,
    unsafe_allow_html=True,
)

base_dir = Path(__file__).parent
logo_candidates = [
    base_dir / "logo.jpg",
    base_dir / "logo.png",
    base_dir / "assets" / "logo.jpg",
    base_dir / "assets" / "logo.png",
]
logo_path = None
for candidate in logo_candidates:
    if candidate.exists():
        logo_path = candidate
        break

logo_bytes = None
if logo_path:
    try:
        logo_bytes = logo_path.read_bytes()
    except Exception:
        logo_bytes = None

if logo_bytes:
    header_cols = st.columns([1, 6])
    with header_cols[0]:
        st.image(logo_bytes, width=120)
    with header_cols[1]:
        st.title("Carousel Allocation Tool")
else:
    st.title("Carousel Allocation Tool")


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


def _clear_prefix(prefixes):
    for key in list(st.session_state.keys()):
        if any(key.startswith(p) for p in prefixes):
            st.session_state.pop(key, None)


def _reset_after_upload():
    keys = [
        "mapping_confirmed",
        "cat_term_confirmed",
        "makeup_confirmed",
        "time_step_confirmed",
        "carousels_confirmed",
        "run_done",
        "results",
        "col_mapping",
        "keep_extra_cols",
        "keep_extra_cols_ui",
        "cat_mapping",
        "term_mapping",
        "makeup_signature",
        "time_step_value",
        "car_file_sig",
    ]
    for k in keys:
        st.session_state.pop(k, None)
    _clear_prefix(("map_", "catmap_", "termmap_"))


def _reset_after_mapping():
    keys = [
        "cat_term_confirmed",
        "makeup_confirmed",
        "time_step_confirmed",
        "carousels_confirmed",
        "run_done",
        "results",
        "cat_mapping",
        "term_mapping",
        "makeup_signature",
        "time_step_value",
        "car_file_sig",
    ]
    for k in keys:
        st.session_state.pop(k, None)
    _clear_prefix(("catmap_", "termmap_"))


def _reset_after_cat_term():
    keys = [
        "makeup_confirmed",
        "time_step_confirmed",
        "carousels_confirmed",
        "run_done",
        "results",
        "makeup_signature",
        "time_step_value",
        "car_file_sig",
    ]
    for k in keys:
        st.session_state.pop(k, None)


def _reset_after_makeup():
    keys = [
        "time_step_confirmed",
        "carousels_confirmed",
        "run_done",
        "results",
        "time_step_value",
        "car_file_sig",
    ]
    for k in keys:
        st.session_state.pop(k, None)


def _reset_after_time_step():
    keys = [
        "carousels_confirmed",
        "run_done",
        "results",
        "car_file_sig",
    ]
    for k in keys:
        st.session_state.pop(k, None)


def _reset_after_carousels():
    keys = [
        "run_done",
        "results",
    ]
    for k in keys:
        st.session_state.pop(k, None)


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


def _get_datetime_columns(df: pd.DataFrame) -> list[str]:
    cols: list[str] = []
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            cols.append(col)
            continue
        if "time" in col.lower() or "date" in col.lower():
            sample = pd.to_datetime(df[col].dropna().head(50), errors="coerce")
            if sample.notna().any():
                cols.append(col)
    return cols


def _render_filters(df: pd.DataFrame, prefix: str, defaults: dict | None = None) -> dict:
    defaults = defaults or {}
    filters: dict = {}
    if "Terminal" in df.columns:
        options = sorted(df["Terminal"].dropna().astype(str).unique().tolist())
        default_val = defaults.get("terminal", options)
        if default_val is None:
            default_val = options
        default_val = [v for v in default_val if v in options]
        terminal_sel = st.multiselect(
            "Terminal",
            options,
            default=default_val,
            key=f"{prefix}_terminal",
        )
        filters["terminal"] = terminal_sel
    if "Category" in df.columns:
        options = sorted(df["Category"].dropna().astype(str).unique().tolist())
        default_val = defaults.get("category", options)
        if default_val is None:
            default_val = options
        default_val = [v for v in default_val if v in options]
        category_sel = st.multiselect(
            "Category",
            options,
            default=default_val,
            key=f"{prefix}_category",
        )
        filters["category"] = category_sel

    dt_cols = _get_datetime_columns(df)
    if dt_cols:
        default_col = defaults.get("date_col")
        if default_col not in dt_cols:
            default_col = "DepartureTime" if "DepartureTime" in dt_cols else dt_cols[0]
        date_col = st.selectbox(
            "Date column",
            dt_cols,
            index=dt_cols.index(default_col),
            key=f"{prefix}_date_col",
        )
        dt_series = pd.to_datetime(df[date_col], errors="coerce")
        min_dt = dt_series.min()
        max_dt = dt_series.max()
        if pd.notna(min_dt) and pd.notna(max_dt):
            default_range = defaults.get("date_range")
            if not default_range:
                default_range = (min_dt.date(), max_dt.date())
            if default_range[0] < min_dt.date():
                default_range = (min_dt.date(), default_range[1])
            if default_range[1] > max_dt.date():
                default_range = (default_range[0], max_dt.date())
            date_range = st.date_input(
                "Date range",
                value=default_range,
                min_value=min_dt.date(),
                max_value=max_dt.date(),
                key=f"{prefix}_date_range",
            )
            if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
                filters["date_col"] = date_col
                filters["date_range"] = (date_range[0], date_range[1])
    return filters


def _apply_filters(df: pd.DataFrame, filters: dict | None) -> pd.DataFrame:
    if not filters:
        return df
    out = df.copy()
    if "terminal" in filters and "Terminal" in out.columns:
        terminals = filters.get("terminal")
        if terminals is not None:
            if terminals:
                out = out[out["Terminal"].astype(str).isin(terminals)]
            else:
                return out.iloc[0:0]
    if "category" in filters and "Category" in out.columns:
        cats = filters.get("category")
        if cats is not None:
            if cats:
                out = out[out["Category"].astype(str).isin(cats)]
            else:
                return out.iloc[0:0]
    date_col = filters.get("date_col")
    date_range = filters.get("date_range")
    if date_col and date_col in out.columns and date_range:
        start, end = date_range
        dt_series = pd.to_datetime(out[date_col], errors="coerce")
        mask = (dt_series.dt.date >= start) & (dt_series.dt.date <= end)
        out = out[mask]
    return out


def _aggregate_series(series: pd.Series, agg: str):
    if agg == "count":
        return series.count()
    if agg == "count_distinct":
        return series.nunique()
    return series.agg(agg)


def _aggregate_grouped(df: pd.DataFrame, group_cols: list[str], measure: str, agg: str) -> pd.DataFrame:
    if agg == "count":
        grouped = df.groupby(group_cols, dropna=False)[measure].count()
    elif agg == "count_distinct":
        grouped = df.groupby(group_cols, dropna=False)[measure].nunique()
    else:
        grouped = df.groupby(group_cols, dropna=False)[measure].agg(agg)
    return grouped.reset_index(name="value")


def _altair_field_type(series: pd.Series) -> str:
    if pd.api.types.is_datetime64_any_dtype(series):
        return "T"
    if pd.api.types.is_numeric_dtype(series):
        return "Q"
    if series.dropna().apply(lambda v: isinstance(v, (pd.Timestamp, datetime, date))).any():
        return "T"
    return "N"


def _build_timeline_long(timeline_df: pd.DataFrame) -> pd.DataFrame:
    if timeline_df is None or timeline_df.empty:
        return pd.DataFrame(columns=["Timestamp", "Carousel", "Value"])
    long_df = timeline_df.copy()
    long_df = long_df.reset_index().rename(columns={long_df.index.name or "index": "Timestamp"})
    long_df = long_df.melt(id_vars=["Timestamp"], var_name="Carousel", value_name="Value")
    return long_df


def _build_carousels_df(timeline_df: pd.DataFrame | None, flights_df: pd.DataFrame | None) -> pd.DataFrame:
    names = []
    if timeline_df is not None and not timeline_df.empty:
        names.extend([str(c) for c in timeline_df.columns])
    if not names and flights_df is not None and "AssignedCarousel" in flights_df.columns:
        names.extend([str(x) for x in flights_df["AssignedCarousel"].dropna().unique().tolist()])
    seen = set()
    rows = []
    for name in names:
        if name in seen:
            continue
        seen.add(name)
        terminal = None
        carousel = name
        if "-" in name:
            parts = name.split("-", 1)
            terminal = parts[0].strip()
            carousel = parts[1].strip()
        rows.append({"CarouselKey": name, "Carousel": carousel, "Terminal": terminal})
    return pd.DataFrame(rows)


def _serialize_filters(filters: dict | None) -> dict | None:
    if not filters:
        return None
    payload = dict(filters)
    if "date_range" in payload and payload["date_range"]:
        start, end = payload["date_range"]
        payload["date_range"] = (
            start.isoformat() if isinstance(start, date) else start,
            end.isoformat() if isinstance(end, date) else end,
        )
    return payload


def _deserialize_filters(filters: dict | None) -> dict | None:
    if not filters:
        return None
    payload = dict(filters)
    if "date_range" in payload and payload["date_range"]:
        start, end = payload["date_range"]
        try:
            start_date = date.fromisoformat(start)
            end_date = date.fromisoformat(end)
            payload["date_range"] = (start_date, end_date)
        except Exception:
            payload.pop("date_range", None)
    return payload


def _render_analytics_page():
    st.header("Analytics")

    results = st.session_state.get("results")
    if not results or results.get("flights_out") is None:
        st.info("Exécutez une allocation pour generer les datasets (flights_out, timeline_df).")
        return

    flights_df = results.get("flights_out")
    timeline_df = results.get("timeline_df")
    sources = {
        "Flights": flights_df,
    }
    if timeline_df is not None:
        sources["Timeline"] = _build_timeline_long(timeline_df)
    sources["Carrousels"] = _build_carousels_df(timeline_df, flights_df)

    st.session_state.setdefault("analytics_vars", [])
    st.session_state.setdefault("analytics_kpis", [])
    st.session_state.setdefault("analytics_charts", [])
    st.session_state.setdefault("analytics_filters", {})

    with st.sidebar:
        st.header("Analytics")
        st.subheader("Filtres globaux")
        global_filters = _render_filters(
            flights_df,
            prefix="global_filters",
            defaults=st.session_state.get("analytics_filters"),
        )
        st.session_state["analytics_filters"] = global_filters

        st.subheader("Variables calculees")
        st.caption(
            "Formules supportees: + - * /, if/then/else, diff_minutes(a,b), hour(a), day(a), "
            "isnull(x), contains(x, 'text'), lower(x), comparaisons (==, !=, <, <=, >, >=)."
        )
        with st.form("add_calc_var"):
            source_name = st.selectbox("Source", list(sources.keys()), key="calc_source")
            var_name = st.text_input("Nom variable", key="calc_name")
            var_type = st.selectbox(
                "Type",
                ["number", "text", "boolean", "datetime"],
                key="calc_type",
            )
            var_expr = st.text_area("Formule", key="calc_expr", height=80)
            submit_var = st.form_submit_button("Ajouter / Mettre a jour")

        if submit_var:
            if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", var_name or ""):
                st.error("Nom de variable invalide (utilisez lettres, chiffres, underscore).")
            else:
                base_df = sources[source_name]
                if base_df is None or base_df.empty:
                    st.error("Source vide: impossible de valider la formule.")
                else:
                    try:
                        _eval_expression(var_expr, base_df.head(200))
                        vars_list = st.session_state["analytics_vars"]
                        existing = [v for v in vars_list if v["name"] == var_name and v["source"] == source_name]
                        payload = {
                            "name": var_name,
                            "source": source_name,
                            "dtype": var_type,
                            "expr": var_expr,
                        }
                        if existing:
                            idx = vars_list.index(existing[0])
                            vars_list[idx] = payload
                        else:
                            vars_list.append(payload)
                        st.session_state["analytics_vars"] = vars_list
                        st.success("Variable enregistree.")
                    except Exception as exc:
                        st.error(f"Formule invalide: {exc}")

        if st.session_state["analytics_vars"]:
            st.markdown("Variables existantes")
            for var in list(st.session_state["analytics_vars"]):
                cols = st.columns([5, 1])
                cols[0].write(f"{var['name']} ({var['source']}) = {var['expr']}")
                if cols[1].button("Supprimer", key=f"del_var_{var['source']}_{var['name']}"):
                    st.session_state["analytics_vars"] = [
                        v for v in st.session_state["analytics_vars"]
                        if not (v["name"] == var["name"] and v["source"] == var["source"])
                    ]
                    st.rerun()

        with st.expander("Dashboard config", expanded=False):
            config_payload = {
                "version": 1,
                "filters": _serialize_filters(st.session_state.get("analytics_filters")),
                "variables": st.session_state.get("analytics_vars", []),
                "kpis": st.session_state.get("analytics_kpis", []),
                "charts": st.session_state.get("analytics_charts", []),
            }
            st.download_button(
                "Save dashboard config",
                data=json.dumps(config_payload, indent=2),
                file_name="dashboard_config.json",
                key="dl_dashboard_config",
            )
            uploaded_config = st.file_uploader(
                "Load config (JSON)",
                type=["json"],
                key="upload_dashboard_config",
            )
            if uploaded_config:
                try:
                    loaded = json.loads(uploaded_config.read().decode("utf-8"))
                    st.session_state["analytics_vars"] = loaded.get("variables", [])
                    st.session_state["analytics_kpis"] = loaded.get("kpis", [])
                    st.session_state["analytics_charts"] = loaded.get("charts", [])
                    st.session_state["analytics_filters"] = _deserialize_filters(loaded.get("filters")) or {}
                    st.success("Config chargee.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Config invalide: {exc}")

    st.subheader("Add KPI")
    with st.form("add_kpi_form"):
        kpi_title = st.text_input("Titre KPI", key="kpi_title")
        kpi_source = st.selectbox("Source", list(sources.keys()), key="kpi_source")
        use_global = st.checkbox("Utiliser filtres globaux", value=True, key="kpi_use_global")
        kpi_filters = {}
        if not use_global and sources.get(kpi_source) is not None:
            kpi_filters = _render_filters(
                sources[kpi_source],
                prefix="kpi_filters",
            )
        base_df, var_errors = _apply_calculated_fields(
            sources[kpi_source],
            [v for v in st.session_state["analytics_vars"] if v["source"] == kpi_source],
        )
        if var_errors:
            st.warning("Erreurs variables: " + " | ".join(var_errors))
        measure_options = sorted(base_df.columns.tolist())
        kpi_measure = st.selectbox("Mesure", measure_options, key="kpi_measure")
        kpi_agg = st.selectbox(
            "Aggregation",
            ["sum", "mean", "count", "count_distinct", "min", "max"],
            key="kpi_agg",
        )
        add_kpi = st.form_submit_button("Ajouter KPI")

    if add_kpi:
        kpi_entry = {
            "id": str(uuid.uuid4()),
            "title": kpi_title or f"{kpi_agg}({kpi_measure})",
            "source": kpi_source,
            "measure": kpi_measure,
            "agg": kpi_agg,
            "use_global": use_global,
            "filters": kpi_filters,
        }
        st.session_state["analytics_kpis"].append(kpi_entry)
        st.success("KPI ajoute.")

    st.subheader("Add Chart")
    with st.form("add_chart_form"):
        chart_title = st.text_input("Titre chart", key="chart_title")
        chart_source = st.selectbox("Source", list(sources.keys()), key="chart_source")
        chart_type = st.selectbox("Type", ["table", "bar", "line", "pie"], key="chart_type")
        use_global_chart = st.checkbox("Utiliser filtres globaux", value=True, key="chart_use_global")
        chart_filters = {}
        if not use_global_chart and sources.get(chart_source) is not None:
            chart_filters = _render_filters(
                sources[chart_source],
                prefix="chart_filters",
            )
        base_df, var_errors = _apply_calculated_fields(
            sources[chart_source],
            [v for v in st.session_state["analytics_vars"] if v["source"] == chart_source],
        )
        if var_errors:
            st.warning("Erreurs variables: " + " | ".join(var_errors))
        chart_columns = base_df.columns.tolist()
        x_dim = st.selectbox("X (dimension)", chart_columns, key="chart_x")
        y_measure = st.selectbox("Y (mesure)", chart_columns, key="chart_y")
        y_agg = st.selectbox(
            "Aggregation",
            ["sum", "mean", "count", "count_distinct", "min", "max"],
            key="chart_agg",
        )
        series_options = ["(none)"] + chart_columns
        series_col = st.selectbox("Serie (color)", series_options, key="chart_series")
        top_n = st.number_input("Top N", min_value=0, value=0, step=1, key="chart_topn")
        sort_order = st.selectbox("Tri", ["desc", "asc"], key="chart_sort")
        add_chart = st.form_submit_button("Ajouter chart")

    if add_chart:
        chart_entry = {
            "id": str(uuid.uuid4()),
            "title": chart_title or f"{chart_type} {x_dim} / {y_agg}({y_measure})",
            "source": chart_source,
            "type": chart_type,
            "x": x_dim,
            "y": y_measure,
            "agg": y_agg,
            "series": None if series_col == "(none)" else series_col,
            "top_n": int(top_n) if top_n else 0,
            "sort": sort_order,
            "use_global": use_global_chart,
            "filters": chart_filters,
        }
        st.session_state["analytics_charts"].append(chart_entry)
        st.success("Chart ajoute.")

    st.subheader("Dashboard")
    if not st.session_state["analytics_kpis"] and not st.session_state["analytics_charts"]:
        st.info("Ajoutez des KPI ou des charts pour construire votre dashboard.")
        return

    if st.session_state["analytics_kpis"]:
        st.markdown("KPI")
        kpi_items = list(st.session_state["analytics_kpis"])
        for row_start in range(0, len(kpi_items), 4):
            row = kpi_items[row_start:row_start + 4]
            kpi_cols = st.columns(4)
            for idx, kpi in enumerate(row):
                df_source = sources.get(kpi["source"])
                if df_source is None or df_source.empty:
                    continue
                df_calc, var_errors = _apply_calculated_fields(
                    df_source,
                    [v for v in st.session_state["analytics_vars"] if v["source"] == kpi["source"]],
                )
                if var_errors:
                    st.warning("Erreurs variables: " + " | ".join(var_errors))
                if kpi.get("use_global"):
                    df_calc = _apply_filters(df_calc, st.session_state.get("analytics_filters"))
                df_calc = _apply_filters(df_calc, kpi.get("filters"))
                if kpi["measure"] not in df_calc.columns:
                    continue
                value = _aggregate_series(df_calc[kpi["measure"]], kpi["agg"])
                col = kpi_cols[idx]
                col.metric(kpi["title"], value)
                if col.button("Supprimer", key=f"del_kpi_{kpi['id']}"):
                    st.session_state["analytics_kpis"] = [
                        item for item in st.session_state["analytics_kpis"] if item["id"] != kpi["id"]
                    ]
                    st.rerun()

    if st.session_state["analytics_charts"]:
        st.markdown("Charts")
        for chart in list(st.session_state["analytics_charts"]):
            st.markdown(f"**{chart['title']}**")
            df_source = sources.get(chart["source"])
            if df_source is None or df_source.empty:
                st.info("Source vide.")
                continue
            df_calc, var_errors = _apply_calculated_fields(
                df_source,
                [v for v in st.session_state["analytics_vars"] if v["source"] == chart["source"]],
            )
            if var_errors:
                st.warning("Erreurs variables: " + " | ".join(var_errors))
            if chart.get("use_global"):
                df_calc = _apply_filters(df_calc, st.session_state.get("analytics_filters"))
            df_calc = _apply_filters(df_calc, chart.get("filters"))
            if chart["x"] not in df_calc.columns or chart["y"] not in df_calc.columns:
                st.warning("Colonnes manquantes pour ce chart.")
                continue
            group_cols = [chart["x"]]
            if chart.get("series"):
                group_cols.append(chart["series"])
            agg_df = _aggregate_grouped(df_calc, group_cols, chart["y"], chart["agg"])

            if chart.get("top_n"):
                if chart.get("series"):
                    totals = agg_df.groupby(chart["x"])["value"].sum().sort_values(ascending=False)
                    keep = totals.head(int(chart["top_n"])).index
                    agg_df = agg_df[agg_df[chart["x"]].isin(keep)]
                else:
                    agg_df = agg_df.sort_values("value", ascending=False).head(int(chart["top_n"]))

            if chart["type"] in ["bar", "pie", "table"]:
                agg_df = agg_df.sort_values("value", ascending=(chart["sort"] == "asc"))
            if chart["type"] == "line":
                agg_df = agg_df.sort_values(chart["x"])

            if chart["type"] == "table":
                st.dataframe(agg_df, use_container_width=True)
            else:
                x_type = _altair_field_type(agg_df[chart["x"]])
                x_field = f"{chart['x']}:{x_type}"
                if chart["type"] == "bar":
                    chart_obj = alt.Chart(agg_df).mark_bar().encode(
                        x=alt.X(x_field, sort=None),
                        y=alt.Y("value:Q"),
                        color=alt.Color(f"{chart['series']}:N") if chart.get("series") else alt.value(BRAND_RED),
                        tooltip=list(agg_df.columns),
                    )
                elif chart["type"] == "line":
                    chart_obj = alt.Chart(agg_df).mark_line(point=True).encode(
                        x=alt.X(x_field, sort=None),
                        y=alt.Y("value:Q"),
                        color=alt.Color(f"{chart['series']}:N") if chart.get("series") else alt.value(BRAND_RED),
                        tooltip=list(agg_df.columns),
                    )
                else:
                    chart_obj = alt.Chart(agg_df).mark_arc().encode(
                        theta=alt.Theta("value:Q"),
                        color=alt.Color(f"{chart['series']}:N") if chart.get("series") else alt.Color(f"{chart['x']}:N"),
                        tooltip=list(agg_df.columns),
                    )
                st.altair_chart(chart_obj, use_container_width=True)

            if st.button("Supprimer", key=f"del_chart_{chart['id']}"):
                st.session_state["analytics_charts"] = [
                    item for item in st.session_state["analytics_charts"] if item["id"] != chart["id"]
                ]
                st.rerun()


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
        df["_TerminalStd"] = df["Terminal"].astype(str).str.strip().map(lambda x: term_mapping.get(x, "IGNORER"))
        ignored_term = df[df["_TerminalStd"] == "IGNORER"]
        if len(ignored_term) > 0:
            warnings.append({
                "Type": "Terminal non mappe",
                "Message": "Lignes ignorees (Terminal non mappe)",
                "Count": int(len(ignored_term)),
            })
        df = df[df["_TerminalStd"] != "IGNORER"].copy()
        df["Terminal"] = df["_TerminalStd"]
        df = df.drop(columns=["_TerminalStd"])

    return df, warnings


def _default_extra_caps_from_caps(caps: dict | None) -> tuple[int, int]:
    if not caps:
        return 8, 4
    max_wide = max(int(c.wide) for c in caps.values())
    max_narrow = max(int(c.narrow) for c in caps.values())
    return max_wide, max_narrow


def _build_extra_terms_and_defaults(
    df_ready: pd.DataFrame,
    carousels_mode: str | None,
    caps_by_terminal: dict | None,
    caps_manual: dict | None,
) -> tuple[list[str], dict[str, tuple[int, int]]]:
    if df_ready is None or "Terminal" not in df_ready.columns:
        wide_def, nar_def = _default_extra_caps_from_caps(caps_manual)
        return ["ALL"], {"ALL": (wide_def, nar_def)}

    terminals = sorted([str(x).strip() for x in df_ready["Terminal"].dropna().unique().tolist()])
    if carousels_mode == "file" and caps_by_terminal:
        valid_terms = [t for t in terminals if t in caps_by_terminal]
        defaults = {t: _default_extra_caps_from_caps(caps_by_terminal.get(t)) for t in valid_terms}
        return valid_terms, defaults

    wide_def, nar_def = _default_extra_caps_from_caps(caps_manual)
    defaults = {t: (wide_def, nar_def) for t in terminals}
    return terminals, defaults


def _normalize_segments(value: object) -> list[dict[str, object]]:
    if value is None:
        return []
    if isinstance(value, list):
        return [seg for seg in value if isinstance(seg, dict)]
    if isinstance(value, dict):
        return [value]
    if isinstance(value, str):
        text = value.strip()
        if not text or text.lower() in ("nan", "none"):
            return []
        try:
            parsed = ast.literal_eval(text)
        except Exception:
            return []
        return _normalize_segments(parsed)
    return []


def _has_assignment_segments(flights_df: pd.DataFrame) -> bool:
    if flights_df is None or "AssignmentSegments" not in flights_df.columns:
        return False
    return flights_df["AssignmentSegments"].apply(lambda v: len(_normalize_segments(v)) > 0).any()


def _ensure_segments_for_heatmap(
    flights_df: pd.DataFrame,
    caps: dict[str, CarouselCapacity],
) -> pd.DataFrame:
    if flights_df is None:
        return pd.DataFrame()
    if flights_df.empty:
        out = flights_df.copy()
        if "AssignmentSegments" not in out.columns:
            out["AssignmentSegments"] = [[] for _ in range(len(out))]
        return out
    if not caps:
        out = flights_df.copy()
        if "AssignmentSegments" not in out.columns:
            out["AssignmentSegments"] = [[] for _ in range(len(out))]
        return out
    if _has_assignment_segments(flights_df):
        return flights_df
    try:
        return compute_single_assignment_segments(flights_df, caps)
    except Exception:
        out = flights_df.copy()
        out["AssignmentSegments"] = [[] for _ in range(len(out))]
        return out


def _compute_occupancy_arrays(
    flights_df: pd.DataFrame,
    timeline_index: pd.DatetimeIndex,
    carousels: list[str],
) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    size = len(timeline_index)
    usage_wide = {c: np.zeros(size, dtype=int) for c in carousels}
    usage_narrow = {c: np.zeros(size, dtype=int) for c in carousels}
    if flights_df is None or flights_df.empty or size == 0:
        return usage_wide, usage_narrow

    for _, row in flights_df.iterrows():
        open_t = pd.Timestamp(row.get("MakeupOpening"))
        close_t = pd.Timestamp(row.get("MakeupClosing"))
        if pd.isna(open_t) or pd.isna(close_t) or close_t <= open_t:
            continue
        start_idx = timeline_index.searchsorted(open_t, side="right") - 1
        end_idx = timeline_index.searchsorted(close_t, side="left")
        if start_idx < 0:
            start_idx = 0
        if end_idx > size:
            end_idx = size
        if start_idx >= end_idx:
            continue

        segments = _normalize_segments(row.get("AssignmentSegments"))
        if not segments:
            continue
        for seg in segments:
            carousel = str(seg.get("carousel", "")).strip()
            if not carousel or carousel not in usage_wide:
                continue
            try:
                wide_used = int(seg.get("wide_used", 0))
            except Exception:
                wide_used = 0
            try:
                narrow_used = int(seg.get("narrow_used", 0))
            except Exception:
                narrow_used = 0
            if wide_used == 0 and narrow_used == 0:
                continue
            usage_wide[carousel][start_idx:end_idx] += wide_used
            usage_narrow[carousel][start_idx:end_idx] += narrow_used

    return usage_wide, usage_narrow


def _extract_extra_carousels(columns: list[str], term: str | None = None) -> list[str]:
    extras: list[str] = []
    prefix = f"{term}-" if term else None
    for col in columns or []:
        name = str(col)
        if prefix:
            if not name.startswith(prefix):
                continue
            base = name[len(prefix):]
        else:
            base = name
        if base.upper().startswith("EXTRA"):
            extras.append(base)
    seen: set[str] = set()
    uniq: list[str] = []
    for extra in extras:
        if extra not in seen:
            seen.add(extra)
            uniq.append(extra)
    return uniq


def _add_extras_to_caps(
    caps: dict[str, CarouselCapacity] | None,
    extras: list[str],
    extra_cap: CarouselCapacity | None,
) -> dict[str, CarouselCapacity]:
    out = dict(caps or {})
    if extra_cap is None:
        return out
    for extra in extras:
        if extra not in out:
            out[extra] = CarouselCapacity(int(extra_cap.wide), int(extra_cap.narrow))
    return out


def _build_heatmap_frames(
    flights_df: pd.DataFrame,
    timeline_index: pd.DatetimeIndex,
    caps: dict[str, CarouselCapacity],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    flights_seg = _ensure_segments_for_heatmap(flights_df, caps)
    carousels = list(caps.keys())
    usage_wide, usage_narrow = _compute_occupancy_arrays(flights_seg, timeline_index, carousels)

    data_occ: dict[str, object] = {}
    data_free: dict[str, object] = {}
    for carousel in carousels:
        wide_occ = usage_wide.get(carousel, np.zeros(len(timeline_index), dtype=int))
        nar_occ = usage_narrow.get(carousel, np.zeros(len(timeline_index), dtype=int))
        data_occ[f"{carousel}_Wide"] = wide_occ
        data_occ[f"{carousel}_Narrow"] = nar_occ
        cap = caps.get(carousel)
        cap_wide = int(cap.wide) if cap else 0
        cap_nar = int(cap.narrow) if cap else 0
        data_free[f"{carousel}_Wide"] = cap_wide - wide_occ
        data_free[f"{carousel}_Narrow"] = cap_nar - nar_occ

    occ_df = pd.DataFrame(data_occ, index=timeline_index)
    free_df = pd.DataFrame(data_free, index=timeline_index)
    return occ_df, free_df


def _build_heatmap_sheets(
    flights_df: pd.DataFrame,
    timeline_index: pd.DatetimeIndex,
    timeline_columns: list[str],
    *,
    carousels_mode: str | None,
    caps_manual: dict[str, CarouselCapacity] | None,
    caps_by_terminal: dict[str, dict[str, CarouselCapacity]] | None,
    extra_caps_by_terminal: dict[str, CarouselCapacity] | None,
) -> tuple[dict[str, pd.DataFrame], dict[str, pd.DataFrame]]:
    occ_sheets: dict[str, pd.DataFrame] = {}
    free_sheets: dict[str, pd.DataFrame] = {}

    if carousels_mode == "file" and caps_by_terminal:
        for term, caps_term in caps_by_terminal.items():
            df_term = flights_df
            if df_term is not None and "Terminal" in df_term.columns:
                df_term = df_term[df_term["Terminal"].astype(str) == str(term)]
            else:
                df_term = df_term.iloc[0:0] if df_term is not None else df_term
            extras = _extract_extra_carousels(timeline_columns, term)
            extra_cap = extra_caps_by_terminal.get(term) if extra_caps_by_terminal else None
            caps_full = _add_extras_to_caps(caps_term, extras, extra_cap)
            occ_df, free_df = _build_heatmap_frames(df_term, timeline_index, caps_full)
            occ_sheets[str(term)] = occ_df
            free_sheets[str(term)] = free_df
    else:
        extras = _extract_extra_carousels(timeline_columns)
        extra_cap = extra_caps_by_terminal.get("ALL") if extra_caps_by_terminal else None
        caps_full = _add_extras_to_caps(caps_manual, extras, extra_cap)
        occ_df, free_df = _build_heatmap_frames(flights_df, timeline_index, caps_full)
        occ_sheets["Planning"] = occ_df
        free_sheets["Planning"] = free_df

    if not occ_sheets:
        empty = pd.DataFrame(index=timeline_index)
        occ_sheets["Planning"] = empty
        free_sheets["Planning"] = empty

    return occ_sheets, free_sheets


def _readjust_terminal_allocations(
    flights_out_term: pd.DataFrame,
    carousel_caps: dict[str, CarouselCapacity],
    *,
    extra_capacity: CarouselCapacity | None,
    time_step_minutes: int,
    start_time: pd.Timestamp,
    end_time: pd.Timestamp,
    max_carousels_narrow: int,
    max_carousels_wide: int,
    rule_order: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame, list[str], pd.DataFrame]:
    if flights_out_term is None or len(flights_out_term) == 0:
        empty = flights_out_term.copy() if flights_out_term is not None else pd.DataFrame()
        timeline = build_timeline_from_assignments(
            empty,
            list(carousel_caps.keys()),
            time_step_minutes,
            start_time,
            end_time,
        )
        return empty, timeline, [], empty.iloc[0:0].copy()

    readjusted = flights_out_term.copy()
    readjusted["OriginalCategory"] = readjusted["Category"].astype(str).str.strip()
    readjusted["FinalCategory"] = readjusted["OriginalCategory"]
    readjusted["CategoryChanged"] = "NO"
    readjusted["AssignedCarousels"] = [[] for _ in range(len(readjusted))]
    readjusted["AssignmentSegments"] = [[] for _ in range(len(readjusted))]
    readjusted["SplitCount"] = 0

    assigned_vals = readjusted["AssignedCarousel"].fillna("").astype(str).str.strip()
    assigned_mask = (
        assigned_vals.ne("")
        & assigned_vals.str.upper().ne("UNASSIGNED")
        & assigned_vals.str.lower().ne("nan")
    )
    readjusted.loc[assigned_mask, "AssignedCarousels"] = assigned_vals[assigned_mask].apply(lambda x: [x])
    readjusted.loc[assigned_mask, "SplitCount"] = 1

    fixed = readjusted[assigned_mask].copy()
    if len(fixed) > 0:
        fixed = compute_single_assignment_segments(
            fixed,
            carousel_caps,
        )
        readjusted.loc[fixed.index, "AssignmentSegments"] = fixed["AssignmentSegments"]

    def _candidate_mask(df: pd.DataFrame) -> pd.Series:
        reasons = df["UnassignedReason"].fillna("").astype(str).str.upper()
        return (df["AssignedCarousels"].apply(len) == 0) & reasons.isin(["NO_CAPACITY", "IMPOSSIBLE_DEMAND"])

    def _apply_updates(updates: pd.DataFrame):
        if updates is None or len(updates) == 0:
            return
        for idx, row in updates.iterrows():
            assigned_list = row.get("AssignedCarousels", [])
            readjusted.at[idx, "AssignedCarousels"] = assigned_list
            readjusted.at[idx, "AssignmentSegments"] = row.get("AssignmentSegments", [])
            readjusted.at[idx, "UnassignedReason"] = row.get("UnassignedReason", "")
            readjusted.at[idx, "SplitCount"] = len(assigned_list) if assigned_list else 0

            alloc_cat = str(row.get("AllocationCategory", "")).strip().lower()
            orig_cat = str(readjusted.at[idx, "OriginalCategory"]).strip().lower()
            if assigned_list and alloc_cat == "wide" and orig_cat == "narrow":
                readjusted.at[idx, "FinalCategory"] = "Wide"
                readjusted.at[idx, "CategoryChanged"] = "YES"

    extras_used: list[str] = []
    current_caps = dict(carousel_caps)
    allow_multi = False
    allow_narrow_wide = False

    def _current_max() -> tuple[int, int]:
        if allow_multi:
            return int(max_carousels_narrow), int(max_carousels_wide)
        return 1, 1

    def _allocate_step():
        flex = readjusted[_candidate_mask(readjusted)].copy()
        if len(flex) == 0:
            return
        fixed = readjusted[readjusted["AssignedCarousels"].apply(len) > 0].copy()
        max_n, max_w = _current_max()
        assigned = allocate_with_fixed_assignments(
            fixed,
            flex,
            current_caps,
            max_carousels_per_flight_narrow=max_n,
            max_carousels_per_flight_wide=max_w,
            allow_narrow_use_wide=allow_narrow_wide,
        )
        _apply_updates(assigned)

    def _allocate_with_extras():
        nonlocal current_caps, extras_used
        if extra_capacity is None:
            return
        flex = readjusted[_candidate_mask(readjusted)].copy()
        if len(flex) == 0:
            return
        fixed = readjusted[readjusted["AssignedCarousels"].apply(len) > 0].copy()
        max_n, max_w = _current_max()

        max_k = len(flex)
        best = None
        best_k = 0
        best_caps = current_caps
        for k in range(1, max_k + 1):
            caps_extra = {
                **current_caps,
                **{f"EXTRA{i}": extra_capacity for i in range(1, k + 1)},
            }
            attempt = allocate_with_fixed_assignments(
                fixed,
                flex,
                caps_extra,
                max_carousels_per_flight_narrow=max_n,
                max_carousels_per_flight_wide=max_w,
                allow_narrow_use_wide=allow_narrow_wide,
            )
            blocked = attempt[
                (attempt["AssignedCarousels"].apply(len) == 0)
                & (attempt["UnassignedReason"] != "IMPOSSIBLE_DEMAND")
            ]
            best = attempt
            best_k = k
            best_caps = caps_extra
            if len(blocked) == 0:
                break

        if best is not None:
            extras_used = [f"EXTRA{i}" for i in range(1, best_k + 1)]
            current_caps = best_caps
            _apply_updates(best)

    seen = set()
    for rule in rule_order or []:
        if rule in seen:
            continue
        seen.add(rule)
        if rule == "multi":
            allow_multi = True
            _allocate_step()
        elif rule == "narrow_wide":
            allow_narrow_wide = True
            _allocate_step()
        elif rule == "extras":
            _allocate_with_extras()

    carousels_list = list(carousel_caps.keys()) + extras_used
    timeline_term = build_timeline_from_assignments(
        readjusted,
        carousels_list,
        time_step_minutes,
        start_time,
        end_time,
    )

    def _assigned_carousel_value(lst: list[str]) -> str:
        if not lst:
            return "UNASSIGNED"
        if len(lst) == 1:
            return lst[0]
        return "SPLIT"

    readjusted["SplitCount"] = readjusted["AssignedCarousels"].apply(len)
    readjusted["AssignedCarousel"] = readjusted["AssignedCarousels"].apply(_assigned_carousel_value)
    readjusted["Category"] = readjusted["FinalCategory"]
    readjusted["AssignedCarousels"] = readjusted["AssignedCarousels"].apply(
        lambda lst: "+".join(lst) if lst else "UNASSIGNED"
    )
    impossible_df = readjusted[
        (readjusted["AssignedCarousels"] == "UNASSIGNED")
        & (readjusted["UnassignedReason"] == "IMPOSSIBLE_DEMAND")
    ].copy()

    return readjusted, timeline_term, extras_used, impossible_df


page = st.sidebar.radio(
    "Page",
    options=["Allocation", "Analytics"],
    index=0,
    key="page_select",
)
if page == "Analytics":
    _render_analytics_page()
    st.stop()

st.subheader("Etape 1 - Upload fichier vols")
uploaded = st.file_uploader("Chargez le fichier Excel des vols", type=["xlsx"], key="flights_file")

df_raw = None
if uploaded:
    file_sig = (uploaded.name, uploaded.size)
    if st.session_state.get("flights_file_sig") != file_sig:
        _reset_after_upload()
        st.session_state["flights_file_sig"] = file_sig
    try:
        df_raw = pd.read_excel(uploaded)
    except Exception:
        st.error("Impossible de lire le fichier Excel des vols.")
else:
    st.info("Chargez un fichier Excel pour demarrer.")


col_mapping_preview = st.session_state.get("col_mapping")
mapping_confirmed = bool(st.session_state.get("mapping_confirmed", False))
df_mapped_preview = None
has_terminal = False
if df_raw is not None and mapping_confirmed and col_mapping_preview:
    df_mapped_preview = df_raw.rename(columns=col_mapping_preview).copy()
    has_terminal = "Terminal" in df_mapped_preview.columns


with st.sidebar:
    st.header("Parametres")
    if st.button("Reset project"):
        st.session_state.clear()
        st.rerun()

    st.subheader("Make-up")
    makeup_mode = st.radio(
        "Mode make-up",
        options=["Colonnes (MakeupOpening/MakeupClosing)", "Offsets"],
        index=0,
        key="makeup_mode",
    )
    if makeup_mode == "Offsets":
        wide_x = st.number_input("Wide: opening (min)", min_value=0, value=120, step=5, key="wide_x")
        wide_y = st.number_input("Wide: closing (min)", min_value=0, value=15, step=5, key="wide_y")
        nar_x = st.number_input("Narrow: opening (min)", min_value=0, value=90, step=5, key="nar_x")
        nar_y = st.number_input("Narrow: closing (min)", min_value=0, value=10, step=5, key="nar_y")
    else:
        wide_x = st.session_state.get("wide_x", 120)
        wide_y = st.session_state.get("wide_y", 15)
        nar_x = st.session_state.get("nar_x", 90)
        nar_y = st.session_state.get("nar_y", 10)

    st.subheader("Time step")
    time_step = st.number_input("Pas de temps (minutes)", min_value=1, value=5, step=1, key="time_step")

    st.subheader("Planning - Couleurs")
    color_options = ["Par categorie", "Par vol"]
    if has_terminal:
        color_options.append("Par terminal")
    color_mode_ui = st.radio(
        "Mode couleur planning",
        options=color_options,
        index=0,
        key="color_mode_ui",
    )
    wide_color_default = "#D32F2F"
    narrow_color_default = "#FFEBEE"
    split_color_default = "#FFC107"
    narrow_wide_color_default = "#00B894"
    wide_color = st.session_state.get("wide_color", wide_color_default)
    narrow_color = st.session_state.get("narrow_color", narrow_color_default)
    split_color = st.session_state.get("split_color", split_color_default)
    narrow_wide_color = st.session_state.get("narrow_wide_color", narrow_wide_color_default)
    if color_mode_ui == "Par terminal":
        st.caption("Mode par terminal: couleurs automatiques (hors exceptions).")
    elif color_mode_ui == "Par vol":
        st.caption("Mode par vol: couleurs automatiques (hors exceptions).")
    else:
        st.caption("Couleurs Wide/Narrow definies dans l'etape 6b.")

    with st.expander("Options avancees", expanded=False):
        show_warnings = st.checkbox("Afficher panneau Warnings", value=True, key="show_warnings")
        show_debug = st.checkbox("Afficher details erreur", value=False, key="show_debug_errors")


if df_raw is None:
    st.stop()

with st.expander("Preview fichier vols", expanded=False):
    st.dataframe(df_raw.head(20), use_container_width=True)


st.divider()
st.subheader("Etape 2 - Mapping colonnes")

cols = list(df_raw.columns)
default_dep = _guess_col(cols, ["std", "departure time", "heure de depart", "dep time"])
default_flt = _guess_col(cols, ["flight number", "flight no", "flt", "numero de vol", "num vol"])
default_cat = _guess_col(cols, ["category", "categorie", "cat", "type"])
default_pos = _guess_col(cols, ["positions", "position", "pos", "nb position", "nbr position"])
default_term = _guess_col(cols, ["terminal", "term", "tml"])
default_open = _guess_col(cols, ["make up opening", "make-up opening", "makeup opening", "opening"])
default_close = _guess_col(cols, ["make up closing", "make-up closing", "makeup closing", "closing"])


def _selectbox(label, default, key, existing=None):
    options = ["(Aucune)"] + cols
    if existing in options:
        idx = options.index(existing)
    elif default in options:
        idx = options.index(default)
    else:
        idx = 0
    return st.selectbox(label, options=options, index=idx, key=key)


if not mapping_confirmed:
    c_dep = _selectbox("Departure time (ex: STD)", default_dep, "map_dep", st.session_state.get("map_dep"))
    c_flt = _selectbox("Flight number", default_flt, "map_flt", st.session_state.get("map_flt"))
    c_cat = _selectbox("Category (ex: Wide body / Narrow body)", default_cat, "map_cat", st.session_state.get("map_cat"))
    c_pos = _selectbox("Positions", default_pos, "map_pos", st.session_state.get("map_pos"))

    st.caption("Optionnels")
    c_term = _selectbox("Terminal (optionnel)", default_term, "map_term", st.session_state.get("map_term"))
    c_open = _selectbox("MakeupOpening (optionnel)", default_open, "map_open", st.session_state.get("map_open"))
    c_close = _selectbox("MakeupClosing (optionnel)", default_close, "map_close", st.session_state.get("map_close"))

    st.markdown("**Colonnes supplementaires a conserver (optionnel)**")
    selected_raw = {c_dep, c_flt, c_cat, c_pos, c_term, c_open, c_close}
    selected_raw.discard("(Aucune)")
    extra_candidates = [c for c in cols if c not in selected_raw]
    if extra_candidates:
        default_keep = extra_candidates
        if "keep_extra_cols_ui" in st.session_state:
            default_keep = st.session_state.get("keep_extra_cols_ui", [])
        default_keep = [c for c in default_keep if c in extra_candidates]
        keep_extra_cols = st.multiselect(
            "Ces colonnes seront conservees dans summary/summary_readjusted.",
            options=extra_candidates,
            default=default_keep,
            key="keep_extra_cols_ui",
        )
    else:
        keep_extra_cols = []
        st.caption("Aucune colonne supplementaire disponible.")

    if st.button("Confirmer mapping colonnes", key="confirm_mapping_cols"):
        missing = []
        if c_dep == "(Aucune)":
            missing.append("DepartureTime")
        if c_flt == "(Aucune)":
            missing.append("FlightNumber")
        if c_cat == "(Aucune)":
            missing.append("Category")
        if c_pos == "(Aucune)":
            missing.append("Positions")
        if missing:
            st.error(f"Colonnes obligatoires non selectionnees : {missing}")
            st.stop()

        col_mapping = {
            c_dep: "DepartureTime",
            c_flt: "FlightNumber",
            c_cat: "Category",
            c_pos: "Positions",
        }
        if c_term != "(Aucune)":
            col_mapping[c_term] = "Terminal"
        if c_open != "(Aucune)":
            col_mapping[c_open] = "MakeupOpening"
        if c_close != "(Aucune)":
            col_mapping[c_close] = "MakeupClosing"

        keep_extra_cols = [c for c in (keep_extra_cols or []) if c in cols]
        st.session_state["col_mapping"] = col_mapping
        st.session_state["keep_extra_cols"] = keep_extra_cols
        st.session_state["mapping_confirmed"] = True
        st.rerun()
else:
    col_mapping = st.session_state.get("col_mapping", {})
    if not col_mapping:
        st.error("Mapping colonnes manquant.")
        st.session_state["mapping_confirmed"] = False
        st.stop()

    st.success("Mapping colonnes confirme.")
    if st.button("Modifier mapping colonnes", key="modify_mapping_cols"):
        st.session_state["mapping_confirmed"] = False
        _reset_after_mapping()
        st.rerun()


mapping_confirmed = bool(st.session_state.get("mapping_confirmed", False))
if not mapping_confirmed:
    st.stop()

col_mapping = st.session_state.get("col_mapping", {})
df_mapped = df_raw.rename(columns=col_mapping).copy()
required_mapped = ["DepartureTime", "FlightNumber", "Category", "Positions"]
missing_mapped = [c for c in required_mapped if c not in df_mapped.columns]
if missing_mapped:
    st.error(f"Colonnes obligatoires manquantes apres mapping : {missing_mapped}")
    st.stop()

with st.expander("Apercu colonnes mappees", expanded=False):
    st.dataframe(df_mapped.head(20), use_container_width=True)


st.divider()
st.subheader("Etape 3 - Mapping categories & terminals")

cat_term_confirmed = bool(st.session_state.get("cat_term_confirmed", False))
raw_cats = sorted([str(x).strip() for x in df_mapped["Category"].dropna().unique().tolist()])


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


cat_options = ["Wide", "Narrow", "IGNORER"]
cat_mapping = {}
term_mapping = {}

if not cat_term_confirmed:
    with st.expander("Mapping categories", expanded=True):
        for v in raw_cats:
            key = f"catmap_{v}"
            existing = st.session_state.get(key)
            default = existing if existing in cat_options else suggest_cat(v)
            idx = cat_options.index(default) if default in cat_options else 0
            st.selectbox(f"'{v}' ->", options=cat_options, index=idx, key=key)
            cat_mapping[v] = st.session_state.get(key, default)

    if "Terminal" in df_mapped.columns:
        raw_terms = sorted([str(x).strip() for x in df_mapped["Terminal"].dropna().unique().tolist()])
        suggested = {v: suggest_term(v) for v in raw_terms}
        std_terms = sorted(set(suggested.values()))
        std_options = std_terms + ["IGNORER"]

        with st.expander("Mapping terminals", expanded=True):
            for v in raw_terms:
                key = f"termmap_{v}"
                existing = st.session_state.get(key)
                default = existing if existing in std_options else suggested[v]
                idx = std_options.index(default) if default in std_options else 0
                st.selectbox(f"'{v}' ->", options=std_options, index=idx, key=key)
                term_mapping[v] = st.session_state.get(key, default)

    if st.button("Confirmer mapping categories & terminals", key="confirm_cat_term"):
        st.session_state["cat_mapping"] = cat_mapping
        st.session_state["term_mapping"] = term_mapping
        st.session_state["cat_term_confirmed"] = True
        st.rerun()
else:
    st.success("Mapping categories & terminals confirme.")
    if st.button("Modifier mapping categories & terminals", key="modify_cat_term"):
        st.session_state["cat_term_confirmed"] = False
        _reset_after_cat_term()
        st.rerun()


cat_term_confirmed = bool(st.session_state.get("cat_term_confirmed", False))
if not cat_term_confirmed:
    st.stop()

cat_mapping = st.session_state.get("cat_mapping")
if not cat_mapping:
    st.error("Mapping categories manquant.")
    st.session_state["cat_term_confirmed"] = False
    st.stop()

term_mapping = st.session_state.get("term_mapping", {})
df_std, mapping_warnings = _apply_cat_term_mapping(df_mapped, cat_mapping, term_mapping)


st.divider()
st.subheader("Etape 4 - Make-up times")

makeup_confirmed = bool(st.session_state.get("makeup_confirmed", False))
current_signature = (makeup_mode, wide_x, wide_y, nar_x, nar_y)
if makeup_confirmed and st.session_state.get("makeup_signature") != current_signature:
    st.session_state["makeup_confirmed"] = False
    _reset_after_makeup()
    makeup_confirmed = False

if makeup_mode == "Colonnes (MakeupOpening/MakeupClosing)":
    if "MakeupOpening" not in df_std.columns or "MakeupClosing" not in df_std.columns:
        st.error("Colonnes MakeupOpening/MakeupClosing manquantes.")
        st.stop()
    df_ready = df_std.copy()
else:
    df_ready = df_std.copy()

    def compute_open_close(row):
        dep = pd.Timestamp(row["DepartureTime"])
        cat = str(row["Category"]).strip().lower()
        if cat == "wide":
            return dep - pd.Timedelta(minutes=wide_x), dep - pd.Timedelta(minutes=wide_y)
        if cat == "narrow":
            return dep - pd.Timedelta(minutes=nar_x), dep - pd.Timedelta(minutes=nar_y)
        return pd.NaT, pd.NaT

    oc = df_ready.apply(compute_open_close, axis=1, result_type="expand")
    df_ready["MakeupOpening"] = oc[0]
    df_ready["MakeupClosing"] = oc[1]

open_ts = pd.to_datetime(df_ready["MakeupOpening"], errors="coerce")
close_ts = pd.to_datetime(df_ready["MakeupClosing"], errors="coerce")
bad_times = df_ready[
    open_ts.isna()
    | close_ts.isna()
    | (open_ts >= close_ts)
]
makeup_warnings = []
if len(bad_times) > 0:
    makeup_warnings.append({
        "Type": "Makeup invalide",
        "Message": "MakeupOpening >= MakeupClosing ou valeurs manquantes",
        "Count": int(len(bad_times)),
    })

if not makeup_confirmed:
    if st.button("Confirmer make-up times", key="confirm_makeup"):
        st.session_state["makeup_confirmed"] = True
        st.session_state["makeup_signature"] = current_signature
        st.rerun()
else:
    st.success("Make-up times confirmes.")
    if st.button("Modifier make-up times", key="modify_makeup"):
        st.session_state["makeup_confirmed"] = False
        _reset_after_makeup()
        st.rerun()


makeup_confirmed = bool(st.session_state.get("makeup_confirmed", False))
if not makeup_confirmed:
    st.stop()


st.divider()
st.subheader("Etape 5 - Time step")

time_step_confirmed = bool(st.session_state.get("time_step_confirmed", False))
current_time_step = int(time_step)
if time_step_confirmed and st.session_state.get("time_step_value") != current_time_step:
    st.session_state["time_step_confirmed"] = False
    _reset_after_time_step()
    time_step_confirmed = False

if not time_step_confirmed:
    if st.button("Confirmer time step", key="confirm_time_step"):
        st.session_state["time_step_confirmed"] = True
        st.session_state["time_step_value"] = current_time_step
        st.rerun()
else:
    st.success("Time step confirme.")
    if st.button("Modifier time step", key="modify_time_step"):
        st.session_state["time_step_confirmed"] = False
        _reset_after_time_step()
        st.rerun()


time_step_confirmed = bool(st.session_state.get("time_step_confirmed", False))
if not time_step_confirmed:
    st.stop()


st.divider()
st.subheader("Etape 6 - Configuration carrousels")

car_file = st.file_uploader(
    "Chargez le fichier carousels_by_terminal.csv (optionnel)",
    type=["csv", "txt"],
    key="carousels_file",
)

carousels_confirmed = bool(st.session_state.get("carousels_confirmed", False))
carousels_mode = None
caps_by_terminal = None
caps_manual = None
car_warnings = []

if car_file:
    car_sig = (car_file.name, car_file.size)
    if st.session_state.get("car_file_sig") != car_sig:
        st.session_state["carousels_confirmed"] = False
        _reset_after_carousels()
        st.session_state["car_file_sig"] = car_sig

    try:
        car_df = pd.read_csv(car_file, sep=";")
    except Exception:
        st.error("Impossible de lire carousels_by_terminal.csv.")
        st.stop()

    car_df.columns = car_df.columns.astype(str).str.strip()
    expected = {"Terminal", "CarouselName", "WideCapacity", "NarrowCapacity"}
    if not expected.issubset(set(car_df.columns)):
        st.error(f"Colonnes attendues dans le fichier carrousels : {sorted(list(expected))}")
        st.stop()

    car_df["Terminal"] = car_df["Terminal"].astype(str).str.strip()
    car_df["CarouselName"] = car_df["CarouselName"].astype(str).str.strip()
    car_df["WideCapacity"] = car_df["WideCapacity"].astype(int)
    car_df["NarrowCapacity"] = car_df["NarrowCapacity"].astype(int)

    st.dataframe(car_df, use_container_width=True)
    summary_counts = car_df.groupby("Terminal")["CarouselName"].count().sort_index()
    summary_text = ", ".join([f"{t}: {c} carrousels" for t, c in summary_counts.items()])
    if summary_text:
        st.info(f"Resume : {summary_text}")

    if "Terminal" in df_ready.columns:
        missing_terms = sorted(set(df_ready["Terminal"].unique()) - set(car_df["Terminal"].unique()))
        if missing_terms:
            st.warning(f"Terminals non configures -> vols UNASSIGNED : {', '.join(missing_terms)}")
            car_warnings.append({
                "Type": "Terminal non configure",
                "Message": "Terminal absent du fichier carrousels",
                "Count": int(len(missing_terms)),
            })

    if not carousels_confirmed:
        if st.button("Confirmer carrousels (fichier)", key="confirm_carousels_file"):
            caps_by_terminal = {}
            for term, g in car_df.groupby("Terminal"):
                caps_by_terminal[term] = {
                    row["CarouselName"]: CarouselCapacity(
                        wide=int(row["WideCapacity"]),
                        narrow=int(row["NarrowCapacity"]),
                    )
                    for _, row in g.iterrows()
                }
            st.session_state["caps_by_terminal"] = caps_by_terminal
            st.session_state["carousels_confirmed"] = True
            st.session_state["carousels_mode"] = "file"
            st.rerun()
    else:
        st.success("Configuration carrousels (fichier) confirmee.")
        if st.button("Modifier carrousels", key="modify_carousels_file"):
            st.session_state["carousels_confirmed"] = False
            _reset_after_carousels()
            st.rerun()
else:
    st.info("Mode manuel (pas de fichier carrousels charge).")
    nb = st.number_input("Nombre de carrousels", min_value=1, value=3, step=1, key="nb_carousels")
    caps_manual = {}
    cols = st.columns(int(nb))
    for i in range(int(nb)):
        with cols[i]:
            c_name = f"Carousel {i+1}"
            wide = st.number_input(f"{c_name} - Wide capacity", min_value=0, value=8, step=1, key=f"w{i}")
            nar = st.number_input(f"{c_name} - Narrow capacity", min_value=0, value=4, step=1, key=f"n{i}")
            caps_manual[c_name] = CarouselCapacity(wide=int(wide), narrow=int(nar))

    if not carousels_confirmed:
        if st.button("Confirmer carrousels (manuel)", key="confirm_carousels_manual"):
            st.session_state["caps_manual"] = caps_manual
            st.session_state["carousels_confirmed"] = True
            st.session_state["carousels_mode"] = "manual"
            st.rerun()
    else:
        st.success("Configuration carrousels (manuel) confirmee.")
        if st.button("Modifier carrousels", key="modify_carousels_manual"):
            st.session_state["carousels_confirmed"] = False
            _reset_after_carousels()
            st.rerun()


carousels_confirmed = bool(st.session_state.get("carousels_confirmed", False))
if not carousels_confirmed:
    st.stop()


st.divider()
st.subheader("Etape 6b - Capacity sizing (extras)")

caps_by_terminal = st.session_state.get("caps_by_terminal")
caps_manual = st.session_state.get("caps_manual")
carousels_mode = st.session_state.get("carousels_mode")

st.markdown("### Readjustement")
apply_readjustment = st.checkbox(
    "Appliquer les regles de readjustement",
    value=True,
    key="apply_readjustment",
)

rule_multi = False
rule_narrow_wide = False
rule_extras = False
max_carousels_narrow = 1
max_carousels_wide = 1
rule_order = []

if apply_readjustment:
    rule_multi = st.checkbox("Regle 1 - Multi-carousels", value=True, key="rule_multi")
    max_cols = st.columns(2)
    with max_cols[0]:
        max_carousels_narrow = st.number_input(
            "MAX_CAROUSELS_PER_FLIGHT_NARROW",
            min_value=1,
            value=int(st.session_state.get("max_carousels_narrow", 3)),
            step=1,
            key="max_carousels_narrow",
            disabled=not rule_multi,
        )
    with max_cols[1]:
        max_carousels_wide = st.number_input(
            "MAX_CAROUSELS_PER_FLIGHT_WIDE",
            min_value=1,
            value=int(st.session_state.get("max_carousels_wide", 2)),
            step=1,
            key="max_carousels_wide",
            disabled=not rule_multi,
        )

    rule_narrow_wide = st.checkbox("Regle 2 - Narrow -> Wide", value=False, key="rule_narrow_wide")
    rule_extras = st.checkbox("Regle 3 - Extras", value=True, key="rule_extras")

    enabled_rules = []
    if rule_multi:
        enabled_rules.append("multi")
    if rule_narrow_wide:
        enabled_rules.append("narrow_wide")
    if rule_extras:
        enabled_rules.append("extras")

    if enabled_rules:
        label_map = {
            "multi": "Regle 1 - Multi-carousels",
            "narrow_wide": "Regle 2 - Narrow -> Wide",
            "extras": "Regle 3 - Extras",
        }
        id_by_label = {v: k for k, v in label_map.items()}
        default_order = [r for r in st.session_state.get("rule_order", []) if r in enabled_rules]
        for r in ["multi", "narrow_wide", "extras"]:
            if r in enabled_rules and r not in default_order:
                default_order.append(r)

        st.markdown("**Ordre de priorite**")
        remaining = enabled_rules.copy()
        order = []

        opt1 = [label_map[r] for r in remaining]
        default1 = label_map[default_order[0]] if default_order else opt1[0]
        sel1 = st.selectbox("Priorite 1", options=opt1, index=opt1.index(default1), key="rule_order_1")
        sel1_id = id_by_label[sel1]
        order.append(sel1_id)
        remaining.remove(sel1_id)

        if remaining:
            opt2 = [label_map[r] for r in remaining]
            default2 = label_map[default_order[1]] if len(default_order) > 1 and default_order[1] in remaining else opt2[0]
            sel2 = st.selectbox("Priorite 2", options=opt2, index=opt2.index(default2), key="rule_order_2")
            sel2_id = id_by_label[sel2]
            order.append(sel2_id)
            remaining.remove(sel2_id)

        if remaining:
            opt3 = [label_map[r] for r in remaining]
            default3 = label_map[default_order[2]] if len(default_order) > 2 and default_order[2] in remaining else opt3[0]
            sel3 = st.selectbox("Priorite 3", options=opt3, index=opt3.index(default3), key="rule_order_3")
            sel3_id = id_by_label[sel3]
            order.append(sel3_id)
            remaining.remove(sel3_id)

        rule_order = order

st.markdown("**Couleurs planning (regles / exceptions)**")
color_cols = st.columns(4)
with color_cols[0]:
    st.color_picker(
        "Couleur Wide",
        value=st.session_state.get("wide_color", "#D32F2F"),
        key="wide_color",
    )
with color_cols[1]:
    st.color_picker(
        "Couleur Narrow",
        value=st.session_state.get("narrow_color", "#FFEBEE"),
        key="narrow_color",
    )
with color_cols[2]:
    st.color_picker(
        "Couleur Split",
        value=st.session_state.get("split_color", "#FFC107"),
        key="split_color",
    )
with color_cols[3]:
    st.color_picker(
        "Couleur Narrow -> Wide",
        value=st.session_state.get("narrow_wide_color", "#00B894"),
        key="narrow_wide_color",
    )
st.caption("Les couleurs Split / Narrow->Wide ont priorite sur les autres modes.")

st.session_state["rule_order"] = rule_order

extra_terminals, extra_defaults = _build_extra_terms_and_defaults(
    df_ready,
    carousels_mode,
    caps_by_terminal,
    caps_manual,
)

extra_caps_by_terminal = {}
extras_enabled = bool(apply_readjustment and rule_extras)
if not extra_terminals:
    st.info("Aucun terminal configure pour dimensionnement extra.")
elif extra_terminals == ["ALL"]:
    wide_def, nar_def = extra_defaults.get("ALL", (8, 4))
    wide_val = st.number_input(
        "Extra Wide capacity",
        min_value=0,
        value=int(wide_def),
        step=1,
        key="extra_wide_ALL",
        disabled=not extras_enabled,
    )
    nar_val = st.number_input(
        "Extra Narrow capacity",
        min_value=0,
        value=int(nar_def),
        step=1,
        key="extra_narrow_ALL",
        disabled=not extras_enabled,
    )
    extra_caps_by_terminal["ALL"] = CarouselCapacity(int(wide_val), int(nar_val))
else:
    st.caption("Capacite standard des extra make-up par terminal.")
    for term in extra_terminals:
        wide_def, nar_def = extra_defaults.get(term, (8, 4))
        cols = st.columns(2)
        with cols[0]:
            wide_val = st.number_input(
                f"{term} - Wide capacity",
                min_value=0,
                value=int(wide_def),
                step=1,
                key=f"extra_wide_{term}",
                disabled=not extras_enabled,
            )
        with cols[1]:
            nar_val = st.number_input(
                f"{term} - Narrow capacity",
                min_value=0,
                value=int(nar_def),
                step=1,
                key=f"extra_narrow_{term}",
                disabled=not extras_enabled,
            )
        extra_caps_by_terminal[term] = CarouselCapacity(int(wide_val), int(nar_val))


st.divider()
st.subheader("Etape 7 - Run + outputs")

color_mode_ui = st.session_state.get("color_mode_ui", "Par categorie")
if color_mode_ui == "Par categorie":
    color_mode = "category"
elif color_mode_ui == "Par terminal":
    color_mode = "terminal"
else:
    color_mode = "flight"

warnings_rows = []
warnings_rows.extend(mapping_warnings)
warnings_rows.extend(makeup_warnings)
warnings_rows.extend(car_warnings)

if color_mode == "terminal" and "Terminal" not in df_ready.columns:
    warnings_rows.append({
        "Type": "Mode couleur",
        "Message": "Mode terminal demande mais colonne Terminal absente. Fallback par vol.",
        "Count": 1,
    })
    color_mode = "flight"


if st.button("Run allocation", key="run_allocation"):
    try:
        required = ["DepartureTime", "FlightNumber", "Category", "Positions", "MakeupOpening", "MakeupClosing"]
        missing = [c for c in required if c not in df_ready.columns]
        if missing:
            st.error(f"Colonnes manquantes : {missing}")
            st.stop()

        start_time = pd.to_datetime(df_ready["MakeupOpening"]).min()
        end_time = pd.to_datetime(df_ready["DepartureTime"]).max()

        carousels_mode = st.session_state.get("carousels_mode")
        if carousels_mode == "file":
            if "Terminal" not in df_ready.columns:
                st.error("Mode carrousels par terminal mais colonne Terminal absente.")
                st.stop()
            caps_by_terminal = st.session_state.get("caps_by_terminal")
            if not caps_by_terminal:
                st.error("Configuration carrousels manquante (mode fichier).")
                st.stop()
            flights_out_list = []
            timelines = []
            for term, df_term in df_ready.groupby("Terminal"):
                if term not in caps_by_terminal:
                    tmp = df_term.copy()
                    tmp["AssignedCarousel"] = "UNASSIGNED"
                    tmp["UnassignedReason"] = "TERMINAL_NOT_CONFIGURED"
                    flights_out_list.append(tmp)
                    continue

                flights_out_term, timeline_term = allocate_round_robin(
                    flights=df_term,
                    carousel_caps=caps_by_terminal[term],
                    time_step_minutes=int(current_time_step),
                    start_time=pd.Timestamp(start_time),
                    end_time=pd.Timestamp(end_time),
                )
                timeline_term = timeline_term.rename(columns={c: f"{term}-{c}" for c in timeline_term.columns})
                flights_out_list.append(flights_out_term)
                timelines.append(timeline_term)

            flights_out = pd.concat(flights_out_list, ignore_index=True)
            if timelines:
                timeline_df = pd.concat(timelines, axis=1).sort_index(axis=1)
            else:
                timeline_df = pd.DataFrame(index=pd.date_range(start=start_time, end=end_time, freq=f"{int(current_time_step)}min"))
        else:
            caps_manual = st.session_state.get("caps_manual")
            if not caps_manual:
                st.error("Configuration carrousels manquante (mode manuel).")
                st.stop()
            flights_out, timeline_df = allocate_round_robin(
                flights=df_ready,
                carousel_caps=caps_manual,
                time_step_minutes=int(current_time_step),
                start_time=pd.Timestamp(start_time),
                end_time=pd.Timestamp(end_time),
            )

        apply_readjustment = bool(st.session_state.get("apply_readjustment", True))
        max_carousels_narrow = int(st.session_state.get("max_carousels_narrow", 3))
        max_carousels_wide = int(st.session_state.get("max_carousels_wide", 2))
        rule_multi = bool(st.session_state.get("rule_multi", False))
        rule_narrow_wide = bool(st.session_state.get("rule_narrow_wide", False))
        rule_extras = bool(st.session_state.get("rule_extras", False))
        rule_order = st.session_state.get("rule_order", [])

        enabled_rules = []
        if apply_readjustment:
            if rule_multi:
                enabled_rules.append("multi")
            if rule_narrow_wide:
                enabled_rules.append("narrow_wide")
            if rule_extras:
                enabled_rules.append("extras")
            rule_order = [r for r in rule_order if r in enabled_rules]
            for r in ["multi", "narrow_wide", "extras"]:
                if r in enabled_rules and r not in rule_order:
                    rule_order.append(r)
        else:
            rule_order = []

        flights_readjusted_list = []
        timelines_readjusted = []
        extra_columns = []
        extra_summary_rows = []
        extra_warnings = []
        processed_terms = set()

        if not apply_readjustment or not rule_order:
            flights_readjusted = flights_out.copy()
            flights_readjusted["OriginalCategory"] = flights_readjusted["Category"].astype(str).str.strip()
            flights_readjusted["FinalCategory"] = flights_readjusted["OriginalCategory"]
            flights_readjusted["CategoryChanged"] = "NO"
            flights_readjusted["Category"] = flights_readjusted["FinalCategory"]
            flights_readjusted["AssignedCarousels"] = (
                flights_readjusted["AssignedCarousel"].fillna("UNASSIGNED").astype(str)
            )
            flights_readjusted["SplitCount"] = flights_readjusted["AssignedCarousels"].apply(
                lambda v: 0 if str(v).upper() == "UNASSIGNED" else 1
            )
            timeline_readjusted = timeline_df.copy()
        elif carousels_mode == "file":
            for term, df_term in flights_out.groupby("Terminal"):
                processed_terms.add(term)
                caps_term = caps_by_terminal.get(term)
                if caps_term is None:
                    tmp = df_term.copy()
                    tmp["OriginalCategory"] = tmp["Category"].astype(str).str.strip()
                    tmp["FinalCategory"] = tmp["OriginalCategory"]
                    tmp["CategoryChanged"] = "NO"
                    tmp["Category"] = tmp["FinalCategory"]
                    tmp["AssignedCarousels"] = "UNASSIGNED"
                    tmp["SplitCount"] = 0
                    tmp["AssignedCarousel"] = "UNASSIGNED"
                    flights_readjusted_list.append(tmp)
                    extra_summary_rows.append({
                        "Terminal": term,
                        "Nb extra makeups": 0,
                        "Liste": "",
                    })
                    continue

                extra_cap = None
                if rule_extras and extra_caps_by_terminal:
                    extra_cap = extra_caps_by_terminal.get(term)
                readj_term, timeline_term, extras_used, impossible_df = allocate_round_robin_with_rules(
                    flights=df_term,
                    carousel_caps=caps_term,
                    time_step_minutes=int(current_time_step),
                    start_time=pd.Timestamp(start_time),
                    end_time=pd.Timestamp(end_time),
                    max_carousels_per_flight_narrow=max_carousels_narrow,
                    max_carousels_per_flight_wide=max_carousels_wide,
                    rule_order=rule_order,
                    extra_capacity=extra_cap,
                )

                if timeline_term is not None and len(timeline_term.columns) > 0:
                    timeline_term = timeline_term.reindex(timeline_df.index, fill_value="")
                    timeline_term = timeline_term.rename(columns={
                        c: f"{term}-{c}" for c in timeline_term.columns
                    })
                    timelines_readjusted.append(timeline_term)

                flights_readjusted_list.append(readj_term)
                cols = [f"{term}-{c}" for c in extras_used]
                extra_columns.extend(cols)
                extra_summary_rows.append({
                    "Terminal": term,
                    "Nb extra makeups": int(len(extras_used)),
                    "Liste": ", ".join(cols),
                })

                if rule_extras and extra_cap is None:
                    remaining = readj_term[readj_term["AssignedCarousel"] == "UNASSIGNED"]
                    if len(remaining) > 0:
                        extra_warnings.append({
                            "Type": "Extra sizing",
                            "Message": f"Terminal sans capacite extra configuree: {term}",
                            "Count": int(len(remaining)),
                        })

                if rule_extras and impossible_df is not None and len(impossible_df) > 0:
                    extra_warnings.append({
                        "Type": "Extra sizing",
                        "Message": f"Vols impossibles pour extra ({term})",
                        "Count": int(len(impossible_df)),
                    })

            flights_readjusted = (
                pd.concat(flights_readjusted_list, ignore_index=True)
                if flights_readjusted_list
                else flights_out.copy()
            )
            if timelines_readjusted:
                timeline_readjusted = pd.concat(timelines_readjusted, axis=1).sort_index(axis=1)
            else:
                timeline_readjusted = pd.DataFrame(index=timeline_df.index)
        else:
            extra_cap = None
            if rule_extras and extra_caps_by_terminal:
                extra_cap = extra_caps_by_terminal.get("ALL")
            flights_readjusted, timeline_readjusted, extras_used, impossible_df = allocate_round_robin_with_rules(
                flights=flights_out,
                carousel_caps=caps_manual,
                time_step_minutes=int(current_time_step),
                start_time=pd.Timestamp(start_time),
                end_time=pd.Timestamp(end_time),
                max_carousels_per_flight_narrow=max_carousels_narrow,
                max_carousels_per_flight_wide=max_carousels_wide,
                rule_order=rule_order,
                extra_capacity=extra_cap,
            )
            timeline_readjusted = timeline_readjusted.reindex(timeline_df.index, fill_value="")
            extra_columns = extras_used
            extra_summary_rows.append({
                "Terminal": "ALL",
                "Nb extra makeups": int(len(extras_used)),
                "Liste": ", ".join(extras_used),
            })

            if rule_extras and extra_cap is None:
                remaining = flights_readjusted[flights_readjusted["AssignedCarousel"] == "UNASSIGNED"]
                if len(remaining) > 0:
                    extra_warnings.append({
                        "Type": "Extra sizing",
                        "Message": "Terminal sans capacite extra configuree: ALL",
                        "Count": int(len(remaining)),
                    })

            if rule_extras and impossible_df is not None and len(impossible_df) > 0:
                extra_warnings.append({
                    "Type": "Extra sizing",
                    "Message": "Vols impossibles pour extra (ALL)",
                    "Count": int(len(impossible_df)),
                })
            processed_terms.add("ALL")

        if extra_caps_by_terminal:
            for term in extra_caps_by_terminal.keys():
                if term not in processed_terms:
                    extra_summary_rows.append({
                        "Terminal": term,
                        "Nb extra makeups": 0,
                        "Liste": "",
                    })

        if extra_summary_rows:
            extra_summary_df = pd.DataFrame(extra_summary_rows)
            extra_makeups_df = extra_summary_df[["Terminal", "Nb extra makeups"]].rename(
                columns={"Nb extra makeups": "ExtraMakeupsNeeded"}
            )
        else:
            extra_summary_df = pd.DataFrame(columns=["Terminal", "Nb extra makeups", "Liste"])
            extra_makeups_df = pd.DataFrame(columns=["Terminal", "ExtraMakeupsNeeded"])

        warnings_rows.extend(extra_warnings)

        unassigned_df = flights_readjusted[flights_readjusted["AssignedCarousel"] == "UNASSIGNED"].copy()
        warnings_rows.append({
            "Type": "UNASSIGNED",
            "Message": "Vols non assignes",
            "Count": int(len(unassigned_df)),
        })

        keep_extra_cols = st.session_state.get("keep_extra_cols", [])

        st.session_state["results"] = {
            "flights_out": flights_out,
            "flights_readjusted": flights_readjusted,
            "timeline_df": timeline_df,
            "timeline_readjusted": timeline_readjusted,
            "warnings_rows": warnings_rows,
            "unassigned_df": unassigned_df,
            "color_mode": color_mode,
            "wide_color": wide_color,
            "narrow_color": narrow_color,
            "split_color": split_color,
            "narrow_wide_color": narrow_wide_color,
            "extra_columns": extra_columns,
            "extra_summary_df": extra_summary_df,
            "extra_makeups_df": extra_makeups_df,
            "keep_extra_cols": keep_extra_cols,
        }
        st.session_state["run_done"] = True
        st.rerun()
    except Exception as exc:
        if st.session_state.get("show_debug_errors", False):
            st.exception(exc)
        else:
            st.error("Erreur pendant l'allocation. Verifiez les donnees.")


if st.session_state.get("run_done") and st.session_state.get("results"):
    results = st.session_state["results"]
    flights_out = results["flights_out"]
    flights_readjusted = results.get("flights_readjusted", flights_out)
    timeline_df = results["timeline_df"]
    timeline_readjusted = results.get("timeline_readjusted", timeline_df)
    warnings_rows = results["warnings_rows"]
    unassigned_df = results["unassigned_df"]
    extra_columns = results.get("extra_columns", [])
    extra_summary_df = results.get("extra_summary_df")
    extra_makeups_df = results.get("extra_makeups_df")
    keep_extra_cols = results.get("keep_extra_cols", [])
    split_color = results.get("split_color", "#FFC107")
    narrow_wide_color = results.get("narrow_wide_color", "#00B894")

    display_df = flights_readjusted.drop(columns=["AssignmentSegments"], errors="ignore").copy()
    legend = pd.Series([""] * len(display_df), index=display_df.index, dtype="object")
    changed_mask = display_df.get("CategoryChanged", pd.Series([""] * len(display_df))).astype(str).str.upper() == "YES"
    legend[changed_mask] = "Narrow->Wide"
    split_mask = pd.Series([False] * len(display_df), index=display_df.index)
    if "SplitCount" in display_df.columns:
        split_mask |= display_df["SplitCount"].fillna(0).astype(int) > 1
    if "AssignedCarousels" in display_df.columns:
        split_mask |= display_df["AssignedCarousels"].astype(str).str.contains(r"\+")
    legend[(~changed_mask) & split_mask] = "Split"
    cat_col = "FinalCategory" if "FinalCategory" in display_df.columns else "Category"
    cat_series = display_df.get(cat_col, pd.Series([""] * len(display_df))).astype(str).str.strip().str.lower()
    cat_label = cat_series.map({"wide": "Wide", "w": "Wide", "narrow": "Narrow", "n": "Narrow"}).fillna("Other")
    legend_mask = legend == ""
    legend[legend_mask] = cat_label[legend_mask]
    display_df["LegendCategory"] = legend
    total = int(len(display_df))
    unassigned_count = int(len(unassigned_df))
    assigned_pct = 0 if total == 0 else int(round(100 * (total - unassigned_count) / total))

    kpi_cols = st.columns(3)
    kpi_cols[0].metric("Total vols", total)
    kpi_cols[1].metric("% assignes", f"{assigned_pct}%")
    kpi_cols[2].metric("Nb UNASSIGNED", unassigned_count)

    split_count = int((display_df.get("SplitCount", 0).fillna(0).astype(int) > 1).sum()) if total else 0
    split_pct = 0 if total == 0 else int(round(100 * split_count / total))
    changed_mask = display_df.get("CategoryChanged", pd.Series([""] * total)).astype(str).str.upper() == "YES"
    narrow_wide_count = int(changed_mask.sum()) if total else 0
    narrow_wide_pct = 0 if total == 0 else int(round(100 * narrow_wide_count / total))
    kpi_cols2 = st.columns(4)
    kpi_cols2[0].metric("Nb vols split", split_count)
    kpi_cols2[1].metric("% split", f"{split_pct}%")
    kpi_cols2[2].metric("Nb Narrow->Wide", narrow_wide_count)
    kpi_cols2[3].metric("% Narrow->Wide", f"{narrow_wide_pct}%")

    with st.expander("Filtres resultats", expanded=True):
        assigned_opts = sorted(display_df["AssignedCarousel"].dropna().unique().tolist())
        assigned_sel = st.multiselect("AssignedCarousel", assigned_opts, default=assigned_opts)

        if "Terminal" in display_df.columns:
            term_opts = sorted(display_df["Terminal"].dropna().unique().tolist())
            term_sel = st.multiselect("Terminal", term_opts, default=term_opts)
        else:
            term_sel = None

        cat_opts = sorted(display_df["Category"].dropna().unique().tolist())
        cat_sel = st.multiselect("Category", cat_opts, default=cat_opts)

        legend_opts = sorted(display_df["LegendCategory"].dropna().unique().tolist())
        legend_sel = st.multiselect("Type (legend)", legend_opts, default=legend_opts)

    filtered = display_df.copy()
    if assigned_sel:
        filtered = filtered[filtered["AssignedCarousel"].isin(assigned_sel)]
    if term_sel is not None:
        if term_sel:
            filtered = filtered[filtered["Terminal"].isin(term_sel)]
        else:
            filtered = filtered.iloc[0:0]
    if cat_sel:
        filtered = filtered[filtered["Category"].isin(cat_sel)]
    else:
        filtered = filtered.iloc[0:0]
    if legend_sel:
        filtered = filtered[filtered["LegendCategory"].isin(legend_sel)]
    else:
        filtered = filtered.iloc[0:0]

    st.dataframe(filtered.sort_values("DepartureTime"), use_container_width=True)

    if extra_summary_df is not None and len(extra_summary_df) > 0:
        st.subheader("Summary extra makeups")
        st.dataframe(extra_summary_df, use_container_width=True)

    import tempfile, os
    tmpdir = tempfile.mkdtemp()
    txt_path = os.path.join(tmpdir, "summary.txt")
    csv_path = os.path.join(tmpdir, "summary.csv")
    txt_readjusted_path = os.path.join(tmpdir, "summary_readjusted.txt")
    csv_readjusted_path = os.path.join(tmpdir, "summary_readjusted.csv")
    xlsx_path = os.path.join(tmpdir, "timeline.xlsx")
    readjusted_path = os.path.join(tmpdir, "timeline_readjusted.xlsx")
    heatmap_occ_path = os.path.join(tmpdir, "heatmap_positions_occupied.xlsx")
    heatmap_free_path = os.path.join(tmpdir, "heatmap_positions_free.xlsx")
    extra_csv_path = os.path.join(tmpdir, "extra_makeups_needed.csv")

    write_summary_txt(txt_path, flights_out, extra_cols=keep_extra_cols)
    write_summary_csv(csv_path, flights_out)
    export_readjusted = flights_readjusted.drop(columns=["AssignmentSegments"], errors="ignore")
    export_readjusted.sort_values("DepartureTime").to_csv(
        csv_readjusted_path,
        index=False,
        encoding="utf-8",
    )
    export_readjusted.sort_values("DepartureTime").to_csv(
        txt_readjusted_path,
        index=False,
        encoding="utf-8",
        sep="|",
    )
    write_timeline_excel(
        xlsx_path,
        timeline_df,
        flights_out,
        color_mode=results["color_mode"],
        wide_color=results["wide_color"],
        narrow_color=results["narrow_color"],
        split_color=split_color,
        narrow_wide_color=narrow_wide_color,
    )
    write_timeline_excel(
        readjusted_path,
        timeline_readjusted,
        flights_readjusted,
        color_mode=results["color_mode"],
        wide_color=results["wide_color"],
        narrow_color=results["narrow_color"],
        split_color=split_color,
        narrow_wide_color=narrow_wide_color,
        extra_columns=extra_columns,
        extra_summary=extra_summary_df,
    )

    heatmap_occ_sheets, heatmap_free_sheets = _build_heatmap_sheets(
        flights_readjusted,
        timeline_readjusted.index,
        list(timeline_readjusted.columns),
        carousels_mode=st.session_state.get("carousels_mode"),
        caps_manual=st.session_state.get("caps_manual"),
        caps_by_terminal=st.session_state.get("caps_by_terminal"),
        extra_caps_by_terminal=extra_caps_by_terminal,
    )
    write_heatmap_excel(heatmap_occ_path, heatmap_occ_sheets, mode="occupied")
    write_heatmap_excel(heatmap_free_path, heatmap_free_sheets, mode="free")

    if extra_makeups_df is not None:
        extra_makeups_df.to_csv(extra_csv_path, index=False, encoding="utf-8")
    else:
        pd.DataFrame(columns=["Terminal", "ExtraMakeupsNeeded"]).to_csv(extra_csv_path, index=False, encoding="utf-8")

    st.subheader("Downloads")
    st.markdown("**Resultats principaux**")
    main_cols = st.columns(3)
    main_cols[0].download_button(
        "summary.csv",
        data=open(csv_path, "rb"),
        file_name="summary.csv",
        key="dl_summary_csv",
    )
    main_cols[1].download_button(
        "summary.txt",
        data=open(txt_path, "rb"),
        file_name="summary.txt",
        key="dl_summary_txt",
    )
    main_cols[2].download_button(
        "extra_makeups_needed.csv",
        data=open(extra_csv_path, "rb"),
        file_name="extra_makeups_needed.csv",
        key="dl_extra_makeups_needed",
    )

    readj_cols = st.columns(2)
    readj_cols[0].download_button(
        "summary_readjusted.csv",
        data=open(csv_readjusted_path, "rb"),
        file_name="summary_readjusted.csv",
        key="dl_summary_readjusted_csv",
    )
    readj_cols[1].download_button(
        "summary_readjusted.txt",
        data=open(txt_readjusted_path, "rb"),
        file_name="summary_readjusted.txt",
        key="dl_summary_readjusted_txt",
    )

    st.markdown("**Planning**")
    plan_cols = st.columns(3)
    plan_cols[0].download_button(
        "timeline.xlsx",
        data=open(xlsx_path, "rb"),
        file_name="timeline.xlsx",
        key="dl_timeline",
    )
    plan_cols[1].download_button(
        "timeline_readjusted.xlsx",
        data=open(readjusted_path, "rb"),
        file_name="timeline_readjusted.xlsx",
        key="dl_timeline_readjusted",
    )

    st.markdown("**Heatmaps**")
    heat_cols = st.columns(2)
    heat_cols[0].download_button(
        "heatmap_positions_occupied.xlsx",
        data=open(heatmap_occ_path, "rb"),
        file_name="heatmap_positions_occupied.xlsx",
        key="dl_heatmap_occupied",
    )
    heat_cols[1].download_button(
        "heatmap_positions_free.xlsx",
        data=open(heatmap_free_path, "rb"),
        file_name="heatmap_positions_free.xlsx",
        key="dl_heatmap_free",
    )

    st.markdown("**Diagnostics**")
    diag_cols = st.columns(3)
    if len(unassigned_df) > 0:
        unassigned_csv = unassigned_df.to_csv(index=False, encoding="utf-8")
        diag_cols[0].download_button(
            "unassigned_reasons.csv",
            data=unassigned_csv,
            file_name="unassigned_reasons.csv",
            key="dl_unassigned_reasons",
        )
    else:
        diag_cols[0].download_button(
            "unassigned_reasons.csv",
            data="",
            file_name="unassigned_reasons.csv",
            key="dl_unassigned_reasons",
        )
    diag_cols[1].download_button(
        "warnings.csv",
        data=pd.DataFrame(warnings_rows).to_csv(index=False, encoding="utf-8") if warnings_rows else "",
        file_name="warnings.csv",
        key="dl_warnings_diag",
    )

    if show_warnings:
        st.subheader("Warnings")
        if warnings_rows:
            warnings_df = pd.DataFrame(warnings_rows)
            st.dataframe(warnings_df, use_container_width=True)
            warnings_csv = warnings_df.to_csv(index=False, encoding="utf-8")
            st.download_button(
                "warnings.csv",
                data=warnings_csv,
                file_name="warnings.csv",
                key="dl_warnings_panel",
            )
        else:
            st.success("Aucun warning.")
