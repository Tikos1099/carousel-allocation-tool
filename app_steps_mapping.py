from __future__ import annotations

import pandas as pd
import streamlit as st

from app_mapping import _guess_col
from app_state import _reset_after_mapping


def render_mapping_step(df_raw: pd.DataFrame) -> pd.DataFrame:
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

    mapping_confirmed = bool(st.session_state.get("mapping_confirmed", False))
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

    return df_mapped
