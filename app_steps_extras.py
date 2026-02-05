from __future__ import annotations

import streamlit as st

from allocator import CarouselCapacity
from app_readjust import _build_extra_terms_and_defaults


def render_extras_step(
    df_ready,
    carousels_mode: str | None,
    caps_by_terminal: dict | None,
    caps_manual: dict | None,
) -> dict[str, CarouselCapacity]:
    st.divider()
    st.subheader("Etape 6b - Capacity sizing (extras)")

    st.markdown("### Readjustement")
    apply_readjustment = st.checkbox(
        "Appliquer les regles de readjustement",
        value=True,
        key="apply_readjustment",
    )

    rule_multi = False
    rule_narrow_wide = False
    rule_extras = False
    max_carousels_narrow = 1
    max_carousels_wide = 1
    rule_order: list[str] = []

    if apply_readjustment:
        rule_multi = st.checkbox("Regle 1 - Multi-carousels", value=True, key="rule_multi")
        max_cols = st.columns(2)
        with max_cols[0]:
            max_carousels_narrow = st.number_input(
                "MAX_CAROUSELS_PER_FLIGHT_NARROW",
                min_value=1,
                value=int(st.session_state.get("max_carousels_narrow", 3)),
                step=1,
                key="max_carousels_narrow",
                disabled=not rule_multi,
            )
        with max_cols[1]:
            max_carousels_wide = st.number_input(
                "MAX_CAROUSELS_PER_FLIGHT_WIDE",
                min_value=1,
                value=int(st.session_state.get("max_carousels_wide", 2)),
                step=1,
                key="max_carousels_wide",
                disabled=not rule_multi,
            )

        rule_narrow_wide = st.checkbox("Regle 2 - Narrow -> Wide", value=False, key="rule_narrow_wide")
        rule_extras = st.checkbox("Regle 3 - Extras", value=True, key="rule_extras")

        enabled_rules = []
        if rule_multi:
            enabled_rules.append("multi")
        if rule_narrow_wide:
            enabled_rules.append("narrow_wide")
        if rule_extras:
            enabled_rules.append("extras")

        if enabled_rules:
            label_map = {
                "multi": "Regle 1 - Multi-carousels",
                "narrow_wide": "Regle 2 - Narrow -> Wide",
                "extras": "Regle 3 - Extras",
            }
            id_by_label = {v: k for k, v in label_map.items()}
            default_order = [r for r in st.session_state.get("rule_order", []) if r in enabled_rules]
            for r in ["multi", "narrow_wide", "extras"]:
                if r in enabled_rules and r not in default_order:
                    default_order.append(r)

            st.markdown("**Ordre de priorite**")
            remaining = enabled_rules.copy()
            order: list[str] = []

            opt1 = [label_map[r] for r in remaining]
            default1 = label_map[default_order[0]] if default_order else opt1[0]
            sel1 = st.selectbox("Priorite 1", options=opt1, index=opt1.index(default1), key="rule_order_1")
            sel1_id = id_by_label[sel1]
            order.append(sel1_id)
            remaining.remove(sel1_id)

            if remaining:
                opt2 = [label_map[r] for r in remaining]
                default2 = label_map[default_order[1]] if len(default_order) > 1 and default_order[1] in remaining else opt2[0]
                sel2 = st.selectbox("Priorite 2", options=opt2, index=opt2.index(default2), key="rule_order_2")
                sel2_id = id_by_label[sel2]
                order.append(sel2_id)
                remaining.remove(sel2_id)

            if remaining:
                opt3 = [label_map[r] for r in remaining]
                default3 = label_map[default_order[2]] if len(default_order) > 2 and default_order[2] in remaining else opt3[0]
                sel3 = st.selectbox("Priorite 3", options=opt3, index=opt3.index(default3), key="rule_order_3")
                sel3_id = id_by_label[sel3]
                order.append(sel3_id)
                remaining.remove(sel3_id)

            rule_order = order

    st.markdown("**Couleurs planning (regles / exceptions)**")
    color_cols = st.columns(4)
    with color_cols[0]:
        st.color_picker(
            "Couleur Wide",
            value=st.session_state.get("wide_color", "#D32F2F"),
            key="wide_color",
        )
    with color_cols[1]:
        st.color_picker(
            "Couleur Narrow",
            value=st.session_state.get("narrow_color", "#FFEBEE"),
            key="narrow_color",
        )
    with color_cols[2]:
        st.color_picker(
            "Couleur Split",
            value=st.session_state.get("split_color", "#FFC107"),
            key="split_color",
        )
    with color_cols[3]:
        st.color_picker(
            "Couleur Narrow -> Wide",
            value=st.session_state.get("narrow_wide_color", "#00B894"),
            key="narrow_wide_color",
        )
    st.caption("Les couleurs Split / Narrow->Wide ont priorite sur les autres modes.")

    st.session_state["rule_order"] = rule_order

    extra_terminals, extra_defaults = _build_extra_terms_and_defaults(
        df_ready,
        carousels_mode,
        caps_by_terminal,
        caps_manual,
    )

    extra_caps_by_terminal: dict[str, CarouselCapacity] = {}
    extras_enabled = bool(apply_readjustment and rule_extras)
    if not extra_terminals:
        st.info("Aucun terminal configure pour dimensionnement extra.")
    elif extra_terminals == ["ALL"]:
        wide_def, nar_def = extra_defaults.get("ALL", (8, 4))
        wide_val = st.number_input(
            "Extra Wide capacity",
            min_value=0,
            value=int(wide_def),
            step=1,
            key="extra_wide_ALL",
            disabled=not extras_enabled,
        )
        nar_val = st.number_input(
            "Extra Narrow capacity",
            min_value=0,
            value=int(nar_def),
            step=1,
            key="extra_narrow_ALL",
            disabled=not extras_enabled,
        )
        extra_caps_by_terminal["ALL"] = CarouselCapacity(int(wide_val), int(nar_val))
    else:
        st.caption("Capacite standard des extra make-up par terminal.")
        for term in extra_terminals:
            wide_def, nar_def = extra_defaults.get(term, (8, 4))
            cols = st.columns(2)
            with cols[0]:
                wide_val = st.number_input(
                    f"{term} - Wide capacity",
                    min_value=0,
                    value=int(wide_def),
                    step=1,
                    key=f"extra_wide_{term}",
                    disabled=not extras_enabled,
                )
            with cols[1]:
                nar_val = st.number_input(
                    f"{term} - Narrow capacity",
                    min_value=0,
                    value=int(nar_def),
                    step=1,
                    key=f"extra_narrow_{term}",
                    disabled=not extras_enabled,
                )
            extra_caps_by_terminal[term] = CarouselCapacity(int(wide_val), int(nar_val))

    return extra_caps_by_terminal
