from __future__ import annotations
import streamlit as st
import pandas as pd
import re
import unicodedata

from allocator import CarouselCapacity, allocate_round_robin
from io_excel import write_summary_txt, write_summary_csv, write_timeline_excel

st.set_page_config(page_title="Carousel Allocation Tool", layout="wide")
st.title("Carousel Allocation Tool")

uploaded = st.file_uploader("Chargez le fichier Excel des vols", type=["xlsx"])

if uploaded:

    if "mapping_confirmed" not in st.session_state:
        st.session_state["mapping_confirmed"] = False

    def _norm(s: str) -> str:
        s = str(s).strip()
        s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
        s = s.lower()
        s = re.sub(r"\s+", " ", s)
        return s

    def _guess_col(cols, keywords):
        """Return best matching col name from cols based on keywords in normalized name."""
        norm_map = {c: _norm(c) for c in cols}
        for kw in keywords:
            for c, nc in norm_map.items():
                if kw in nc:
                    return c
        return None

    # --- LECTURE brute (on ne dépend plus du mapping automatique ici) ---
    df_raw = pd.read_excel(uploaded)

    st.subheader("Aperçu du fichier (brut)")
    st.dataframe(df_raw.head(20), use_container_width=True)


    st.divider()
    st.subheader("Étape 0 — Mapping des colonnes")

    # initialiser le flag
    if "mapping_confirmed" not in st.session_state:
        st.session_state["mapping_confirmed"] = False

    cols = list(df_raw.columns)

    # Deviner les colonnes par défaut
    default_dep = _guess_col(cols, ["std", "departure time", "heure de depart", "dep time"])
    default_flt = _guess_col(cols, ["flight number", "flight no", "flt", "numero de vol", "num vol"])
    default_cat = _guess_col(cols, ["category", "categorie", "cat", "type"])
    default_pos = _guess_col(cols, ["positions", "position", "pos", "nb position", "nbr position"])
    default_term = _guess_col(cols, ["terminal", "term", "tml"])
    default_open = _guess_col(cols, ["make up opening", "make-up opening", "makeup opening", "opening"])
    default_close = _guess_col(cols, ["make up closing", "make-up closing", "makeup closing", "closing"])

    def _selectbox(label, default, key):
        options = ["(Aucune)"] + cols
        idx = options.index(default) if (default in options) else 0
        return st.selectbox(label, options=options, index=idx, key=key)

    if not st.session_state["mapping_confirmed"]:
        c_dep = _selectbox("Departure time (ex: STD)", default_dep, "map_dep")
        c_flt = _selectbox("Flight number", default_flt, "map_flt")
        c_cat = _selectbox("Category (ex: Wide body / Narrow body)", default_cat, "map_cat")
        c_pos = _selectbox("Positions", default_pos, "map_pos")

        st.caption("Optionnels")
        c_term = _selectbox("Terminal (optionnel)", default_term, "map_term")
        c_open = _selectbox("MakeupOpening (optionnel)", default_open, "map_open")
        c_close = _selectbox("MakeupClosing (optionnel)", default_close, "map_close")

        if st.button("✅ Appliquer le mapping"):
            missing = []
            if c_dep == "(Aucune)": missing.append("DepartureTime")
            if c_flt == "(Aucune)": missing.append("FlightNumber")
            if c_cat == "(Aucune)": missing.append("Category")
            if c_pos == "(Aucune)": missing.append("Positions")
            if missing:
                st.error(f"Colonnes obligatoires non sélectionnées : {missing}")
                st.stop()

            rename_map = {c_dep: "DepartureTime", c_flt: "FlightNumber", c_cat: "Category", c_pos: "Positions"}
            if c_term != "(Aucune)": rename_map[c_term] = "Terminal"
            if c_open != "(Aucune)": rename_map[c_open] = "MakeupOpening"
            if c_close != "(Aucune)": rename_map[c_close] = "MakeupClosing"

            df = df_raw.rename(columns=rename_map).copy()
            st.session_state["df_mapped"] = df
            st.session_state["mapping_confirmed"] = True
            st.rerun()
    else:
        st.success("Mapping déjà confirmé ✅")
        if st.button("🔄 Modifier le mapping"):
            st.session_state["mapping_confirmed"] = False
            st.session_state.pop("df_mapped", None)
            st.rerun()

    df = st.session_state.get("df_mapped")
    if df is None:
        st.stop()

    st.write("Colonnes après mapping :", list(df.columns))
    st.dataframe(df.head(20), use_container_width=True)


    st.divider()
    st.subheader("Étape 0ter — Fichier carrousels par terminal (optionnel)")

    car_file = st.file_uploader(
        "Chargez le fichier carrousels_by_terminal.csv (optionnel)",
        type=["csv", "txt"]
    )

    caps_by_terminal = None

    if car_file:
        car_df = pd.read_csv(car_file, sep=";")
        car_df.columns = car_df.columns.astype(str).str.strip()
        st.write("Colonnes lues:", list(car_df.columns))
        # colonnes attendues
        expected = {"Terminal", "CarouselName", "WideCapacity", "NarrowCapacity"}
        if not expected.issubset(set(car_df.columns)):
            st.error(f"Colonnes attendues dans le fichier carrousels: {sorted(list(expected))}")
            st.stop()

        # Normaliser Terminal comme on a fait (simple)
        car_df["Terminal"] = car_df["Terminal"].astype(str).str.strip()
        car_df["CarouselName"] = car_df["CarouselName"].astype(str).str.strip()
        car_df["WideCapacity"] = car_df["WideCapacity"].astype(int)
        car_df["NarrowCapacity"] = car_df["NarrowCapacity"].astype(int)

        st.write("Aperçu carrousels:")
        st.dataframe(car_df, use_container_width=True)

        # Construire une structure: {terminal: {carousel_name: CarouselCapacity}}
        caps_by_terminal = {}
        for term, g in car_df.groupby("Terminal"):
            caps_by_terminal[term] = {
                row["CarouselName"]: CarouselCapacity(wide=int(row["WideCapacity"]), narrow=int(row["NarrowCapacity"]))
                for _, row in g.iterrows()
            }

        st.success("Carrousels par terminal chargés ✅")
    else:
        st.info("Pas de fichier carrousels → on utilisera la configuration manuelle (comme avant).")




    warnings = []  # on collectera des warnings pour les afficher

    # ---------- A) Mapping Category ----------
    if "Category" not in df.columns:
        st.error("La colonne 'Category' est absente après mapping.")
        st.stop()

    raw_cats = sorted([str(x).strip() for x in df["Category"].dropna().unique().tolist()])
    st.write("Valeurs trouvées dans Category :", raw_cats)

    # suggestions automatiques
    def suggest_cat(v: str) -> str:
        s = v.strip().lower()
        if "wide" in s or s in ["wb", "w"]:
            return "Wide"
        if "narrow" in s or s in ["nb", "n"]:
            return "Narrow"
        return "IGNORER"

    cat_options = ["Wide", "Narrow", "IGNORER"]
    cat_mapping = {}

    with st.expander("Configurer le mapping Category", expanded=True):
        for v in raw_cats:
            default = suggest_cat(v)
            cat_mapping[v] = st.selectbox(
                f"'{v}' →",
                options=cat_options,
                index=cat_options.index(default),
                key=f"catmap_{v}",
            )

    # appliquer mapping catégories
    df["_CategoryStd"] = df["Category"].astype(str).str.strip().map(lambda x: cat_mapping.get(x, "IGNORER"))

    ignored_cat = df[df["_CategoryStd"] == "IGNORER"]
    if len(ignored_cat) > 0:
        warnings.append(f"{len(ignored_cat)} lignes ignorées (Category non mappée).")

    df = df[df["_CategoryStd"] != "IGNORER"].copy()
    df["Category"] = df["_CategoryStd"]
    df = df.drop(columns=["_CategoryStd"])

    st.success("Mapping Category appliqué ✅")
    st.write("Catégories standard après mapping :", sorted(df["Category"].unique().tolist()))

    # ---------- B) Normalisation Terminal (optionnel) ----------
    if "Terminal" in df.columns:
        raw_terms = sorted([str(x).strip() for x in df["Terminal"].dropna().unique().tolist()])
        st.write("Valeurs trouvées dans Terminal :", raw_terms)

        def suggest_term(v: str) -> str:
            s = v.strip().upper()
            # extraire un chiffre si présent
            m = re.search(r"(\d+)", s)
            if s.startswith("T") and len(s) >= 2 and s[1].isdigit():
                return "T" + re.search(r"\d+", s).group(0)
            if "TERMINAL" in s and m:
                return "T" + m.group(1)
            if m and len(m.group(1)) <= 2:
                return "T" + m.group(1)
            # si c’est déjà un code type A/B, on le garde tel quel
            return s if s else "INCONNU"

        # propositions de terminals standards
        suggested = {v: suggest_term(v) for v in raw_terms}
        std_terms = sorted(set(suggested.values()))
        std_options = std_terms + ["IGNORER"]

        term_mapping = {}
        with st.expander("Configurer le mapping Terminal", expanded=True):
            for v in raw_terms:
                default = suggested[v]
                # si default pas dans std_options (rare), on prend le 1er
                idx = std_options.index(default) if default in std_options else 0
                term_mapping[v] = st.selectbox(
                    f"'{v}' →",
                    options=std_options,
                    index=idx,
                    key=f"termmap_{v}",
                )

        df["_TerminalStd"] = df["Terminal"].astype(str).str.strip().map(lambda x: term_mapping.get(x, "IGNORER"))

        ignored_term = df[df["_TerminalStd"] == "IGNORER"]
        if len(ignored_term) > 0:
            warnings.append(f"{len(ignored_term)} lignes ignorées (Terminal non mappé).")

        df = df[df["_TerminalStd"] != "IGNORER"].copy()
        df["Terminal"] = df["_TerminalStd"]
        df = df.drop(columns=["_TerminalStd"])

        st.success("Mapping Terminal appliqué ✅")
        st.write("Terminals standard après mapping :", sorted(df["Terminal"].unique().tolist()))
    else:
        st.info("Aucune colonne Terminal fournie → pas de contrainte terminal pour l’instant (v1).")

    # ---------- Affichage warnings ----------
    if warnings:
        st.warning("Warnings :\n- " + "\n- ".join(warnings))

    # IMPORTANT : df est maintenant standardisé (Category, Terminal si présent)

    has_cols = st.radio(
        "Votre fichier contient-il MakeupOpening & MakeupClosing ?",
        options=["Oui", "Non"],
        horizontal=True,
    )

    if has_cols == "Oui":
        if "MakeupOpening" not in df.columns or "MakeupClosing" not in df.columns:
            st.error("Vous avez répondu Oui, mais les colonnes ne sont pas détectées.")
            st.stop()
    else:
        mode = st.radio(
            "Ces make-up times sont-ils des offsets relatifs au départ ? (cas le plus courant)",
            options=["Oui (Departure - X min / - Y min)", "Non (autre règle)"],
        )

        if mode.startswith("Oui"):
            st.write("Saisissez X (opening) et Y (closing) en minutes, par catégorie.")
            wide_x = st.number_input("Wide: X minutes (opening = départ - X)", min_value=0, value=120, step=5)
            wide_y = st.number_input("Wide: Y minutes (closing = départ - Y)", min_value=0, value=15, step=5)
            nar_x  = st.number_input("Narrow: X minutes (opening = départ - X)", min_value=0, value=90, step=5)
            nar_y  = st.number_input("Narrow: Y minutes (closing = départ - Y)", min_value=0, value=10, step=5)

            def compute_open_close(row):
                dep = pd.Timestamp(row["DepartureTime"])
                cat = str(row["Category"]).strip().lower()
                if cat == "wide":
                    return dep - pd.Timedelta(minutes=wide_x), dep - pd.Timedelta(minutes=wide_y)
                elif cat == "narrow":
                    return dep - pd.Timedelta(minutes=nar_x), dep - pd.Timedelta(minutes=nar_y)
                else:
                    return pd.NaT, pd.NaT

            oc = df.apply(compute_open_close, axis=1, result_type="expand")
            df["MakeupOpening"] = oc[0]
            df["MakeupClosing"] = oc[1]
        else:
            st.warning("Mode 'autre règle' pas encore implémenté dans ce MVP.")
            st.stop()

    st.divider()
    st.subheader("Étape 2 — Time step (timeline)")
    step = st.number_input("Pas de temps (minutes)", min_value=1, value=5, step=1)

    # timeline bounds
    start_time = pd.to_datetime(df["MakeupOpening"]).min()
    end_time = pd.to_datetime(df["DepartureTime"]).max()

    st.info(f"Timeline: {start_time} → {end_time}")

    st.divider()
    st.subheader("Etape 2bis -- Couleurs")
    color_mode_ui = st.radio(
        "Mode couleur",
        options=["Par categorie", "Par vol"],
        index=0,
        horizontal=True,
    )
    color_mode = "category" if color_mode_ui == "Par categorie" else "flight"
    wide_color_default = "#F4B183"
    narrow_color_default = "#A9D08E"
    if color_mode == "category":
        wide_color = st.color_picker("Couleur Wide", value=wide_color_default)
        narrow_color = st.color_picker("Couleur Narrow", value=narrow_color_default)
    else:
        wide_color = wide_color_default
        narrow_color = narrow_color_default
        st.caption("Mode par vol: couleurs automatiques basees sur le numero de vol.")

    
    st.divider()
    st.subheader("Étape 3 — Carrousels et capacités")

    if caps_by_terminal is not None:
        st.success("Mode fichier carrousels activé ✅ (par terminal)")

        # Affichage clair: Terminal -> carrousels + capacités
        rows = []
        for term, car_map in caps_by_terminal.items():
            for car_name, cap in car_map.items():
                rows.append({
                    "Terminal": term,
                    "Carousel": car_name,
                    "WideCapacity": cap.wide,
                    "NarrowCapacity": cap.narrow,
                })

        car_display = pd.DataFrame(rows).sort_values(["Terminal", "Carousel"])
        st.dataframe(car_display, use_container_width=True)

        st.info("Les capacités viennent du fichier. (On peut ajouter un mode 'édition' plus tard si tu veux.)")

        caps = None  # pas utilisé en mode terminal

    else:
        st.info("Mode manuel (pas de fichier carrousels chargé)")

        nb = st.number_input("Nombre de carrousels", min_value=1, value=3, step=1)
        caps = {}
        cols = st.columns(int(nb))
        for i in range(int(nb)):
            with cols[i]:
                c_name = f"Carousel {i+1}"
                wide = st.number_input(f"{c_name} - Wide capacity", min_value=0, value=8, step=1, key=f"w{i}")
                nar = st.number_input(f"{c_name} - Narrow capacity", min_value=0, value=4, step=1, key=f"n{i}")
                caps[c_name] = CarouselCapacity(wide=int(wide), narrow=int(nar))



    st.divider()
    st.subheader("Lancer l'allocation")


    if st.button("Run"):
        required = ["DepartureTime", "FlightNumber", "Category", "Positions", "MakeupOpening", "MakeupClosing"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            st.error(f"Colonnes manquantes: {missing}")
            st.stop()

        use_terminal = ("Terminal" in df.columns) and (caps_by_terminal is not None)

        if use_terminal:
            flights_out_list = []
            timelines = []

            for term, df_term in df.groupby("Terminal"):
                if term not in caps_by_terminal:
                    tmp = df_term.copy()
                    tmp["AssignedCarousel"] = "UNASSIGNED"
                    flights_out_list.append(tmp)
                    continue

                flights_out_term, timeline_term = allocate_round_robin(
                    flights=df_term,
                    carousel_caps=caps_by_terminal[term],
                    time_step_minutes=int(step),
                    start_time=pd.Timestamp(start_time),
                    end_time=pd.Timestamp(end_time),
                )

                # préfixer colonnes timeline pour éviter collisions de noms MU
                timeline_term = timeline_term.rename(columns={c: f"{term}-{c}" for c in timeline_term.columns})

                flights_out_list.append(flights_out_term)
                timelines.append(timeline_term)

            flights_out = pd.concat(flights_out_list, ignore_index=True)

            if timelines:
                timeline_df = pd.concat(timelines, axis=1).sort_index(axis=1)
            else:
                timeline_df = pd.DataFrame(index=pd.date_range(start=start_time, end=end_time, freq=f"{int(step)}min"))

        else:
            flights_out, timeline_df = allocate_round_robin(
                flights=df,
                carousel_caps=caps,  # config manuelle
                time_step_minutes=int(step),
                start_time=pd.Timestamp(start_time),
                end_time=pd.Timestamp(end_time),
            )

        st.success("Allocation terminée")
        st.subheader("Résultat vols")
        st.dataframe(flights_out.sort_values("DepartureTime"), use_container_width=True)

        # write files to disk for download
        import tempfile, os
        tmpdir = tempfile.mkdtemp()
        txt_path = os.path.join(tmpdir, "summary.txt")
        csv_path = os.path.join(tmpdir, "summary.csv")
        xlsx_path = os.path.join(tmpdir, "timeline.xlsx")

        write_summary_txt(txt_path, flights_out)
        write_summary_csv(csv_path, flights_out)
        write_timeline_excel(
            xlsx_path,
            timeline_df,
            flights_out,
            color_mode=color_mode,
            wide_color=wide_color,
            narrow_color=narrow_color,
        )

        st.download_button("Télécharger summary.txt", data=open(txt_path, "rb"), file_name="summary.txt")
        st.download_button("Télécharger summary.csv", data=open(csv_path, "rb"), file_name="summary.csv")
        st.download_button("Télécharger timeline.xlsx", data=open(xlsx_path, "rb"), file_name="timeline.xlsx")

