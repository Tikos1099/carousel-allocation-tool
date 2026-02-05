from __future__ import annotations

import pandas as pd
import streamlit as st

from app_mapping import _apply_cat_term_mapping, suggest_cat, suggest_term
from app_state import _reset_after_cat_term


def render_cat_term_step(df_mapped: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    st.divider()
    st.subheader("Etape 3 - Mapping categories & terminals")

    cat_term_confirmed = bool(st.session_state.get("cat_term_confirmed", False))
    raw_cats = sorted([str(x).strip() for x in df_mapped["Category"].dropna().unique().tolist()])

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

    return df_std, mapping_warnings
