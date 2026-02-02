from __future__ import annotations
import streamlit as st
import pandas as pd
import re
import unicodedata
from pathlib import Path

from allocator import CarouselCapacity, allocate_round_robin
from io_excel import write_summary_txt, write_summary_csv, write_timeline_excel

BRAND_RED = "#D32F2F"
BRAND_RED_DARK = "#B71C1C"
BRAND_BG = "#FFFFFF"
BRAND_SIDEBAR = "#F7F7F7"
BRAND_BORDER = "#E5E5E5"

st.set_page_config(page_title="Carousel Allocation Tool", layout="wide")
st.markdown(
    f"""
    <style>
        :root {{
            --brand-red: {BRAND_RED};
            --brand-red-dark: {BRAND_RED_DARK};
            --brand-bg: {BRAND_BG};
            --brand-sidebar: {BRAND_SIDEBAR};
            --brand-border: {BRAND_BORDER};
        }}
        html, body, [data-testid="stAppViewContainer"] {{
            background: var(--brand-bg);
            color: #111111;
        }}
        [data-testid="stHeader"] {{
            background: #ffffff;
            border-bottom: 1px solid var(--brand-border);
        }}
        [data-testid="stToolbar"] {{
            background: #ffffff;
        }}
        [data-testid="stDecoration"] {{
            background: #ffffff;
        }}
        [data-testid="stSidebar"] > div:first-child {{
            background: var(--brand-sidebar);
        }}
        h1, h2, h3, h4, label, p, span {{
            color: #111111;
        }}
        input, textarea, [data-baseweb="select"] > div {{
            background: #ffffff !important;
            color: #111111 !important;
            border: 1px solid var(--brand-border) !important;
        }}
        [data-testid="stFileUploader"] section {{
            background: #ffffff !important;
            border: 1px dashed var(--brand-border) !important;
            color: #111111 !important;
        }}
        [data-testid="stFileUploader"] button {{
            background: #ffffff !important;
            color: #111111 !important;
            border: 1px solid var(--brand-border) !important;
        }}
        div.stButton > button, div.stDownloadButton > button {{
            background: var(--brand-red);
            color: #ffffff;
            border: 0;
        }}
        div.stButton > button * , div.stDownloadButton > button * {{
            color: #ffffff !important;
        }}
        div.stButton > button:hover, div.stDownloadButton > button:hover {{
            background: var(--brand-red-dark);
            color: #ffffff;
        }}
        [data-testid="stMetric"] {{
            background: #ffffff;
            border: 1px solid var(--brand-border);
            padding: 0.5rem;
            border-radius: 0.5rem;
        }}
        .stAlert {{
            background: #ffffff;
            color: #111111;
            border: 1px solid var(--brand-border);
            border-left: 4px solid var(--brand-red);
        }}
    </style>
    """,
    unsafe_allow_html=True,
)

base_dir = Path(__file__).parent
logo_candidates = [
    base_dir / "logo.jpg",
    base_dir / "logo.png",
    base_dir / "assets" / "logo.jpg",
    base_dir / "assets" / "logo.png",
]
logo_path = None
for candidate in logo_candidates:
    if candidate.exists():
        logo_path = candidate
        break

logo_bytes = None
if logo_path:
    try:
        logo_bytes = logo_path.read_bytes()
    except Exception:
        logo_bytes = None

if logo_bytes:
    header_cols = st.columns([1, 6])
    with header_cols[0]:
        st.image(logo_bytes, width=120)
    with header_cols[1]:
        st.title("Carousel Allocation Tool")
else:
    st.title("Carousel Allocation Tool")


def _norm(s: str) -> str:
    s = str(s).strip()
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = s.lower()
    s = re.sub(r"\s+", " ", s)
    return s


def _guess_col(cols, keywords):
    norm_map = {c: _norm(c) for c in cols}
    for kw in keywords:
        for c, nc in norm_map.items():
            if kw in nc:
                return c
    return None


def _clear_prefix(prefixes):
    for key in list(st.session_state.keys()):
        if any(key.startswith(p) for p in prefixes):
            st.session_state.pop(key, None)


def _reset_after_upload():
    keys = [
        "mapping_confirmed",
        "cat_term_confirmed",
        "makeup_confirmed",
        "time_step_confirmed",
        "carousels_confirmed",
        "run_done",
        "results",
        "col_mapping",
        "cat_mapping",
        "term_mapping",
        "makeup_signature",
        "time_step_value",
        "car_file_sig",
    ]
    for k in keys:
        st.session_state.pop(k, None)
    _clear_prefix(("map_", "catmap_", "termmap_"))


