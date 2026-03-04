from __future__ import annotations

from pathlib import Path

from app_branding import apply_branding, render_header
from app_pages import run_app

apply_branding()
render_header(Path(__file__).parent)
run_app()
