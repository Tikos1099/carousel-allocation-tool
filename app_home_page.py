from __future__ import annotations

import streamlit as st


def _set_page(page: str) -> None:
    st.session_state["page_select"] = page


def render_home_page() -> None:
    st.header("Home")
    st.caption("Choisissez votre workflow.")

    cols = st.columns(2)
    with cols[0]:
        st.subheader("Carousel Allocation")
        st.write("Allocation des vols vers carrousels/make-ups + exports.")
        st.button("Ouvrir Allocation", on_click=_set_page, args=("Allocation",), use_container_width=True)

    with cols[1]:
        st.subheader("Baglist Builder")
        st.write("Generation de baglist.xlsx a partir des bags avec enrichissements.")
        st.button("Ouvrir Baglist", on_click=_set_page, args=("Baglist",), use_container_width=True)
