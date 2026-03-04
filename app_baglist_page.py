from __future__ import annotations

import json
from typing import Any

import pandas as pd
import streamlit as st

from baglist_builder import build_baglist, read_table, render_baglist_excel, template_signature


TEMPLATE_COLUMNS = ["select", "output_column", "type", "source", "join_key", "field", "default", "format"]
TEMPLATE_TYPES = ["copy", "const", "lookup", "formula"]
TEMPLATE_SOURCES = ["bags", "allocation", "transfers"]


def _clear_baglist_state() -> None:
    for key in list(st.session_state.keys()):
        if key.startswith("baglist_"):
            st.session_state.pop(key, None)


def _clear_baglist_results() -> None:
    for key in [
        "baglist_output_df",
        "baglist_warnings_df",
        "baglist_summary",
        "baglist_output_excel",
        "baglist_warnings_csv",
        "baglist_run_sig",
    ]:
        st.session_state.pop(key, None)


def _load_file_cached(file, prefix: str) -> tuple[pd.DataFrame | None, tuple | None]:
    sig_key = f"baglist_{prefix}_sig"
    df_key = f"baglist_{prefix}_df"
    if file is None:
        st.session_state.pop(sig_key, None)
        st.session_state.pop(df_key, None)
        return None, None

    sig = (getattr(file, "name", ""), getattr(file, "size", None))
    if st.session_state.get(sig_key) != sig:
        try:
            df = read_table(file)
        except Exception as exc:
            st.error(f"Erreur lecture {prefix}: {exc}")
            return None, sig
        st.session_state[sig_key] = sig
        st.session_state[df_key] = df
    return st.session_state.get(df_key), st.session_state.get(sig_key)


def _ensure_template_state() -> list[dict[str, Any]]:
    if "baglist_template" not in st.session_state:
        st.session_state["baglist_template"] = []
    return st.session_state["baglist_template"]


def _default_row() -> dict[str, Any]:
    return {
        "select": False,
        "output_column": "",
        "type": "copy",
        "source": "bags",
        "join_key": "",
        "field": "",
        "default": "",
        "format": "",
    }


