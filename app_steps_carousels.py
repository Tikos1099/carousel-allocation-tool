from __future__ import annotations

import pandas as pd
import streamlit as st

from allocator import CarouselCapacity
from app_state import _reset_after_carousels


def render_carousels_step(
    df_ready: pd.DataFrame,
) -> tuple[dict | None, dict | None, str | None, list[dict]]:
    st.divider()
    st.subheader("Etape 6 - Configuration carrousels")

    car_file = st.file_uploader(
        "Chargez le fichier carousels_by_terminal.csv (optionnel)",
        type=["csv", "txt"],
        key="carousels_file",
    )

    carousels_confirmed = bool(st.session_state.get("carousels_confirmed", False))
    carousels_mode = None
    caps_by_terminal = None
    caps_manual = None
    car_warnings: list[dict] = []

    if car_file:
        car_sig = (car_file.name, car_file.size)
        if st.session_state.get("car_file_sig") != car_sig:
            st.session_state["carousels_confirmed"] = False
            _reset_after_carousels()
            st.session_state["car_file_sig"] = car_sig

        try:
            car_df = pd.read_csv(car_file, sep=";")
        except Exception:
            st.error("Impossible de lire carousels_by_terminal.csv.")
            st.stop()

        car_df.columns = car_df.columns.astype(str).str.strip()
        expected = {"Terminal", "CarouselName", "WideCapacity", "NarrowCapacity"}
        if not expected.issubset(set(car_df.columns)):
            st.error(f"Colonnes attendues dans le fichier carrousels : {sorted(list(expected))}")
            st.stop()

        car_df["Terminal"] = car_df["Terminal"].astype(str).str.strip()
        car_df["CarouselName"] = car_df["CarouselName"].astype(str).str.strip()
        car_df["WideCapacity"] = car_df["WideCapacity"].astype(int)
        car_df["NarrowCapacity"] = car_df["NarrowCapacity"].astype(int)

        st.dataframe(car_df, use_container_width=True)
        summary_counts = car_df.groupby("Terminal")["CarouselName"].count().sort_index()
        summary_text = ", ".join([f"{t}: {c} carrousels" for t, c in summary_counts.items()])
        if summary_text:
            st.info(f"Resume : {summary_text}")

        if "Terminal" in df_ready.columns:
            missing_terms = sorted(set(df_ready["Terminal"].unique()) - set(car_df["Terminal"].unique()))
            if missing_terms:
                st.warning(f"Terminals non configures -> vols UNASSIGNED : {', '.join(missing_terms)}")
                car_warnings.append({
                    "Type": "Terminal non configure",
                    "Message": "Terminal absent du fichier carrousels",
                    "Count": int(len(missing_terms)),
                })

        if not carousels_confirmed:
            if st.button("Confirmer carrousels (fichier)", key="confirm_carousels_file"):
                caps_by_terminal = {}
                for term, g in car_df.groupby("Terminal"):
                    caps_by_terminal[term] = {
                        row["CarouselName"]: CarouselCapacity(
                            wide=int(row["WideCapacity"]),
                            narrow=int(row["NarrowCapacity"]),
                        )
                        for _, row in g.iterrows()
                    }
                st.session_state["caps_by_terminal"] = caps_by_terminal
                st.session_state["carousels_confirmed"] = True
                st.session_state["carousels_mode"] = "file"
                st.rerun()
        else:
            st.success("Configuration carrousels (fichier) confirmee.")
            if st.button("Modifier carrousels", key="modify_carousels_file"):
                st.session_state["carousels_confirmed"] = False
                _reset_after_carousels()
                st.rerun()
    else:
        st.info("Mode manuel (pas de fichier carrousels charge).")
        nb = st.number_input("Nombre de carrousels", min_value=1, value=3, step=1, key="nb_carousels")
        caps_manual = {}
        cols = st.columns(int(nb))
        for i in range(int(nb)):
            with cols[i]:
                c_name = f"Carousel {i+1}"
                wide = st.number_input(f"{c_name} - Wide capacity", min_value=0, value=8, step=1, key=f"w{i}")
                nar = st.number_input(f"{c_name} - Narrow capacity", min_value=0, value=4, step=1, key=f"n{i}")
                caps_manual[c_name] = CarouselCapacity(wide=int(wide), narrow=int(nar))

        if not carousels_confirmed:
            if st.button("Confirmer carrousels (manuel)", key="confirm_carousels_manual"):
                st.session_state["caps_manual"] = caps_manual
                st.session_state["carousels_confirmed"] = True
                st.session_state["carousels_mode"] = "manual"
                st.rerun()
        else:
            st.success("Configuration carrousels (manuel) confirmee.")
            if st.button("Modifier carrousels", key="modify_carousels_manual"):
                st.session_state["carousels_confirmed"] = False
                _reset_after_carousels()
                st.rerun()

    carousels_confirmed = bool(st.session_state.get("carousels_confirmed", False))
    if not carousels_confirmed:
        st.stop()

    caps_by_terminal = st.session_state.get("caps_by_terminal")
    caps_manual = st.session_state.get("caps_manual")
    carousels_mode = st.session_state.get("carousels_mode")

    return caps_by_terminal, caps_manual, carousels_mode, car_warnings
