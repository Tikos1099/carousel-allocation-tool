from __future__ import annotations

import streamlit as st

from app_results import render_results
from app_run_allocation import handle_run_allocation
from app_sidebar import render_sidebar
from app_steps_carousels import render_carousels_step
from app_steps_cat_term import render_cat_term_step
from app_steps_extras import render_extras_step
from app_steps_makeup import render_makeup_step
from app_steps_mapping import render_mapping_step
from app_steps_time_step import render_time_step_step
from app_steps_upload import render_upload_step


def render_allocation_page() -> None:
    df_raw = render_upload_step()

    col_mapping_preview = st.session_state.get("col_mapping")
    mapping_confirmed = bool(st.session_state.get("mapping_confirmed", False))
    df_mapped_preview = None
    has_terminal = False
    if df_raw is not None and mapping_confirmed and col_mapping_preview:
        df_mapped_preview = df_raw.rename(columns=col_mapping_preview).copy()
        has_terminal = "Terminal" in df_mapped_preview.columns

    sidebar_state = render_sidebar(has_terminal)

    if df_raw is None:
        st.stop()

    with st.expander("Preview fichier vols", expanded=False):
        st.dataframe(df_raw.head(20), use_container_width=True)

    df_mapped = render_mapping_step(df_raw)
    df_std, mapping_warnings = render_cat_term_step(df_mapped)
    df_ready, makeup_warnings = render_makeup_step(
        df_std,
        sidebar_state["makeup_mode"],
        sidebar_state["wide_x"],
        sidebar_state["wide_y"],
        sidebar_state["nar_x"],
        sidebar_state["nar_y"],
    )
    current_time_step = render_time_step_step(sidebar_state["time_step"])
    caps_by_terminal, caps_manual, carousels_mode, car_warnings = render_carousels_step(df_ready)
    extra_caps_by_terminal = render_extras_step(df_ready, carousels_mode, caps_by_terminal, caps_manual)

    handle_run_allocation(
        df_ready,
        current_time_step,
        mapping_warnings,
        makeup_warnings,
        car_warnings,
        extra_caps_by_terminal,
    )
    render_results(extra_caps_by_terminal, sidebar_state["show_warnings"])