def _template_to_df(rows: list[dict[str, Any]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=TEMPLATE_COLUMNS)
    df = pd.DataFrame(rows)
    for col in TEMPLATE_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    if "select" not in df.columns:
        df["select"] = False
    df["select"] = df["select"].fillna(False).astype(bool)
    return df[TEMPLATE_COLUMNS]


def _normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    normalized = _default_row()
    for key in TEMPLATE_COLUMNS:
        if key in row:
            normalized[key] = row[key]
    normalized["type"] = str(normalized.get("type", "copy")).strip().lower() or "copy"
    normalized["source"] = str(normalized.get("source", "bags")).strip().lower() or "bags"
    normalized["output_column"] = str(normalized.get("output_column", "")).strip()
    normalized["join_key"] = str(normalized.get("join_key", "")).strip()
    return normalized


def _df_to_template(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df is None or df.empty:
        return []
    rows = df.to_dict("records")
    cleaned = []
    for row in rows:
        row.pop("select", None)
        cleaned.append(_normalize_row(row))
    return cleaned


def _move_selected(rows: list[dict[str, Any]], direction: str) -> list[dict[str, Any]]:
    if not rows:
        return rows
    items = list(rows)
    if direction == "up":
        for i in range(1, len(items)):
            if items[i].get("select") and not items[i - 1].get("select"):
                items[i - 1], items[i] = items[i], items[i - 1]
    elif direction == "down":
        for i in range(len(items) - 2, -1, -1):
            if items[i].get("select") and not items[i + 1].get("select"):
                items[i + 1], items[i] = items[i], items[i + 1]
    return items


def _template_rows_with_select(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df is None or df.empty:
        return []
    return df.to_dict("records")


def render_baglist_page() -> None:
    st.header("Baglist Builder")
    st.caption("Generez un baglist.xlsx a partir des bags avec enrichissements et formules.")

    with st.sidebar:
        st.header("Baglist")
        if st.button("Reset baglist"):
            _clear_baglist_state()
            st.rerun()
        duplicate_strategy = st.selectbox(
            "Doublons lookup",
            options=["first", "error"],
            index=0,
            help="first: conserve la premiere valeur. error: bloque si doublons.",
            key="baglist_dup_strategy",
        )

        with st.expander("Aide formules", expanded=False):
            st.markdown(
                """
- `to_datetime(day, time, base_date?)`
- `minutes(dt)` / `diff_minutes(dt1, dt2)`
- `concat(a, b, ...)`
- `if(cond, a, b)`
- `coalesce(a, b, ...)`
- `to_int(x)` / `to_str(x)`
                """
            )

    st.subheader("1) Fichiers d'entree")
    bags_file = st.file_uploader("Bags file (xlsx/csv)", type=["xlsx", "xls", "csv"], key="baglist_bags_file")
    allocation_file = st.file_uploader(
        "Allocation file (optionnel)", type=["xlsx", "xls", "csv"], key="baglist_alloc_file"
    )
    transfers_file = st.file_uploader(
        "Transfers file (optionnel)", type=["xlsx", "xls", "csv"], key="baglist_transfers_file"
    )

    bags_df, bags_sig = _load_file_cached(bags_file, "bags")
    allocation_df, alloc_sig = _load_file_cached(allocation_file, "allocation")
    transfers_df, transfers_sig = _load_file_cached(transfers_file, "transfers")

    template_rows = _ensure_template_state()
    template_sig = template_signature(template_rows)
    current_sig = (bags_sig, alloc_sig, transfers_sig, template_sig, duplicate_strategy)
    if st.session_state.get("baglist_run_sig") and st.session_state["baglist_run_sig"] != current_sig:
        _clear_baglist_results()

    if bags_df is None:
        st.info("Chargez un fichier bags pour commencer.")
        return

    st.subheader("2) Preview & colonnes")
    st.dataframe(bags_df.head(20), use_container_width=True)
    st.caption(f"{len(bags_df)} lignes, {len(bags_df.columns)} colonnes detectees.")

    with st.expander("Auto-detection colonnes", expanded=False):
        cols = list(bags_df.columns)
        selected_cols = st.multiselect("Colonnes a copier", options=cols, key="baglist_cols_select")
        col_buttons = st.columns(2)
        if col_buttons[0].button("Ajouter selection"):
            rows_with_select = _template_rows_with_select(_template_to_df(template_rows))
            existing = {row.get("output_column") for row in rows_with_select}
            for col in selected_cols:
                if col in existing:
                    continue
                rows_with_select.append(
                    {
                        "select": False,
                        "output_column": col,
                        "type": "copy",
                        "source": "bags",
                        "join_key": "",
                        "field": col,
                        "default": "",
                        "format": "",
                    }
                )
            st.session_state["baglist_template"] = _df_to_template(pd.DataFrame(rows_with_select))
            st.rerun()
        if col_buttons[1].button("Remplacer par toutes les colonnes"):
            rows_with_select = [
                {
                    "select": False,
                    "output_column": col,
                    "type": "copy",
                    "source": "bags",
                    "join_key": "",
                    "field": col,
                    "default": "",
                    "format": "",
                }
                for col in cols
            ]
            st.session_state["baglist_template"] = _df_to_template(pd.DataFrame(rows_with_select))
            st.rerun()

    st.subheader("3) Template Builder")
    template_df = _template_to_df(template_rows)
    edited_df = st.data_editor(
        template_df,
        key="baglist_template_editor",
        hide_index=True,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "select": st.column_config.CheckboxColumn("Select", width="small"),
            "type": st.column_config.SelectboxColumn("Type", options=TEMPLATE_TYPES, width="small"),
            "source": st.column_config.SelectboxColumn("Source", options=TEMPLATE_SOURCES, width="small"),
        },
    )
    st.session_state["baglist_template"] = _df_to_template(edited_df)

    action_cols = st.columns(5)
    if action_cols[0].button("Ajouter ligne"):
        rows = _template_rows_with_select(edited_df)
        rows.append(_default_row())
        st.session_state["baglist_template"] = _df_to_template(pd.DataFrame(rows))
        st.rerun()
    if action_cols[1].button("Dupliquer selection"):
        rows = _template_rows_with_select(edited_df)
        selected = [row for row in rows if row.get("select")]
        for row in selected:
            new_row = dict(row)
            new_row["select"] = False
            rows.append(new_row)
        st.session_state["baglist_template"] = _df_to_template(pd.DataFrame(rows))
        st.rerun()
    if action_cols[2].button("Supprimer selection"):
        rows = _template_rows_with_select(edited_df)
        rows = [row for row in rows if not row.get("select")]
        st.session_state["baglist_template"] = _df_to_template(pd.DataFrame(rows))
        st.rerun()
    if action_cols[3].button("Monter"):
        rows = _move_selected(_template_rows_with_select(edited_df), "up")
        st.session_state["baglist_template"] = _df_to_template(pd.DataFrame(rows))
        st.rerun()
    if action_cols[4].button("Descendre"):
        rows = _move_selected(_template_rows_with_select(edited_df), "down")
        st.session_state["baglist_template"] = _df_to_template(pd.DataFrame(rows))
        st.rerun()

    with st.expander("Template JSON", expanded=False):
        template_rows = _ensure_template_state()
        if template_rows:
            payload = json.dumps(template_rows, ensure_ascii=False, indent=2)
            st.download_button(
                "Exporter profil JSON",
                data=payload,
                file_name="baglist_template.json",
                mime="application/json",
            )
        uploaded_template = st.file_uploader("Importer profil JSON", type=["json"], key="baglist_template_upload")
        if uploaded_template is not None:
            sig = (uploaded_template.name, uploaded_template.size)
            if st.session_state.get("baglist_template_upload_sig") != sig:
                st.session_state["baglist_template_upload_sig"] = sig
                try:
                    raw = uploaded_template.getvalue().decode("utf-8")
                    parsed = json.loads(raw)
                    if not isinstance(parsed, list):
                        raise ValueError("Le JSON doit etre une liste de colonnes.")
                    st.session_state["baglist_template"] = [_normalize_row(r) for r in parsed]
                    st.success("Template charge.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Import template impossible: {exc}")

    st.subheader("4) Generation")
    run_cols = st.columns(2)
    if run_cols[0].button("Run generation"):
        template_rows = _ensure_template_state()
        if not template_rows:
            st.error("Template vide.")
        else:
            try:
                output_df, warnings_df, summary, format_map = build_baglist(
                    bags_df=bags_df,
                    allocation_df=allocation_df,
                    transfers_df=transfers_df,
                    template_rows=template_rows,
                    duplicate_strategy=duplicate_strategy,
                )
                st.session_state["baglist_output_df"] = output_df
                st.session_state["baglist_warnings_df"] = warnings_df
                st.session_state["baglist_summary"] = summary
                st.session_state["baglist_output_excel"] = render_baglist_excel(output_df, format_map)
                if warnings_df is not None and not warnings_df.empty:
                    st.session_state["baglist_warnings_csv"] = warnings_df.to_csv(index=False).encode("utf-8")
                else:
                    st.session_state["baglist_warnings_csv"] = None
                st.session_state["baglist_run_sig"] = current_sig
                st.success("Baglist genere.")
            except Exception as exc:
                st.error(f"Generation echouee: {exc}")

    if "baglist_output_df" in st.session_state:
        output_df = st.session_state.get("baglist_output_df")
        warnings_df = st.session_state.get("baglist_warnings_df")
        summary = st.session_state.get("baglist_summary", {})

        st.subheader("5) Resultats")
        metrics_cols = st.columns(5)
        metrics_cols[0].metric("Rows in", summary.get("rows_in", 0))
        metrics_cols[1].metric("Rows out", summary.get("rows_out", 0))
        metrics_cols[2].metric("Warnings", summary.get("warnings", 0))
        metrics_cols[3].metric("Missing keys", summary.get("missing_keys", 0))
        metrics_cols[4].metric("Duplicates", summary.get("duplicate_keys", 0))

        st.dataframe(output_df.head(50), use_container_width=True)

        st.download_button(
            "Download baglist.xlsx",
            data=st.session_state.get("baglist_output_excel"),
            file_name="baglist.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        if st.session_state.get("baglist_warnings_csv"):
            st.download_button(
                "Download baglist_warnings.csv",
                data=st.session_state.get("baglist_warnings_csv"),
                file_name="baglist_warnings.csv",
                mime="text/csv",
            )
            with st.expander("Warnings preview", expanded=False):
                st.dataframe(warnings_df.head(50), use_container_width=True)
