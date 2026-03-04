from __future__ import annotations

import streamlit as st

from app_state import _reset_after_time_step


def render_time_step_step(time_step: int) -> int:
    st.divider()
    st.subheader("Etape 5 - Time step")

    time_step_confirmed = bool(st.session_state.get("time_step_confirmed", False))
    current_time_step = int(time_step)
    if time_step_confirmed and st.session_state.get("time_step_value") != current_time_step:
        st.session_state["time_step_confirmed"] = False
        _reset_after_time_step()
        time_step_confirmed = False

    if not time_step_confirmed:
        if st.button("Confirmer time step", key="confirm_time_step"):
            st.session_state["time_step_confirmed"] = True
            st.session_state["time_step_value"] = current_time_step
            st.rerun()
    else:
        st.success("Time step confirme.")
        if st.button("Modifier time step", key="modify_time_step"):
            st.session_state["time_step_confirmed"] = False
            _reset_after_time_step()
            st.rerun()

    time_step_confirmed = bool(st.session_state.get("time_step_confirmed", False))
    if not time_step_confirmed:
        st.stop()

    return current_time_step
