from __future__ import annotations

from pathlib import Path
import streamlit as st

BRAND_RED = "#D32F2F"
BRAND_RED_DARK = "#B71C1C"
BRAND_BG = "#FFFFFF"
BRAND_SIDEBAR = "#F7F7F7"
BRAND_BORDER = "#E5E5E5"


def apply_branding() -> None:
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
                --primary-color: var(--brand-red);
                --secondary-background-color: var(--brand-sidebar);
                --background-color: var(--brand-bg);
                --text-color: #111111;
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
            input:focus, textarea:focus, [data-baseweb="select"] > div:focus-within {{
                border-color: var(--brand-red) !important;
                box-shadow: 0 0 0 2px rgba(211, 47, 47, 0.2);
            }}
            input[type="radio"], input[type="checkbox"], input[type="range"] {{
                accent-color: var(--brand-red);
            }}
            :focus-visible {{
                outline-color: var(--brand-red) !important;
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
        div.stDownloadButton {{
            text-align: left;
        }}
        div.stDownloadButton > button {{
            margin-left: 0;
            justify-content: flex-start;
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


def _find_logo_bytes(base_dir: Path) -> bytes | None:
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
    if not logo_path:
        return None
    try:
        return logo_path.read_bytes()
    except Exception:
        return None


def render_header(base_dir: Path, title: str = "Carousel Allocation Tool") -> None:
    logo_bytes = _find_logo_bytes(base_dir)
    if logo_bytes:
        header_cols = st.columns([1, 6])
        with header_cols[0]:
            st.image(logo_bytes, width=120)
        with header_cols[1]:
            st.title(title)
    else:
        st.title(title)
