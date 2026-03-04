from __future__ import annotations

import streamlit as st


def _clear_prefix(prefixes) -> None:
    for key in list(st.session_state.keys()):
        if any(key.startswith(p) for p in prefixes):
            st.session_state.pop(key, None)


def _reset_after_upload() -> None:
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


def _reset_after_mapping() -> None:
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


def _reset_after_cat_term() -> None:
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


def _reset_after_makeup() -> None:
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


def _reset_after_time_step() -> None:
    keys = [
        "carousels_confirmed",
        "run_done",
        "results",
        "car_file_sig",
    ]
    for k in keys:
        st.session_state.pop(k, None)


def _reset_after_carousels() -> None:
    keys = [
        "run_done",
        "results",
    ]
    for k in keys:
        st.session_state.pop(k, None)
