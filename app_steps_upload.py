from __future__ import annotations

import pandas as pd
import streamlit as st

from app_state import _reset_after_upload


def render_upload_step() -> pd.DataFrame | None:
    st.subheader("Etape 1 - Upload fichier vols")
    uploaded = st.file_uploader("Chargez le fichier Excel des vols", type=["xlsx"], key="flights_file")

    df_raw = None
    if uploaded:
        file_sig = (uploaded.name, uploaded.size)
        if st.session_state.get("flights_file_sig") != file_sig:
            _reset_after_upload()
            st.session_state["flights_file_sig"] = file_sig
        try:
            df_raw = pd.read_excel(uploaded)
        except Exception:
            st.error("Impossible de lire le fichier Excel des vols.")
    else:
        st.info("Chargez un fichier Excel pour demarrer.")

    return df_raw
