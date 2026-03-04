from __future__ import annotations

import json
import re
import uuid
from datetime import date

import altair as alt
import pandas as pd
import streamlit as st

from app_branding import BRAND_RED
from app_expr import _apply_calculated_fields, _eval_expression
from app_filters import (
    _aggregate_grouped,
    _aggregate_series,
    _altair_field_type,
    _apply_filters,
    _render_filters,
)


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


def _render_analytics_page() -> None:
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
