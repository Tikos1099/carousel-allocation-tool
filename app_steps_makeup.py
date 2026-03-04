from __future__ import annotations

import pandas as pd
import streamlit as st

from app_state import _reset_after_makeup


def render_makeup_step(
    df_std: pd.DataFrame,
    makeup_mode: str,
    wide_x: int,
    wide_y: int,
    nar_x: int,
    nar_y: int,
) -> tuple[pd.DataFrame, list[dict]]:
    st.divider()
    st.subheader("Etape 4 - Make-up times")

    makeup_confirmed = bool(st.session_state.get("makeup_confirmed", False))
    current_signature = (makeup_mode, wide_x, wide_y, nar_x, nar_y)
    if makeup_confirmed and st.session_state.get("makeup_signature") != current_signature:
        st.session_state["makeup_confirmed"] = False
        _reset_after_makeup()
        makeup_confirmed = False

    if makeup_mode == "Colonnes (MakeupOpening/MakeupClosing)":
        if "MakeupOpening" not in df_std.columns or "MakeupClosing" not in df_std.columns:
            st.error("Colonnes MakeupOpening/MakeupClosing manquantes.")
            st.stop()
        df_ready = df_std.copy()
    else:
        df_ready = df_std.copy()

        def compute_open_close(row):
            dep = pd.Timestamp(row["DepartureTime"])
            cat = str(row["Category"]).strip().lower()
            if cat == "wide":
                return dep - pd.Timedelta(minutes=wide_x), dep - pd.Timedelta(minutes=wide_y)
            if cat == "narrow":
                return dep - pd.Timedelta(minutes=nar_x), dep - pd.Timedelta(minutes=nar_y)
            return pd.NaT, pd.NaT

        oc = df_ready.apply(compute_open_close, axis=1, result_type="expand")
        df_ready["MakeupOpening"] = oc[0]
        df_ready["MakeupClosing"] = oc[1]

    open_ts = pd.to_datetime(df_ready["MakeupOpening"], errors="coerce")
    close_ts = pd.to_datetime(df_ready["MakeupClosing"], errors="coerce")
    bad_times = df_ready[
        open_ts.isna()
        | close_ts.isna()
        | (open_ts >= close_ts)
    ]
    makeup_warnings = []
    if len(bad_times) > 0:
        makeup_warnings.append({
            "Type": "Makeup invalide",
            "Message": "MakeupOpening >= MakeupClosing ou valeurs manquantes",
            "Count": int(len(bad_times)),
        })

    if not makeup_confirmed:
        if st.button("Confirmer make-up times", key="confirm_makeup"):
            st.session_state["makeup_confirmed"] = True
            st.session_state["makeup_signature"] = current_signature
            st.rerun()
    else:
        st.success("Make-up times confirmes.")
        if st.button("Modifier make-up times", key="modify_makeup"):
            st.session_state["makeup_confirmed"] = False
            _reset_after_makeup()
            st.rerun()

    makeup_confirmed = bool(st.session_state.get("makeup_confirmed", False))
    if not makeup_confirmed:
        st.stop()

    return df_ready, makeup_warnings
