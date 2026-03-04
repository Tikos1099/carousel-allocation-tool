from __future__ import annotations

import streamlit as st


def render_sidebar(has_terminal: bool) -> dict:
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

    return {
        "makeup_mode": makeup_mode,
        "wide_x": wide_x,
        "wide_y": wide_y,
        "nar_x": nar_x,
        "nar_y": nar_y,
        "time_step": time_step,
        "color_mode_ui": color_mode_ui,
        "wide_color": wide_color,
        "narrow_color": narrow_color,
        "split_color": split_color,
        "narrow_wide_color": narrow_wide_color,
        "show_warnings": show_warnings,
        "show_debug": show_debug,
    }
