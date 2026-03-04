from __future__ import annotations

import os
import tempfile

import pandas as pd
import streamlit as st

from app_heatmap import _build_heatmap_sheets
from io_excel import write_heatmap_excel, write_summary_csv, write_summary_txt, write_timeline_excel


def render_results(extra_caps_by_terminal: dict, show_warnings: bool) -> None:
    if not st.session_state.get("run_done") or not st.session_state.get("results"):
        return

    results = st.session_state["results"]
    flights_out = results["flights_out"]
    flights_readjusted = results.get("flights_readjusted", flights_out)
    timeline_df = results["timeline_df"]
    timeline_readjusted = results.get("timeline_readjusted", timeline_df)
    warnings_rows = results["warnings_rows"]
    unassigned_df = results["unassigned_df"]
    extra_columns = results.get("extra_columns", [])
    extra_summary_df = results.get("extra_summary_df")
    extra_makeups_df = results.get("extra_makeups_df")
    keep_extra_cols = results.get("keep_extra_cols", [])
    split_color = results.get("split_color", "#FFC107")
    narrow_wide_color = results.get("narrow_wide_color", "#00B894")

    display_df = flights_readjusted.drop(columns=["AssignmentSegments"], errors="ignore").copy()
    legend = pd.Series([""] * len(display_df), index=display_df.index, dtype="object")
    changed_mask = display_df.get("CategoryChanged", pd.Series([""] * len(display_df))).astype(str).str.upper() == "YES"
    legend[changed_mask] = "Narrow->Wide"
    split_mask = pd.Series([False] * len(display_df), index=display_df.index)
    if "SplitCount" in display_df.columns:
        split_mask |= display_df["SplitCount"].fillna(0).astype(int) > 1
    if "AssignedCarousels" in display_df.columns:
        split_mask |= display_df["AssignedCarousels"].astype(str).str.contains(r"\+")
    legend[(~changed_mask) & split_mask] = "Split"
    cat_col = "FinalCategory" if "FinalCategory" in display_df.columns else "Category"
    cat_series = display_df.get(cat_col, pd.Series([""] * len(display_df))).astype(str).str.strip().str.lower()
    cat_label = cat_series.map({"wide": "Wide", "w": "Wide", "narrow": "Narrow", "n": "Narrow"}).fillna("Other")
    legend_mask = legend == ""
    legend[legend_mask] = cat_label[legend_mask]
    display_df["LegendCategory"] = legend
    total = int(len(display_df))
    unassigned_count = int(len(unassigned_df))
    assigned_pct = 0 if total == 0 else int(round(100 * (total - unassigned_count) / total))

    kpi_cols = st.columns(3)
    kpi_cols[0].metric("Total vols", total)
    kpi_cols[1].metric("% assignes", f"{assigned_pct}%")
    kpi_cols[2].metric("Nb UNASSIGNED", unassigned_count)

    split_count = int((display_df.get("SplitCount", 0).fillna(0).astype(int) > 1).sum()) if total else 0
    split_pct = 0 if total == 0 else int(round(100 * split_count / total))
    changed_mask = display_df.get("CategoryChanged", pd.Series([""] * total)).astype(str).str.upper() == "YES"
    narrow_wide_count = int(changed_mask.sum()) if total else 0
    narrow_wide_pct = 0 if total == 0 else int(round(100 * narrow_wide_count / total))
    kpi_cols2 = st.columns(4)
    kpi_cols2[0].metric("Nb vols split", split_count)
    kpi_cols2[1].metric("% split", f"{split_pct}%")
    kpi_cols2[2].metric("Nb Narrow->Wide", narrow_wide_count)
    kpi_cols2[3].metric("% Narrow->Wide", f"{narrow_wide_pct}%")

    with st.expander("Filtres resultats", expanded=True):
        assigned_opts = sorted(display_df["AssignedCarousel"].dropna().unique().tolist())
        assigned_sel = st.multiselect("AssignedCarousel", assigned_opts, default=assigned_opts)

        if "Terminal" in display_df.columns:
            term_opts = sorted(display_df["Terminal"].dropna().unique().tolist())
            term_sel = st.multiselect("Terminal", term_opts, default=term_opts)
        else:
            term_sel = None

        cat_opts = sorted(display_df["Category"].dropna().unique().tolist())
        cat_sel = st.multiselect("Category", cat_opts, default=cat_opts)

        legend_opts = sorted(display_df["LegendCategory"].dropna().unique().tolist())
        legend_sel = st.multiselect("Type (legend)", legend_opts, default=legend_opts)

    filtered = display_df.copy()
    if assigned_sel:
        filtered = filtered[filtered["AssignedCarousel"].isin(assigned_sel)]
    if term_sel is not None:
        if term_sel:
            filtered = filtered[filtered["Terminal"].isin(term_sel)]
        else:
            filtered = filtered.iloc[0:0]
    if cat_sel:
        filtered = filtered[filtered["Category"].isin(cat_sel)]
    else:
        filtered = filtered.iloc[0:0]
    if legend_sel:
        filtered = filtered[filtered["LegendCategory"].isin(legend_sel)]
    else:
        filtered = filtered.iloc[0:0]

    st.dataframe(filtered.sort_values("DepartureTime"), use_container_width=True)

    if extra_summary_df is not None and len(extra_summary_df) > 0:
        st.subheader("Summary extra makeups")
        st.dataframe(extra_summary_df, use_container_width=True)

    tmpdir = tempfile.mkdtemp()
    txt_path = os.path.join(tmpdir, "summary.txt")
    csv_path = os.path.join(tmpdir, "summary.csv")
    txt_readjusted_path = os.path.join(tmpdir, "summary_readjusted.txt")
    csv_readjusted_path = os.path.join(tmpdir, "summary_readjusted.csv")
    xlsx_path = os.path.join(tmpdir, "timeline.xlsx")
    readjusted_path = os.path.join(tmpdir, "timeline_readjusted.xlsx")
    heatmap_occ_path = os.path.join(tmpdir, "heatmap_positions_occupied.xlsx")
    heatmap_free_path = os.path.join(tmpdir, "heatmap_positions_free.xlsx")
    extra_csv_path = os.path.join(tmpdir, "extra_makeups_needed.csv")

    write_summary_txt(txt_path, flights_out, extra_cols=keep_extra_cols)
    write_summary_csv(csv_path, flights_out)
    export_readjusted = flights_readjusted.drop(columns=["AssignmentSegments"], errors="ignore")
    export_readjusted.sort_values("DepartureTime").to_csv(
        csv_readjusted_path,
        index=False,
        encoding="utf-8",
    )
    export_readjusted.sort_values("DepartureTime").to_csv(
        txt_readjusted_path,
        index=False,
        encoding="utf-8",
        sep="|",
    )
    write_timeline_excel(
        xlsx_path,
        timeline_df,
        flights_out,
        color_mode=results["color_mode"],
        wide_color=results["wide_color"],
        narrow_color=results["narrow_color"],
        split_color=split_color,
        narrow_wide_color=narrow_wide_color,
    )
    write_timeline_excel(
        readjusted_path,
        timeline_readjusted,
        flights_readjusted,
        color_mode=results["color_mode"],
        wide_color=results["wide_color"],
        narrow_color=results["narrow_color"],
        split_color=split_color,
        narrow_wide_color=narrow_wide_color,
        extra_columns=extra_columns,
        extra_summary=extra_summary_df,
    )

    heatmap_occ_sheets, heatmap_free_sheets = _build_heatmap_sheets(
        flights_readjusted,
        timeline_readjusted.index,
        list(timeline_readjusted.columns),
        carousels_mode=st.session_state.get("carousels_mode"),
        caps_manual=st.session_state.get("caps_manual"),
        caps_by_terminal=st.session_state.get("caps_by_terminal"),
        extra_caps_by_terminal=extra_caps_by_terminal,
    )
    write_heatmap_excel(heatmap_occ_path, heatmap_occ_sheets, mode="occupied")
    write_heatmap_excel(heatmap_free_path, heatmap_free_sheets, mode="free")

    if extra_makeups_df is not None:
        extra_makeups_df.to_csv(extra_csv_path, index=False, encoding="utf-8")
    else:
        pd.DataFrame(columns=["Terminal", "ExtraMakeupsNeeded"]).to_csv(extra_csv_path, index=False, encoding="utf-8")

    st.subheader("Downloads")
    st.markdown("**Resultats principaux**")
    main_cols = st.columns(3)
    main_cols[0].download_button(
        "summary.csv",
        data=open(csv_path, "rb"),
        file_name="summary.csv",
        key="dl_summary_csv",
    )
    main_cols[1].download_button(
        "summary.txt",
        data=open(txt_path, "rb"),
        file_name="summary.txt",
        key="dl_summary_txt",
    )
    main_cols[2].download_button(
        "extra_makeups_needed.csv",
        data=open(extra_csv_path, "rb"),
        file_name="extra_makeups_needed.csv",
        key="dl_extra_makeups_needed",
    )

    readj_cols = st.columns(2)
    readj_cols[0].download_button(
        "summary_readjusted.csv",
        data=open(csv_readjusted_path, "rb"),
        file_name="summary_readjusted.csv",
        key="dl_summary_readjusted_csv",
    )
    readj_cols[1].download_button(
        "summary_readjusted.txt",
        data=open(txt_readjusted_path, "rb"),
        file_name="summary_readjusted.txt",
        key="dl_summary_readjusted_txt",
    )

    st.markdown("**Planning**")
    plan_cols = st.columns(3)
    plan_cols[0].download_button(
        "timeline.xlsx",
        data=open(xlsx_path, "rb"),
        file_name="timeline.xlsx",
        key="dl_timeline",
    )
    plan_cols[1].download_button(
        "timeline_readjusted.xlsx",
        data=open(readjusted_path, "rb"),
        file_name="timeline_readjusted.xlsx",
        key="dl_timeline_readjusted",
    )

    st.markdown("**Heatmaps**")
    heat_cols = st.columns(2)
    heat_cols[0].download_button(
        "heatmap_positions_occupied.xlsx",
        data=open(heatmap_occ_path, "rb"),
        file_name="heatmap_positions_occupied.xlsx",
        key="dl_heatmap_occupied",
    )
    heat_cols[1].download_button(
        "heatmap_positions_free.xlsx",
        data=open(heatmap_free_path, "rb"),
        file_name="heatmap_positions_free.xlsx",
        key="dl_heatmap_free",
    )

    st.markdown("**Diagnostics**")
    diag_cols = st.columns(3)
    if len(unassigned_df) > 0:
        unassigned_csv = unassigned_df.to_csv(index=False, encoding="utf-8")
        diag_cols[0].download_button(
            "unassigned_reasons.csv",
            data=unassigned_csv,
            file_name="unassigned_reasons.csv",
            key="dl_unassigned_reasons",
        )
    else:
        diag_cols[0].download_button(
            "unassigned_reasons.csv",
            data="",
            file_name="unassigned_reasons.csv",
            key="dl_unassigned_reasons",
        )
    diag_cols[1].download_button(
        "warnings.csv",
        data=pd.DataFrame(warnings_rows).to_csv(index=False, encoding="utf-8") if warnings_rows else "",
        file_name="warnings.csv",
        key="dl_warnings_diag",
    )

    if show_warnings:
        st.subheader("Warnings")
        if warnings_rows:
            warnings_df = pd.DataFrame(warnings_rows)
            st.dataframe(warnings_df, use_container_width=True)
            warnings_csv = warnings_df.to_csv(index=False, encoding="utf-8")
            st.download_button(
                "warnings.csv",
                data=warnings_csv,
                file_name="warnings.csv",
                key="dl_warnings_panel",
            )
        else:
            st.success("Aucun warning.")