def _reset_after_mapping():
    keys = [
        "cat_term_confirmed",
        "makeup_confirmed",
        "time_step_confirmed",
        "carousels_confirmed",
        "run_done",
        "results",
        "cat_mapping",
        "term_mapping",
        "makeup_signature",
        "time_step_value",
        "car_file_sig",
    ]
    for k in keys:
        st.session_state.pop(k, None)
    _clear_prefix(("catmap_", "termmap_"))


def _reset_after_cat_term():
    keys = [
        "makeup_confirmed",
        "time_step_confirmed",
        "carousels_confirmed",
        "run_done",
        "results",
        "makeup_signature",
        "time_step_value",
        "car_file_sig",
    ]
    for k in keys:
        st.session_state.pop(k, None)


def _reset_after_makeup():
    keys = [
        "time_step_confirmed",
        "carousels_confirmed",
        "run_done",
        "results",
        "time_step_value",
        "car_file_sig",
    ]
    for k in keys:
        st.session_state.pop(k, None)


def _reset_after_time_step():
    keys = [
        "carousels_confirmed",
        "run_done",
        "results",
        "car_file_sig",
    ]
    for k in keys:
        st.session_state.pop(k, None)


def _reset_after_carousels():
    keys = [
        "run_done",
        "results",
    ]
    for k in keys:
        st.session_state.pop(k, None)


def _apply_cat_term_mapping(df: pd.DataFrame, cat_mapping: dict, term_mapping: dict):
    warnings = []
    df = df.copy()
    df["_CategoryStd"] = df["Category"].astype(str).str.strip().map(lambda x: cat_mapping.get(x, "IGNORER"))
    ignored_cat = df[df["_CategoryStd"] == "IGNORER"]
    if len(ignored_cat) > 0:
        warnings.append({
            "Type": "Category non mappee",
            "Message": "Lignes ignorees (Category non mappee)",
            "Count": int(len(ignored_cat)),
        })
    df = df[df["_CategoryStd"] != "IGNORER"].copy()
    df["Category"] = df["_CategoryStd"]
    df = df.drop(columns=["_CategoryStd"])

    if "Terminal" in df.columns and term_mapping:
        df["_TerminalStd"] = df["Terminal"].astype(str).str.strip().map(lambda x: term_mapping.get(x, "IGNORER"))
        ignored_term = df[df["_TerminalStd"] == "IGNORER"]
        if len(ignored_term) > 0:
            warnings.append({
                "Type": "Terminal non mappe",
                "Message": "Lignes ignorees (Terminal non mappe)",
                "Count": int(len(ignored_term)),
            })
        df = df[df["_TerminalStd"] != "IGNORER"].copy()
        df["Terminal"] = df["_TerminalStd"]
        df = df.drop(columns=["_TerminalStd"])

    return df, warnings


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


col_mapping_preview = st.session_state.get("col_mapping")
mapping_confirmed = bool(st.session_state.get("mapping_confirmed", False))
df_mapped_preview = None
has_terminal = False
if df_raw is not None and mapping_confirmed and col_mapping_preview:
    df_mapped_preview = df_raw.rename(columns=col_mapping_preview).copy()
    has_terminal = "Terminal" in df_mapped_preview.columns


