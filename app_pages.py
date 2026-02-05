from __future__ import annotations

import streamlit as st

from app_allocation_page import render_allocation_page
from app_analytics import _render_analytics_page


def run_app() -> None:
    page = st.sidebar.radio(
        "Page",
        options=["Allocation", "Analytics"],
        index=0,
        key="page_select",
    )
    if page == "Analytics":
        _render_analytics_page()
        st.stop()

    render_allocation_page()
