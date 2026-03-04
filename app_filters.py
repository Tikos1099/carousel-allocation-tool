from __future__ import annotations

from datetime import date, datetime
import pandas as pd
import streamlit as st


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
    if agg == "sum":
        return series.sum()
    if agg == "mean":
        return series.mean()
    if agg == "min":
        return series.min()
    if agg == "max":
        return series.max()
    return series.sum()


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