with st.sidebar:
    st.header("Parametres")
    if st.button("Reset project"):
        st.session_state.clear()
        st.rerun()

    st.subheader("Make-up")
    makeup_mode = st.radio(
        "Mode make-up",
        options=["Colonnes (MakeupOpening/MakeupClosing)", "Offsets"],
        index=0,
        key="makeup_mode",
    )
    if makeup_mode == "Offsets":
        wide_x = st.number_input("Wide: opening (min)", min_value=0, value=120, step=5, key="wide_x")
        wide_y = st.number_input("Wide: closing (min)", min_value=0, value=15, step=5, key="wide_y")
        nar_x = st.number_input("Narrow: opening (min)", min_value=0, value=90, step=5, key="nar_x")
        nar_y = st.number_input("Narrow: closing (min)", min_value=0, value=10, step=5, key="nar_y")
    else:
        wide_x = st.session_state.get("wide_x", 120)
        wide_y = st.session_state.get("wide_y", 15)
        nar_x = st.session_state.get("nar_x", 90)
        nar_y = st.session_state.get("nar_y", 10)

    st.subheader("Time step")
    time_step = st.number_input("Pas de temps (minutes)", min_value=1, value=5, step=1, key="time_step")

    st.subheader("Planning - Couleurs")
    color_options = ["Par categorie", "Par vol"]
    if has_terminal:
        color_options.append("Par terminal")
    color_mode_ui = st.radio(
        "Mode couleur planning",
        options=color_options,
        index=0,
        key="color_mode_ui",
    )
    wide_color_default = "#D32F2F"
    narrow_color_default = "#FFEBEE"
    if color_mode_ui == "Par categorie":
        wide_color = st.color_picker("Couleur Wide", value=wide_color_default, key="wide_color")
        narrow_color = st.color_picker("Couleur Narrow", value=narrow_color_default, key="narrow_color")
    else:
        wide_color = st.session_state.get("wide_color", wide_color_default)
        narrow_color = st.session_state.get("narrow_color", narrow_color_default)
        if color_mode_ui == "Par terminal":
            st.caption("Mode par terminal: couleurs automatiques.")
        else:
            st.caption("Mode par vol: couleurs automatiques.")

    with st.expander("Options avancees", expanded=False):
        show_warnings = st.checkbox("Afficher panneau Warnings", value=True, key="show_warnings")


if df_raw is None:
    st.stop()

with st.expander("Preview fichier vols", expanded=False):
    st.dataframe(df_raw.head(20), use_container_width=True)


st.divider()
st.subheader("Etape 2 - Mapping colonnes")

cols = list(df_raw.columns)
default_dep = _guess_col(cols, ["std", "departure time", "heure de depart", "dep time"])
default_flt = _guess_col(cols, ["flight number", "flight no", "flt", "numero de vol", "num vol"])
default_cat = _guess_col(cols, ["category", "categorie", "cat", "type"])
default_pos = _guess_col(cols, ["positions", "position", "pos", "nb position", "nbr position"])
default_term = _guess_col(cols, ["terminal", "term", "tml"])
default_open = _guess_col(cols, ["make up opening", "make-up opening", "makeup opening", "opening"])
default_close = _guess_col(cols, ["make up closing", "make-up closing", "makeup closing", "closing"])


def _selectbox(label, default, key, existing=None):
    options = ["(Aucune)"] + cols
    if existing in options:
        idx = options.index(existing)
    elif default in options:
        idx = options.index(default)
    else:
        idx = 0
    return st.selectbox(label, options=options, index=idx, key=key)


if not mapping_confirmed:
    c_dep = _selectbox("Departure time (ex: STD)", default_dep, "map_dep", st.session_state.get("map_dep"))
    c_flt = _selectbox("Flight number", default_flt, "map_flt", st.session_state.get("map_flt"))
    c_cat = _selectbox("Category (ex: Wide body / Narrow body)", default_cat, "map_cat", st.session_state.get("map_cat"))
    c_pos = _selectbox("Positions", default_pos, "map_pos", st.session_state.get("map_pos"))

    st.caption("Optionnels")
    c_term = _selectbox("Terminal (optionnel)", default_term, "map_term", st.session_state.get("map_term"))
    c_open = _selectbox("MakeupOpening (optionnel)", default_open, "map_open", st.session_state.get("map_open"))
    c_close = _selectbox("MakeupClosing (optionnel)", default_close, "map_close", st.session_state.get("map_close"))

    if st.button("Confirmer mapping colonnes", key="confirm_mapping_cols"):
        missing = []
        if c_dep == "(Aucune)":
            missing.append("DepartureTime")
        if c_flt == "(Aucune)":
            missing.append("FlightNumber")
        if c_cat == "(Aucune)":
            missing.append("Category")
        if c_pos == "(Aucune)":
            missing.append("Positions")
        if missing:
            st.error(f"Colonnes obligatoires non selectionnees : {missing}")
            st.stop()

        col_mapping = {
            c_dep: "DepartureTime",
            c_flt: "FlightNumber",
            c_cat: "Category",
            c_pos: "Positions",
        }
        if c_term != "(Aucune)":
            col_mapping[c_term] = "Terminal"
        if c_open != "(Aucune)":
            col_mapping[c_open] = "MakeupOpening"
        if c_close != "(Aucune)":
            col_mapping[c_close] = "MakeupClosing"

        st.session_state["col_mapping"] = col_mapping
        st.session_state["mapping_confirmed"] = True
        st.rerun()
