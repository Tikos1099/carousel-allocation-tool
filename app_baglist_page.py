from __future__ import annotations

import streamlit as st
import streamlit.components.v1 as components


def render_baglist_page() -> None:
    st.title("Baglist Builder")
    st.caption("Ouvrez et pilotez la génération de baglist depuis l'interface dédiée.")

    default_url = st.session_state.get("baglist_url", "http://localhost:8000/baglist")
    baglist_url = st.text_input("URL Baglist", value=default_url)
    st.session_state["baglist_url"] = baglist_url

    cols = st.columns([1, 1, 2])
    with cols[0]:
        st.link_button("Ouvrir Baglist", baglist_url)
    with cols[1]:
        if st.button("Rafraichir"):
            st.rerun()

    st.divider()
    components.iframe(baglist_url, height=1100, scrolling=True)
