from __future__ import annotations

import pandas as pd
import streamlit as st

from allocator import allocate_round_robin, allocate_round_robin_with_rules


def handle_run_allocation(
    df_ready: pd.DataFrame,
    current_time_step: int,
    mapping_warnings: list[dict],
    makeup_warnings: list[dict],
    car_warnings: list[dict],
    extra_caps_by_terminal: dict,
) -> None:
    st.subheader("Etape 7 - Run + outputs")

    color_mode_ui = st.session_state.get("color_mode_ui", "Par categorie")
    if color_mode_ui == "Par categorie":
        color_mode = "category"
    elif color_mode_ui == "Par terminal":
        color_mode = "terminal"
    else:
        color_mode = "flight"

    warnings_rows: list[dict] = []
    warnings_rows.extend(mapping_warnings)
    warnings_rows.extend(makeup_warnings)
    warnings_rows.extend(car_warnings)

    if color_mode == "terminal" and "Terminal" not in df_ready.columns:
        warnings_rows.append({
            "Type": "Mode couleur",
            "Message": "Mode terminal demande mais colonne Terminal absente. Fallback par vol.",
            "Count": 1,
        })
        color_mode = "flight"

    if st.button("Run allocation", key="run_allocation"):
        try:
            required = ["DepartureTime", "FlightNumber", "Category", "Positions", "MakeupOpening", "MakeupClosing"]
            missing = [c for c in required if c not in df_ready.columns]
            if missing:
                st.error(f"Colonnes manquantes : {missing}")
                st.stop()

            start_time = pd.to_datetime(df_ready["MakeupOpening"]).min()
            end_time = pd.to_datetime(df_ready["DepartureTime"]).max()

            carousels_mode = st.session_state.get("carousels_mode")
            if carousels_mode == "file":
                if "Terminal" not in df_ready.columns:
                    st.error("Mode carrousels par terminal mais colonne Terminal absente.")
                    st.stop()
                caps_by_terminal = st.session_state.get("caps_by_terminal")
                if not caps_by_terminal:
                    st.error("Configuration carrousels manquante (mode fichier).")
                    st.stop()
                flights_out_list = []
                timelines = []
                for term, df_term in df_ready.groupby("Terminal"):
                    if term not in caps_by_terminal:
                        tmp = df_term.copy()
                        tmp["AssignedCarousel"] = "UNASSIGNED"
                        tmp["UnassignedReason"] = "TERMINAL_NOT_CONFIGURED"
                        flights_out_list.append(tmp)
                        continue

                    flights_out_term, timeline_term = allocate_round_robin(
                        flights=df_term,
                        carousel_caps=caps_by_terminal[term],
                        time_step_minutes=int(current_time_step),
                        start_time=pd.Timestamp(start_time),
                        end_time=pd.Timestamp(end_time),
                    )
                    timeline_term = timeline_term.rename(columns={c: f"{term}-{c}" for c in timeline_term.columns})
                    flights_out_list.append(flights_out_term)
                    timelines.append(timeline_term)

                flights_out = pd.concat(flights_out_list, ignore_index=True)
                if timelines:
                    timeline_df = pd.concat(timelines, axis=1).sort_index(axis=1)
                else:
                    timeline_df = pd.DataFrame(index=pd.date_range(start=start_time, end=end_time, freq=f"{int(current_time_step)}min"))
            else:
                caps_manual = st.session_state.get("caps_manual")
                if not caps_manual:
                    st.error("Configuration carrousels manquante (mode manuel).")
                    st.stop()
                flights_out, timeline_df = allocate_round_robin(
                    flights=df_ready,
                    carousel_caps=caps_manual,
                    time_step_minutes=int(current_time_step),
                    start_time=pd.Timestamp(start_time),
                    end_time=pd.Timestamp(end_time),
                )

            apply_readjustment = bool(st.session_state.get("apply_readjustment", True))
            max_carousels_narrow = int(st.session_state.get("max_carousels_narrow", 3))
            max_carousels_wide = int(st.session_state.get("max_carousels_wide", 2))
            rule_multi = bool(st.session_state.get("rule_multi", False))
            rule_narrow_wide = bool(st.session_state.get("rule_narrow_wide", False))
            rule_extras = bool(st.session_state.get("rule_extras", False))
            rule_order = st.session_state.get("rule_order", [])

            enabled_rules = []
            if apply_readjustment:
                if rule_multi:
                    enabled_rules.append("multi")
                if rule_narrow_wide:
                    enabled_rules.append("narrow_wide")
                if rule_extras:
                    enabled_rules.append("extras")
                rule_order = [r for r in rule_order if r in enabled_rules]
                for r in ["multi", "narrow_wide", "extras"]:
                    if r in enabled_rules and r not in rule_order:
                        rule_order.append(r)
            else:
                rule_order = []

            flights_readjusted_list = []
            timelines_readjusted = []
            extra_columns = []
            extra_summary_rows = []
            extra_warnings = []
            processed_terms = set()

            if not apply_readjustment or not rule_order:
                flights_readjusted = flights_out.copy()
                flights_readjusted["OriginalCategory"] = flights_readjusted["Category"].astype(str).str.strip()
                flights_readjusted["FinalCategory"] = flights_readjusted["OriginalCategory"]
                flights_readjusted["CategoryChanged"] = "NO"
                flights_readjusted["Category"] = flights_readjusted["FinalCategory"]
                flights_readjusted["AssignedCarousels"] = (
                    flights_readjusted["AssignedCarousel"].fillna("UNASSIGNED").astype(str)
                )
                flights_readjusted["SplitCount"] = flights_readjusted["AssignedCarousels"].apply(
                    lambda v: 0 if str(v).upper() == "UNASSIGNED" else 1
                )
                timeline_readjusted = timeline_df.copy()
            elif carousels_mode == "file":
                caps_by_terminal = st.session_state.get("caps_by_terminal") or {}
                for term, df_term in flights_out.groupby("Terminal"):
                    processed_terms.add(term)
                    caps_term = caps_by_terminal.get(term)
                    if caps_term is None:
                        tmp = df_term.copy()
                        tmp["OriginalCategory"] = tmp["Category"].astype(str).str.strip()
                        tmp["FinalCategory"] = tmp["OriginalCategory"]
                        tmp["CategoryChanged"] = "NO"
                        tmp["Category"] = tmp["FinalCategory"]
                        tmp["AssignedCarousels"] = "UNASSIGNED"
                        tmp["SplitCount"] = 0
                        tmp["AssignedCarousel"] = "UNASSIGNED"
                        flights_readjusted_list.append(tmp)
                        extra_summary_rows.append({
                            "Terminal": term,
                            "Nb extra makeups": 0,
                            "Liste": "",
                        })
                        continue

                    extra_cap = None
                    if rule_extras and extra_caps_by_terminal:
                        extra_cap = extra_caps_by_terminal.get(term)
                    readj_term, timeline_term, extras_used, impossible_df = allocate_round_robin_with_rules(
                        flights=df_term,
                        carousel_caps=caps_term,
                        time_step_minutes=int(current_time_step),
                        start_time=pd.Timestamp(start_time),
                        end_time=pd.Timestamp(end_time),
                        max_carousels_per_flight_narrow=max_carousels_narrow,
                        max_carousels_per_flight_wide=max_carousels_wide,
                        rule_order=rule_order,
                        extra_capacity=extra_cap,
                    )

                    if timeline_term is not None and len(timeline_term.columns) > 0:
                        timeline_term = timeline_term.reindex(timeline_df.index, fill_value="")
                        timeline_term = timeline_term.rename(columns={
                            c: f"{term}-{c}" for c in timeline_term.columns
                        })
                        timelines_readjusted.append(timeline_term)

                    flights_readjusted_list.append(readj_term)
                    cols = [f"{term}-{c}" for c in extras_used]
                    extra_columns.extend(cols)
                    extra_summary_rows.append({
                        "Terminal": term,
                        "Nb extra makeups": int(len(extras_used)),
                        "Liste": ", ".join(cols),
                    })

                    if rule_extras and extra_cap is None:
                        remaining = readj_term[readj_term["AssignedCarousel"] == "UNASSIGNED"]
                        if len(remaining) > 0:
                            extra_warnings.append({
                                "Type": "Extra sizing",
                                "Message": f"Terminal sans capacite extra configuree: {term}",
                                "Count": int(len(remaining)),
                            })

                    if rule_extras and impossible_df is not None and len(impossible_df) > 0:
                        extra_warnings.append({
                            "Type": "Extra sizing",
                            "Message": f"Vols impossibles pour extra ({term})",
                            "Count": int(len(impossible_df)),
                        })

                flights_readjusted = (
                    pd.concat(flights_readjusted_list, ignore_index=True)
                    if flights_readjusted_list
                    else flights_out.copy()
                )
                if timelines_readjusted:
                    timeline_readjusted = pd.concat(timelines_readjusted, axis=1).sort_index(axis=1)
                else:
                    timeline_readjusted = pd.DataFrame(index=timeline_df.index)
            else:
                extra_cap = None
                if rule_extras and extra_caps_by_terminal:
                    extra_cap = extra_caps_by_terminal.get("ALL")
                flights_readjusted, timeline_readjusted, extras_used, impossible_df = allocate_round_robin_with_rules(
                    flights=flights_out,
                    carousel_caps=caps_manual,
                    time_step_minutes=int(current_time_step),
                    start_time=pd.Timestamp(start_time),
                    end_time=pd.Timestamp(end_time),
                    max_carousels_per_flight_narrow=max_carousels_narrow,
                    max_carousels_per_flight_wide=max_carousels_wide,
                    rule_order=rule_order,
                    extra_capacity=extra_cap,
                )
                timeline_readjusted = timeline_readjusted.reindex(timeline_df.index, fill_value="")
                extra_columns = extras_used
                extra_summary_rows.append({
                    "Terminal": "ALL",
                    "Nb extra makeups": int(len(extras_used)),
                    "Liste": ", ".join(extras_used),
                })

                if rule_extras and extra_cap is None:
                    remaining = flights_readjusted[flights_readjusted["AssignedCarousel"] == "UNASSIGNED"]
                    if len(remaining) > 0:
                        extra_warnings.append({
                            "Type": "Extra sizing",
                            "Message": "Terminal sans capacite extra configuree: ALL",
                            "Count": int(len(remaining)),
                        })

                if rule_extras and impossible_df is not None and len(impossible_df) > 0:
                    extra_warnings.append({
                        "Type": "Extra sizing",
                        "Message": "Vols impossibles pour extra (ALL)",
                        "Count": int(len(impossible_df)),
                    })
                processed_terms.add("ALL")

            if extra_caps_by_terminal:
                for term in extra_caps_by_terminal.keys():
                    if term not in processed_terms:
                        extra_summary_rows.append({
                            "Terminal": term,
                            "Nb extra makeups": 0,
                            "Liste": "",
                        })

            if extra_summary_rows:
                extra_summary_df = pd.DataFrame(extra_summary_rows)
                extra_makeups_df = extra_summary_df[["Terminal", "Nb extra makeups"]].rename(
                    columns={"Nb extra makeups": "ExtraMakeupsNeeded"}
                )
            else:
                extra_summary_df = pd.DataFrame(columns=["Terminal", "Nb extra makeups", "Liste"])
                extra_makeups_df = pd.DataFrame(columns=["Terminal", "ExtraMakeupsNeeded"])

            warnings_rows.extend(extra_warnings)

            unassigned_df = flights_readjusted[flights_readjusted["AssignedCarousel"] == "UNASSIGNED"].copy()
            warnings_rows.append({
                "Type": "UNASSIGNED",
                "Message": "Vols non assignes",
                "Count": int(len(unassigned_df)),
            })

            keep_extra_cols = st.session_state.get("keep_extra_cols", [])

            st.session_state["results"] = {
                "flights_out": flights_out,
                "flights_readjusted": flights_readjusted,
                "timeline_df": timeline_df,
                "timeline_readjusted": timeline_readjusted,
                "warnings_rows": warnings_rows,
                "unassigned_df": unassigned_df,
                "color_mode": color_mode,
                "wide_color": st.session_state.get("wide_color", "#D32F2F"),
                "narrow_color": st.session_state.get("narrow_color", "#FFEBEE"),
                "split_color": st.session_state.get("split_color", "#FFC107"),
                "narrow_wide_color": st.session_state.get("narrow_wide_color", "#00B894"),
                "extra_columns": extra_columns,
                "extra_summary_df": extra_summary_df,
                "extra_makeups_df": extra_makeups_df,
                "keep_extra_cols": keep_extra_cols,
            }
            st.session_state["run_done"] = True
            st.rerun()
        except Exception as exc:
            if st.session_state.get("show_debug_errors", False):
                st.exception(exc)
            else:
                st.error("Erreur pendant l'allocation. Verifiez les donnees.")