else:
    col_mapping = st.session_state.get("col_mapping", {})
    if not col_mapping:
        st.error("Mapping colonnes manquant.")
        st.session_state["mapping_confirmed"] = False
        st.stop()

    st.success("Mapping colonnes confirme.")
    st.write("Colonnes mappees :", list(col_mapping.values()))
    if st.button("Modifier mapping colonnes", key="modify_mapping_cols"):
        st.session_state["mapping_confirmed"] = False
        _reset_after_mapping()
        st.rerun()


mapping_confirmed = bool(st.session_state.get("mapping_confirmed", False))
if not mapping_confirmed:
    st.stop()

col_mapping = st.session_state.get("col_mapping", {})
df_mapped = df_raw.rename(columns=col_mapping).copy()
required_mapped = ["DepartureTime", "FlightNumber", "Category", "Positions"]
missing_mapped = [c for c in required_mapped if c not in df_mapped.columns]
if missing_mapped:
    st.error(f"Colonnes obligatoires manquantes apres mapping : {missing_mapped}")
    st.stop()

with st.expander("Apercu colonnes mappees", expanded=False):
    st.dataframe(df_mapped.head(20), use_container_width=True)


st.divider()
st.subheader("Etape 3 - Mapping categories & terminals")

cat_term_confirmed = bool(st.session_state.get("cat_term_confirmed", False))
raw_cats = sorted([str(x).strip() for x in df_mapped["Category"].dropna().unique().tolist()])


def suggest_cat(v: str) -> str:
    s = v.strip().lower()
    if "wide" in s or s in ["wb", "w"]:
        return "Wide"
    if "narrow" in s or s in ["nb", "n"]:
        return "Narrow"
    return "IGNORER"


def suggest_term(v: str) -> str:
    s = v.strip().upper()
    m = re.search(r"(\d+)", s)
    if s.startswith("T") and len(s) >= 2 and s[1].isdigit():
        return "T" + re.search(r"\d+", s).group(0)
    if "TERMINAL" in s and m:
        return "T" + m.group(1)
    if m and len(m.group(1)) <= 2:
        return "T" + m.group(1)
    return s if s else "INCONNU"


cat_options = ["Wide", "Narrow", "IGNORER"]
cat_mapping = {}
term_mapping = {}

if not cat_term_confirmed:
    with st.expander("Mapping categories", expanded=True):
        for v in raw_cats:
            key = f"catmap_{v}"
            existing = st.session_state.get(key)
            default = existing if existing in cat_options else suggest_cat(v)
            idx = cat_options.index(default) if default in cat_options else 0
            st.selectbox(f"'{v}' ->", options=cat_options, index=idx, key=key)
            cat_mapping[v] = st.session_state.get(key, default)

    if "Terminal" in df_mapped.columns:
        raw_terms = sorted([str(x).strip() for x in df_mapped["Terminal"].dropna().unique().tolist()])
        suggested = {v: suggest_term(v) for v in raw_terms}
        std_terms = sorted(set(suggested.values()))
        std_options = std_terms + ["IGNORER"]

        with st.expander("Mapping terminals", expanded=True):
            for v in raw_terms:
                key = f"termmap_{v}"
                existing = st.session_state.get(key)
                default = existing if existing in std_options else suggested[v]
                idx = std_options.index(default) if default in std_options else 0
                st.selectbox(f"'{v}' ->", options=std_options, index=idx, key=key)
                term_mapping[v] = st.session_state.get(key, default)

    if st.button("Confirmer mapping categories & terminals", key="confirm_cat_term"):
        st.session_state["cat_mapping"] = cat_mapping
        st.session_state["term_mapping"] = term_mapping
        st.session_state["cat_term_confirmed"] = True
        st.rerun()
else:
    st.success("Mapping categories & terminals confirme.")
    if st.button("Modifier mapping categories & terminals", key="modify_cat_term"):
        st.session_state["cat_term_confirmed"] = False
        _reset_after_cat_term()
        st.rerun()


cat_term_confirmed = bool(st.session_state.get("cat_term_confirmed", False))
if not cat_term_confirmed:
    st.stop()

cat_mapping = st.session_state.get("cat_mapping")
if not cat_mapping:
    st.error("Mapping categories manquant.")
    st.session_state["cat_term_confirmed"] = False
    st.stop()

term_mapping = st.session_state.get("term_mapping", {})
df_std, mapping_warnings = _apply_cat_term_mapping(df_mapped, cat_mapping, term_mapping)

st.write("Categories standard :", sorted(df_std["Category"].unique().tolist()))
if "Terminal" in df_std.columns:
    st.write("Terminals standard :", sorted(df_std["Terminal"].unique().tolist()))


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
    st.write(f"Mode make-up selectionne : {makeup_mode}")
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


st.divider()
st.subheader("Etape 5 - Time step")

time_step_confirmed = bool(st.session_state.get("time_step_confirmed", False))
current_time_step = int(time_step)
if time_step_confirmed and st.session_state.get("time_step_value") != current_time_step:
    st.session_state["time_step_confirmed"] = False
    _reset_after_time_step()
    time_step_confirmed = False

st.write(f"Pas de temps actuel : {current_time_step} minutes")
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
car_warnings = []

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


st.divider()
st.subheader("Etape 7 - Run + outputs")

color_mode_ui = st.session_state.get("color_mode_ui", "Par categorie")
if color_mode_ui == "Par categorie":
    color_mode = "category"
elif color_mode_ui == "Par terminal":
    color_mode = "terminal"
else:
    color_mode = "flight"

warnings_rows = []
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

        unassigned_df = flights_out[flights_out["AssignedCarousel"] == "UNASSIGNED"].copy()
        warnings_rows.append({
            "Type": "UNASSIGNED",
            "Message": "Vols non assignes",
            "Count": int(len(unassigned_df)),
        })

        st.session_state["results"] = {
            "flights_out": flights_out,
            "timeline_df": timeline_df,
            "warnings_rows": warnings_rows,
            "unassigned_df": unassigned_df,
            "color_mode": color_mode,
            "wide_color": wide_color,
            "narrow_color": narrow_color,
        }
        st.session_state["run_done"] = True
        st.rerun()
    except Exception:
        st.error("Erreur pendant l'allocation. Verifiez les donnees.")


if st.session_state.get("run_done") and st.session_state.get("results"):
    results = st.session_state["results"]
    flights_out = results["flights_out"]
    timeline_df = results["timeline_df"]
    warnings_rows = results["warnings_rows"]
    unassigned_df = results["unassigned_df"]

    total = int(len(flights_out))
    unassigned_count = int(len(unassigned_df))
    assigned_pct = 0 if total == 0 else int(round(100 * (total - unassigned_count) / total))

    kpi_cols = st.columns(3)
    kpi_cols[0].metric("Total vols", total)
    kpi_cols[1].metric("% assignes", f"{assigned_pct}%")
    kpi_cols[2].metric("Nb UNASSIGNED", unassigned_count)

    with st.expander("Filtres resultats", expanded=True):
        assigned_opts = sorted(flights_out["AssignedCarousel"].dropna().unique().tolist())
        assigned_sel = st.multiselect("AssignedCarousel", assigned_opts, default=assigned_opts)

        if "Terminal" in flights_out.columns:
            term_opts = sorted(flights_out["Terminal"].dropna().unique().tolist())
            term_sel = st.multiselect("Terminal", term_opts, default=term_opts)
        else:
            term_sel = None

        cat_opts = sorted(flights_out["Category"].dropna().unique().tolist())
        cat_sel = st.multiselect("Category", cat_opts, default=cat_opts)

    filtered = flights_out.copy()
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

    st.dataframe(filtered.sort_values("DepartureTime"), use_container_width=True)

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
        color_mode=results["color_mode"],
        wide_color=results["wide_color"],
        narrow_color=results["narrow_color"],
    )

    download_cols = st.columns(4)
    download_cols[0].download_button("summary.csv", data=open(csv_path, "rb"), file_name="summary.csv")
    download_cols[1].download_button("summary.txt", data=open(txt_path, "rb"), file_name="summary.txt")
    download_cols[2].download_button("timeline.xlsx", data=open(xlsx_path, "rb"), file_name="timeline.xlsx")
    if len(unassigned_df) > 0:
        unassigned_csv = unassigned_df.to_csv(index=False, encoding="utf-8")
        download_cols[3].download_button(
            "unassigned_reasons.csv",
            data=unassigned_csv,
            file_name="unassigned_reasons.csv",
        )
    else:
        download_cols[3].download_button(
            "unassigned_reasons.csv",
            data="",
            file_name="unassigned_reasons.csv",
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
            )
        else:
            st.success("Aucun warning.")
